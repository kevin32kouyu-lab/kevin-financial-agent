"""测试 LangGraph 金融研究图的状态模型和状态合并工具。"""

from __future__ import annotations

from app.agent_graph.state import (
    QualityGateResult,
    add_warning,
    block_graph,
    build_initial_state,
)
from app.agent_runtime.models import AgentRunRequest


def test_build_initial_state_sets_runtime_defaults():
    """初始图状态应包含前端兼容字段和空的质量门容器。"""
    payload = AgentRunRequest(query="Find low risk quality tech stocks for 10000 USD")

    state = build_initial_state(
        payload=payload,
        run_id="run-1",
        runtime={"provider": "fake"},
    )

    assert state["run_id"] == "run-1"
    assert state["query"] == ""
    assert state["status"] == "running"
    assert state["payload"]["query"] == payload.query
    assert state["runtime"] == {"provider": "fake"}
    assert state["stages"] == []
    assert state["agent_trace"] == []
    assert state["quality_gates"] == []
    assert state["warnings"] == []
    assert state["artifacts"] == {}


def test_quality_gate_result_is_serializable():
    """质量门结果应能直接写入 artifact 和 LangGraph checkpoint。"""
    result = QualityGateResult(
        name="data_quality_gate",
        status="warning",
        summary="新闻数据降级。",
        warnings=["新闻缺失"],
        blocking_reason=None,
    )

    assert result.to_dict() == {
        "name": "data_quality_gate",
        "status": "warning",
        "summary": "新闻数据降级。",
        "warnings": ["新闻缺失"],
        "blocking_reason": None,
    }


def test_add_warning_and_block_graph_update_state_without_losing_existing_values():
    """追加 warning 或阻断时，不应清空已有状态。"""
    state = build_initial_state(
        payload=AgentRunRequest(query="Find low risk quality tech stocks for 10000 USD"),
        run_id="run-1",
        runtime={},
    )

    warned = add_warning(state, source="news", message="新闻数据缺失")
    blocked = block_graph(
        warned,
        source="data_quality_gate",
        reason="没有候选股票，停止生成报告。",
    )

    assert blocked["status"] == "failed"
    assert blocked["blocking_reason"] == "没有候选股票，停止生成报告。"
    assert blocked["warnings"] == [{"source": "news", "message": "新闻数据缺失"}]
    assert blocked["quality_gates"][-1]["status"] == "block"
    assert blocked["quality_gates"][-1]["blocking_reason"] == "没有候选股票，停止生成报告。"
