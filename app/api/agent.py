from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Depends

from app.integrations.llm_client import LlmConfigError

from app.core.auth import get_api_key
from app.core.runtime import get_runtime
from app.domain.contracts import AgentRunRequest


router = APIRouter(prefix="/api/v1/agent", tags=["agent"], dependencies=[Depends(get_api_key)])


@router.get("/runtime-config")
async def runtime_config(request: Request, model: str | None = None, base_url: str | None = None) -> dict:
    runtime = get_runtime(request.app)
    return runtime.agent_service.get_runtime_config(model=model, base_url=base_url)


@router.post("/run")
async def run_agent(request: Request, payload: AgentRunRequest) -> dict:
    runtime = get_runtime(request.app)
    try:
        return await runtime.agent_service.run(payload)
    except LlmConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
