"""LangGraph intake 节点，负责理解问题、合并记忆和追问判断。"""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.agent_graph.adapters import append_stage, append_trace, finish_trace, store_artifact
from app.agent_graph.state import FinancialGraphState, clone_state
from app.agent_runtime.controlled_agents import IntakeAgent
from app.agent_runtime.models import AgentRunRequest
from app.domain.contracts import utc_now_iso


def run_intake_node(state: FinancialGraphState) -> FinancialGraphState:
    """执行意图解析节点。"""
    next_state = clone_state(state)
    payload = AgentRunRequest.model_validate(next_state["payload"])
    started_at = utc_now_iso()
    started_perf = perf_counter()
    intake = IntakeAgent().run(payload)
    intake.trace.agent_name = "IntakeNode"
    finish_trace(intake.trace, started_at=started_at, started_perf=started_perf)

    next_state["query"] = intake.normalized_query
    next_state["memory_applied_fields"] = list(intake.memory_applied_fields)
    next_state["parsed_intent"] = intake.parsed_intent.model_dump()
    next_state["memory_resolution"] = {
        "reused_memory": bool(intake.memory_summary.get("used")),
        "applied_fields": list(intake.memory_applied_fields),
        "applied_labels": list(intake.memory_summary.get("applied_labels") or []),
        "note": intake.memory_summary.get("note"),
        "skipped_reason": intake.memory_summary.get("skipped_reason"),
    }
    next_state["memory_usage_summary"] = {
        "source": "account_or_browser_profile" if intake.memory_summary.get("used") else "current_input_only",
        "applied_fields": list(intake.memory_applied_fields),
        "applied_labels": list(intake.memory_summary.get("applied_labels") or []),
        "note": intake.memory_summary.get("note"),
        "unused_missing_fields": []
        if intake.memory_summary.get("used")
        else list(intake.parsed_intent.agent_control.missing_critical_info),
        "skipped_reason": intake.memory_summary.get("skipped_reason"),
    }
    next_state = store_artifact(next_state, "derived", "parsed_intent", next_state["parsed_intent"])
    next_state = store_artifact(next_state, "derived", "memory_resolution", next_state["memory_resolution"])
    next_state = store_artifact(next_state, "derived", "memory_usage_summary", next_state["memory_usage_summary"])

    if payload.memory_context is not None:
        next_state["memory_context"] = payload.memory_context.model_dump()
        next_state = store_artifact(next_state, "derived", "memory_context", next_state["memory_context"])
    if intake.memory_summary.get("used"):
        next_state["memory_summary"] = _jsonable(intake.memory_summary)
        next_state = store_artifact(next_state, "derived", "memory_summary", next_state["memory_summary"])
        next_state = store_artifact(next_state, "derived", "memory_applied_fields", next_state["memory_applied_fields"])

    next_state = append_trace(next_state, intake.trace, dependency_artifacts=[])
    next_state = append_stage(
        next_state,
        key="intent_analysis",
        label="意图解析",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="completed",
        summary=intake.trace.output_summary,
    )

    if intake.follow_up_question:
        next_state["follow_up_question"] = intake.follow_up_question
        next_state["preference_snapshot"] = intake.preference_snapshot or {}
        next_state["status"] = "needs_clarification"
        next_state = store_artifact(next_state, "derived", "follow_up_question", intake.follow_up_question)
        next_state = store_artifact(next_state, "derived", "preference_snapshot", next_state["preference_snapshot"])
        next_state = append_stage(
            next_state,
            key="follow_up",
            label="补充追问",
            elapsed_ms=0.0,
            status="completed",
            summary="核心约束信息不足，等待用户补充后再继续。",
        )
    return next_state


def _jsonable(value: Any) -> Any:
    """把 Pydantic 或普通对象转成可序列化结构。"""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value
