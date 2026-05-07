"""LangGraph finalize 节点，负责生成旧前端兼容的最终响应。"""

from __future__ import annotations

from time import perf_counter

from app.agent_graph.adapters import append_stage, build_public_response, store_artifact
from app.agent_graph.state import FinancialGraphState, clone_state
from app.agent_runtime.memory import build_preference_snapshot
from app.agent_runtime.models import AgentRunRequest, ParsedIntent
from app.domain.contracts import utc_now_iso
from app.services.report_outputs import attach_dual_report_outputs


def run_finalize_node(state: FinancialGraphState) -> FinancialGraphState:
    """收束图状态，生成最终响应和报告输出。"""
    started_perf = perf_counter()
    next_state = clone_state(state)
    if next_state.get("status") == "running":
        next_state["status"] = "completed"

    if "parsed_intent" in next_state:
        payload = AgentRunRequest.model_validate(next_state["payload"])
        intent = ParsedIntent.model_validate(next_state["parsed_intent"])
        next_state["preference_snapshot"] = build_preference_snapshot(
            intent,
            query=str(next_state.get("query") or payload.query),
            research_mode=payload.research_context.research_mode,
            applied_fields=list(next_state.get("memory_applied_fields") or []),
        )
        next_state = store_artifact(next_state, "derived", "preference_snapshot", next_state["preference_snapshot"])

    if next_state.get("status") == "completed" and isinstance(next_state.get("report_bundle"), dict):
        intent = ParsedIntent.model_validate(next_state["parsed_intent"])
        report_outputs = attach_dual_report_outputs(
            bundle=next_state["report_bundle"],
            query=str(next_state.get("query") or ""),
            language_code=intent.system_context.language,
            agent_trace=list(next_state.get("agent_trace") or []),
            research_plan=next_state.get("research_plan"),
            backtest=None,
        )
        next_state["report_outputs"] = report_outputs
        next_state = store_artifact(next_state, "report", "outputs", report_outputs)
        next_state = store_artifact(next_state, "report", "final_report", next_state.get("final_report"))

    if next_state.get("status") in {"failed", "needs_clarification"}:
        next_state = append_stage(
            next_state,
            key="finalize",
            label="流程收束",
            elapsed_ms=(perf_counter() - started_perf) * 1000,
            status=next_state["status"],
            summary=str(next_state.get("blocking_reason") or next_state.get("follow_up_question") or "流程已停止。"),
        )
    else:
        next_state = append_stage(
            next_state,
            key="finalize",
            label="流程收束",
            elapsed_ms=(perf_counter() - started_perf) * 1000,
            status="completed",
            summary="LangGraph 研究流程已完成。",
        )

    next_state["final_response"] = build_public_response(next_state)
    next_state = store_artifact(next_state, "output", "final_response", next_state["final_response"])
    return next_state
