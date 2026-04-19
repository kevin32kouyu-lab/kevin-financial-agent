"""Alpha Vantage data fetcher.

Provides backup source for:
- Price data
- Technical indicators
"""

from datetime import date
from typing import Any

from app.core.config import AppSettings
from .base import _compute_rsi

import requests

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
REQUEST_HEADERS = {
    "User-Agent": "FinancialAgentLab/1.0 (academic-research)",
}


def _get_alpha_vantage_api_key(settings: AppSettings) -> str:
    """Get Alpha Vantage API key from settings."""
    return settings.alpha_vantage_api_key or ""


def _fetch_alpha_vantage_daily_prices(ticker: str, settings: AppSettings | None = None) -> list[float]:
    """Fetch daily price series from Alpha Vantage.

    Args:
        ticker: Stock ticker symbol
        settings: AppSettings instance (uses env if None)

    Returns:
        List of closing prices
    """
    api_key = _get_alpha_vantage_api_key(settings or AppSettings.from_env())
    if not api_key:
        return []

    try:
        response = requests.get(
            ALPHA_VANTAGE_URL,
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": "compact",
                "apikey": api_key,
            },
            headers=REQUEST_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    # 免费额度不足时会返回 Note/Information，不带 Time Series。
    if not isinstance(payload, dict):
        return []
    if payload.get("Note") or payload.get("Information") or payload.get("Error Message"):
        return []

    series = payload.get("Time Series (Daily)") or {}
    ordered_dates = sorted(series.keys())
    closes: list[float] = []
    for item_date in ordered_dates:
        close_raw = (series.get(item_date) or {}).get("4. close")
        if close_raw is None:
            continue
        try:
            closes.append(float(close_raw))
        except (TypeError, ValueError):
            continue
    return closes


def _fetch_only_price_from_alpha_vantage(ticker: str, settings: AppSettings | None = None) -> dict[str, Any]:
    """Fetch latest price and trend from Alpha Vantage.

    Args:
        ticker: Stock ticker symbol
        settings: AppSettings instance (uses env if None)

    Returns:
        Dictionary with latest price and 5-day trend
    """
    prices = _fetch_alpha_vantage_daily_prices(ticker, settings)
    if len(prices) < 1:
        return {"Ticker": ticker, "Status": "No Data", "Source": "alpha_vantage"}

    trend = [round(price,2) for price in prices[-5:]]
    return {
        "Ticker": ticker,
        "Latest_Price": trend[-1],
        "Trend_5D": trend,
        "Status": "Success",
        "Source": "alpha_vantage",
    }


def _fetch_tech_from_alpha_vantage(ticker: str, settings: AppSettings | None = None) -> dict[str, Any]:
    """Fetch technical indicators from Alpha Vantage.

    Args:
        ticker: Stock ticker symbol
        settings: AppSettings instance (uses env if None)

    Returns:
        Dictionary with MA20, MA50, and RSI14 indicators
    """
    prices = _fetch_alpha_vantage_daily_prices(ticker, settings)
    if len(prices) < 60:
        return {"Ticker": ticker, "Status": "No Data", "Source": "alpha_vantage"}

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
        "Source": "alpha_vantage",
    }


def _load_alpha_history_window(ticker: str, start_date: date, end_date: date, settings: AppSettings) -> list[float]:
    """Load historical price data from Alpha Vantage for a date range.

    Args:
        ticker: Stock ticker symbol
        start_date: Start of date range
        end_date: End of date range
        settings: AppSettings instance

    Returns:
        List of closing prices in date range
    """
    from datetime import date, timedelta

    api_key = _get_alpha_vantage_api_key(settings)
    if not api_key:
        return []
    try:
        response = requests.get(
            ALPHA_VANTAGE_URL,
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": "compact",
                "apikey": api_key,
            },
            headers=REQUEST_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    if payload.get("Note") or payload.get("Information") or payload.get("Error Message"):
        return []
    series = payload.get("Time Series (Daily)") or {}
    ordered_dates = sorted(point for point in series.keys() if start_date.isoformat() <= point <= end_date.isoformat())
    closes: list[float] = []
    for point_date in ordered_dates:
        close_raw = (series.get(point_date) or {}).get("4. close")
        if close_raw is None:
            continue
        try:
            closes.append(float(close_raw))
        except (TypeError, ValueError):
            continue
    return closes
