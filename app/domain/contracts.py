from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent_runtime.models import AgentRunRequest, ParsedIntent
from app.analysis_runtime.models import (
    DebugAnalysisRequest,
    ExplicitTargets,
    FundamentalFilters,
    InvestmentStrategy,
    PipelineOptions,
    RiskProfile,
)


RunMode = Literal["agent", "structured"]
RunStatus = Literal["queued", "running", "completed", "failed", "needs_clarification"]


class RunCreateRequest(BaseModel):
    mode: RunMode = "agent"
    agent: AgentRunRequest | None = None
    structured: DebugAnalysisRequest | None = None


class RunSummary(BaseModel):
    id: str
    mode: RunMode
    workflow_key: str
    status: str
    title: str
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    parent_run_id: str | None = None
    error_message: str | None = None
    report_mode: str | None = None
    attempt_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunStepRecord(BaseModel):
    step_key: str
    label: str
    status: str
    elapsed_ms: float | None = None
    summary: str | None = None
    position: int = 0
    created_at: str
    updated_at: str
    input_data: Any = None
    output_data: Any = None
    error_data: Any = None


class ArtifactRecord(BaseModel):
    id: int
    kind: str
    name: str
    created_at: str
    updated_at: str
    content: Any


class RunDetail(BaseModel):
    run: RunSummary
    steps: list[RunStepRecord] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    result: dict[str, Any] | None = None


class RunEventRecord(BaseModel):
    id: int
    run_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class RunListResponse(BaseModel):
    items: list[RunSummary] = Field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


__all__ = [
    "AgentRunRequest",
    "DebugAnalysisRequest",
    "ExplicitTargets",
    "FundamentalFilters",
    "InvestmentStrategy",
    "ParsedIntent",
    "PipelineOptions",
    "RiskProfile",
    "RunCreateRequest",
    "RunDetail",
    "RunEventRecord",
    "RunListResponse",
    "RunMode",
    "RunStatus",
    "RunStepRecord",
    "RunSummary",
    "ArtifactRecord",
    "utc_now_iso",
]
