from __future__ import annotations

from datetime import date, datetime
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
RunStatus = Literal["queued", "running", "completed", "failed", "needs_clarification", "cancelled"]


class RunCreateRequest(BaseModel):
    mode: RunMode = "agent"
    agent: AgentRunRequest | None = None
    structured: DebugAnalysisRequest | None = None


class AgentResumeRequest(BaseModel):
    agent_name: str = Field(min_length=1)
    reason: str = ""


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


class UserPreferenceValues(BaseModel):
    capital_amount: int | None = None
    currency: str | None = None
    risk_tolerance: str | None = None
    investment_horizon: str | None = None
    investment_style: str | None = None
    preferred_sectors: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)
    explicit_tickers: list[str] = Field(default_factory=list)


class UserPreferenceSummary(BaseModel):
    profile_id: str = "default"
    updated_at: str | None = None
    source_run_id: str | None = None
    source_query: str | None = None
    research_mode: str | None = None
    locale: str = "zh"
    memory_applied_fields: list[str] = Field(default_factory=list)
    values: UserPreferenceValues = Field(default_factory=UserPreferenceValues)


class PreferenceUpdateRequest(BaseModel):
    capital_amount: int | None = None
    currency: str | None = None
    risk_tolerance: str | None = None
    investment_horizon: str | None = None
    investment_style: str | None = None
    preferred_sectors: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)
    explicit_tickers: list[str] = Field(default_factory=list)
    locale: str = "zh"
    research_mode: str | None = None
    source_query: str | None = None


class RunAuditSummary(BaseModel):
    run_id: str
    title: str
    status: str
    query: str | None = None
    report_mode: str | None = None
    research_mode: str | None = None
    as_of_date: str | None = None
    top_pick: str | None = None
    confidence_level: str | None = None
    validation_flags: list[str] = Field(default_factory=list)
    coverage_flags: list[str] = Field(default_factory=list)
    used_sources: list[str] = Field(default_factory=list)
    degraded_modules: list[str] = Field(default_factory=list)
    memory_applied_fields: list[str] = Field(default_factory=list)
    follow_up_question: str | None = None


class BacktestCreateRequest(BaseModel):
    mode: Literal["replay", "reference"] = "replay"
    source_run_id: str
    entry_date: date | None = None
    end_date: date | None = None


class BacktestPoint(BaseModel):
    point_date: str
    portfolio_value: float
    benchmark_value: float
    portfolio_return_pct: float
    benchmark_return_pct: float


class BacktestPositionPoint(BaseModel):
    point_date: str
    close_price: float
    daily_return_pct: float
    cumulative_return_pct: float
    contribution_pct: float


class BacktestPosition(BaseModel):

    ticker: str
    weight: float
    verdict: str
    entry_date: str
    entry_price: float
    latest_price: float
    shares: float
    invested_amount: float
    current_value: float
    return_pct: float
    contribution_pct: float
    timeseries: list[BacktestPositionPoint] = Field(default_factory=list)


class BacktestMetrics(BaseModel):
    initial_capital: float
    final_value: float
    benchmark_final_value: float
    total_return_pct: float
    benchmark_return_pct: float
    excess_return_pct: float
    annualized_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    trading_days: int


class BacktestSummary(BaseModel):
    id: str
    source_run_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    entry_date: str
    end_date: str
    benchmark_ticker: str = "SPY"
    metrics: BacktestMetrics
    requested_count: int = 0
    coverage_count: int = 0
    dropped_tickers: list[dict[str, Any]] = Field(default_factory=list)


class BacktestDetail(BaseModel):
    summary: BacktestSummary
    positions: list[BacktestPosition] = Field(default_factory=list)
    points: list[BacktestPoint] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class BacktestListResponse(BaseModel):
    items: list[BacktestSummary] = Field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


__all__ = [
    "AgentRunRequest",
    "AgentResumeRequest",
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
    "BacktestCreateRequest",
    "BacktestPoint",
    "BacktestPositionPoint",
    "BacktestPosition",
    "BacktestMetrics",
    "BacktestSummary",
    "BacktestDetail",
    "BacktestListResponse",
    "RunMode",
    "RunStatus",
    "RunStepRecord",
    "RunSummary",
    "UserPreferenceSummary",
    "PreferenceUpdateRequest",
    "RunAuditSummary",
    "ArtifactRecord",
    "utc_now_iso",
]
