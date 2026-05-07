"""LangGraph 报告节点，负责生成报告并执行一致性校验。"""

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


async def run_report_node(state: FinancialGraphState, report_service: Any) -> FinancialGraphState:
    """调用报告服务生成正式报告。"""
    next_state = clone_state(state)
    payload = AgentRunRequest.model_validate(next_state["payload"])
    intent = ParsedIntent.model_validate(next_state["parsed_intent"])
    query = str(next_state.get("query") or payload.query)
    started_at = utc_now_iso()
    started_perf = perf_counter()
    bundle = await report_service.render_report(
        query=query,
        intent=intent,
        merged_data_package=next_state["merged_data_package"],
        report_input=next_state["report_input"],
        report_briefing=next_state["report_briefing"],
        model=payload.llm.model,
        base_url=payload.llm.base_url,
    )
    next_state = append_tool_invocation(
        next_state,
        tool_name="report.render",
        agent_name="ReportNode",
        permission_scope="reporting",
        started_at=started_at,
        started_perf=started_perf,
        arguments={"query": query},
        output={"report_mode": bundle.get("report_mode"), "has_report": bool(bundle.get("final_report"))},
    )
    next_state["report_bundle"] = bundle
    next_state["report_input"] = bundle["report_input"]
    next_state["report_briefing"] = bundle["report_briefing"]
    next_state["final_report"] = bundle["final_report"]
    next_state["report_mode"] = bundle.get("report_mode")
    next_state["report_error"] = bundle.get("report_error")
    next_state["llm_raw"] = bundle.get("llm_raw") or {}
    trace = AgentTraceEntry(
        agent_name="ReportNode",
        input_summary="接收报告输入、证据、引用和裁决结果。",
        output_summary=f"已生成报告，模式为 {bundle.get('report_mode') or 'unknown'}。",
        confidence=0.84 if bundle.get("report_mode") == "llm" else 0.62,
        warnings=[str(bundle["report_error"])] if bundle.get("report_error") else [],
        artifact_keys=["final_report", "report_mode", "llm_raw"],
        decision="根据证据包和 Arbiter 裁决生成用户可读报告。",
        tool_calls=list(next_state.get("tool_invocations") or [])[-1:],
    )
    finish_trace(trace, started_at=started_at, started_perf=started_perf)
    next_state = store_artifact(next_state, "report", "input", next_state["report_input"])
    next_state = store_artifact(next_state, "report", "briefing", next_state["report_briefing"])
    next_state = store_artifact(next_state, "report", "final_report", next_state["final_report"])
    if next_state["llm_raw"].get("report_response"):
        next_state = store_artifact(next_state, "llm", "report_response", next_state["llm_raw"]["report_response"])
    next_state = append_trace(next_state, trace, dependency_artifacts=["report_input", "report_briefing", "debate_rounds"])
    return append_stage(
        next_state,
        key="final_report",
        label="最终报告",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="fallback" if next_state["report_mode"] == "fallback" else "completed",
        summary=trace.output_summary,
    )


def run_report_validation_node(state: FinancialGraphState, report_service: Any) -> FinancialGraphState:
    """执行现有报告一致性校验，并供报告质量门读取。"""
    next_state = clone_state(state)
    if not isinstance(next_state.get("report_bundle"), dict):
        return next_state
    payload = AgentRunRequest.model_validate(next_state["payload"])
    intent = ParsedIntent.model_validate(next_state["parsed_intent"])
    started_at = utc_now_iso()
    started_perf = perf_counter()
    validation_meta = report_service.validate_report_bundle(
        next_state["report_bundle"],
        language_code=intent.system_context.language,
    )
    next_state = append_tool_invocation(
        next_state,
        tool_name="report.validate",
        agent_name="ReportQualityGate",
        permission_scope="validation",
        started_at=started_at,
        started_perf=started_perf,
        arguments={"language_code": intent.system_context.language},
        output={"confidence_level": validation_meta.get("confidence_level")},
    )
    next_state["report_briefing"] = next_state["report_bundle"]["report_briefing"]
    next_state = store_artifact(next_state, "report", "briefing", next_state["report_briefing"])
    next_state = store_artifact(next_state, "derived", "validation_checks", validation_meta.get("validation_checks", []))
    return next_state
