"""受限自治 agent 的工具注册与调用审计层，统一处理权限、重试和超时。"""

from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable

from app.domain.contracts import utc_now_iso


ToolCallable = Callable[[dict[str, Any]], Any]


@dataclass(slots=True)
class ToolSpec:
    """描述一个 agent 可调用工具的权限、输入要求和执行策略。"""

    name: str
    description: str
    permission_scope: str
    runner: ToolCallable
    input_schema: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 15.0
    max_retries: int = 0
    cache_policy: str | None = None


@dataclass(slots=True)
class ToolInvocationRequest:
    """一次工具调用请求，携带 agent 的白名单和权限范围。"""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    agent_name: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    allowed_scopes: list[str] = field(default_factory=list)
    run_id: str | None = None


@dataclass(slots=True)
class ToolInvocationResult:
    """一次工具调用结果，既供 agent 使用，也作为审计 artifact 保存。"""

    tool_name: str
    status: str
    agent_name: str | None
    permission_scope: str | None
    started_at: str
    finished_at: str
    elapsed_ms: float
    attempts: int = 1
    output: Any = None
    error_message: str | None = None
    arguments_preview: str = ""
    output_preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的轻量审计记录。"""
        return {
            "tool_name": self.tool_name,
            "status": self.status,
            "agent_name": self.agent_name,
            "permission_scope": self.permission_scope,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_ms": round(max(float(self.elapsed_ms or 0.0), 0.0), 2),
            "attempts": self.attempts,
            "arguments_preview": self.arguments_preview,
            "output_preview": self.output_preview,
            "error_message": self.error_message,
        }


class ToolRegistry:
    """保存内部工具清单，避免 agent 任意调用未登记函数。"""

    def __init__(self):
        """初始化空工具表。"""
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        """登记或替换一个工具。"""
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        """按名称读取工具定义。"""
        return self._tools.get(name)

    def list_allowed(self, *, tool_names: list[str] | None = None, scopes: list[str] | None = None) -> list[ToolSpec]:
        """列出某个 agent 当前允许访问的工具。"""
        allowed_tools = set(tool_names or [])
        allowed_scopes = set(scopes or [])
        return [
            spec
            for spec in self._tools.values()
            if ("*" in allowed_tools or spec.name in allowed_tools)
            and ("*" in allowed_scopes or spec.permission_scope in allowed_scopes)
        ]


class ToolRunner:
    """执行注册工具，并统一输出权限、重试、超时和审计结果。"""

    def __init__(self, registry: ToolRegistry):
        """绑定工具注册表。"""
        self.registry = registry
        self.invocations: list[ToolInvocationResult] = []

    async def run(self, request: ToolInvocationRequest) -> ToolInvocationResult:
        """执行一次工具调用，并把结果加入审计列表。"""
        spec = self.registry.get(request.tool_name)
        if spec is None:
            return self._record(
                request,
                permission_scope=None,
                status="not_found",
                started_at=utc_now_iso(),
                started_perf=perf_counter(),
                attempts=0,
                error_message=f"Tool is not registered: {request.tool_name}",
            )

        denied_reason = self._permission_denied_reason(request, spec)
        if denied_reason:
            return self._record(
                request,
                permission_scope=spec.permission_scope,
                status="permission_denied",
                started_at=utc_now_iso(),
                started_perf=perf_counter(),
                attempts=0,
                error_message=denied_reason,
            )

        validation_error = self._validate_arguments(spec, request.arguments)
        if validation_error:
            return self._record(
                request,
                permission_scope=spec.permission_scope,
                status="invalid_input",
                started_at=utc_now_iso(),
                started_perf=perf_counter(),
                attempts=0,
                error_message=validation_error,
            )

        started_at = utc_now_iso()
        started_perf = perf_counter()
        attempts = 0
        last_error: str | None = None
        for attempt in range(1, max(0, spec.max_retries) + 2):
            attempts = attempt
            try:
                output = await asyncio.wait_for(
                    self._call_tool(spec, request.arguments),
                    timeout=max(float(spec.timeout_seconds), 0.01),
                )
                return self._record(
                    request,
                    permission_scope=spec.permission_scope,
                    status="success",
                    started_at=started_at,
                    started_perf=started_perf,
                    attempts=attempts,
                    output=output,
                )
            except TimeoutError:
                last_error = f"Tool timed out after {spec.timeout_seconds} seconds."
            except Exception as exc:  # noqa: BLE001 - 工具边界需要捕获并审计所有异常
                last_error = str(exc).strip() or exc.__class__.__name__

        return self._record(
            request,
            permission_scope=spec.permission_scope,
            status="failed",
            started_at=started_at,
            started_perf=started_perf,
            attempts=attempts,
            error_message=last_error,
        )

    async def _call_tool(self, spec: ToolSpec, arguments: dict[str, Any]) -> Any:
        """兼容同步和异步工具函数。"""
        result = spec.runner(arguments)
        if inspect.isawaitable(result):
            return await result
        return result

    def _record(
        self,
        request: ToolInvocationRequest,
        *,
        permission_scope: str | None,
        status: str,
        started_at: str,
        started_perf: float,
        attempts: int,
        output: Any = None,
        error_message: str | None = None,
    ) -> ToolInvocationResult:
        """生成审计结果并保存。"""
        result = ToolInvocationResult(
            tool_name=request.tool_name,
            status=status,
            agent_name=request.agent_name,
            permission_scope=permission_scope,
            started_at=started_at,
            finished_at=utc_now_iso(),
            elapsed_ms=(perf_counter() - started_perf) * 1000,
            attempts=attempts,
            output=output,
            error_message=error_message,
            arguments_preview=self._preview(request.arguments),
            output_preview=self._preview(output),
        )
        self.invocations.append(result)
        return result

    @staticmethod
    def _permission_denied_reason(request: ToolInvocationRequest, spec: ToolSpec) -> str | None:
        """检查工具名和权限范围是否都在 Planner 白名单内。"""
        allowed_tools = set(request.allowed_tools or [])
        allowed_scopes = set(request.allowed_scopes or [])
        if "*" not in allowed_tools and spec.name not in allowed_tools:
            return f"{request.agent_name or 'Agent'} is not allowed to call {spec.name}."
        if "*" not in allowed_scopes and spec.permission_scope not in allowed_scopes:
            return f"{request.agent_name or 'Agent'} lacks scope {spec.permission_scope}."
        return None

    @staticmethod
    def _validate_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> str | None:
        """按轻量 schema 检查必填字段。"""
        required = spec.input_schema.get("required") if isinstance(spec.input_schema, dict) else None
        if not isinstance(required, list):
            return None
        missing = [str(key) for key in required if key not in arguments]
        return f"Missing required tool arguments: {', '.join(missing)}" if missing else None

    @staticmethod
    def _preview(value: Any, *, max_chars: int = 700) -> str:
        """把工具输入输出压缩成可读预览，避免 trace 过大。"""
        if value is None:
            return ""
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)
        return text if len(text) <= max_chars else text[: max_chars - 3] + "..."
