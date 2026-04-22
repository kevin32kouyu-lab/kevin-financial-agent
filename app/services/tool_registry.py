"""受控工具注册与执行层，供 agent 通过白名单工具完成数据访问。"""
from __future__ import annotations

import asyncio
import inspect
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable


ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(slots=True)
class ToolSpec:
    """描述一个可被 agent 调用的受控工具。"""

    name: str
    description: str
    permission: str
    handler: ToolHandler
    input_schema: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 15.0
    retries: int = 0
    cache_ttl_seconds: float = 0.0


@dataclass(slots=True)
class ToolInvocationRequest:
    """描述一次工具调用请求。"""

    tool_name: str
    payload: dict[str, Any]
    allowed_permissions: set[str]
    caller: str = "agent"


@dataclass(slots=True)
class ToolInvocationResult:
    """描述一次工具调用结果，可直接写入 tool_invocations artifact。"""

    tool_name: str
    permission: str | None
    status: str
    output: Any = None
    error_message: str | None = None
    attempts: int = 0
    elapsed_ms: int = 0
    cached: bool = False
    caller: str = "agent"
    started_at: str = ""
    finished_at: str = ""

    def to_artifact(self) -> dict[str, Any]:
        """转换成可序列化 artifact。"""
        return {
            "tool_name": self.tool_name,
            "permission": self.permission,
            "status": self.status,
            "output": self.output,
            "error_message": self.error_message,
            "attempts": self.attempts,
            "elapsed_ms": self.elapsed_ms,
            "cached": self.cached,
            "caller": self.caller,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class ToolRegistry:
    """保存工具定义，统一处理重名和查询。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        """注册一个工具。"""
        name = spec.name.strip()
        if not name:
            raise ValueError("Tool name is required.")
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = spec

    def get(self, name: str) -> ToolSpec | None:
        """按名称读取工具。"""
        return self._tools.get(name)

    def list_specs(self) -> list[ToolSpec]:
        """列出所有工具定义。"""
        return list(self._tools.values())


class ToolRunner:
    """执行工具，并统一处理权限、超时、重试、缓存和审计。"""

    def __init__(
        self,
        registry: ToolRegistry,
        audit_sink: Callable[[ToolInvocationResult], None] | None = None,
    ) -> None:
        self.registry = registry
        self.audit_sink = audit_sink
        self._cache: dict[str, tuple[float, Any]] = {}

    async def run(self, request: ToolInvocationRequest) -> ToolInvocationResult:
        """执行一次工具调用。"""
        started_at = _utc_now()
        started = time.perf_counter()
        spec = self.registry.get(request.tool_name)
        if not spec:
            return self._finish(
                ToolInvocationResult(
                    tool_name=request.tool_name,
                    permission=None,
                    status="not_found",
                    error_message=f"Tool is not registered: {request.tool_name}",
                    caller=request.caller,
                    started_at=started_at,
                ),
                started,
            )

        if spec.permission not in request.allowed_permissions:
            return self._finish(
                ToolInvocationResult(
                    tool_name=spec.name,
                    permission=spec.permission,
                    status="permission_denied",
                    error_message=f"Permission '{spec.permission}' is not allowed for this agent.",
                    caller=request.caller,
                    started_at=started_at,
                ),
                started,
            )

        cache_key = _cache_key(spec.name, request.payload)
        if spec.cache_ttl_seconds > 0 and cache_key in self._cache:
            cached_at, output = self._cache[cache_key]
            if time.monotonic() - cached_at <= spec.cache_ttl_seconds:
                return self._finish(
                    ToolInvocationResult(
                        tool_name=spec.name,
                        permission=spec.permission,
                        status="success",
                        output=output,
                        attempts=0,
                        cached=True,
                        caller=request.caller,
                        started_at=started_at,
                    ),
                    started,
                )

        attempts = 0
        last_error: Exception | None = None
        for attempt_index in range(max(spec.retries, 0) + 1):
            attempts = attempt_index + 1
            try:
                output = await asyncio.wait_for(_call_handler(spec.handler, request.payload), timeout=spec.timeout_seconds)
                if spec.cache_ttl_seconds > 0:
                    self._cache[cache_key] = (time.monotonic(), output)
                return self._finish(
                    ToolInvocationResult(
                        tool_name=spec.name,
                        permission=spec.permission,
                        status="success",
                        output=output,
                        attempts=attempts,
                        caller=request.caller,
                        started_at=started_at,
                    ),
                    started,
                )
            except asyncio.TimeoutError as error:
                last_error = error
                break
            except Exception as error:  # noqa: BLE001 - 工具层必须把失败转换成结构化结果。
                last_error = error

        status = "timeout" if isinstance(last_error, asyncio.TimeoutError) else "error"
        return self._finish(
            ToolInvocationResult(
                tool_name=spec.name,
                permission=spec.permission,
                status=status,
                error_message=str(last_error) if last_error else "Tool invocation failed.",
                attempts=attempts,
                caller=request.caller,
                started_at=started_at,
            ),
            started,
        )

    async def run_many(self, requests: Iterable[ToolInvocationRequest]) -> list[ToolInvocationResult]:
        """并发执行多次工具调用。"""
        return await asyncio.gather(*(self.run(request) for request in requests))

    def _finish(self, result: ToolInvocationResult, started: float) -> ToolInvocationResult:
        result.finished_at = _utc_now()
        result.elapsed_ms = max(round((time.perf_counter() - started) * 1000), 0)
        if self.audit_sink:
            self.audit_sink(result)
        return result


async def _call_handler(handler: ToolHandler, payload: dict[str, Any]) -> Any:
    """兼容同步与异步工具函数。"""
    if inspect.iscoroutinefunction(handler):
        return await handler(payload)
    return await asyncio.to_thread(handler, payload)


def _cache_key(tool_name: str, payload: dict[str, Any]) -> str:
    """生成稳定缓存键。"""
    return f"{tool_name}:{json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)}"


def _utc_now() -> str:
    """返回 UTC ISO 时间。"""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
