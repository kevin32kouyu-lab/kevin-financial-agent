"""管理员 API：查看操作审计等生产治理信息。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_api_key, require_admin
from app.core.runtime import get_runtime


router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(get_api_key)])


@router.get("/audit-events")
async def list_audit_events(request: Request, limit: int = 50) -> dict:
    """管理员查看操作审计。"""
    require_admin(request)
    runtime = get_runtime(request.app)
    return {"items": runtime.repository.list_audit_events(limit=limit)}
