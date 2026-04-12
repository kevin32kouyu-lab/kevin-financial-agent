from __future__ import annotations

import asyncio
from typing import Any, Callable

from app.tools.fetchers import (
    fetch_macro_regime,
    fetch_bulk_tech_indicators,
    fetch_only_price,
    fetch_rss_news,
    fetch_sec_audit_data,
    fetch_smart_money_data,
)


ToolWorker = Callable[[str], dict[str, Any]]


class MarketToolKit:
    async def _collect_records(
        self,
        tickers: list[str],
        worker: ToolWorker,
        timeout_seconds: float,
        max_concurrency: int = 2,
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _run_single(ticker: str) -> dict[str, Any]:
            try:
                async with semaphore:
                    return await asyncio.wait_for(asyncio.to_thread(worker, ticker), timeout=timeout_seconds)
            except Exception as exc:
                return {"Ticker": ticker, "Status": f"Failed: {exc}"}

        if not tickers:
            return []
        return await asyncio.gather(*[_run_single(ticker) for ticker in tickers])

    async def _collect_news(self, tickers: list[str]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        semaphore = asyncio.Semaphore(3)

        async def _run_single(ticker: str) -> tuple[str, list[dict[str, Any]]]:
            try:
                async with semaphore:
                    items = await asyncio.wait_for(asyncio.to_thread(fetch_rss_news, ticker), timeout=10.0)
                return ticker, items
            except Exception:
                return ticker, []

        results = await asyncio.gather(*[_run_single(ticker) for ticker in tickers]) if tickers else []
        flat_news: list[dict[str, Any]] = []
        news_by_ticker: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}

        for ticker, items in results:
            news_by_ticker[ticker] = items
            flat_news.extend(items)

        return flat_news, news_by_ticker

    async def collect_live_package(self, tickers: list[str], fetch_live_data: bool) -> dict[str, Any]:
        if not fetch_live_data:
            skipped = [{"Ticker": ticker, "Status": "Skipped (live data disabled)"} for ticker in tickers]
            return {
                "price_data": skipped,
                "technical_data": skipped,
                "audit_data": skipped,
                "smart_money_data": skipped,
                "raw_news_list": [],
                "news_by_ticker": {ticker: [] for ticker in tickers},
                "macro_data": {
                    "Status": "Skipped (live data disabled)",
                    "Systemic_Risk_Warning": "Live data fetch was disabled for this run.",
                },
            }

        price_task = self._collect_records(tickers, fetch_only_price, 12.0)
        tech_task = asyncio.wait_for(asyncio.to_thread(fetch_bulk_tech_indicators, tickers), timeout=45.0)
        audit_task = self._collect_records(tickers, fetch_sec_audit_data, 18.0)
        smart_money_task = self._collect_records(tickers, fetch_smart_money_data, 12.0)
        news_task = self._collect_news(tickers)

        try:
            from app.core.config import AppSettings
            settings = AppSettings.from_env()
            macro_data = await asyncio.wait_for(asyncio.to_thread(fetch_macro_regime, settings), timeout=10.0)
        except Exception as exc:
            macro_data = {"Status": f"Failed: {str(exc)}", "Source": "macro_unavailable"}

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

    @staticmethod
    def build_ticker_snapshots(
        comparison_matrix: list[dict[str, Any]],
        live_package: dict[str, Any],
    ) -> list[dict[str, Any]]:
        def _index_by_ticker(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
            output: dict[str, dict[str, Any]] = {}
            for item in items:
                ticker = item.get("Ticker")
                if ticker:
                    output[str(ticker).upper()] = item
            return output

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
