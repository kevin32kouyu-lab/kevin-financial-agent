"""Tests for scoring algorithms."""

import pytest

from app.agent_runtime.reporting.scoring import (
    _coerce_float,
    _coerce_percent_points,
    _clamp,
    _normalize_trend_score,
    _analyst_bonus,
    _macro_is_severe,
    _build_allocation_plan,
)


class TestCoerceFloat:
    """Test float coercion utility."""

    def test_coerce_float_from_int(self):
        """Test coercing integer to float."""
        assert _coerce_float(42) == 42.0

    def test_coerce_float_from_float(self):
        """Test coercing float to float."""
        assert _coerce_float(3.14) == 3.14

    def test_coerce_float_from_string(self):
        """Test coercing string to float."""
        assert _coerce_float("42.5") == 42.5
        assert _coerce_float("1,234.56") == 1234.56
        assert _coerce_float("50%") == 50.0

    def test_coerce_float_none_values(self):
        """Test coercion of None-like values."""
        assert _coerce_float(None) is None
        assert _coerce_float("N/A") is None
        assert _coerce_float("None") is None
        assert _coerce_float("") is None

    def test_coerce_float_boolean_returns_none(self):
        """Test that booleans return None."""
        assert _coerce_float(True) is None
        assert _coerce_float(False) is None


class TestCoercePercentPoints:
    """Test percentage points coercion."""

    def test_coerce_percent_with_percent_sign(self):
        """Test coercion with percent sign."""
        assert _coerce_percent_points("15%") == 15.0
        assert _coerce_percent_points("-5%") == -5.0

    def test_coerce_percent_decimal_below_one(self):
        """Test coercion of decimal below 1 (interpreted as percentage)."""
        assert _coerce_percent_points(0.25) == 25.0
        assert _coerce_percent_points(0.50) == 50.0

    def test_coerce_percent_decimal_above_one(self):
        """Test coercion of decimal above 1 (kept as is)."""
        assert _coerce_percent_points(1.25) == 1.25
        assert _coerce_percent_points(15.0) == 15.0

    def test_coerce_percent_none(self):
        """Test coercion of None."""
        assert _coerce_percent_points(None) is None
        assert _coerce_percent_points("N/A") is None


class TestClamp:
    """Test value clamping utility."""

    def test_clamp_within_bounds(self):
        """Test clamping value within bounds."""
        assert _clamp(50.0, 0.0, 100.0) == 50.0
        assert _clamp(25.0, 10.0, 50.0) == 25.0

    def test_clamp_above_upper(self):
        """Test clamping value above upper bound."""
        assert _clamp(150.0, 0.0, 100.0) == 100.0
        assert _clamp(75.0, 10.0, 50.0) == 50.0

    def test_clamp_below_lower(self):
        """Test clamping value below lower bound."""
        assert _clamp(-10.0, 0.0, 100.0) == 0.0
        assert _clamp(5.0, 10.0, 50.0) == 10.0

    def test_clamp_default_bounds(self):
        """Test clamping with default bounds."""
        assert _clamp(-10.0) == 0.0
        assert _clamp(150.0) == 100.0


class TestNormalizeTrendScore:
    """Test trend score normalization."""

    def test_normalize_trend_positive(self):
        """Test normalizing positive trend."""
        score = _normalize_trend_score(5.0)  # 5% positive trend
        assert score > 50.0
        assert score <= 90.0

    def test_normalize_trend_negative(self):
        """Test normalizing negative trend."""
        score = _normalize_trend_score(-5.0)  # 5% negative trend
        assert score < 50.0
        assert score >= 15.0

    def test_normalize_trend_zero(self):
        """Test normalizing zero trend."""
        score = _normalize_trend_score(0.0)
        assert score == 50.0

    def test_normalize_trend_none(self):
        """Test normalizing None trend."""
        score = _normalize_trend_score(None)
        assert score == 50.0

    def test_normalize_trend_high_magnitude(self):
        """Test normalizing high magnitude trend."""
        score = _normalize_trend_score(10.0)  # 10% trend
        assert score == 90.0  # Upper bound

    def test_normalize_trend_very_negative(self):
        """Test normalizing very negative trend."""
        score = _normalize_trend_score(-10.0)  # -10% trend
        assert score == 15.0  # Lower bound


class TestAnalystBonus:
    """Test analyst rating bonus."""

    def test_analyst_bonus_strong_buy(self):
        """Test strong buy bonus."""
        assert _analyst_bonus("strong_buy") == 10.0
        assert _analyst_bonus("STRONG_BUY") == 10.0
        assert _analyst_bonus("Strong Buy") == 10.0

    def test_analyst_bonus_buy(self):
        """Test buy bonus."""
        assert _analyst_bonus("buy") == 6.0
        assert _analyst_bonus("BUY") == 6.0
        assert _analyst_bonus("Buy") == 6.0

    def test_analyst_bonus_other(self):
        """Test other ratings return 0."""
        assert _analyst_bonus("hold") == 0.0
        assert _analyst_bonus("sell") == 0.0
        assert _analyst_bonus("unknown") == 0.0
        assert _analyst_bonus(None) == 0.0


