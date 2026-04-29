"""三报告输出测试：验证简单版、专业版和开发者报告来自同一次结构化结果。"""
from __future__ import annotations

from app.services.report_outputs import build_dual_report_outputs


def test_dual_report_outputs_keep_final_report_compatible() -> None:
    """简单版报告应成为兼容旧前端的 final_report 来源。"""
    bundle = _sample_bundle()
    outputs = build_dual_report_outputs(
        bundle=bundle,
        query="Find conservative long-term compounders.",
        language_code="en",
        agent_trace=_sample_agent_trace(),
        research_plan=_sample_research_plan(),
    )

    assert set(outputs) == {"simple_investment", "professional_investment", "investment", "development"}
    assert outputs["investment"] == outputs["simple_investment"]
    assert outputs["simple_investment"]["markdown"].startswith("# Simple Investment Report")
    assert "## One-line Verdict" in outputs["simple_investment"]["markdown"]
    assert "## Recommended Portfolio" in outputs["simple_investment"]["markdown"]
    assert "## Why These Holdings" in outputs["simple_investment"]["markdown"]
    assert "## Source Memo Reference" not in outputs["simple_investment"]["markdown"]
    assert "Agent Workflow" not in outputs["simple_investment"]["markdown"]
    assert outputs["professional_investment"]["markdown"].startswith("# Professional Investment Report")
    assert "## Executive Summary" in outputs["professional_investment"]["markdown"]
    assert "## Core Holdings Deep Dive" in outputs["professional_investment"]["markdown"]
    assert "## Satellite / Watchlist Brief Review" in outputs["professional_investment"]["markdown"]
    assert "## Valuation View" in outputs["professional_investment"]["markdown"]
    assert "## Quality & Growth Analysis" in outputs["professional_investment"]["markdown"]
    assert "## Scenario Analysis" in outputs["professional_investment"]["markdown"]
    assert "## Methodology and Data Notes" in outputs["professional_investment"]["markdown"]
    assert "MSFT" in outputs["professional_investment"]["markdown"]
    assert "Agent Workflow" in outputs["development"]["markdown"]
    assert "EvidenceAgent" in outputs["development"]["markdown"]
    assert outputs["development"]["diagnostics"]["agent_count"] == 2
    assert outputs["development"]["diagnostics"]["evidence_count"] == 1
    assert outputs["development"]["diagnostics"]["validation_check_count"] == 1
    assert outputs["development"]["diagnostics"]["rag_evidence_count"] == 1
    assert outputs["development"]["diagnostics"]["validation_warning_count"] == 1


def test_core_holdings_count_follows_risk_profile_and_single_stock_request() -> None:
    """核心持仓数量应根据风险画像和单票请求调整。"""
    low_risk = _sample_bundle()
    low_risk["report_briefing"]["meta"]["user_profile"]["risk_tolerance"] = "low"
    low_risk["report_briefing"]["meta"]["user_profile"]["investment_style"] = "dividend"
    low_outputs = build_dual_report_outputs(bundle=low_risk, query="Build a low risk dividend basket.", language_code="en")

    high_risk = _sample_bundle()
    high_risk["report_briefing"]["meta"]["user_profile"]["risk_tolerance"] = "high"
    high_risk["report_briefing"]["meta"]["user_profile"]["investment_style"] = "growth"
    high_outputs = build_dual_report_outputs(bundle=high_risk, query="Find aggressive growth stocks.", language_code="en")

    single = _sample_bundle()
    single["report_briefing"]["meta"]["user_profile"]["explicit_tickers"] = ["AAPL"]
    single_outputs = build_dual_report_outputs(bundle=single, query="Should I buy AAPL?", language_code="en")

    assert len(low_outputs["simple_investment"]["core_holdings"]) >= 3
    assert 1 <= len(high_outputs["simple_investment"]["core_holdings"]) <= 3
    assert [item["ticker"] for item in single_outputs["simple_investment"]["core_holdings"]] == ["AAPL"]


def test_investment_chart_payloads_have_four_named_sections() -> None:
    """投资报告第一版应提供四类图表数据，并在缺回测时写明缺口。"""
    outputs = build_dual_report_outputs(bundle=_sample_bundle(), query="Find quality stocks.", language_code="en")
    charts = outputs["simple_investment"]["charts"]

    assert set(charts) == {
        "portfolio_allocation",
        "candidate_score_comparison",
        "portfolio_vs_benchmark_backtest",
        "risk_contribution",
    }
    assert charts["portfolio_allocation"]["items"]
    assert charts["candidate_score_comparison"]["items"]
    assert charts["risk_contribution"]["items"]
    assert charts["risk_contribution"]["items"][0]["value"] > 0
    assert charts["portfolio_vs_benchmark_backtest"]["status"] == "missing"


