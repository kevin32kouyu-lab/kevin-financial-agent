"""把 LangGraph 节点状态转换为现有前端和仓储可消费的格式。"""

from __future__ import annotations

import copy
import json
from time import perf_counter
from typing import Any

from app.agent_graph.state import FinancialGraphState, clone_state
from app.agent_runtime.controlled_agents import AgentTraceEntry
from app.domain.contracts import utc_now_iso


def finish_trace(
    trace: AgentTraceEntry,
    *,
    started_at: str,
    started_perf: float,
    status: str = "completed",
    error_message: str | None = None,
) -> AgentTraceEntry:
    """补齐 trace 的时间、状态和错误字段。"""
    trace.status = status
    trace.started_at = started_at
    trace.finished_at = utc_now_iso()
    trace.elapsed_ms = (perf_counter() - started_perf) * 1000
    trace.error_message = error_message
    return trace


def append_stage(
    state: FinancialGraphState,
    *,
    key: str,
    label: str,
    elapsed_ms: float,
    status: str,
    summary: str,
) -> FinancialGraphState:
    """追加一个现有前端进度条可读取的阶段。"""
    next_state = clone_state(state)
    stages = list(next_state.get("stages") or [])
    stages.append(
        {
            "key": key,
            "label": label,
            "status": status,
            "elapsed_ms": round(max(float(elapsed_ms or 0.0), 0.0), 2),
            "summary": summary,
        }
    )
    next_state["stages"] = stages
    return next_state


def append_trace(
    state: FinancialGraphState,
    trace: AgentTraceEntry,
    *,
    dependency_artifacts: list[str] | None = None,
) -> FinancialGraphState:
    """追加 agent trace，并同步 checkpoint。"""
    next_state = clone_state(state)
    checkpoints = list(next_state.get("agent_checkpoints") or [])
    checkpoint_id = trace.checkpoint_id or f"lg-ckpt-{len(checkpoints) + 1:02d}-{trace.agent_name}"
    trace.checkpoint_id = checkpoint_id
    trace.rerunnable = trace.agent_name not in {"IntakeNode", "PlannerNode"}
    trace.dependency_artifacts = list(dependency_artifacts or [])
    checkpoints.append(
        {
            "checkpoint_id": checkpoint_id,
            "agent_name": trace.agent_name,
            "status": trace.status,
            "created_at": trace.finished_at or utc_now_iso(),
            "artifact_keys": list(trace.artifact_keys),
            "dependency_artifacts": list(trace.dependency_artifacts),
            "rerunnable": trace.rerunnable,
            "resume_scope": [],
            "summary": trace.output_summary,
            "error_message": trace.error_message,
        }
    )
    traces = list(next_state.get("agent_trace") or [])
    traces.append(trace.to_dict())
    next_state["agent_trace"] = traces
    next_state["agent_checkpoints"] = checkpoints
    next_state = store_artifact(next_state, "derived", "agent_trace", traces)
    next_state = store_artifact(next_state, "derived", "agent_checkpoints", checkpoints)
    return next_state


def store_artifact(state: FinancialGraphState, kind: str, name: str, value: Any) -> FinancialGraphState:
    """把 artifact 暂存在图状态中，workflow 负责写入仓储。"""
    next_state = clone_state(state)
    artifacts = dict(next_state.get("artifacts") or {})
    artifacts[f"{kind}:{name}"] = {
        "kind": kind,
        "name": name,
        "content": copy.deepcopy(value),
    }
    next_state["artifacts"] = artifacts
    return next_state


def append_tool_invocation(
    state: FinancialGraphState,
    *,
    tool_name: str,
    agent_name: str,
    permission_scope: str,
    started_at: str,
    started_perf: float,
    status: str = "success",
    attempts: int = 1,
    arguments: Any = None,
    output: Any = None,
    error_message: str | None = None,
) -> FinancialGraphState:
    """追加轻量工具审计记录。"""
    next_state = clone_state(state)
    invocations = list(next_state.get("tool_invocations") or [])
    invocations.append(
        {
            "tool_name": tool_name,
            "status": status,
            "agent_name": agent_name,
            "permission_scope": permission_scope,
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "elapsed_ms": round(max((perf_counter() - started_perf) * 1000, 0.0), 2),
            "attempts": attempts,
            "arguments_preview": _preview(arguments),
            "output_preview": _preview(output),
            "error_message": error_message,
        }
    )
    next_state["tool_invocations"] = invocations
    return store_artifact(next_state, "derived", "tool_invocations", invocations)


def build_public_response(state: FinancialGraphState) -> dict[str, Any]:
    """把图状态压缩为旧前端兼容的 run response。"""
    response: dict[str, Any] = {
        "mode": state.get("mode", "natural_language"),
        "query": state.get("query", ""),
        "status": state.get("status", "running"),
        "runtime": copy.deepcopy(state.get("runtime") or {}),
        "research_context": copy.deepcopy(state.get("research_context") or {}),
        "stages": copy.deepcopy(state.get("stages") or []),
        "agent_trace": copy.deepcopy(state.get("agent_trace") or []),
        "tool_invocations": copy.deepcopy(state.get("tool_invocations") or []),
        "debate_rounds": copy.deepcopy(state.get("debate_rounds") or []),
        "agent_checkpoints": copy.deepcopy(state.get("agent_checkpoints") or []),
        "llm_raw": copy.deepcopy(state.get("llm_raw") or {}),
        "quality_gates": copy.deepcopy(state.get("quality_gates") or []),
        "warnings": copy.deepcopy(state.get("warnings") or []),
    }
    optional_keys = [
        "parsed_intent",
        "memory_resolution",
        "memory_usage_summary",
        "memory_applied_fields",
        "memory_context",
        "memory_summary",
        "follow_up_question",
        "preference_snapshot",
        "research_plan",
        "analysis",
        "data_packages",
        "report_input",
        "report_briefing",
        "merged_data_package",
        "evidence",
        "final_report",
        "report_mode",
        "report_error",
        "report_outputs",
        "blocking_reason",
    ]
    for key in optional_keys:
        if key in state:
            response[key] = copy.deepcopy(state.get(key))
    if state.get("blocking_reason"):
        response["error_message"] = state["blocking_reason"]
    return response


def _preview(value: Any, *, max_chars: int = 700) -> str:
    """生成工具输入输出预览，避免审计记录过大。"""
    if value is None:
        return ""
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    return text if len(text) <= max_chars else text[: max_chars - 3] + "..."
