from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

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
RunStatus = Literal["queued", "running", "completed", "failed", "needs_clarification", "cancelled"]


class RunCreateRequest(BaseModel):
    mode: RunMode = "agent"
    agent: AgentRunRequest | None = None
    structured: DebugAnalysisRequest | None = None


class UserProfile(BaseModel):
    capital_amount: int | None = Field(default=None, ge=0)
    currency: str | None = None
    risk_tolerance: str | None = None
    investment_horizon: str | None = None
    investment_style: str | None = None
    preferred_sectors: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip().upper()
        return text or None

    @field_validator("risk_tolerance", "investment_horizon", "investment_style", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("preferred_sectors", "preferred_industries", mode="before")
    @classmethod
    def _normalize_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item).strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(text)
        return normalized


class RunMemory(BaseModel):
    profile: UserProfile = Field(default_factory=UserProfile)
    applied_fields: list[str] = Field(default_factory=list)
    updated_fields: list[str] = Field(default_factory=list)


class ProfileResponse(BaseModel):
    client_id: str
    profile: UserProfile = Field(default_factory=UserProfile)
    updated_at: str | None = None


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
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "AgentRunRequest",
    "DebugAnalysisRequest",
    "ExplicitTargets",
    "FundamentalFilters",
    "InvestmentStrategy",
    "ParsedIntent",
    "PipelineOptions",
    "ProfileResponse",
    "RiskProfile",
    "RunMemory",
    "RunCreateRequest",
    "RunDetail",
    "RunEventRecord",
    "RunListResponse",
    "RunMode",
    "RunStatus",
    "RunStepRecord",
    "RunSummary",
    "UserProfile",
    "ArtifactRecord",
    "utc_now_iso",
]
