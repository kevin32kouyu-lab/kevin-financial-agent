"""长桥数据抓取器。

提供可选的实时报价和历史日线能力，用于价格链路的备用源。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.config import AppSettings

try:
    from longbridge.openapi import AdjustType, Config, Period, QuoteContext
except Exception:  # pragma: no cover - 没装 SDK 时走降级路径
    AdjustType = None  # type: ignore[assignment]
    Config = None  # type: ignore[assignment]
    Period = None  # type: ignore[assignment]
    QuoteContext = None  # type: ignore[assignment]


def has_longbridge_credentials(settings: AppSettings) -> bool:
    """检查长桥凭证是否已配置。"""
    return settings.longbridge_configured


def _normalize_ticker(ticker: str) -> str:
    """规范化内部 ticker。"""
    return str(ticker or "").upper().strip().replace("/", "").replace(" ", "")


def to_longbridge_symbol(ticker: str) -> str:
    """将内部 ticker 转换为长桥 symbol。"""
    normalized = _normalize_ticker(ticker)
    if not normalized:
        return ""
    if "." in normalized:
        left, right = normalized.rsplit(".", 1)
        if right in {"US", "HK", "CN"} and left:
            if right == "HK" and left.isdigit():
                return f"{int(left)}.HK"
            return f"{left}.{right}"
    if normalized.isdigit():
        return f"{int(normalized)}.HK"
    return f"{normalized}.US"


def from_longbridge_symbol(symbol: str) -> str:
    """将长桥 symbol 还原为内部 ticker。"""
    normalized = _normalize_ticker(symbol)
    if not normalized:
        return ""
    if "." not in normalized:
        return normalized
    left, right = normalized.rsplit(".", 1)
    if right == "US":
        return left
    if right == "HK":
        return str(int(left)) if left.isdigit() else left
    return f"{left}.{right}"


def _build_context(settings: AppSettings) -> QuoteContext | None:
    """创建长桥行情上下文。"""
    if not has_longbridge_credentials(settings):
        return None
    if Config is None or QuoteContext is None:
        return None
    config = Config.from_apikey(
        settings.longbridge_app_key,
        settings.longbridge_app_secret,
        settings.longbridge_access_token,
        enable_print_quote_packages=False,
    )
    return QuoteContext(config)


def _chunk_symbols(symbols: list[str], size: int = 20) -> list[list[str]]:
    """按固定大小切分 symbol 列表。"""
    if not symbols:
        return []
    return [symbols[index:index + size] for index in range(0, len(symbols), size)]


def fetch_longbridge_bulk_price_snapshots(
    tickers: list[str],
    settings: AppSettings | None = None,
) -> list[dict[str, Any]]:
    """批量抓取长桥最新价格。"""
    runtime_settings = settings or AppSettings.from_env()
    normalized_tickers = [_normalize_ticker(ticker) for ticker in tickers if _normalize_ticker(ticker)]
    deduped_tickers: list[str] = list(dict.fromkeys(normalized_tickers))
    if not deduped_tickers:
        return []

    context = _build_context(runtime_settings)
    if context is None:
        return [{"Ticker": ticker, "Status": "No Data", "Source": "longbridge"} for ticker in deduped_tickers]

    symbol_map = {
        ticker: to_longbridge_symbol(ticker)
        for ticker in deduped_tickers
    }
    reverse_map = {
        symbol: ticker
        for ticker, symbol in symbol_map.items()
        if symbol
    }

    outputs: dict[str, dict[str, Any]] = {}
    try:
        for batch in _chunk_symbols(list(reverse_map.keys()), size=20):
            quotes = context.quote(batch)
            for quote in quotes:
                symbol = str(getattr(quote, "symbol", "")).upper().strip()
                ticker = reverse_map.get(symbol) or from_longbridge_symbol(symbol)
                try:
                    last_done = float(getattr(quote, "last_done"))
                    open_price = float(getattr(quote, "open", last_done))
                    low_price = float(getattr(quote, "low", last_done))
                    prev_close = float(getattr(quote, "prev_close", last_done))
                except (TypeError, ValueError):
                    continue
                trend = [round(value, 2) for value in [prev_close, open_price, low_price, last_done]]
                outputs[ticker] = {
                    "Ticker": ticker,
                    "Latest_Price": round(last_done, 2),
                    "Trend_5D": trend[-5:],
                    "Status": "Success",
                    "Source": "longbridge_quote",
                }
    except Exception:
        return [{"Ticker": ticker, "Status": "No Data", "Source": "longbridge_quote"} for ticker in deduped_tickers]

    results: list[dict[str, Any]] = []
    for ticker in deduped_tickers:
        if ticker in outputs:
            results.append(outputs[ticker])
        else:
            results.append({"Ticker": ticker, "Status": "No Data", "Source": "longbridge_quote"})
    return results


def fetch_longbridge_price_snapshot(ticker: str, settings: AppSettings | None = None) -> dict[str, Any]:
    """单票抓取长桥最新价格。"""
    results = fetch_longbridge_bulk_price_snapshots([ticker], settings)
    if results:
        return results[0]
    return {"Ticker": _normalize_ticker(ticker), "Status": "No Data", "Source": "longbridge_quote"}


def fetch_longbridge_daily_bars(
    settings: AppSettings,
    tickers: list[str],
    start_date: date,
    end_date: date,
) -> dict[str, list[dict[str, Any]]]:
    """抓取长桥日线 OHLC，用于历史研究与回测。"""
    context = _build_context(settings)
    if context is None or Period is None or AdjustType is None:
        return {}

    normalized_tickers = [_normalize_ticker(ticker) for ticker in tickers if _normalize_ticker(ticker)]
    deduped_tickers: list[str] = list(dict.fromkeys(normalized_tickers))
    if not deduped_tickers:
        return {}

    outputs: dict[str, list[dict[str, Any]]] = {}
    for ticker in deduped_tickers:
        symbol = to_longbridge_symbol(ticker)
        if not symbol:
            continue
        try:
            candlesticks = context.history_candlesticks_by_date(
                symbol,
                Period.Day,
                AdjustType.NoAdjust,
                start_date,
                end_date,
            )
        except Exception:
            continue

        records: list[dict[str, Any]] = []
        for item in candlesticks:
            point_date = getattr(item, "timestamp", None)
            if point_date is None:
                continue
            try:
                open_price = float(getattr(item, "open"))
                close_price = float(getattr(item, "close"))
            except (TypeError, ValueError):
                continue
            records.append(
                {
                    "Date": point_date.date(),
                    "Open": open_price,
                    "Close": close_price,
                }
            )
        if records:
            records.sort(key=lambda row: row["Date"])
            outputs[ticker] = records
    return outputs


def load_longbridge_history_window(
    ticker: str,
    start_date: date,
    end_date: date,
    settings: AppSettings | None = None,
) -> list[float]:
    """读取长桥历史区间收盘价序列。"""
    runtime_settings = settings or AppSettings.from_env()
    bars = fetch_longbridge_daily_bars(runtime_settings, [ticker], start_date, end_date)
    normalized = _normalize_ticker(ticker)
    records = bars.get(normalized) or []
    closes: list[float] = []
    for item in records:
        try:
            closes.append(float(item["Close"]))
        except (TypeError, ValueError, KeyError):
            continue
    return closes


__all__ = [
    "has_longbridge_credentials",
    "to_longbridge_symbol",
    "from_longbridge_symbol",
    "fetch_longbridge_bulk_price_snapshots",
    "fetch_longbridge_price_snapshot",
    "fetch_longbridge_daily_bars",
    "load_longbridge_history_window",
]
