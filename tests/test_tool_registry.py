"""验证两层工具注册表的权限、重试、缓存和审计行为。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.agent_runtime.tool_registry import (
    ToolInvocationRequest as AgentToolInvocationRequest,
)
from app.agent_runtime.tool_registry import (
    ToolRegistry as AgentToolRegistry,
)
from app.agent_runtime.tool_registry import (
    ToolRunner as AgentToolRunner,
)
from app.agent_runtime.tool_registry import (
    ToolSpec as AgentToolSpec,
)
from app.services.tool_registry import (
    ToolInvocationRequest,
    ToolRegistry,
    ToolRunner,
    ToolSpec,
)


@pytest.mark.asyncio
async def test_service_tool_runner_denies_unapproved_permission() -> None:
    """服务层工具必须先通过权限白名单。"""
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="market.price",
            description="Fetch price",
            permission="market_data",
            handler=lambda payload: {"price": 123},
        )
    )
    runner = ToolRunner(registry)

    result = await runner.run(ToolInvocationRequest(tool_name="market.price", payload={}, allowed_permissions={"rag"}))

    assert result.status == "permission_denied"
    assert result.attempts == 0
    assert "market_data" in str(result.error_message)


@pytest.mark.asyncio
async def test_service_tool_runner_caches_successful_results_by_payload() -> None:
    """相同 payload 在缓存有效期内应复用上次成功结果。"""
    registry = ToolRegistry()
    calls = 0

    def cached_handler(payload: dict) -> dict:
        """统计真实调用次数。"""
        nonlocal calls
        calls += 1
        return {"calls": calls, "ticker": payload["ticker"]}

    registry.register(
        ToolSpec(
            name="rag.retrieve",
            description="Retrieve evidence",
            permission="rag",
            handler=cached_handler,
            cache_ttl_seconds=60,
        )
    )
    runner = ToolRunner(registry)
    request = ToolInvocationRequest(tool_name="rag.retrieve", payload={"ticker": "AAPL"}, allowed_permissions={"rag"})

    first = await runner.run(request)
    second = await runner.run(request)

    assert first.status == "success"
    assert second.status == "success"
    assert first.output == {"calls": 1, "ticker": "AAPL"}
    assert second.output == {"calls": 1, "ticker": "AAPL"}
    assert first.cached is False
    assert second.cached is True
    assert calls == 1


@pytest.mark.asyncio
async def test_service_tool_runner_reports_timeout_without_raising() -> None:
    """工具超时应返回结构化失败结果，而不是向上抛异常。"""
    registry = ToolRegistry()

    async def slow_handler(payload: dict) -> dict:
        """模拟慢工具。"""
        await asyncio.sleep(0.05)
        return {"ok": True}

    registry.register(
        ToolSpec(
            name="sec.lookup",
            description="Lookup SEC filing",
            permission="sec",
            handler=slow_handler,
            timeout_seconds=0.01,
        )
    )
    runner = ToolRunner(registry)

    result = await runner.run(ToolInvocationRequest(tool_name="sec.lookup", payload={}, allowed_permissions={"sec"}))

    assert result.status == "timeout"
    assert result.output is None
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_agent_tool_runner_denies_tools_outside_agent_policy() -> None:
    """agent 只能调用白名单工具和权限范围内的工具。"""
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(
            name="market.snapshot",
            description="读取行情快照",
            permission_scope="market_data",
            runner=lambda arguments: {"ticker": arguments["ticker"], "price": 100},
        )
    )
    runner = AgentToolRunner(registry)

    result = await runner.run(
        AgentToolInvocationRequest(
            tool_name="market.snapshot",
            arguments={"ticker": "AAPL"},
            agent_name="EvidenceAgent",
            allowed_tools=["rag.retrieve"],
            allowed_scopes=["rag"],
        )
    )

    assert result.status == "permission_denied"
    assert result.output is None
    assert result.error_message
    assert runner.invocations[0].to_dict()["tool_name"] == "market.snapshot"


@pytest.mark.asyncio
async def test_agent_tool_runner_retries_and_records_successful_invocation() -> None:
    """临时失败的 agent 工具应按注册策略重试，并留下统一审计记录。"""
    attempts = {"count": 0}

    async def flaky_tool(arguments: dict[str, Any]) -> dict[str, Any]:
        """第一次失败，第二次成功。"""
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary provider error")
        return {"ok": True, "ticker": arguments["ticker"]}

    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(
            name="news.search",
            description="检索新闻摘要",
            permission_scope="news",
            max_retries=1,
            runner=flaky_tool,
        )
    )
    runner = AgentToolRunner(registry)

    result = await runner.run(
        AgentToolInvocationRequest(
            tool_name="news.search",
            arguments={"ticker": "MSFT"},
            agent_name="DataAgent",
            allowed_tools=["news.search"],
            allowed_scopes=["news"],
        )
    )

    assert result.status == "success"
    assert result.attempts == 2
    assert result.output == {"ok": True, "ticker": "MSFT"}
    audit = [item.to_dict() for item in runner.invocations]
    assert audit[0]["status"] == "success"
    assert audit[0]["agent_name"] == "DataAgent"
    assert audit[0]["permission_scope"] == "news"
