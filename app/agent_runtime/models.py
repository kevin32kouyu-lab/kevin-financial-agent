from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.analysis_runtime import (
    ExplicitTargets,
    FundamentalFilters,
    InvestmentStrategy,
    PipelineOptions,
    RiskProfile,
)


class SystemContext(BaseModel):
    language: str = "zh"


class PortfolioSizing(BaseModel):
    capital_amount: int | None = None
    currency: str | None = None


class AgentControl(BaseModel):
    is_intent_clear: bool = False
    is_intent_usable: bool = False
    missing_critical_info: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class ParsedIntent(BaseModel):
    system_context: SystemContext = Field(default_factory=SystemContext)
    portfolio_sizing: PortfolioSizing = Field(default_factory=PortfolioSizing)
    risk_profile: RiskProfile = Field(default_factory=RiskProfile)
    investment_strategy: InvestmentStrategy = Field(default_factory=InvestmentStrategy)
    fundamental_filters: FundamentalFilters = Field(default_factory=FundamentalFilters)
    explicit_targets: ExplicitTargets = Field(default_factory=ExplicitTargets)
    agent_control: AgentControl = Field(default_factory=AgentControl)


class AgentLlmOptions(BaseModel):
    model: str | None = None
    base_url: str | None = None


class AgentMemoryContext(BaseModel):
    """轻量记忆：只保留最近一次稳定可复用的偏好。"""

    capital_amount: int | None = None
    currency: str | None = None
    risk_tolerance: str | None = None
    investment_horizon: str | None = None
    investment_style: str | None = None
    preferred_sectors: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)
    explicit_tickers: list[str] = Field(default_factory=list)


class ResearchContext(BaseModel):
    research_mode: Literal["realtime", "historical"] = "realtime"
    as_of_date: date | None = None


class AgentRunRequest(BaseModel):
    query: str = Field(min_length=1)
    options: PipelineOptions = Field(default_factory=PipelineOptions)
    llm: AgentLlmOptions = Field(default_factory=AgentLlmOptions)
    research_context: ResearchContext = Field(default_factory=ResearchContext)
    memory_context: AgentMemoryContext | None = None