def test_backtest_chart_payload_preserves_points_and_summary() -> None:
    """有回测时，投资报告图表要保留 points 与 summary 结构。"""
    outputs = build_dual_report_outputs(
        bundle=_sample_bundle(),
        query="Find quality stocks.",
        language_code="en",
        backtest=_sample_backtest(),
    )
    backtest_chart = outputs["simple_investment"]["charts"]["portfolio_vs_benchmark_backtest"]

    assert backtest_chart["status"] == "available"
    assert backtest_chart["summary"]["entry_date"] == "2026-01-16"
    assert len(backtest_chart["points"]) == 2
    assert backtest_chart["points"][0]["portfolio_value"] == 100.0


def test_simple_report_output_includes_two_page_display_model() -> None:
    """简单版报告应提供网页和 PDF 共用的两页展示母版。"""
    outputs = build_dual_report_outputs(
        bundle=_sample_bundle(),
        query="Find conservative long-term compounders.",
        language_code="en",
        backtest=_sample_backtest(),
    )
    model = outputs["simple_investment"]["display_model"]

    assert model["version"] == "simple_report_showcase_v1"
    assert model["layout"] == "two_page_showcase"
    assert [page["id"] for page in model["pages"]] == ["decision", "credibility"]
    assert model["query"] == "Find conservative long-term compounders."
    assert model["decision"]["headline"] == "AAPL is the primary recommendation."
    assert model["decision"]["action"] == "Build gradually and keep MSFT as a satellite."
    assert model["decision"]["top_pick"] == "AAPL"
    assert {metric["key"] for metric in model["key_metrics"]} >= {
        "mandate_fit",
        "evidence_count",
        "portfolio_return",
        "excess_return",
    }
    assert [chart["key"] for chart in model["chart_slots"]] == [
        "portfolio_allocation",
        "candidate_score_comparison",
        "portfolio_vs_benchmark_backtest",
    ]
    assert model["holdings"][0]["ticker"] == "AAPL"
    assert model["reasons"][0]["ticker"] == "AAPL"
    assert model["risks"][0]["category"] == "Valuation"
    assert model["evidence"][0]["title"] == "Apple filing"
    assert model["validation"]["headline"] == "Checks passed."


