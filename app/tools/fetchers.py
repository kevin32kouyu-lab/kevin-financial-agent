"""
Data fetchers module for fetching financial data from multiple sources.

This module has been refactored into submodules for better maintainability:
- base: shared utilities and helper functions
- yfinance_fetcher: primary price, technical, and smart money data
- alpha_vantage_fetcher: backup price and technical data
- finnhub_fetcher: backup news data
- yahoo_rss_fetcher: primary news data
- fred_fetcher: backup macro data
- sec_fetcher: primary audit and filing data
- alpaca_fetcher: primary universe data
- historical_fetcher: historical price and technical data for backtesting
- macro_fetcher: macro regime with fallback logic
- utils: provider status and configuration utilities

This file maintains backward compatibility by re-exporting all public functions.
"""

# Re-export all functions from submodules
from .fetchers.base import (
    _compute_rsi,
    _build_technical_payload_from_prices,
    _load_cached_snapshot,
    _store_cached_snapshot,
    _history_window_start,
    _get_cik_mapping,
)

from .fetchers.yfinance_fetcher import (
    fetch_bulk_only_price,
    fetch_bulk_smart_money_data,
    fetch_only_price,
    fetch_tech_indicators,
    fetch_smart_money_data,
    fetch_bulk_tech_indicators,
    _load_yfinance_history_window,
    _fetch_macro_regime_from_yfinance,
    _fetch_macro_regime_from_yfinance_as_of,
)

from .fetchers.alpha_vantage_fetcher import (
    _fetch_alpha_vantage_daily_prices,
    _fetch_only_price_from_alpha_vantage,
    _fetch_tech_from_alpha_vantage,
    _load_alpha_history_window,
)

from .fetchers.finnhub_fetcher import (
    _fetch_finnhub_company_news,
)

from .fetchers.yahoo_rss_fetcher import (
    fetch_rss_news,
)

from .fetchers.fred_fetcher import (
    _fetch_fred_latest_value,
    _fetch_macro_regime_from_fred,
)

from .fetchers.sec_fetcher import (
    fetch_sec_audit_data,
    fetch_historical_audit_data,
    fetch_historical_smart_money_data,
)

from .fetchers.alpaca_fetcher import (
    fetch_alpaca_us_equities,
    fetch_alpaca_daily_bars,
    fetch_alpaca_price_snapshot,
    fetch_alpaca_bulk_price_snapshots,
    load_alpaca_history_window,
    has_alpaca_credentials,
)

from .fetchers.longbridge_fetcher import (
    has_longbridge_credentials,
    fetch_longbridge_price_snapshot,
    fetch_longbridge_bulk_price_snapshots,
    fetch_longbridge_daily_bars,
    load_longbridge_history_window,
)

from .fetchers.historical_fetcher import (
    fetch_historical_price_snapshot,
    fetch_historical_tech_indicators,
)

from .fetchers.macro_fetcher import (
    fetch_macro_regime,
    fetch_macro_regime_as_of,
)

from .fetchers.utils import (
    provider_statuses,
)

# Re-export constants for backward compatibility
REQUEST_HEADERS = {
    "User-Agent": "FinancialAgentLab/1.0 (academic-research)",
}

SEC_HEADERS = {
    "User-Agent": "FinancialAgentLab/1.0 research-contact@example.com",
}

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

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

__all__ = [
    # Constants
    "REQUEST_HEADERS",
    "SEC_HEADERS",
    "FRED_HEADERS",
    "FRED_SERIES",
    "FRED_OBSERVATIONS_URL",
    "ALPHA_VANTAGE_URL",
    "FINNHUB_BASE_URL",
    # Base helpers
    "_compute_rsi",
    "_build_technical_payload_from_prices",
    "_load_cached_snapshot",
    "_store_cached_snapshot",
    "_history_window_start",
    "_get_cik_mapping",
    # yfinance
    "fetch_bulk_only_price",
    "fetch_bulk_smart_money_data",
    "fetch_only_price",
    "fetch_tech_indicators",
    "fetch_smart_money_data",
    "fetch_bulk_tech_indicators",
    "_load_yfinance_history_window",
    "_fetch_macro_regime_from_yfinance",
    "_fetch_macro_regime_from_yfinance_as_of",
    # Alpha Vantage
    "_fetch_alpha_vantage_daily_prices",
    "_fetch_only_price_from_alpha_vantage",
    "_fetch_tech_from_alpha_vantage",
    "_load_alpha_history_window",
    # Finnhub
    "_fetch_finnhub_company_news",
    # Yahoo RSS
    "fetch_rss_news",
    # FRED
    "_fetch_fred_latest_value",
    "_fetch_macro_regime_from_fred",
    # SEC
    "fetch_sec_audit_data",
    "fetch_historical_audit_data",
    "fetch_historical_smart_money_data",
    # Alpaca
    "fetch_alpaca_us_equities",
    "fetch_alpaca_daily_bars",
    "fetch_alpaca_price_snapshot",
    "fetch_alpaca_bulk_price_snapshots",
    "load_alpaca_history_window",
    "has_alpaca_credentials",
    # Longbridge
    "has_longbridge_credentials",
    "fetch_longbridge_price_snapshot",
    "fetch_longbridge_bulk_price_snapshots",
    "fetch_longbridge_daily_bars",
    "load_longbridge_history_window",
    # Historical
    "fetch_historical_price_snapshot",
    "fetch_historical_tech_indicators",
    # Macro
    "fetch_macro_regime",
    "fetch_macro_regime_as_of",
    # Utils
    "provider_statuses",
]
