"""Historical data fetcher.

Provides historical price and technical indicators for backtesting.
"""

from datetime import date
from typing import Any

from app.core.config import AppSettings
from .base import (
    _history_window_start,
    _build_technical_payload_from_prices,
)
from .alpaca_fetcher import load_alpaca_history_window
from .longbridge_fetcher import load_longbridge_history_window
from .yfinance_fetcher import _load_yfinance_history_window
from .alpha_vantage_fetcher import _load_alpha_history_window
from .yfinance_proxy_router import yfinance_failure_message


def fetch_historical_price_snapshot(ticker: str, as_of_date: date) -> dict[str, Any]:
    """Fetch historical price snapshot as of a specific date.

    Tries Alpaca first, then yfinance, then Alpha Vantage as fallback.

    Args:
        ticker: Stock ticker symbol
        as_of_date: Historical date to fetch data for

    Returns:
        Dictionary with latest price and trend as of specified date
    """
    settings = AppSettings.from_env()
    start_date = _history_window_start(as_of_date, 20)
    alpaca_error: Exception | None = None
    longbridge_error: Exception | None = None
    yfinance_error: Exception | None = None
    alpha_error: Exception | None = None
    source = "alpaca_historical"
    try:
        prices = load_alpaca_history_window(ticker, start_date, as_of_date, settings)
    except Exception as exc:
        alpaca_error = exc
        prices = []

    if not prices:
        source = "longbridge_historical"
        try:
            prices = load_longbridge_history_window(ticker, start_date, as_of_date, settings)
        except Exception as exc:
            longbridge_error = exc
            prices = []

    if not prices:
        source = "yfinance_historical"
        try:
            prices = _load_yfinance_history_window(ticker, start_date, as_of_date)
        except Exception as exc:
            yfinance_error = exc
            prices = []

    if not prices:
        source = "alpha_vantage_historical"
        try:
            prices = _load_alpha_history_window(ticker, start_date, as_of_date, settings)
        except Exception as exc:
            alpha_error = exc
            prices = []

    if not prices:
        fallback_parts: list[str] = []
        if alpaca_error is not None:
            fallback_parts.append("alpaca_unavailable")
        if longbridge_error is not None:
            fallback_parts.append("longbridge_unavailable")
        if yfinance_error is not None:
            fallback_parts.append(yfinance_failure_message(yfinance_error))
        if alpha_error is not None:
            fallback_parts.append("alpha_unavailable")
        fallback_reason = "; ".join(fallback_parts) if fallback_parts else "all_sources_unavailable"
        return {
            "Ticker": ticker,
            "Status": "Historical data unavailable",
            "Source": "historical_unavailable",
            "Fallback_Reason": fallback_reason,
        }

    trend = [round(price,2) for price in prices[-5:]]
    return {
        "Ticker": ticker,
        "Latest_Price": trend[-1],
        "Trend_5D": trend,
        "Status": "Success",
        "Source": source,
        "As_Of_Date": as_of_date.isoformat(),
    }


def fetch_historical_tech_indicators(ticker: str, as_of_date: date) -> dict[str, Any]:
    """Fetch historical technical indicators as of a specific date.

    Tries Alpaca first, then yfinance, then Alpha Vantage as fallback.

    Args:
        ticker: Stock ticker symbol
        as_of_date: Historical date to fetch data for

    Returns:
        Dictionary with MA20, MA50, RSI14 as of specified date
    """
    settings = AppSettings.from_env()
    start_date = _history_window_start(as_of_date, 220)
    alpaca_error: Exception | None = None
    longbridge_error: Exception | None = None
    yfinance_error: Exception | None = None
    alpha_error: Exception | None = None
    source = "alpaca_historical"
    try:
        prices = load_alpaca_history_window(ticker, start_date, as_of_date, settings)
    except Exception as exc:
        alpaca_error = exc
        prices = []

    if not prices:
        source = "longbridge_historical"
        try:
            prices = load_longbridge_history_window(ticker, start_date, as_of_date, settings)
        except Exception as exc:
            longbridge_error = exc
            prices = []

    if not prices:
        source = "yfinance_historical"
        try:
            prices = _load_yfinance_history_window(ticker, start_date, as_of_date)
        except Exception as exc:
            yfinance_error = exc
            prices = []

    if not prices:
        source = "alpha_vantage_historical"
        try:
            prices = _load_alpha_history_window(ticker, start_date, as_of_date, settings)
        except Exception as exc:
            alpha_error = exc
            prices = []

    payload = _build_technical_payload_from_prices(ticker, prices, source)
    payload["As_Of_Date"] = as_of_date.isoformat()
    if payload.get("Status") == "No Data":
        fallback_parts: list[str] = []
        if alpaca_error is not None:
            fallback_parts.append("alpaca_unavailable")
        if longbridge_error is not None:
            fallback_parts.append("longbridge_unavailable")
        if yfinance_error is not None:
            fallback_parts.append(yfinance_failure_message(yfinance_error))
        if alpha_error is not None:
            fallback_parts.append("alpha_unavailable")
        payload["Status"] = "Historical data unavailable"
        payload["Source"] = "historical_unavailable"
        if fallback_parts:
            payload["Fallback_Reason"] = "; ".join(fallback_parts)
    return payload
