"""yfinance 代理路由器。

这个模块只负责 yfinance 的网络路径控制，避免全局代理影响 Yahoo 请求。
它会被 `yfinance_fetcher.py` 与 `backtest_service.py` 复用。
"""

from __future__ import annotations

from contextlib import contextmanager
import contextvars
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from app.core.config import AppSettings


T = TypeVar("T")
_PROXY_LOCK = threading.RLock()
_PROXY_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
_NO_PROXY_KEYS = ("NO_PROXY", "no_proxy")
_YAHOO_THROTTLE_LOCK = threading.RLock()
_LAST_YAHOO_REQUEST_AT = 0.0
_YAHOO_MIN_INTERVAL_SECONDS = 0.35
_LAST_ROUTE_TRACE: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "yfinance_last_route_trace",
    default=None,
)


@dataclass(slots=True)
class YFinanceCallError(Exception):
    """封装 yfinance 路由失败信息。"""

    operation: str
    route: str
    reason_code: str
    original: Exception
    route_attempts: tuple[str, ...] = ()
    final_route: str | None = None
    proxy_url_source: str | None = None

    def __str__(self) -> str:
        return (
            f"yfinance call failed ({self.operation}, route={self.route}, reason={self.reason_code}, "
            f"attempts={list(self.route_attempts)}): {self.original}"
        )


def classify_yfinance_exception(exc: Exception) -> str:
    """把异常归类成可读原因码。"""
    if isinstance(exc, YFinanceCallError):
        return exc.reason_code
    message = str(exc).lower()
    if "too many requests" in message or "rate limit" in message or "429" in message:
        return "yahoo_rate_limited"
    if "proxy" in message or "tunnel connection failed" in message or "407" in message:
        return "proxy_connection_failed"
    if "timed out" in message or "timeout" in message:
        return "network_timeout"
    if "name or service not known" in message or "temporary failure in name resolution" in message:
        return "dns_resolution_failed"
    return "upstream_unavailable"


def yfinance_failure_message(exc: Exception) -> str:
    """把异常转成前端可读文案。"""
    reason = classify_yfinance_exception(exc)
    if reason == "yahoo_rate_limited":
        return "Yahoo request was rate-limited (429)."
    if reason == "proxy_connection_failed":
        return "Proxy route failed before Yahoo request completed."
    if reason == "network_timeout":
        return "Yahoo request timed out."
    if reason == "dns_resolution_failed":
        return "Yahoo hostname resolution failed."
    if reason == "proxy_not_configured":
        return "Proxy mode is enabled but MARKET_PROXY_URL is missing."
    return "Yahoo data source is temporarily unavailable."


def get_last_yfinance_route_trace() -> dict[str, Any] | None:
    """返回最近一次 yfinance 路由追踪结果。"""
    trace = _LAST_ROUTE_TRACE.get()
    if not trace:
        return None
    return dict(trace)


def yfinance_route_debug(exc: Exception | None = None) -> dict[str, Any]:
    """生成统一的路由调试信息。"""
    if isinstance(exc, YFinanceCallError):
        return {
            "route_attempts": list(exc.route_attempts),
            "route_final": exc.final_route or exc.route,
            "failure_reason_code": exc.reason_code,
            "proxy_url_source": exc.proxy_url_source,
        }
    trace = get_last_yfinance_route_trace() or {}
    output = {
        "route_attempts": trace.get("route_attempts", []),
        "route_final": trace.get("route_final"),
        "failure_reason_code": trace.get("failure_reason_code"),
        "proxy_url_source": trace.get("proxy_url_source"),
    }
    return output


