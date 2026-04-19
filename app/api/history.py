from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_api_key
from app.core.runtime import get_runtime


router = APIRouter(prefix="/api/v1/runs", tags=["run-history"], dependencies=[Depends(get_api_key)])


@router.get("/history")
async def list_run_history(
    request: Request,
    limit: int = 20,
    mode: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> dict:
    runtime = get_runtime(request.app)
    return runtime.run_service.list_run_history(limit=limit, mode=mode, status=status, search=search)


@router.get("/{run_id}/audit-summary")
async def get_run_audit_summary(request: Request, run_id: str) -> dict:
    runtime = get_runtime(request.app)
    return runtime.run_service.get_run_audit_summary_or_404(run_id)
