"""Tests for yfinance proxy routing behavior."""

from __future__ import annotations

import os

import pytest

from app.core.config import AppSettings
from app.tools.fetchers.yfinance_proxy_router import (
    YFinanceCallError,
    classify_yfinance_exception,
    get_last_yfinance_route_trace,
    run_yfinance_call,
    yfinance_route_debug,
)


def test_classify_rate_limit_error() -> None:
    """Should classify Yahoo 429 as rate limited."""
    exc = RuntimeError("Too Many Requests. Rate limited (429)")
    assert classify_yfinance_exception(exc) == "yahoo_rate_limited"


def test_direct_mode_disables_proxy_temporarily(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct mode should clear proxy only in call scope."""
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.local:7890")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:7890")
    monkeypatch.setenv("NO_PROXY", "localhost")
    settings = AppSettings(
        market_proxy_mode="direct",
        market_no_proxy_hosts=("query1.finance.yahoo.com",),
    )

    def _probe() -> dict[str, str | None]:
        return {
            "http_proxy": os.environ.get("HTTP_PROXY"),
            "https_proxy": os.environ.get("HTTPS_PROXY"),
            "no_proxy": os.environ.get("NO_PROXY"),
        }

    inside = run_yfinance_call(settings, "probe", _probe)
    assert inside["http_proxy"] is None
    assert inside["https_proxy"] is None
    assert "query1.finance.yahoo.com" in (inside["no_proxy"] or "")
    assert os.environ.get("HTTP_PROXY") == "http://proxy.local:7890"
    assert os.environ.get("HTTPS_PROXY") == "http://proxy.local:7890"


def test_proxy_mode_requires_proxy_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Proxy mode should fail fast when proxy URL is missing."""
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("ALL_PROXY", raising=False)
    monkeypatch.delenv("http_proxy", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    monkeypatch.delenv("all_proxy", raising=False)
    monkeypatch.delenv("MARKET_PROXY_URL", raising=False)
    settings = AppSettings(market_proxy_mode="proxy", market_proxy_url=None)
    with pytest.raises(YFinanceCallError) as exc_info:
        run_yfinance_call(settings, "probe", lambda: {"ok": True})
    assert exc_info.value.reason_code == "proxy_not_configured"


def test_auto_mode_uses_system_proxy_when_market_proxy_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto mode should pick system proxy env vars when MARKET_PROXY_URL is absent."""
    monkeypatch.delenv("MARKET_PROXY_URL", raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://sys-proxy.local:7890")
    settings = AppSettings(
        market_proxy_mode="auto",
        market_proxy_url=None,
        market_no_proxy_hosts=("query1.finance.yahoo.com",),
    )
    attempts: list[str | None] = []

    def _probe() -> str:
        attempts.append(os.environ.get("HTTPS_PROXY"))
        if len(attempts) == 1:
            raise RuntimeError("429 Too Many Requests")
        return "ok"

    result = run_yfinance_call(settings, "probe", _probe)
    assert result == "ok"
    assert attempts[0] is None
    assert attempts[1] == "http://sys-proxy.local:7890"
    trace = get_last_yfinance_route_trace() or {}
    assert trace.get("route_final") == "proxy"
    assert trace.get("proxy_url_source") == "HTTPS_PROXY"


def test_auto_mode_retries_with_proxy_after_direct_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto mode should retry once with proxy when direct call fails."""
    settings = AppSettings(
        market_proxy_mode="auto",
        market_proxy_url="http://proxy.local:7890",
        market_no_proxy_hosts=("query1.finance.yahoo.com",),
    )
    attempts: list[dict[str, str | None]] = []

    def _probe() -> str:
        attempts.append(
            {
                "HTTP_PROXY": os.environ.get("HTTP_PROXY"),
                "HTTPS_PROXY": os.environ.get("HTTPS_PROXY"),
            }
        )
        if len(attempts) == 1:
            raise RuntimeError("429 Too Many Requests")
        return "ok"

    result = run_yfinance_call(settings, "probe", _probe)
    assert result == "ok"
    assert attempts[0]["HTTP_PROXY"] is None
    assert attempts[1]["HTTP_PROXY"] == "http://proxy.local:7890"


def test_route_debug_contains_failure_reason_code() -> None:
    """Route debug should expose reason code for readable diagnostics."""
    settings = AppSettings(market_proxy_mode="direct", market_no_proxy_hosts=("query1.finance.yahoo.com",))

    with pytest.raises(YFinanceCallError) as exc_info:
        run_yfinance_call(settings, "probe", lambda: (_ for _ in ()).throw(RuntimeError("429 Too Many Requests")))

    debug = yfinance_route_debug(exc_info.value)
    assert debug["failure_reason_code"] == "yahoo_rate_limited"
    assert debug["route_attempts"] == ["direct"]
