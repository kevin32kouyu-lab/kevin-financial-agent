from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent_runtime import AgentRunRequest
from app.analysis_runtime import DebugAnalysisRequest


RunMode = Literal["agent", "structured"]
RunStatus = Literal["queued", "running", "completed", "failed", "needs_clarification"]


class RunCreateRequest(BaseModel):
    mode: RunMode = "agent"
    agent: AgentRunRequest | None = None
    structured: DebugAnalysisRequest | None = None


class RunSummary(BaseModel):
    id: str
    mode: RunMode
    status: str
    title: str
    created_at: str
    updated_at: str
    error_message: str | None = None
    report_mode: str | None = None


class RunStepRecord(BaseModel):
    step_key: str
    label: str
    status: str
    elapsed_ms: float | None = None
    summary: str | None = None
    position: int = 0
    created_at: str
    updated_at: str


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


class RunListResponse(BaseModel):
    items: list[RunSummary] = Field(default_factory=list)


class RunEventRecord(BaseModel):
    id: int
    run_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
