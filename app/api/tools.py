from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request

from app.api.legacy import build_debug_request, extract_tickers_from_matrix, parse_legacy_payload
from app.core.auth import get_api_key
from app.core.runtime import get_runtime
from app.tools.fetchers import (
    fetch_macro_regime,
    fetch_only_price,
    fetch_rss_news,
    fetch_sec_audit_data,
    fetch_smart_money_data,
    fetch_tech_indicators,
)


router = APIRouter(tags=["tools"], dependencies=[Depends(get_api_key)])


def _ticker_error() -> dict[str, str]:
    return {"error": "未收到有效股票代码。"}


@router.post("/api/v1/analyze_and_compare")
async def analyze_and_compare(request: Request) -> dict:
    payload = await parse_legacy_payload(request)
    runtime = get_runtime(request.app)
    return runtime.analysis_service.run_screener_only(build_debug_request(payload))


@router.get("/api/v1/data/status")
async def get_data_status(request: Request) -> dict:
    runtime = get_runtime(request.app)
    return runtime.market_data_service.get_status()


@router.post("/api/v1/data/refresh")
async def refresh_data_status(request: Request) -> dict:
    runtime = get_runtime(request.app)
    return await asyncio.to_thread(runtime.market_data_service.refresh_core_datasets)


@router.post("/api/v1/data/refresh/universe")
async def refresh_universe(request: Request) -> dict:
    runtime = get_runtime(request.app)
    return await asyncio.to_thread(runtime.market_data_service.refresh_universe)


@router.post("/api/v1/data/refresh/macro")
async def refresh_macro(request: Request) -> dict:
    runtime = get_runtime(request.app)
    return await asyncio.to_thread(runtime.market_data_service.refresh_macro_snapshot)


@router.post("/api/v1/data/refresh/all")
async def refresh_all(request: Request) -> dict:
    runtime = get_runtime(request.app)
    return await asyncio.to_thread(runtime.market_data_service.refresh_core_datasets)


@router.get("/api/v1/data/jobs")
async def list_refresh_jobs(request: Request, limit: int = 20) -> dict:
    runtime = get_runtime(request.app)
    return runtime.market_data_service.list_refresh_jobs(limit=limit)


@router.post("/api/v1/fetch_stock_prices")
async def fetch_stock_prices(request: Request) -> dict:
    payload = await parse_legacy_payload(request)
    tickers = extract_tickers_from_matrix(payload)
    if not tickers:
        return _ticker_error()

    async def _run_single(ticker: str) -> dict:
        try:
            return await asyncio.wait_for(asyncio.to_thread(fetch_only_price, ticker), timeout=8.0)
        except Exception:
            return {"Ticker": ticker, "Status": "Timeout"}

    return {"price_data": await asyncio.gather(*[_run_single(ticker) for ticker in tickers])}


@router.post("/api/v1/fetch_raw_news")
async def fetch_raw_news(request: Request) -> dict:
    payload = await parse_legacy_payload(request)
    tickers = extract_tickers_from_matrix(payload)
    if not tickers:
        return _ticker_error()

    async def _run_single(ticker: str) -> list[dict]:
        try:
            return await asyncio.wait_for(asyncio.to_thread(fetch_rss_news, ticker), timeout=8.0)
        except Exception:
            return []

    results = await asyncio.gather(*[_run_single(ticker) for ticker in tickers])
    output: list[dict] = []
    for items in results:
        output.extend(items)
    return {"raw_news_list": output}


@router.post("/api/v1/fetch_tech_data")
async def fetch_tech_data(request: Request) -> dict:
    payload = await parse_legacy_payload(request)
    tickers = extract_tickers_from_matrix(payload)
    if not tickers:
        return _ticker_error()

    async def _run_single(ticker: str) -> dict:
        try:
            return await asyncio.wait_for(asyncio.to_thread(fetch_tech_indicators, ticker), timeout=8.0)
        except Exception:
            return {"Ticker": ticker, "Status": "Timeout"}

    return {"technical_data": await asyncio.gather(*[_run_single(ticker) for ticker in tickers])}


@router.post("/api/v1/fetch_macro_data")
async def fetch_macro_data(request: Request) -> dict:
    runtime = get_runtime(request.app)
    await parse_legacy_payload(request)
    return {"macro_data": fetch_macro_regime(runtime.settings)}


@router.post("/api/v1/fetch_smart_money_data")
async def fetch_smart_money_data_endpoint(request: Request) -> dict:
    payload = await parse_legacy_payload(request)
    tickers = extract_tickers_from_matrix(payload)
    if not tickers:
        return _ticker_error()

    async def _run_single(ticker: str) -> dict:
        try:
            return await asyncio.wait_for(asyncio.to_thread(fetch_smart_money_data, ticker), timeout=8.0)
        except Exception:
            return {"Ticker": ticker, "Status": "Timeout"}

    return {"smart_money_data": await asyncio.gather(*[_run_single(ticker) for ticker in tickers])}


@router.post("/api/v1/fetch_audit_data")
async def fetch_audit_data(request: Request) -> dict:
    payload = await parse_legacy_payload(request)
    tickers = extract_tickers_from_matrix(payload)
    if not tickers:
        return _ticker_error()

    async def _run_single(ticker: str) -> dict:
        try:
            return await asyncio.wait_for(asyncio.to_thread(fetch_sec_audit_data, ticker), timeout=15.0)
        except Exception:
            return {"Ticker": ticker, "Status": "Timeout"}

    return {"audit_data": await asyncio.gather(*[_run_single(ticker) for ticker in tickers])}
