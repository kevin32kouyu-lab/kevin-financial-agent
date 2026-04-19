"""Yahoo RSS news fetcher.

Provides primary source for news data via RSS feeds.
"""

import xml.etree.ElementTree as ET
import time
import threading
from typing import Any

from app.core.config import AppSettings
from .base import _load_cached_snapshot, _store_cached_snapshot
from .finnhub_fetcher import _fetch_finnhub_company_news
from .yfinance_proxy_router import run_yfinance_call, classify_yfinance_exception

import requests

REQUEST_HEADERS = {
    "User-Agent": "FinancialAgentLab/1.0 (academic-research)",
}
_RSS_THROTTLE_LOCK = threading.RLock()
_LAST_RSS_REQUEST_AT = 0.0
_RSS_MIN_INTERVAL_SECONDS = 0.5


def _throttle_rss_requests() -> None:
    """限制 Yahoo RSS 请求频率，减少 429。"""
    global _LAST_RSS_REQUEST_AT
    with _RSS_THROTTLE_LOCK:
        now = time.monotonic()
        elapsed = now - _LAST_RSS_REQUEST_AT
        if elapsed < _RSS_MIN_INTERVAL_SECONDS:
            time.sleep(_RSS_MIN_INTERVAL_SECONDS - elapsed)
        _LAST_RSS_REQUEST_AT = time.monotonic()


def fetch_rss_news(ticker: str) -> list[dict[str, Any]]:
    """Fetch news from Yahoo RSS with Finnhub fallback.

    Args:
        ticker: Stock ticker symbol

    Returns:
        List of news items from primary and backup sources
    """
    settings = AppSettings.from_env()
    news_items: list[dict[str, Any]] = []

    # 先尝试 Yahoo RSS（自动路由：直连失败后代理重试）
    try:
        _throttle_rss_requests()
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        response = run_yfinance_call(
            settings,
            operation=f"yahoo_rss:{ticker}",
            call=lambda: requests.get(url, headers=REQUEST_HEADERS, timeout=6),
        )
        if response.status_code == 429:
            news_items = []
        elif response.status_code != 200:
            news_items = []
        else:
            root = ET.fromstring(response.content)
            for item in root.findall("./channel/item")[:5]:
                title = item.findtext("title", default="")
                if not title:
                    continue
                news_items.append(
                    {
                        "ticker": ticker,
                        "title": title,
                        "link": item.findtext("link", default=""),
                        "published_at": item.findtext("pubDate", default=""),
                        "source": "yahoo_rss",
                    }
                )
    except Exception as exc:
        reason_code = classify_yfinance_exception(exc)
        if reason_code in {"yahoo_rate_limited", "network_timeout", "proxy_connection_failed"}:
            news_items = []
        else:
            news_items = []

    # Yahoo 不可用时直接切 Finnhub，不等待额外长超时
    try:
        finnhub_items = _fetch_finnhub_company_news(ticker, settings)
    except Exception:
        finnhub_items = []

    # 合并并按标题去重
    merged: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for item in [*news_items, *finnhub_items]:
        title = str(item.get("title") or "").strip().lower()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        merged.append(item)
    merged = merged[:6]

    if merged:
        _store_cached_snapshot(settings, ticker, "news", merged)
        return merged

    cached = _load_cached_snapshot(settings, ticker, "news", ttl_minutes=360)
    if isinstance(cached, list):
        # 给缓存补充来源标记，方便前端显示
        normalized: list[dict[str, Any]] = []
        for item in cached:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row["source"] = row.get("source") or "cache"
            normalized.append(row)
        return normalized
    return []
