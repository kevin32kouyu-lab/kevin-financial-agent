"""LangGraph 质量门节点。"""

from __future__ import annotations

from time import perf_counter
from typing import Callable

from app.agent_graph.adapters import append_stage, append_trace, finish_trace, store_artifact
from app.agent_graph.quality import evaluate_data_quality, evaluate_evidence_quality, evaluate_report_quality
from app.agent_graph.state import FinancialGraphState, QualityGateResult, append_quality_gate
from app.agent_runtime.controlled_agents import AgentTraceEntry
from app.domain.contracts import utc_now_iso


def run_data_quality_gate_node(state: FinancialGraphState) -> FinancialGraphState:
    """执行数据质量门。"""
    return _run_quality_gate(
        state,
        evaluator=evaluate_data_quality,
        agent_name="DataQualityGate",
        stage_key="data_quality_gate",
        stage_label="数据质量门",
        dependency_artifacts=["structured_analysis", "data_packages"],
    )


def run_evidence_quality_gate_node(state: FinancialGraphState) -> FinancialGraphState:
    """执行证据质量门。"""
    return _run_quality_gate(
        state,
        evaluator=evaluate_evidence_quality,
        agent_name="EvidenceQualityGate",
        stage_key="evidence_quality_gate",
        stage_label="证据质量门",
        dependency_artifacts=["retrieved_evidence", "citation_map"],
    )


def run_report_quality_gate_node(state: FinancialGraphState) -> FinancialGraphState:
    """执行报告质量门。"""
    return _run_quality_gate(
        state,
        evaluator=evaluate_report_quality,
        agent_name="ReportQualityGate",
        stage_key="report_quality_gate",
        stage_label="报告质量门",
        dependency_artifacts=["final_report", "report_briefing"],
    )


def _run_quality_gate(
    state: FinancialGraphState,
    *,
    evaluator: Callable[[FinancialGraphState], QualityGateResult],
    agent_name: str,
    stage_key: str,
    stage_label: str,
    dependency_artifacts: list[str],
) -> FinancialGraphState:
    """运行一个质量门并追加 trace、stage 和 artifact。"""
    started_at = utc_now_iso()
    started_perf = perf_counter()
    result = evaluator(state)
    next_state = append_quality_gate(state, result)
    trace = AgentTraceEntry(
        agent_name=agent_name,
        input_summary="接收上游产物并执行确定性质量检查。",
        output_summary=result.summary,
        confidence={"pass": 0.86, "warning": 0.68, "block": 0.42}.get(result.status, 0.6),
        warnings=list(result.warnings),
        artifact_keys=["quality_gates"],
        status="failed" if result.status == "block" else "completed",
        error_message=result.blocking_reason if result.status == "block" else None,
        decision=f"质量门结果：{result.status}",
    )
    finish_trace(
        trace,
        started_at=started_at,
        started_perf=started_perf,
        status="failed" if result.status == "block" else "completed",
        error_message=result.blocking_reason if result.status == "block" else None,
    )
    next_state = store_artifact(next_state, "derived", "quality_gates", next_state.get("quality_gates") or [])
    next_state = append_trace(next_state, trace, dependency_artifacts=dependency_artifacts)
    return append_stage(
        next_state,
        key=stage_key,
        label=stage_label,
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="failed" if result.status == "block" else result.status,
        summary=result.summary,
    )
