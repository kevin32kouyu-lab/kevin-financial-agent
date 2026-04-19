from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_api_key
from app.core.runtime import get_runtime
from app.domain.contracts import PreferenceUpdateRequest


router = APIRouter(prefix="/api/v1/profile", tags=["profile"], dependencies=[Depends(get_api_key)])


@router.get("/preferences")
async def get_preferences(request: Request) -> dict:
    runtime = get_runtime(request.app)
    return runtime.run_service.get_user_preferences()


@router.patch("/preferences")
async def update_preferences(request: Request, payload: PreferenceUpdateRequest) -> dict:
    runtime = get_runtime(request.app)
    return runtime.run_service.update_user_preferences(payload)
