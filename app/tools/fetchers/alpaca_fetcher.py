"""Alpaca data fetcher.

Provides primary source for US equities universe and price bars.
"""

from datetime import date, datetime, timedelta
from typing import Any

from app.core.config import AppSettings

import requests

REQUEST_HEADERS = {
    "User-Agent": "FinancialAgentLab/1.0 (academic-research)",
}
ALPACA_SUPPORTED_FEEDS = {"iex", "sip"}
ALPACA_BAR_BATCH_SIZE = 40


def _get_alpaca_api_key(settings: AppSettings) -> str:
    """Get Alpaca API key from settings."""
    return settings.alpaca_api_key or ""


def _get_alpaca_api_secret(settings: AppSettings) -> str:
    """Get Alpaca API secret from settings."""
    return settings.alpaca_api_secret or ""


def _get_alpaca_assets_url(settings: AppSettings) -> str:
    """Get Alpaca assets URL from settings."""
    return settings.alpaca_assets_url


def _get_alpaca_data_base_url(settings: AppSettings) -> str:
    """Resolve Alpaca market-data base URL from configured base URL."""
    configured = settings.alpaca_base_url.rstrip("/")
    if "data.alpaca.markets" in configured:
        return configured
    return "https://data.alpaca.markets"


def _build_alpaca_headers(settings: AppSettings) -> dict[str, str]:
    """Build authenticated headers for Alpaca requests."""
    return {
        **REQUEST_HEADERS,
        "APCA-API-KEY-ID": _get_alpaca_api_key(settings),
        "APCA-API-SECRET-KEY": _get_alpaca_api_secret(settings),
    }


def _normalize_symbols(symbols: list[str]) -> list[str]:
    """Normalize symbol list and remove duplicates."""
    seen: set[str] = set()
    normalized: list[str] = []
    for symbol in symbols:
        ticker = str(symbol or "").upper().strip().replace(".", "-")
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        normalized.append(ticker)
    return normalized


