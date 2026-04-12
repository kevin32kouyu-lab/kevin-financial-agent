from __future__ import annotations

import asyncio
from typing import Any

from legacy.api_audit import fetch_sec_audit_data
from legacy.api_macro import fetch_macro_regime
from legacy.api_news import fetch_rss_news
from legacy.api_price import fetch_only_price
from legacy.api_smart_money import fetch_smart_money_data
from legacy.api_tech import fetch_tech_indicators


async def _collect_records(
    tickers: list[str],
    worker,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    async def _run_single(ticker: str) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(asyncio.to_thread(worker, ticker), timeout=timeout_seconds)
        except Exception as exc:
            return {
                "Ticker": ticker,
                "Status": f"Failed: {exc}",
            }

    if not tickers:
        return []

    tasks = [_run_single(ticker) for ticker in tickers]
    return await asyncio.gather(*tasks)


async def _collect_news(
    tickers: list[str],
    fetch_live_data: bool,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    if not fetch_live_data:
        return [], {ticker: [] for ticker in tickers}

    async def _run_single(ticker: str) -> tuple[str, list[dict[str, Any]]]:
        try:
            items = await asyncio.wait_for(asyncio.to_thread(fetch_rss_news, ticker), timeout=10.0)
            return ticker, items
        except Exception:
            return ticker, []

    results = await asyncio.gather(*[_run_single(ticker) for ticker in tickers]) if tickers else []

    flat_news: list[dict[str, Any]] = []
    by_ticker: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}

    for ticker, items in results:
        by_ticker[ticker] = items
        flat_news.extend(items)

    return flat_news, by_ticker


async def collect_live_data(tickers: list[str], fetch_live_data: bool) -> dict[str, Any]:
    if not fetch_live_data:
        skipped_list = [{"Ticker": ticker, "Status": "Skipped (live data disabled)"} for ticker in tickers]
        return {
            "price_data": skipped_list,
            "technical_data": skipped_list,
            "audit_data": skipped_list,
            "smart_money_data": skipped_list,
            "raw_news_list": [],
            "news_by_ticker": {ticker: [] for ticker in tickers},
            "macro_data": {
                "Status": "Skipped (live data disabled)",
                "Systemic_Risk_Warning": "Live data fetch was disabled for this run.",
            },
        }

    price_task = _collect_records(tickers, fetch_only_price, 12.0)
    tech_task = _collect_records(tickers, fetch_tech_indicators, 12.0)
    audit_task = _collect_records(tickers, fetch_sec_audit_data, 18.0)
    smart_money_task = _collect_records(tickers, fetch_smart_money_data, 12.0)
    news_task = _collect_news(tickers, fetch_live_data=True)

    try:
        macro_data = await asyncio.wait_for(asyncio.to_thread(fetch_macro_regime), timeout=10.0)
    except Exception as exc:
        macro_data = {"Status": f"Failed: {exc}"}

    price_data, technical_data, audit_data, smart_money_data, news_result = await asyncio.gather(
        price_task,
        tech_task,
        audit_task,
        smart_money_task,
        news_task,
    )

    raw_news_list, news_by_ticker = news_result

    return {
        "price_data": price_data,
        "technical_data": technical_data,
        "audit_data": audit_data,
        "smart_money_data": smart_money_data,
        "raw_news_list": raw_news_list,
        "news_by_ticker": news_by_ticker,
        "macro_data": macro_data,
    }


def _index_by_ticker(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in items:
        ticker = item.get("Ticker")
        if ticker:
            output[str(ticker).upper()] = item
    return output


def build_ticker_snapshots(
    comparison_matrix: list[dict[str, Any]],
    live_package: dict[str, Any],
) -> list[dict[str, Any]]:
    price_map = _index_by_ticker(live_package["price_data"])
    tech_map = _index_by_ticker(live_package["technical_data"])
    audit_map = _index_by_ticker(live_package["audit_data"])
    smart_money_map = _index_by_ticker(live_package["smart_money_data"])
    news_map = live_package["news_by_ticker"]

    snapshots: list[dict[str, Any]] = []
    for item in comparison_matrix:
        ticker = str(item.get("Ticker", "")).upper()
        snapshots.append(
            {
                "ticker": ticker,
                "company_name": item.get("Company_Name", "Unknown"),
                "sector": item.get("Sector", "Unknown"),
                "quant": item,
                "price": price_map.get(ticker, {"Ticker": ticker, "Status": "Unavailable"}),
                "technical": tech_map.get(ticker, {"Ticker": ticker, "Status": "Unavailable"}),
                "audit": audit_map.get(ticker, {"Ticker": ticker, "Status": "Unavailable"}),
                "smart_money": smart_money_map.get(ticker, {"Ticker": ticker, "Status": "Unavailable"}),
                "news": news_map.get(ticker, []),
            }
        )
    return snapshots
