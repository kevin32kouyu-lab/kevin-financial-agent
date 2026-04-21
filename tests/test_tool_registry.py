"""测试受限自治 agent 使用的工具注册、权限、重试和审计。"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent_runtime.tool_registry import (
    ToolInvocationRequest,
    ToolRegistry,
    ToolRunner,
    ToolSpec,
)


@pytest.mark.asyncio
async def test_tool_runner_denies_tools_outside_agent_policy():
    """agent 只能调用白名单工具和权限范围内的工具。"""
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="market.snapshot",
            description="读取行情快照",
            permission_scope="market_data",
            runner=lambda arguments: {"ticker": arguments["ticker"], "price": 100},
        )
    )
    runner = ToolRunner(registry)

    result = await runner.run(
        ToolInvocationRequest(
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
async def test_tool_runner_retries_and_records_successful_invocation():
    """临时失败的工具应按注册策略重试，并留下统一审计记录。"""
    attempts = {"count": 0}

    async def flaky_tool(arguments: dict[str, Any]) -> dict[str, Any]:
        """第一次失败，第二次成功。"""
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary provider error")
        return {"ok": True, "ticker": arguments["ticker"]}

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="news.search",
            description="检索新闻摘要",
            permission_scope="news",
            max_retries=1,
            runner=flaky_tool,
        )
    )
    runner = ToolRunner(registry)

    result = await runner.run(
        ToolInvocationRequest(
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

