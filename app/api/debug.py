from __future__ import annotations

from fastapi import APIRouter, Request, Depends

from app.core.auth import get_api_key
from app.core.runtime import get_runtime
from app.domain.contracts import DebugAnalysisRequest


router = APIRouter(prefix="/api/v1/debug", tags=["debug"], dependencies=[Depends(get_api_key)])


@router.post("/run-analysis")
async def run_debug_analysis(request: Request, payload: DebugAnalysisRequest) -> dict:
    runtime = get_runtime(request.app)
    return await runtime.analysis_service.run_structured_analysis(payload)
