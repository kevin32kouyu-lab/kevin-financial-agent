"""Tests for report builder functions."""

import pytest

from app.agent_runtime.reporting.builder import _labels


class TestLocalizationLabels:
    """Test localization label retrieval."""

    def test_english_labels(self):
        """Test English label retrieval."""
        labels = _labels("en")

        assert labels["title"] == "Institutional Investment Research Report"
        assert labels["subtitle"] == "Research terminal / portfolio decision memo"

        # Check sections
        assert labels["sections"]["executive"] == "1. Executive Verdict"
        assert labels["sections"]["scoreboard"] == "3. Candidate Scoreboard"

        # Check verdicts
        assert labels["verdicts"]["strong_buy"] == "Strong Buy"
        assert labels["verdicts"]["avoid"] == "Avoid"

        # Check table headers
        assert len(labels["table_headers"]) == 8
        assert "Ticker" in labels["table_headers"]
        assert "Verdict" in labels["table_headers"]

    def test_chinese_labels(self):
        """Test Chinese label retrieval."""
        labels = _labels("zh")

        assert labels["title"] == "机构级投资研究报告"
        assert labels["subtitle"] == "研究终端 / 投资决策备忘录"

        # Check sections
        assert labels["sections"]["executive"] == "一、执行结论"
        assert labels["sections"]["scoreboard"] == "三、候选池评分板"

        # Check verdicts
        assert labels["verdicts"]["strong_buy"] == "优先买入"
        assert labels["verdicts"]["avoid"] == "回避"

        # Check market stance
        assert "defensive" in labels["market_stance"]
        assert "selective" in labels["market_stance"]

    def test_labels_structure_completeness(self):
        """Test that label structure is complete for both languages."""
        for lang in ["en", "zh"]:
            labels = _labels(lang)

            # Required top-level keys
            assert "title" in labels
            assert "subtitle" in labels
            assert "sections" in labels
            assert "table_headers" in labels
            assert "verdicts" in labels
            assert "risk_titles" in labels
            assert "market_stance" in labels

            # Required sections
            required_sections = ["executive", "market", "scoreboard", "cards", "risk"]
            for section in required_sections:
                assert section in labels["sections"]

            # Required verdicts
            required_verdicts = ["strong_buy", "accumulate", "hold_watch", "avoid", "veto_avoid"]
            for verdict in required_verdicts:
                assert verdict in labels["verdicts"]


class TestMacroSeverity:
    """Test macro severity detection integration."""

    def test_macro_risk_off_detection(self):
        """Test that risk-off regime is correctly detected."""
        from app.agent_runtime.reporting.scoring import _macro_is_severe

        assert _macro_is_severe({"Global_Regime": "Risk-off"})
        assert _macro_is_severe({"Global_Regime": "risk-off"})

    def test_macro_normal_condition(self):
        """Test that normal conditions don't trigger severe."""
        from app.agent_runtime.reporting.scoring import _macro_is_severe

        assert not _macro_is_severe({"Global_Regime": "Normal"})
        assert not _macro_is_severe({"Global_Regime": "Neutral"})


class TestAllocationPlanBuilding:
    """Test allocation plan building integration."""

    def test_empty_allocation_when_no_candidates(self):
        """Test empty allocation when no candidates."""
        from app.agent_runtime.reporting.scoring import _build_allocation_plan

        result = _build_allocation_plan([])
        assert result == []

    def test_single_candidate_allocation(self):
        """Test allocation with single candidate gets 100% weight."""
        from app.agent_runtime.reporting.scoring import _build_allocation_plan

        candidates = [
            {
                "ticker": "AAPL",
                "composite_score": 80,
                "verdict_key": "strong_buy",
                "verdict_label": "Strong Buy",
                "veto": False,
            }
        ]

        result = _build_allocation_plan(candidates)
        assert len(result) == 1
        assert result[0]["ticker"] == "AAPL"
        assert result[0]["weight"] == 100.0

    def test_multiple_candidate_weight_distribution(self):
        """Test weight distribution across multiple candidates."""
        from app.agent_runtime.reporting.scoring import _build_allocation_plan

        candidates = [
            {
                "ticker": "AAPL",
                "composite_score": 80,
                "verdict_key": "strong_buy",
                "verdict_label": "Strong Buy",
                "veto": False,
            },
            {
                "ticker": "MSFT",
                "composite_score": 70,
                "verdict_key": "accumulate",
                "verdict_label": "Accumulate",
                "veto": False,
            },
        ]

        result = _build_allocation_plan(candidates)
        assert len(result) == 2

        total_weight = sum(item["weight"] for item in result)
        assert total_weight == pytest.approx(100.0, rel=0.01)

        # Higher score should get higher weight
        assert result[0]["weight"] > result[1]["weight"]