def run_yfinance_call(settings: AppSettings, operation: str, call: Callable[[], T]) -> T:
    """按配置执行 yfinance 调用（direct/proxy/auto）。"""
    route_mode = (settings.market_proxy_mode or "direct").lower().strip()
    if route_mode not in {"direct", "proxy", "auto"}:
        route_mode = "direct"
    attempts: list[str] = []
    proxy_source: str | None = None
    try:
        if route_mode == "direct":
            attempts.append("direct")
            result = _run_with_retry(lambda: _run_direct(settings, operation, call))
            _set_last_route_trace(
                operation=operation,
                route_mode=route_mode,
                route_attempts=attempts,
                route_final="direct",
                success=True,
            )
            return result

        if route_mode == "proxy":
            proxy_url, proxy_source = _resolve_proxy_url(settings)
            attempts.append("proxy")
            result = _run_with_retry(
                lambda: _run_proxy(settings, operation, call, proxy_url=proxy_url, proxy_source=proxy_source)
            )
            _set_last_route_trace(
                operation=operation,
                route_mode=route_mode,
                route_attempts=attempts,
                route_final="proxy",
                success=True,
                proxy_url_source=proxy_source,
            )
            return result

        # auto: 先直连一次，再切换代理重试，避免直连重试拖慢回退
        attempts.append("direct")
        try:
            result = _run_direct(settings, operation, call)
            _set_last_route_trace(
                operation=operation,
                route_mode=route_mode,
                route_attempts=attempts,
                route_final="direct",
                success=True,
            )
            return result
        except Exception as direct_exc:
            proxy_url, proxy_source = _resolve_proxy_url(settings)
            if not proxy_url:
                raise direct_exc
            attempts.append("proxy")
            try:
                result = _run_with_retry(
                    lambda: _run_proxy(settings, operation, call, proxy_url=proxy_url, proxy_source=proxy_source)
                )
                _set_last_route_trace(
                    operation=operation,
                    route_mode=route_mode,
                    route_attempts=attempts,
                    route_final="proxy",
                    success=True,
                    proxy_url_source=proxy_source,
                )
                return result
            except Exception as proxy_exc:
                raise YFinanceCallError(
                    operation=operation,
                    route="auto",
                    reason_code=classify_yfinance_exception(proxy_exc),
                    original=Exception(f"direct failed: {direct_exc}; proxy failed: {proxy_exc}"),
                    route_attempts=tuple(attempts),
                    final_route="proxy",
                    proxy_url_source=proxy_source,
                ) from proxy_exc
    except Exception as exc:
        reason_code = classify_yfinance_exception(exc)
        route_final = attempts[-1] if attempts else route_mode
        _set_last_route_trace(
            operation=operation,
            route_mode=route_mode,
            route_attempts=attempts,
            route_final=route_final,
            success=False,
            failure_reason_code=reason_code,
            proxy_url_source=proxy_source,
        )
        if isinstance(exc, YFinanceCallError):
            if not exc.route_attempts:
                exc.route_attempts = tuple(attempts)
            if not exc.final_route:
                exc.final_route = route_final
            if not exc.proxy_url_source:
                exc.proxy_url_source = proxy_source
            raise
        raise YFinanceCallError(
            operation=operation,
            route=route_mode,
            reason_code=reason_code,
            original=exc,
            route_attempts=tuple(attempts),
            final_route=route_final,
            proxy_url_source=proxy_source,
        ) from exc


def _run_with_retry(execute: Callable[[], T]) -> T:
    """对可恢复错误做有限重试，降低瞬时限流影响。"""
    attempt = 0
    last_exc: Exception | None = None
    while attempt < 3:
        attempt += 1
        try:
            return execute()
        except Exception as exc:
            last_exc = exc
            reason = classify_yfinance_exception(exc)
            retryable = reason in {"yahoo_rate_limited", "network_timeout", "dns_resolution_failed"}
            if not retryable or attempt >= 3:
                raise
            time.sleep(0.6 * attempt)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("yfinance call failed without explicit exception")


def _run_direct(settings: AppSettings, operation: str, call: Callable[[], T]) -> T:
    """在直连模式下临时禁用代理并执行调用。"""
    no_proxy_value = _merge_no_proxy_hosts(settings.market_no_proxy_hosts)
    env_patch = {key: None for key in _PROXY_KEYS}
    env_patch.update({key: no_proxy_value for key in _NO_PROXY_KEYS})
    try:
        with _scoped_env(env_patch):
            _throttle_yahoo_requests()
            return call()
    except Exception as exc:
        raise YFinanceCallError(
            operation=operation,
            route="direct",
            reason_code=classify_yfinance_exception(exc),
            original=exc,
        ) from exc