def _sample_bundle() -> dict:
    """构造覆盖三报告输出的最小 bundle。"""
    return {
        "runtime": {"provider": "mock", "route_mode": "fallback-ready"},
        "report_mode": "fallback",
        "report_error": "mock LLM unavailable",
        "final_report": "Existing memo body that should be wrapped by the investment report.",
        "report_input": {
            "Retrieved_Evidence": [{"ticker": "AAPL", "source_name": "SEC EDGAR"}],
            "Citation_Map": {"Executive Summary": ["C1"]},
        },
        "report_briefing": {
            "meta": {
                "title": "Institutional Investment Research Report",
                "mandate_summary": "Capital 50000 USD | Risk profile low | Horizon long-term | Style dividend",
                "confidence_level": "medium",
                "user_profile": {
                    "risk_tolerance": "low",
                    "investment_horizon": "long-term",
                    "investment_style": "dividend",
                    "explicit_tickers": [],
                },
                "retrieved_evidence": [
                    {
                        "citation_key": "C1",
                        "ticker": "AAPL",
                        "source_name": "SEC EDGAR",
                        "published_at": "2026-04-01",
                        "title": "Apple filing",
                        "summary": "Cash flow stayed resilient.",
                    }
                ],
                "citation_map": {"Executive Summary": ["C1"]},
                "validation_checks": [{"id": "top_pick", "status": "pass", "message": "Top pick is supported."}],
                "validation_summary": {"headline": "Checks passed.", "items": ["Top pick appears in the scoreboard."]},
            },
            "executive": {
                "top_pick": "AAPL",
                "top_pick_verdict": "Accumulate",
                "display_call": "AAPL is the primary recommendation.",
                "display_action_summary": "Build gradually and keep MSFT as a satellite.",
                "mandate_fit_score": 86,
                "allocation_plan": [
                    {"ticker": "AAPL", "weight": 45, "verdict": "Core"},
                    {"ticker": "MSFT", "weight": 30, "verdict": "Core"},
                    {"ticker": "JNJ", "weight": 25, "verdict": "Core"},
                ],
            },
            "macro": {"risk_headline": "Rates remain the main risk.", "regime": "neutral", "vix": 16.2},
            "scoreboard": [
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "composite_score": 88,
                    "suitability_score": 86,
                    "valuation_score": 68,
                    "quality_score": 92,
                    "risk_score": 74,
                    "verdict_label": "Accumulate",
                },
                {
                    "ticker": "MSFT",
                    "company_name": "Microsoft",
                    "composite_score": 85,
                    "suitability_score": 82,
                    "valuation_score": 61,
                    "quality_score": 91,
                    "risk_score": 72,
                    "verdict_label": "Accumulate",
                },
                {
                    "ticker": "JNJ",
                    "company_name": "Johnson & Johnson",
                    "composite_score": 78,
                    "suitability_score": 80,
                    "valuation_score": 70,
                    "quality_score": 84,
                    "risk_score": 79,
                    "verdict_label": "Hold",
                },
                {
                    "ticker": "TSLA",
                    "company_name": "Tesla",
                    "composite_score": 60,
                    "suitability_score": 48,
                    "valuation_score": 35,
                    "quality_score": 70,
                    "risk_score": 40,
                    "verdict_label": "Watch",
                },
            ],
            "ticker_cards": [
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "verdict_label": "Accumulate",
                    "thesis": "Durable cash flow and shareholder returns.",
                    "fit_reason": "Matches conservative long-term mandate.",
                    "technical_summary": "Constructive.",
                    "news_narrative": "Services growth remains supportive.",
                    "audit_summary": "No major filing warning.",
                    "smart_money_positioning": "Large-cap quality proxy.",
                    "execution": "Build gradually.",
                    "caution_points": ["Valuation is not cheap."],
                },
                {
                    "ticker": "MSFT",
                    "company_name": "Microsoft",
                    "verdict_label": "Accumulate",
                    "thesis": "Cloud and AI quality compounder.",
                    "fit_reason": "Good quality but richer valuation.",
                    "execution": "Use as satellite.",
                    "caution_points": ["Multiple compression risk."],
                },
                {
                    "ticker": "JNJ",
                    "company_name": "Johnson & Johnson",
                    "verdict_label": "Hold",
                    "thesis": "Defensive healthcare exposure.",
                    "fit_reason": "Lower volatility but slower growth.",
                    "execution": "Hold as stabilizer.",
                    "caution_points": ["Growth may lag."],
                },
            ],
            "risk_register": [
                {"category": "Valuation", "ticker": "AAPL", "summary": "Multiple compression risk."},
                {"category": "Macro", "summary": "Rates could pressure long-duration assets."},
            ],
        },
    }


def _sample_agent_trace() -> list[dict]:
    """构造开发报告使用的 agent trace。"""
    return [
        {"agent_name": "IntakeAgent", "status": "completed", "output_summary": "Parsed mandate.", "elapsed_ms": 12},
        {"agent_name": "EvidenceAgent", "status": "completed", "output_summary": "Retrieved evidence.", "evidence_count": 1},
    ]


def _sample_research_plan() -> dict:
    """构造开发报告使用的研究计划。"""
    return {
        "objective": "Find conservative quality compounders.",
        "data_requirements": ["prices", "news", "SEC filings"],
        "expected_outputs": ["investment_report", "validation_checks"],
    }


def _sample_backtest() -> dict:
    """构造带 summary 和 points 的回测结果。"""
    return {
        "summary": {
            "entry_date": "2026-01-16",
            "end_date": "2026-04-22",
            "metrics": {
                "total_return_pct": 8.4,
                "benchmark_return_pct": 5.1,
                "excess_return_pct": 3.3,
            },
        },
        "points": [
            {"date": "2026-01-16", "portfolio_value": 100.0, "benchmark_value": 100.0},
            {"date": "2026-04-22", "portfolio_value": 108.4, "benchmark_value": 105.1},
        ],
        "meta": {
            "assumptions": {
                "transaction_cost_bps": 10,
                "slippage_bps": 5,
                "dividend_mode": "cash_only",
                "rebalance": "buy_and_hold",
            }
        },
    }
