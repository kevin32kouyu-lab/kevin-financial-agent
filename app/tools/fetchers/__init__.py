"""Data fetchers module.

This module provides functions for fetching financial data from multiple sources.
Each fetcher handles a specific data source with fallback logic.
"""

# Re-export all public functions
from .base import (
    _compute_rsi,
    _build_technical_payload_from_prices,
    _load_cached_snapshot,
    _store_cached_snapshot,
)

from .yfinance_fetcher import (
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

from .alpha_vantage_fetcher import (
    _fetch_alpha_vantage_daily_prices,
    _fetch_only_price_from_alpha_vantage,
    _fetch_tech_from_alpha_vantage,
    _load_alpha_history_window,
)

from .finnhub_fetcher import (
    _fetch_finnhub_company_news,
)

from .yahoo_rss_fetcher import (
    fetch_rss_news,
)

from .fred_fetcher import (
    _fetch_fred_latest_value,
    _fetch_macro_regime_from_fred,
)

from .sec_fetcher import (
    fetch_sec_audit_data,
    fetch_historical_audit_data,
    fetch_historical_smart_money_data,
)

from .alpaca_fetcher import (
    fetch_alpaca_us_equities,
    fetch_alpaca_daily_bars,
    fetch_alpaca_price_snapshot,
    fetch_alpaca_bulk_price_snapshots,
    load_alpaca_history_window,
    has_alpaca_credentials,
)

from .longbridge_fetcher import (
    has_longbridge_credentials,
    fetch_longbridge_price_snapshot,
    fetch_longbridge_bulk_price_snapshots,
    fetch_longbridge_daily_bars,
    load_longbridge_history_window,
)

from .historical_fetcher import (
    fetch_historical_price_snapshot,
    fetch_historical_tech_indicators,
)

from .macro_fetcher import (
    fetch_macro_regime,
    fetch_macro_regime_as_of,
)

from .utils import (
    _market_repository,
    provider_statuses,
)

__all__ = [
    # Base
    "_compute_rsi",
    "_build_technical_payload_from_prices",
    "_load_cached_snapshot",
    "_store_cached_snapshot",
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
    "_market_repository",
    "provider_statuses",
]
