"""Macro regime data fetcher.

Provides primary source with fallback for macro indicators.
"""

from datetime import date
from typing import Any

from app.core.config import AppSettings
from .yfinance_fetcher import _fetch_macro_regime_from_yfinance, _fetch_macro_regime_from_yfinance_as_of
from .fred_fetcher import _fetch_macro_regime_from_fred, _get_fred_api_key


def fetch_macro_regime(settings: AppSettings) -> dict[str, Any]:
    """Fetch macro regime indicators with FRED fallback.

    Args:
        settings: AppSettings instance

    Returns:
        Dictionary with VIX, S&P 500, 10Y Treasury and regime analysis
    """
    try:
        macro = _fetch_macro_regime_from_yfinance()
        macro["Backup_Source"] = "fred" if _get_fred_api_key(settings) else "none"
        return macro
    except Exception as exc:
        try:
            fred_api_key = _get_fred_api_key(settings)
            if not fred_api_key:
                raise RuntimeError(f"Primary source failed and FRED API key is not configured: {exc}") from exc

            macro = _fetch_macro_regime_from_fred(fred_api_key)
            macro["Fallback_Reason"] = str(exc)
            macro["Primary_Source"] = "yfinance"
            return macro
        except Exception as fallback_exc:
            return {
                "Global_Regime": "Unknown",
                "Status": f"Failed: {fallback_exc}",
                "Source": "unavailable",
            }


def fetch_macro_regime_as_of(settings: AppSettings, as_of_date: date) -> dict[str, Any]:
    """Fetch macro regime as of a specific historical date.

    Args:
        settings: AppSettings instance
        as_of_date: Historical date to fetch data for

    Returns:
        Dictionary with macro indicators as of specified date
    """
    try:
        return _fetch_macro_regime_from_yfinance_as_of(as_of_date)
    except Exception as exc:
        return {
            "Global_Regime": "Unknown",
            "Status": f"Historical data unavailable: {exc}",
            "Source": "historical_unavailable",
            "As_Of_Date": as_of_date.isoformat(),
        }
