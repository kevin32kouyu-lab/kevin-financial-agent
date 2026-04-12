from __future__ import annotations

from fastapi import APIRouter, Request

from app.analysis_runtime.models import DebugAnalysisRequest
from app.analysis_runtime.screener import RISK_WEIGHTS, normalize, run_screener_analysis, safe_float
from app.api.legacy import parse_legacy_payload
from app.core.config import AppSettings
from app.services.market_data_service import MarketDataService


router = APIRouter()

_market_data_service = MarketDataService(AppSettings.from_env())


def get_db():
    _market_data_service.startup()
    return _market_data_service.load_security_universe()


@router.post("/api/v1/analyze_and_compare")
async def analyze_and_compare(request: Request) -> dict:
    payload = await parse_legacy_payload(request)
    debug_request = DebugAnalysisRequest.model_validate(payload)
    return run_screener_analysis(debug_request, get_db())


__all__ = ["RISK_WEIGHTS", "get_db", "normalize", "safe_float", "router"]
