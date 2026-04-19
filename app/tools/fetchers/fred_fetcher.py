"""FRED (Federal Reserve Economic Data) fetcher.

Provides backup source for macro regime data.
"""

from typing import Any

from app.core.config import AppSettings

import requests

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_HEADERS = {
    "User-Agent": "FinancialAgentLab/1.0 (macro-research)",
}

FRED_SERIES = {
    "SP500_Level": "SP500",
    "VIX_Volatility_Index": "VIXCLS",
    "US10Y_Treasury_Yield": "DGS10",
    "Fed_Funds_Rate": "FEDFUNDS",
    "US_CPI_Index": "CPIAUCSL",
    "US_Unemployment_Rate": "UNRATE",
}


def _get_fred_api_key(settings: AppSettings) -> str:
    """Get FRED API key from settings."""
    return settings.fred_api_key or ""


def _fetch_fred_latest_value(series_id: str, api_key: str) -> float | None:
    """Fetch latest value for a FRED series.

    Args:
        series_id: FRED series identifier
        api_key: FRED API key

    Returns:
        Latest numeric value or None if unavailable
    """
    response = requests.get(
        FRED_OBSERVATIONS_URL,
        headers=FRED_HEADERS,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 10,
        },
        timeout=12,
    )
    response.raise_for_status()
    observations = response.json().get("observations", [])
    for item in observations:
        value = str(item.get("value", "")).strip()
        if not value or value == ".":
            continue
        return float(value)
    return None


def _fetch_macro_regime_from_fred(api_key: str) -> dict[str, Any]:
    """Fetch macro regime indicators from FRED.

    Args:
        api_key: FRED API key

    Returns:
        Dictionary with macro indicators and regime analysis
    """
    macro: dict[str, Any] = {}
    for field_name, series_id in FRED_SERIES.items():
        macro[field_name] = _fetch_fred_latest_value(series_id, api_key)

    vix_value = macro.get("VIX_Volatility_Index")
    tnx_value = macro.get("US10Y_Treasury_Yield")
    regime = "Neutral"
    warning = "No major systemic risk detected."

    if isinstance(vix_value, float):
        if vix_value > 30:
            regime = "Extreme Risk-Off (Panic)"
            warning = f"CRITICAL: VIX is at {vix_value:.2f}, indicating extreme market panic."
        elif vix_value > 20:
            regime = "Risk-Off (Caution)"
            warning = f"WARNING: VIX is elevated at {vix_value:.2f}. Market volatility is increasing."
        elif vix_value < 15:
            regime = "Risk-On (Bullish)"
            warning = "Market is calm. High liquidity environment favors equities."

    if isinstance(tnx_value, float) and tnx_value > 4.5:
        warning += f" | NOTE: High 10Y Yield ({tnx_value:.2f}%) may pressure tech stock valuations."

    return {
        **macro,
        "Global_Regime": regime,
        "Systemic_Risk_Warning": warning,
        "Status": "Success",
        "Source": "fred",
    }
