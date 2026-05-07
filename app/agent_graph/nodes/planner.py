"""LangGraph planner 节点，负责生成可审计研究计划。"""

from __future__ import annotations

from time import perf_counter

from app.agent_graph.adapters import append_stage, append_trace, finish_trace, store_artifact
from app.agent_graph.state import FinancialGraphState, clone_state
from app.agent_runtime.controlled_agents import PlannerAgent
from app.agent_runtime.models import AgentRunRequest, ParsedIntent
from app.domain.contracts import utc_now_iso


def run_planner_node(state: FinancialGraphState) -> FinancialGraphState:
    """执行研究计划节点，并标记为 LangGraph 架构。"""
    next_state = clone_state(state)
    payload = AgentRunRequest.model_validate(next_state["payload"])
    intent = ParsedIntent.model_validate(next_state["parsed_intent"])
    started_at = utc_now_iso()
    started_perf = perf_counter()
    planner = PlannerAgent().run(query=str(next_state.get("query") or payload.query), intent=intent, payload=payload)
    planner.trace.agent_name = "PlannerNode"
    finish_trace(planner.trace, started_at=started_at, started_perf=started_perf)

    plan = dict(planner.plan)
    plan["agent_architecture"] = "langgraph_limited_autonomous_multi_agent"
    plan["graph_nodes"] = [
        "intake",
        "planner",
        "market_data",
        "fundamentals",
        "news",
        "sec_macro",
        "merge_data",
        "data_quality_gate",
        "evidence",
        "evidence_quality_gate",
        "bull_case",
        "bear_case",
        "risk_case",
        "arbiter",
        "report",
        "report_quality_gate",
        "finalize",
    ]
    plan["quality_gates"] = ["data_quality_gate", "evidence_quality_gate", "report_quality_gate"]
    next_state["research_plan"] = plan
    next_state = store_artifact(next_state, "derived", "research_plan", plan)
    next_state = append_trace(next_state, planner.trace, dependency_artifacts=["parsed_intent", "memory_resolution"])
    return append_stage(
        next_state,
        key="research_plan",
        label="研究计划",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="completed",
        summary=planner.trace.output_summary,
    )
