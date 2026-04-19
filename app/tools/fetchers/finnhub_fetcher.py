"""Finnhub data fetcher.

Provides backup source for news data.
"""

from datetime import date, timedelta
from typing import Any

from app.core.config import AppSettings

import requests

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
REQUEST_HEADERS = {
    "User-Agent": "FinancialAgentLab/1.0 (academic-research)",
}


def _get_finnhub_api_key(settings: AppSettings) -> str:
    """Get Finnhub API key from settings."""
    return settings.finnhub_api_key or ""


def _fetch_finnhub_company_news(ticker: str, settings: AppSettings) -> list[dict[str, Any]]:
    """Fetch recent company news from Finnhub.

    Args:
        ticker: Stock ticker symbol
        settings: AppSettings instance

    Returns:
        List of news items with title, link, published_at
    """
    api_key = _get_finnhub_api_key(settings)
    if not api_key:
        return []

    end_date = date.today()
    start_date = end_date - timedelta(days=10)
    response = requests.get(
        f"{FINNHUB_BASE_URL}/company-news",
        params={
            "symbol": ticker,
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "token": api_key,
        },
        headers=REQUEST_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []

    news_items: list[dict[str, Any]] = []
    for item in payload[:5]:
        title = str(item.get("headline") or "").strip()
        if not title:
            continue
        news_items.append(
            {
                "ticker": ticker,
                "title": title,
                "link": item.get("url") or "",
                "published_at": item.get("datetime") or "",
                "source": "finnhub",
            }
        )
    return news_items
