"""LangGraph evidence 节点，负责报告包构建和 RAG 证据接入。"""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.agent_graph.adapters import (
    append_stage,
    append_tool_invocation,
    append_trace,
    finish_trace,
    store_artifact,
)
from app.agent_graph.state import FinancialGraphState, clone_state
from app.agent_runtime.controlled_agents import AgentTraceEntry
from app.agent_runtime.models import AgentRunRequest, ParsedIntent
from app.domain.contracts import utc_now_iso


def run_evidence_node(state: FinancialGraphState, report_service: Any) -> FinancialGraphState:
    """构建报告输入并附加 RAG 证据。"""
    next_state = clone_state(state)
    payload = AgentRunRequest.model_validate(next_state["payload"])
    intent = ParsedIntent.model_validate(next_state["parsed_intent"])
    query = str(next_state.get("query") or payload.query)

    package_started_at = utc_now_iso()
    package_started_perf = perf_counter()
    report_package = report_service.build_report_package(
        query=query,
        intent=intent,
        analysis=next_state["analysis"],
        research_context=payload.research_context.model_dump(),
        model=payload.llm.model,
        base_url=payload.llm.base_url,
    )
    next_state = append_tool_invocation(
        next_state,
        tool_name="report.build_package",
        agent_name="EvidenceNode",
        permission_scope="reporting",
        started_at=package_started_at,
        started_perf=package_started_perf,
        arguments={"query": query},
        output={"has_report_input": bool(report_package.get("report_input"))},
    )

    evidence_started_at = utc_now_iso()
    evidence_started_perf = perf_counter()
    evidence_payload = report_service.attach_evidence(
        query=query,
        report_briefing=report_package["report_briefing"],
        report_input=report_package["report_input"],
        research_context=payload.research_context.model_dump(),
    )
    next_state = append_tool_invocation(
        next_state,
        tool_name="rag.attach_evidence",
        agent_name="EvidenceNode",
        permission_scope="rag",
        started_at=evidence_started_at,
        started_perf=evidence_started_perf,
        arguments={"query": query},
        output={"evidence_count": len(evidence_payload.get("retrieved_evidence") or [])},
    )

    evidence_count = len(evidence_payload.get("retrieved_evidence") or [])
    next_state["report_package"] = report_package
    next_state["report_input"] = report_package["report_input"]
    next_state["report_briefing"] = report_package["report_briefing"]
    next_state["merged_data_package"] = report_package["merged_data_package"]
    next_state["evidence"] = evidence_payload
    trace = AgentTraceEntry(
        agent_name="EvidenceNode",
        input_summary="接收合并后的结构化分析结果。",
        output_summary=f"已完成证据接入，引用证据 {evidence_count} 条。",
        confidence=0.78 if evidence_count else 0.45,
        warnings=[] if evidence_count else ["没有检索到可引用证据。"],
        artifact_keys=["report_input", "report_briefing", "retrieved_evidence", "citation_map"],
        evidence_count=evidence_count,
        decision="复用现有报告包和 RAG 能力，证据质量交给后续质量门判断。",
        tool_calls=list(next_state.get("tool_invocations") or [])[-2:],
    )
    finish_trace(trace, started_at=package_started_at, started_perf=package_started_perf)
    next_state = store_artifact(next_state, "report", "input", next_state["report_input"])
    next_state = store_artifact(next_state, "report", "briefing", next_state["report_briefing"])
    next_state = store_artifact(next_state, "report", "retrieved_evidence", evidence_payload.get("retrieved_evidence", []))
    next_state = store_artifact(next_state, "report", "citation_map", evidence_payload.get("citation_map", {}))
    next_state = append_trace(next_state, trace, dependency_artifacts=["structured_analysis", "data_packages"])
    return append_stage(
        next_state,
        key="evidence_retrieval",
        label="证据检索",
        elapsed_ms=(perf_counter() - package_started_perf) * 1000,
        status="completed",
        summary=trace.output_summary,
    )
