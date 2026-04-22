from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_api_key, get_client_id, get_current_user
from app.core.runtime import get_runtime
from app.domain.contracts import LinkClientMemoryRequest, PreferenceUpdateRequest


router = APIRouter(prefix="/api/v1/profile", tags=["profile"], dependencies=[Depends(get_api_key)])


@router.get("/preferences")
async def get_preferences(request: Request) -> dict:
    runtime = get_runtime(request.app)
    client_id = get_client_id(request)
    return runtime.run_service.get_user_preferences(client_id=client_id, user=get_current_user(request))


@router.patch("/preferences")
async def update_preferences(request: Request, payload: PreferenceUpdateRequest) -> dict:
    runtime = get_runtime(request.app)
    client_id = get_client_id(request)
    return runtime.run_service.update_user_preferences(payload, client_id=client_id, user=get_current_user(request))


@router.delete("/preferences")
async def clear_preferences(request: Request) -> dict:
    runtime = get_runtime(request.app)
    client_id = get_client_id(request)
    return runtime.run_service.clear_user_preferences(client_id=client_id, user=get_current_user(request))


@router.post("/link-client-memory")
async def link_client_memory(request: Request, payload: LinkClientMemoryRequest) -> dict:
    runtime = get_runtime(request.app)
    user = get_current_user(request)
    if user is None:
        return {"error": "login_required"}
    return runtime.run_service.link_client_memory(client_id=payload.client_id or get_client_id(request), user=user)
