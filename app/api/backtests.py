from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_api_key
from app.core.runtime import get_runtime
from app.domain.contracts import BacktestCreateRequest


router = APIRouter(prefix="/api/v1/backtests", tags=["backtests"], dependencies=[Depends(get_api_key)])


@router.get("")
async def list_backtests(
    request: Request,
    source_run_id: str | None = None,
    limit: int = 20,
) -> dict:
    runtime = get_runtime(request.app)
    return runtime.backtest_service.list_backtests(source_run_id=source_run_id, limit=limit)


@router.post("")
async def create_backtest(request: Request, payload: BacktestCreateRequest) -> dict:
    runtime = get_runtime(request.app)
    return await asyncio.to_thread(runtime.backtest_service.create_backtest, payload)


@router.get("/{backtest_id}")
async def get_backtest(request: Request, backtest_id: str) -> dict:
    runtime = get_runtime(request.app)
    return runtime.backtest_service.get_backtest_or_404(backtest_id)
