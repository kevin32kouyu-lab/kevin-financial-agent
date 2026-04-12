from __future__ import annotations

from typing import Any

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


class AgentRunRequest(BaseModel):
    query: str = Field(min_length=1)
    options: PipelineOptions = Field(default_factory=PipelineOptions)
    llm: AgentLlmOptions = Field(default_factory=AgentLlmOptions)
