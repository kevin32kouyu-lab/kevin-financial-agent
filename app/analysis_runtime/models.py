from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class RiskProfile(BaseModel):
    tolerance_level: str | None = "medium"
    max_drawdown_expectation: str | None = None


class InvestmentStrategy(BaseModel):
    horizon: str | None = None
    style: str | None = None
    preferred_sectors: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)


class FundamentalFilters(BaseModel):
    max_pe_ratio: float | None = None
    min_roe: float | None = None
    min_dividend_yield: float | None = None
    require_positive_fcf: bool = False
    analyst_rating: str | None = None


class ExplicitTargets(BaseModel):
    tickers: list[str] = Field(default_factory=list)


class PipelineOptions(BaseModel):
    fetch_live_data: bool = True
    max_results: int = Field(default=5, ge=1, le=20)
    allocation_mode: Literal["score_weighted", "equal_weight", "custom_weight"] = "score_weighted"
    custom_weights: dict[str, float] = Field(default_factory=dict)


class DebugAnalysisRequest(BaseModel):
    risk_profile: RiskProfile = Field(default_factory=RiskProfile)
    investment_strategy: InvestmentStrategy = Field(default_factory=InvestmentStrategy)
    fundamental_filters: FundamentalFilters = Field(default_factory=FundamentalFilters)
    explicit_targets: ExplicitTargets = Field(default_factory=ExplicitTargets)
    portfolio_sizing: dict[str, Any] = Field(default_factory=dict)
    options: PipelineOptions = Field(default_factory=PipelineOptions)
    research_mode: str = "realtime"
    as_of_date: date | None = None
