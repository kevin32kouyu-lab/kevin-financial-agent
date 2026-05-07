"""定义 LangGraph 金融研究图共享状态和状态更新工具。"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from app.agent_runtime.models import AgentRunRequest


QualityStatus = Literal["pass", "warning", "block"]


@dataclass(slots=True)
class GraphWarning:
    """记录图执行中的可披露降级提醒。"""

    source: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """转换成可写入 artifact 的字典。"""
        return {"source": self.source, "message": self.message}


@dataclass(slots=True)
class QualityGateResult:
    """记录一个质量门的判断结果。"""

    name: str
    status: QualityStatus
    summary: str
    warnings: list[str] = field(default_factory=list)
    blocking_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换成可序列化的字典。"""
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "warnings": list(self.warnings),
            "blocking_reason": self.blocking_reason,
        }


class FinancialGraphState(TypedDict, total=False):
    """LangGraph 节点之间传递的统一状态。"""

    run_id: str
    mode: str
    payload: dict[str, Any]
    query: str
    status: str
    runtime: dict[str, Any]
    research_context: dict[str, Any]
    parsed_intent: dict[str, Any]
    research_plan: dict[str, Any]
    memory_resolution: dict[str, Any]
    memory_usage_summary: dict[str, Any]
    memory_applied_fields: list[str]
    memory_context: dict[str, Any]
    memory_summary: dict[str, Any]
    follow_up_question: str
    preference_snapshot: dict[str, Any]
    analysis: dict[str, Any]
    data_packages: dict[str, Any]
    report_package: dict[str, Any]
    report_input: dict[str, Any]
    report_briefing: dict[str, Any]
    merged_data_package: dict[str, Any]
    evidence: dict[str, Any]
    debate_rounds: list[dict[str, Any]]
    report_bundle: dict[str, Any]
    final_report: str
    report_mode: str | None
    report_error: str | None
    report_outputs: dict[str, Any]
    llm_raw: dict[str, Any]
    quality_gates: list[dict[str, Any]]
    warnings: list[dict[str, str]]
    blocking_reason: str | None
    stages: list[dict[str, Any]]
    agent_trace: list[dict[str, Any]]
    agent_checkpoints: list[dict[str, Any]]
    tool_invocations: list[dict[str, Any]]
    artifacts: dict[str, dict[str, Any]]
    final_response: dict[str, Any]


def build_initial_state(
    *,
    payload: AgentRunRequest,
    run_id: str,
    runtime: dict[str, Any],
) -> FinancialGraphState:
    """创建一次 LangGraph 研究运行的初始状态。"""
    return {
        "run_id": run_id,
        "mode": "natural_language",
        "payload": payload.model_dump(),
        "query": "",
        "status": "running",
        "runtime": copy.deepcopy(runtime),
        "research_context": payload.research_context.model_dump(),
        "stages": [],
        "agent_trace": [],
        "tool_invocations": [],
        "debate_rounds": [],
        "agent_checkpoints": [],
        "quality_gates": [],
        "warnings": [],
        "artifacts": {},
        "llm_raw": {},
        "data_packages": {},
        "blocking_reason": None,
    }


def clone_state(state: FinancialGraphState) -> FinancialGraphState:
    """复制状态，避免节点间共享可变对象。"""
    return copy.deepcopy(state)


def add_warning(state: FinancialGraphState, *, source: str, message: str) -> FinancialGraphState:
    """追加一条可披露 warning。"""
    next_state = clone_state(state)
    warnings = list(next_state.get("warnings") or [])
    warning = GraphWarning(source=source, message=message).to_dict()
    if warning not in warnings:
        warnings.append(warning)
    next_state["warnings"] = warnings
    return next_state


def append_quality_gate(state: FinancialGraphState, result: QualityGateResult) -> FinancialGraphState:
    """追加一个质量门结果并同步 warning。"""
    next_state = clone_state(state)
    gates = list(next_state.get("quality_gates") or [])
    gates.append(result.to_dict())
    next_state["quality_gates"] = gates
    for warning in result.warnings:
        next_state = add_warning(next_state, source=result.name, message=warning)
    if result.status == "block":
        next_state["status"] = "failed"
        next_state["blocking_reason"] = result.blocking_reason or result.summary
    return next_state


def block_graph(state: FinancialGraphState, *, source: str, reason: str) -> FinancialGraphState:
    """把图状态标记为阻断，不再进入后续报告节点。"""
    result = QualityGateResult(
        name=source,
        status="block",
        summary=reason,
        blocking_reason=reason,
    )
    return append_quality_gate(state, result)
