"""Utility functions for fetchers module."""

from typing import Any

from app.core.config import AppSettings
from .alpaca_fetcher import has_alpaca_credentials
from .longbridge_fetcher import has_longbridge_credentials
from .alpha_vantage_fetcher import _get_alpha_vantage_api_key
from .finnhub_fetcher import _get_finnhub_api_key
from .fred_fetcher import _get_fred_api_key
from .base import _market_repository


def provider_statuses(settings: AppSettings) -> list[dict[str, Any]]:
    """Get status of all configured data providers.

    Args:
        settings: AppSettings instance

    Returns:
        List of provider configuration status dictionaries
    """
    return [
        {"provider": "yfinance", "role": "price_tech_macro_primary", "configured": True},
        {
            "provider": "market_proxy_router",
            "role": "yfinance_route_control",
            "configured": True,
            "mode": settings.market_proxy_mode,
            "proxy_url_configured": bool(settings.market_proxy_url),
        },
        {"provider": "yahoo_rss", "role": "news_primary", "configured": True},
        {"provider": "sec_edgar", "role": "fundamental_primary", "configured": True},
        {"provider": "alpaca", "role": "universe_primary", "configured": has_alpaca_credentials(settings)},
        {"provider": "longbridge", "role": "price_backup", "configured": has_longbridge_credentials(settings)},
        {"provider": "wikipedia", "role": "universe_backup", "configured": True},
        {"provider": "alpha_vantage", "role": "price_tech_backup", "configured": bool(_get_alpha_vantage_api_key(settings))},
        {"provider": "finnhub", "role": "news_backup", "configured": bool(_get_finnhub_api_key(settings))},
        {"provider": "fred", "role": "macro_backup", "configured": bool(_get_fred_api_key(settings))},
    ]


__all__ = ["provider_statuses"]
