"""构建 LangGraph 金融研究执行图。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.agent_graph.nodes.data import (
    run_fundamentals_node,
    run_market_data_node,
    run_merge_data_node,
    run_news_node,
    run_sec_macro_node,
)
from app.agent_graph.nodes.debate import (
    run_arbiter_node,
    run_bear_case_node,
    run_bull_case_node,
    run_risk_case_node,
)
from app.agent_graph.nodes.evidence import run_evidence_node
from app.agent_graph.nodes.finalize import run_finalize_node
from app.agent_graph.nodes.intake import run_intake_node
from app.agent_graph.nodes.planner import run_planner_node
from app.agent_graph.nodes.quality import (
    run_data_quality_gate_node,
    run_evidence_quality_gate_node,
    run_report_quality_gate_node,
)
from app.agent_graph.nodes.report import run_report_node, run_report_validation_node
from app.agent_graph.state import FinancialGraphState


class FinancialResearchGraph:
    """封装 LangGraph 金融研究图的构建和编译。"""

    def __init__(self, analysis_service: Any, report_service: Any):
        """绑定现有业务服务，避免重写数据、RAG 和报告能力。"""
        self.analysis_service = analysis_service
        self.report_service = report_service

    def compile(self, *, checkpointer: Any | None = None) -> Any:
        """编译可执行 LangGraph 图。"""
        builder = StateGraph(FinancialGraphState)
        builder.add_node("intake", run_intake_node)
        builder.add_node("planner", run_planner_node)
        builder.add_node("market_data", self._market_data)
        builder.add_node("fundamentals", run_fundamentals_node)
        builder.add_node("news", run_news_node)
        builder.add_node("sec_macro", run_sec_macro_node)
        builder.add_node("merge_data", run_merge_data_node)
        builder.add_node("data_quality_gate", run_data_quality_gate_node)
        builder.add_node("evidence", self._evidence)
        builder.add_node("evidence_quality_gate", run_evidence_quality_gate_node)
        builder.add_node("bull_case", run_bull_case_node)
        builder.add_node("bear_case", run_bear_case_node)
        builder.add_node("risk_case", run_risk_case_node)
        builder.add_node("arbiter", run_arbiter_node)
        builder.add_node("report", self._report)
        builder.add_node("report_validation", self._report_validation)
        builder.add_node("report_quality_gate", run_report_quality_gate_node)
        builder.add_node("finalize", run_finalize_node)

        builder.add_edge(START, "intake")
        builder.add_conditional_edges(
            "intake",
            _route_after_intake,
            {"continue": "planner", "finalize": "finalize"},
        )
        builder.add_edge("planner", "market_data")
        builder.add_edge("market_data", "fundamentals")
        builder.add_edge("fundamentals", "news")
        builder.add_edge("news", "sec_macro")
        builder.add_edge("sec_macro", "merge_data")
        builder.add_edge("merge_data", "data_quality_gate")
        builder.add_conditional_edges(
            "data_quality_gate",
            _route_after_quality_gate,
            {"continue": "evidence", "finalize": "finalize"},
        )
        builder.add_edge("evidence", "evidence_quality_gate")
        builder.add_conditional_edges(
            "evidence_quality_gate",
            _route_after_quality_gate,
            {"continue": "bull_case", "finalize": "finalize"},
        )
        builder.add_edge("bull_case", "bear_case")
        builder.add_edge("bear_case", "risk_case")
        builder.add_edge("risk_case", "arbiter")
        builder.add_edge("arbiter", "report")
        builder.add_edge("report", "report_validation")
        builder.add_edge("report_validation", "report_quality_gate")
        builder.add_edge("report_quality_gate", "finalize")
        builder.add_edge("finalize", END)
        return builder.compile(checkpointer=checkpointer)

    async def _market_data(self, state: FinancialGraphState) -> FinancialGraphState:
        """执行行情数据节点。"""
        return await run_market_data_node(state, self.analysis_service)

    def _evidence(self, state: FinancialGraphState) -> FinancialGraphState:
        """执行证据节点。"""
        return run_evidence_node(state, self.report_service)

    async def _report(self, state: FinancialGraphState) -> FinancialGraphState:
        """执行报告节点。"""
        return await run_report_node(state, self.report_service)

    def _report_validation(self, state: FinancialGraphState) -> FinancialGraphState:
        """执行报告一致性校验节点。"""
        return run_report_validation_node(state, self.report_service)


def open_sqlite_checkpointer(path: Path) -> Any:
    """打开异步 LangGraph SQLite checkpoint 上下文。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    return AsyncSqliteSaver.from_conn_string(str(path))


def _route_after_intake(state: FinancialGraphState) -> str:
    """根据 intake 结果决定是否继续。"""
    return "finalize" if state.get("status") == "needs_clarification" else "continue"


def _route_after_quality_gate(state: FinancialGraphState) -> str:
    """质量门阻断时直接收束。"""
    return "finalize" if state.get("status") == "failed" else "continue"
