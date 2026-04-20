from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_api_key, get_required_client_id
from app.core.runtime import get_runtime
from app.domain.contracts import UserProfile


router = APIRouter(prefix="/api/v1/profile", tags=["profile"], dependencies=[Depends(get_api_key)])


@router.get("")
async def get_profile(request: Request) -> dict:
    runtime = get_runtime(request.app)
    client_id = get_required_client_id(request)
    return runtime.profile_service.get_profile(client_id).model_dump()


@router.put("")
async def update_profile(request: Request, payload: UserProfile) -> dict:
    runtime = get_runtime(request.app)
    client_id = get_required_client_id(request)
    return runtime.profile_service.update_profile(client_id, payload).model_dump()


@router.delete("")
async def clear_profile(request: Request) -> dict:
    runtime = get_runtime(request.app)
    client_id = get_required_client_id(request)
    return runtime.profile_service.clear_profile(client_id).model_dump()