def _parse_bar_date(raw_timestamp: Any) -> date | None:
    """Parse Alpaca bar timestamp into UTC date."""
    text = str(raw_timestamp or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def has_alpaca_credentials(settings: AppSettings) -> bool:
    """Check if Alpaca credentials are configured."""
    return settings.alpaca_configured


def fetch_alpaca_us_equities(settings: AppSettings) -> list[dict[str, Any]]:
    """Fetch list of US equities from Alpaca."""
    if not has_alpaca_credentials(settings):
        return []

    response = requests.get(
        _get_alpaca_assets_url(settings),
        params={
            "status": "active",
            "asset_class": "us_equity",
        },
        headers=_build_alpaca_headers(settings),
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []

    equities: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").upper().strip().replace(".", "-")
        exchange = str(item.get("exchange") or "").upper().strip()
        if not symbol:
            continue
        if exchange not in {"NYSE", "NASDAQ", "AMEX", "ARCA", "BATS"}:
            continue
        equities.append(
            {
                "ticker": symbol,
                "name": item.get("name"),
                "exchange": exchange,
                "asset_class": item.get("class") or item.get("asset_class") or "us_equity",
                "asset_status": item.get("status") or "active",
                "tradable": bool(item.get("tradable")),
                "marginable": bool(item.get("marginable")),
                "shortable": bool(item.get("shortable")),
                "easy_to_borrow": bool(item.get("easy_to_borrow")),
                "fractionable": bool(item.get("fractionable")),
            }
        )
    return equities


def fetch_alpaca_daily_bars(
    settings: AppSettings,
    symbols: list[str],
    start_date: date,
    end_date: date,
    *,
    feed: str = "iex",
) -> dict[str, list[dict[str, Any]]]:
    """Fetch daily OHLC bars from Alpaca data API for multiple symbols."""
    if not has_alpaca_credentials(settings):
        return {}

    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return {}

    feed_name = feed.lower().strip() or "iex"
    if feed_name not in ALPACA_SUPPORTED_FEEDS:
        feed_name = "iex"

    all_results: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in normalized_symbols}
    data_base_url = _get_alpaca_data_base_url(settings)
    start_text = f"{start_date.isoformat()}T00:00:00Z"
    end_text = f"{end_date.isoformat()}T23:59:59Z"

    for batch_start in range(0, len(normalized_symbols), ALPACA_BAR_BATCH_SIZE):
        batch_symbols = normalized_symbols[batch_start:batch_start + ALPACA_BAR_BATCH_SIZE]
        page_token: str | None = None
        while True:
            params = {
                "symbols": ",".join(batch_symbols),
                "timeframe": "1Day",
                "start": start_text,
                "end": end_text,
                "adjustment": "raw",
                "feed": feed_name,
                "sort": "asc",
                "limit": 10000,
            }
            if page_token:
                params["page_token"] = page_token
            response = requests.get(
                f"{data_base_url}/v2/stocks/bars",
                params=params,
                headers=_build_alpaca_headers(settings),
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            bars_payload = payload.get("bars") if isinstance(payload, dict) else None
            if isinstance(bars_payload, dict):
                items_by_symbol = bars_payload
            elif isinstance(bars_payload, list) and len(batch_symbols) == 1:
                items_by_symbol = {batch_symbols[0]: bars_payload}
            else:
                items_by_symbol = {}

            for symbol in batch_symbols:
                raw_items = items_by_symbol.get(symbol) or []
                if not isinstance(raw_items, list):
                    continue
                for raw_item in raw_items:
                    if not isinstance(raw_item, dict):
                        continue
                    bar_date = _parse_bar_date(raw_item.get("t"))
                    if bar_date is None:
                        continue
                    try:
                        open_price = float(raw_item.get("o"))
                        close_price = float(raw_item.get("c"))
                    except (TypeError, ValueError):
                        continue
                    all_results[symbol].append(
                        {
                            "Date": bar_date,
                            "Open": open_price,
                            "Close": close_price,
                        }
                    )

            page_token = payload.get("next_page_token") if isinstance(payload, dict) else None
            if not page_token:
                break

    for symbol in all_results:
        all_results[symbol].sort(key=lambda item: item["Date"])
    return all_results


def load_alpaca_history_window(
    ticker: str,
    start_date: date,
    end_date: date,
    settings: AppSettings | None = None,
) -> list[float]:
    """Load close prices from Alpaca for a date range."""
    runtime_settings = settings or AppSettings.from_env()
    bars = fetch_alpaca_daily_bars(runtime_settings, [ticker], start_date, end_date)
    symbol = str(ticker or "").upper().strip().replace(".", "-")
    series = bars.get(symbol) or []
    return [float(item["Close"]) for item in series if isinstance(item.get("Close"), (int, float))]


def fetch_alpaca_price_snapshot(ticker: str, settings: AppSettings | None = None) -> dict[str, Any]:
    """Fetch latest price and recent trend from Alpaca."""
    runtime_settings = settings or AppSettings.from_env()
    if not has_alpaca_credentials(runtime_settings):
        return {"Ticker": ticker, "Status": "No Data", "Source": "alpaca"}

    symbol = str(ticker or "").upper().strip().replace(".", "-")
    today = date.today()
    bars = fetch_alpaca_daily_bars(
        runtime_settings,
        [symbol],
        today - timedelta(days=14),
        today + timedelta(days=1),
    )
    series = bars.get(symbol) or []
    closes = [float(item["Close"]) for item in series if isinstance(item.get("Close"), (int, float))]
    if not closes:
        return {"Ticker": symbol, "Status": "No Data", "Source": "alpaca"}
    trend = [round(value, 2) for value in closes[-5:]]
    return {
        "Ticker": symbol,
        "Latest_Price": trend[-1],
        "Trend_5D": trend,
        "Status": "Success",
        "Source": "alpaca_iex",
    }


def fetch_alpaca_bulk_price_snapshots(tickers: list[str], settings: AppSettings | None = None) -> list[dict[str, Any]]:
    """Fetch latest prices for multiple symbols from Alpaca in batch."""
    runtime_settings = settings or AppSettings.from_env()
    normalized = _normalize_symbols(tickers)
    if not normalized:
        return []
    if not has_alpaca_credentials(runtime_settings):
        return [{"Ticker": ticker, "Status": "No Data", "Source": "alpaca"} for ticker in normalized]

    today = date.today()
    bars = fetch_alpaca_daily_bars(
        runtime_settings,
        normalized,
        today - timedelta(days=14),
        today + timedelta(days=1),
    )
    outputs: list[dict[str, Any]] = []
    for ticker in normalized:
        series = bars.get(ticker) or []
        closes = [float(item["Close"]) for item in series if isinstance(item.get("Close"), (int, float))]
        if not closes:
            outputs.append({"Ticker": ticker, "Status": "No Data", "Source": "alpaca_iex"})
            continue
        trend = [round(value, 2) for value in closes[-5:]]
        outputs.append(
            {
                "Ticker": ticker,
                "Latest_Price": trend[-1],
                "Trend_5D": trend,
                "Status": "Success",
                "Source": "alpaca_iex",
            }
        )
    return outputs