def _run_proxy(
    settings: AppSettings,
    operation: str,
    call: Callable[[], T],
    *,
    proxy_url: str | None = None,
    proxy_source: str | None = None,
) -> T:
    """在代理模式下强制使用 MARKET_PROXY_URL。"""
    if proxy_url is None:
        proxy_url, proxy_source = _resolve_proxy_url(settings)
    if not proxy_url:
        raise YFinanceCallError(
            operation=operation,
            route="proxy",
            reason_code="proxy_not_configured",
            original=ValueError("MARKET_PROXY_URL is required when MARKET_PROXY_MODE=proxy or auto retry."),
            proxy_url_source=proxy_source,
        )
    env_patch = {key: proxy_url for key in _PROXY_KEYS}
    try:
        with _scoped_env(env_patch):
            _throttle_yahoo_requests()
            return call()
    except Exception as exc:
        raise YFinanceCallError(
            operation=operation,
            route="proxy",
            reason_code=classify_yfinance_exception(exc),
            original=exc,
            proxy_url_source=proxy_source,
        ) from exc


def _resolve_proxy_url(settings: AppSettings) -> tuple[str | None, str | None]:
    """解析代理地址：优先环境配置，其次系统代理。"""
    configured = (settings.market_proxy_url or "").strip()
    if configured:
        return configured, "MARKET_PROXY_URL"
    env_priority = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")
    for key in env_priority:
        raw = (os.environ.get(key) or "").strip()
        if raw:
            return raw, key
    return None, None


def _merge_no_proxy_hosts(extra_hosts: tuple[str, ...]) -> str:
    """合并默认与已有 NO_PROXY 域名。"""
    hosts: list[str] = []
    for key in _NO_PROXY_KEYS:
        raw = os.environ.get(key, "")
        if raw:
            hosts.extend(item.strip() for item in raw.split(",") if item.strip())
    hosts.extend(item.strip() for item in extra_hosts if item.strip())
    unique_hosts = list(dict.fromkeys(hosts))
    return ",".join(unique_hosts)


def _throttle_yahoo_requests() -> None:
    """统一限速 Yahoo 相关请求，减少瞬时 429。"""
    global _LAST_YAHOO_REQUEST_AT
    with _YAHOO_THROTTLE_LOCK:
        now = time.monotonic()
        elapsed = now - _LAST_YAHOO_REQUEST_AT
        if elapsed < _YAHOO_MIN_INTERVAL_SECONDS:
            time.sleep(_YAHOO_MIN_INTERVAL_SECONDS - elapsed)
        _LAST_YAHOO_REQUEST_AT = time.monotonic()


def _set_last_route_trace(
    *,
    operation: str,
    route_mode: str,
    route_attempts: list[str],
    route_final: str | None,
    success: bool,
    failure_reason_code: str | None = None,
    proxy_url_source: str | None = None,
) -> None:
    """记录最近一次 yfinance 路由结果，便于产物追踪。"""
    _LAST_ROUTE_TRACE.set(
        {
            "operation": operation,
            "route_mode": route_mode,
            "route_attempts": list(route_attempts),
            "route_final": route_final,
            "success": success,
            "failure_reason_code": failure_reason_code,
            "proxy_url_source": proxy_url_source,
        }
    )


@contextmanager
def _scoped_env(overrides: dict[str, str | None]):
    """在临时环境变量作用域内执行逻辑并恢复原值。"""
    with _PROXY_LOCK:
        previous = {key: os.environ.get(key) for key in overrides}
        try:
            for key, value in overrides.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


__all__ = [
    "YFinanceCallError",
    "classify_yfinance_exception",
    "get_last_yfinance_route_trace",
    "run_yfinance_call",
    "yfinance_route_debug",
    "yfinance_failure_message",
]