class TestMacroIsSevere:
    """Test macro severity detection."""

    def test_macro_severe_risk_off(self):
        """Test risk-off regime triggers severe."""
        assert _macro_is_severe({"Global_Regime": "Risk-off"})
        assert _macro_is_severe({"Global_Regime": "RISK-OFF"})

    def test_macro_severe_panic(self):
        """Test panic regime triggers severe."""
        assert _macro_is_severe({"Global_Regime": "Panic"})
        assert _macro_is_severe({"rEGime": "PANIC"})

    def test_macro_severe_warning(self):
        """Test warning text triggers severe."""
        assert _macro_is_severe({"Systemic_Risk_Warning": "warning"})
        assert _macro_is_severe({"Systemic_Risk_Warning": "caution"})

    def test_macro_severe_high_vix(self):
        """Test high VIX triggers severe."""
        assert _macro_is_severe({"VIX_Volatility_Index": 25.0})
        assert _macro_is_severe({"VIX_Volatility_Index": 30.0})

    def test_macro_not_severe(self):
        """Test normal macro conditions."""
        assert not _macro_is_severe({"Global_Regime": "Normal"})
        assert not _macro_is_severe({"Systemic_Risk_Warning": "stable"})
        assert not _macro_is_severe({"VIX_Volatility_Index": 15.0})
        assert not _macro_is_severe({})

    def test_macro_severe_edge_cases(self):
        """Test edge cases for VIX."""
        assert not _macro_is_severe({"VIX_Volatility_Index": 19.9})
        assert _macro_is_severe({"VIX_Volatility_Index": 20.0})
        assert _macro_is_severe({"VIX_Volatility_Index": 20.1})


class TestBuildAllocationPlan:
    """Test allocation plan building."""

    def test_build_allocation_from_strong_buys(self):
        """Test building plan from strong buy candidates."""
        candidates = [
            {"ticker": "AAPL", "composite_score": 80, "verdict_key": "strong_buy", "verdict_label": "Strong Buy", "veto": False},
            {"ticker": "MSFT", "composite_score": 75, "verdict_key": "strong_buy", "verdict_label": "Strong Buy", "veto": False},
            {"ticker": "GOOGL", "composite_score": 70, "verdict_key": "accumulate", "verdict_label": "Accumulate", "veto": False},
        ]

        plan = _build_allocation_plan(candidates)
        assert len(plan) == 3

        total_weight = sum(item["weight"] for item in plan)
        assert total_weight == pytest.approx(100.0, rel=0.01)

        # AAPL should have highest weight
        assert plan[0]["ticker"] == "AAPL"
        assert plan[0]["weight"] > plan[1]["weight"]

    def test_build_allocation_excludes_vetoed(self):
        """Test that vetoed candidates are excluded."""
        candidates = [
            {"ticker": "AAPL", "composite_score": 80, "verdict_key": "strong_buy", "verdict_label": "Strong Buy", "veto": False},
            {"ticker": "MSFT", "composite_score": 75, "verdict_key": "strong_buy", "verdict_label": "Strong Buy", "veto": True},
            {"ticker": "GOOGL", "composite_score": 70, "verdict_key": "accumulate", "verdict_label": "Accumulate", "veto": False},
        ]

        plan = _build_allocation_plan(candidates)
        assert len(plan) == 2
        assert all(item["ticker"] != "MSFT" for item in plan)

    def test_build_allocation_only_top_three(self):
        """Test that only top 3 candidates are selected."""
        candidates = [
            {"ticker": "AAPL", "composite_score": 90, "verdict_key": "strong_buy", "verdict_label": "Strong Buy", "veto": False},
            {"ticker": "MSFT", "composite_score": 85, "verdict_key": "strong_buy", "verdict_label": "Strong Buy", "veto": False},
            {"ticker": "GOOGL", "composite_score": 80, "verdict_key": "strong_buy", "verdict_label": "Strong Buy", "veto": False},
            {"ticker": "AMZN", "composite_score": 75, "verdict_key": "accumulate", "verdict_label": "Accumulate", "veto": False},
            {"ticker": "META", "composite_score": 70, "verdict_key": "accumulate", "verdict_label": "Accumulate", "veto": False},
        ]

        plan = _build_allocation_plan(candidates)
        assert len(plan) == 3

    def test_build_allocation_empty_when_no_eligible(self):
        """Test empty plan when no eligible candidates."""
        candidates = [
            {"ticker": "AAPL", "composite_score": 80, "verdict_key": "hold_watch", "verdict_label": "Hold", "veto": False},
            {"ticker": "MSFT", "composite_score": 75, "verdict_key": "avoid", "verdict_label": "Avoid", "veto": False},
            {"ticker": "GOOGL", "composite_score": 70, "verdict_key": "veto_avoid", "verdict_label": "Veto", "veto": True},
        ]

        plan = _build_allocation_plan(candidates)
        assert len(plan) == 0

    def test_build_allocation_weights_sum_to_100(self):
        """Test that weights always sum to 100%."""
        candidates = [
            {"ticker": "AAPL", "composite_score": 85, "verdict_key": "strong_buy", "verdict_label": "Strong Buy", "veto": False},
            {"ticker": "MSFT", "composite_score": 80, "verdict_key": "accumulate", "verdict_label": "Accumulate", "veto": False},
        ]

        plan = _build_allocation_plan(candidates)
        total_weight = sum(item["weight"] for item in plan)
        assert total_weight == pytest.approx(100.0, rel=0.01)
