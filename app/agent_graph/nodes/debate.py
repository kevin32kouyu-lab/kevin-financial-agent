"""LangGraph 正反论证节点。"""

from __future__ import annotations

from time import perf_counter

from app.agent_graph.adapters import append_stage, append_trace, finish_trace, store_artifact
from app.agent_graph.state import FinancialGraphState, clone_state
from app.agent_runtime.controlled_agents import (
    AgentTraceEntry,
    ArbiterAgent,
    BearAnalystAgent,
    BullAnalystAgent,
)
from app.domain.contracts import utc_now_iso


def run_bull_case_node(state: FinancialGraphState) -> FinancialGraphState:
    """执行正方观点节点。"""
    started_at = utc_now_iso()
    started_perf = perf_counter()
    next_state = clone_state(state)
    result = BullAnalystAgent().run(
        report_briefing=next_state.get("report_briefing") or {},
        evidence_payload=next_state.get("evidence") or {},
    )
    finish_trace(result.trace, started_at=started_at, started_perf=started_perf)
    next_state["bull_case"] = result.payload
    next_state = append_trace(next_state, result.trace, dependency_artifacts=["report_briefing", "retrieved_evidence"])
    return append_stage(
        next_state,
        key="bull_case",
        label="正方观点",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="completed",
        summary=result.trace.output_summary,
    )


def run_bear_case_node(state: FinancialGraphState) -> FinancialGraphState:
    """执行反方风险节点。"""
    started_at = utc_now_iso()
    started_perf = perf_counter()
    next_state = clone_state(state)
    result = BearAnalystAgent().run(
        report_briefing=next_state.get("report_briefing") or {},
        evidence_payload=next_state.get("evidence") or {},
    )
    finish_trace(result.trace, started_at=started_at, started_perf=started_perf)
    next_state["bear_case"] = result.payload
    next_state = append_trace(next_state, result.trace, dependency_artifacts=["report_briefing", "retrieved_evidence"])
    return append_stage(
        next_state,
        key="bear_case",
        label="反方风险",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="completed",
        summary=result.trace.output_summary,
    )


def run_risk_case_node(state: FinancialGraphState) -> FinancialGraphState:
    """汇总质量门和数据缺口形成独立风险观点。"""
    started_at = utc_now_iso()
    started_perf = perf_counter()
    next_state = clone_state(state)
    warnings = [
        str(item.get("message"))
        for item in next_state.get("warnings") or []
        if isinstance(item, dict) and item.get("message")
    ]
    quality_warnings = [
        str(warning)
        for gate in next_state.get("quality_gates") or []
        for warning in gate.get("warnings", [])
        if warning
    ]
    claims = list(dict.fromkeys(warnings + quality_warnings)) or ["未发现额外质量门风险。"]
    payload = {
        "round_id": "debate-1",
        "stance": "risk",
        "agent_name": "RiskCaseNode",
        "claims": claims,
        "quality_gate_count": len(next_state.get("quality_gates") or []),
    }
    next_state["risk_case"] = payload
    trace = AgentTraceEntry(
        agent_name="RiskCaseNode",
        input_summary="接收质量门结果和图级 warning。",
        output_summary=f"已汇总质量门风险 {len(claims)} 条。",
        confidence=0.72,
        warnings=claims if claims != ["未发现额外质量门风险。"] else [],
        artifact_keys=["debate_rounds", "quality_gates"],
        decision="把数据和证据降级显式送入最终裁决。",
        debate_refs=["debate-1"],
    )
    finish_trace(trace, started_at=started_at, started_perf=started_perf)
    next_state = append_trace(next_state, trace, dependency_artifacts=["quality_gates"])
    return append_stage(
        next_state,
        key="risk_case",
        label="质量风险汇总",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="completed",
        summary=trace.output_summary,
    )


def run_arbiter_node(state: FinancialGraphState) -> FinancialGraphState:
    """执行裁决节点，并把风险观点并入反方 claims。"""
    started_at = utc_now_iso()
    started_perf = perf_counter()
    next_state = clone_state(state)
    bear = dict(next_state.get("bear_case") or {})
    risk_claims = list((next_state.get("risk_case") or {}).get("claims") or [])
    bear["claims"] = list(dict.fromkeys(list(bear.get("claims") or []) + risk_claims))
    result = ArbiterAgent().run(
        bull=next_state.get("bull_case") or {},
        bear=bear,
        report_briefing=next_state.get("report_briefing") or {},
    )
    finish_trace(result.trace, started_at=started_at, started_perf=started_perf)
    next_state["debate_rounds"] = [result.payload]
    if isinstance(next_state.get("report_input"), dict):
        next_state["report_input"]["Debate_Rounds"] = next_state["debate_rounds"]
    if isinstance(next_state.get("report_package"), dict):
        next_state["report_package"]["report_input"] = next_state.get("report_input") or {}
        next_state["report_package"]["report_briefing"] = next_state.get("report_briefing") or {}
    next_state = store_artifact(next_state, "derived", "debate_rounds", next_state["debate_rounds"])
    next_state = store_artifact(next_state, "report", "input", next_state.get("report_input") or {})
    next_state = store_artifact(next_state, "report", "briefing", next_state.get("report_briefing") or {})
    next_state = append_trace(next_state, result.trace, dependency_artifacts=["debate_rounds", "quality_gates"])
    return append_stage(
        next_state,
        key="debate_round",
        label="正反论证",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="completed",
        summary=result.trace.output_summary,
    )
