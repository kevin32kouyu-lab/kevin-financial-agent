"""Base utilities and helper functions for data fetchers."""

import threading
from datetime import date, timedelta
from typing import Any

from app.core.config import AppSettings
from app.repositories.sqlite_market_repository import SqliteMarketRepository

_CIK_MAPPING_CACHE: dict[str, int] = {}
_CIK_MAPPING_LOCK = threading.Lock()


def _market_repository(settings: AppSettings) -> SqliteMarketRepository:
    """Get market repository instance for caching."""
    return SqliteMarketRepository(settings.market_db_path)


def _load_cached_snapshot(
    settings: AppSettings,
    ticker: str,
    snapshot_key: str,
    *,
    ttl_minutes: float,
) -> Any:
    """Load cached snapshot from repository with TTL."""
    try:
        return _market_repository(settings).get_cached_snapshot(ticker, snapshot_key, ttl_minutes=ttl_minutes)
    except Exception:
        return None


def _store_cached_snapshot(settings: AppSettings, ticker: str, snapshot_key: str, payload: Any) -> None:
    """Store snapshot in repository for caching."""
    try:
        _market_repository(settings).upsert_cached_snapshot(ticker, snapshot_key, payload)
    except Exception:
        pass


def _compute_rsi(values: list[float], period: int = 14) -> float | None:
    """Compute Relative Strength Index (RSI) from price series.

    Args:
        values: List of closing prices
        period: RSI period (default 14)

    Returns:
        RSI value or None if insufficient data
    """
    if len(values) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(values)):
        delta = values[index] - values[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    recent_gains = gains[-period:]
    recent_losses = losses[-period:]
    avg_gain = sum(recent_gains) / period
    avg_loss = sum(recent_losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _build_technical_payload_from_prices(ticker: str, prices: list[float], source: str) -> dict[str, Any]:
    """Build technical indicator payload from price series.

    Args:
        ticker: Stock ticker symbol
        prices: List of closing prices
        source: Data source identifier

    Returns:
        Dictionary with technical indicators (MA20, MA50, RSI14)
    """
    if len(prices) < 60:
        return {"Ticker": ticker, "Status": "No Data", "Source": source}

    latest_price = prices[-1]
    ma_20 = sum(prices[-20:]) / 20
    ma_50 = sum(prices[-50:]) / 50
    rsi_14 = _compute_rsi(prices, 14)
    return {
        "Ticker": ticker,
        "Latest_Price": round(latest_price, 2),
        "MA_20": round(ma_20, 2),
        "MA_50": round(ma_50, 2),
        "RSI_14": round(rsi_14, 2) if rsi_14 is not None else None,
        "Status": "Success",
        "Source": source,
    }


def _history_window_start(as_of_date: date, lookback_days: int = 220) -> date:
    """Calculate start date for historical data window."""
    return as_of_date - timedelta(days=lookback_days)


def _get_cik_mapping() -> dict[str, int]:
    """Get ticker to CIK mapping from SEC.

    Returns:
        Dictionary mapping ticker symbols to SEC CIK numbers
    """
    global _CIK_MAPPING_CACHE
    if _CIK_MAPPING_CACHE:
        return _CIK_MAPPING_CACHE

    with _CIK_MAPPING_LOCK:
        # Double-check after acquiring lock
        if _CIK_MAPPING_CACHE:
            return _CIK_MAPPING_CACHE
        try:
            import requests
            SEC_HEADERS = {
                "User-Agent": "FinancialAgentLab/1.0 research-contact@example.com",
            }
            response = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=SEC_HEADERS,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            _CIK_MAPPING_CACHE = {str(item["ticker"]).upper(): int(item["cik_str"]) for item in data.values()}
        except Exception:
            _CIK_MAPPING_CACHE = {}
    return _CIK_MAPPING_CACHE
