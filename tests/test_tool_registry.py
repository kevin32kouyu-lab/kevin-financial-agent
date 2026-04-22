"""验证受控工具注册层的权限、重试、缓存和超时行为。"""
from __future__ import annotations

import asyncio

import pytest

from app.services.tool_registry import ToolInvocationRequest, ToolRegistry, ToolRunner, ToolSpec


@pytest.mark.asyncio
async def test_tool_runner_denies_unapproved_permission() -> None:
    """未授权权限应被拒绝，且不能执行真实工具。"""
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
async def test_tool_runner_retries_transient_failures_and_audits_result() -> None:
    """临时失败应按配置重试，并把结果写入审计 sink。"""
    registry = ToolRegistry()
    attempts = 0
    audit_results = []

    def flaky_handler(payload: dict) -> dict:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("temporary upstream error")
        return {"ok": True, "payload": payload}

    registry.register(
        ToolSpec(
            name="news.search",
            description="Search news",
            permission="news",
            handler=flaky_handler,
            retries=1,
        )
    )
    runner = ToolRunner(registry, audit_sink=audit_results.append)

    result = await runner.run(ToolInvocationRequest(tool_name="news.search", payload={"ticker": "MSFT"}, allowed_permissions={"news"}))

    assert result.status == "success"
    assert result.output == {"ok": True, "payload": {"ticker": "MSFT"}}
    assert result.attempts == 2
    assert attempts == 2
    assert audit_results == [result]


@pytest.mark.asyncio
async def test_tool_runner_caches_successful_results_by_payload() -> None:
    """相同 payload 在缓存有效期内应复用上次成功结果。"""
    registry = ToolRegistry()
    calls = 0

    def cached_handler(payload: dict) -> dict:
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
async def test_tool_runner_reports_timeout_without_raising() -> None:
    """工具超时应返回结构化失败结果，而不是向上抛异常。"""
    registry = ToolRegistry()

    async def slow_handler(payload: dict) -> dict:
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
