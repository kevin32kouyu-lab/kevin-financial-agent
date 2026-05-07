"""测试 LangGraph 金融研究图的确定性质量门。"""

from __future__ import annotations

from app.agent_graph.quality import evaluate_data_quality, evaluate_evidence_quality, evaluate_report_quality


def test_data_quality_gate_blocks_empty_candidate_set():
    """没有候选股票时，数据质量门必须阻断后续报告。"""
    result = evaluate_data_quality(
        {
            "analysis": {"debug_summary": {"selected_ticker_count": 0}},
            "data_packages": {"market": {"items": []}},
        }
    )

    assert result.status == "block"
    assert "没有候选股票" in result.summary
    assert result.blocking_reason


def test_data_quality_gate_warns_when_news_is_missing_but_market_data_exists():
    """行情可用但新闻缺失时，只应降级提醒，不应阻断。"""
    result = evaluate_data_quality(
        {
            "analysis": {
                "debug_summary": {"selected_ticker_count": 1},
                "comparison_matrix": [{"Ticker": "AAPL"}],
                "market_data_status": {"source": "test"},
            },
            "data_packages": {
                "market": {"items": [{"ticker": "AAPL"}]},
                "news": {"items": [], "missing": ["news"]},
            },
        }
    )

    assert result.status == "warning"
    assert "新闻" in result.warnings[0]


def test_data_quality_gate_passes_when_core_data_is_present():
    """候选、行情和新闻都有时，数据质量门应放行。"""
    result = evaluate_data_quality(
        {
            "analysis": {
                "debug_summary": {"selected_ticker_count": 1},
                "comparison_matrix": [{"Ticker": "AAPL"}],
                "market_data_status": {"source": "test"},
            },
            "data_packages": {
                "market": {"items": [{"ticker": "AAPL"}]},
                "news": {"items": [{"ticker": "AAPL", "title": "News"}]},
            },
        }
    )

    assert result.status == "pass"
    assert result.blocking_reason is None


def test_evidence_quality_gate_blocks_when_no_evidence_exists():
    """没有任何证据时，不应继续生成强投资报告。"""
    result = evaluate_evidence_quality({"evidence": {"retrieved_evidence": []}})

    assert result.status == "block"
    assert "没有可引用证据" in result.summary


def test_evidence_quality_gate_warns_when_evidence_is_thin():
    """证据很少时可以继续，但必须提示降级。"""
    result = evaluate_evidence_quality({"evidence": {"retrieved_evidence": [{"citation_key": "E1"}]}})

    assert result.status == "warning"
    assert result.warnings


def test_evidence_quality_gate_passes_with_multiple_evidence_items():
    """证据数量达到最低要求时应放行。"""
    result = evaluate_evidence_quality(
        {
            "evidence": {
                "retrieved_evidence": [
                    {"citation_key": "E1"},
                    {"citation_key": "E2"},
                ]
            }
        }
    )

    assert result.status == "pass"


def test_report_quality_gate_does_not_emit_none_warning_text():
    """报告校验项缺少可读名称时，不应向用户展示 None 文本。"""
    result = evaluate_report_quality(
        {
            "report_bundle": {
                "final_report": "# Report",
                "report_error": None,
                "report_briefing": {
                    "meta": {
                        "validation_checks": [
                            {"status": "warning"},
                            {"status": "pass", "name": "top_pick"},
                        ]
                    }
                },
            }
        }
    )

    assert result.status == "pass"
    assert result.warnings == []
