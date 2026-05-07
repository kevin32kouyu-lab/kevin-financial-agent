"""LangGraph 数据节点，复用现有结构化分析并拆成多个数据包。"""

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
from app.agent_runtime.controlled_agents import AgentTraceEntry, build_debug_request
from app.agent_runtime.models import AgentRunRequest, ParsedIntent
from app.domain.contracts import utc_now_iso


async def run_market_data_node(state: FinancialGraphState, analysis_service: Any) -> FinancialGraphState:
    """调用现有结构化分析服务，形成基础行情研究包。"""
    next_state = clone_state(state)
    payload = AgentRunRequest.model_validate(next_state["payload"])
    intent = ParsedIntent.model_validate(next_state["parsed_intent"])
    started_at = utc_now_iso()
    started_perf = perf_counter()
    analysis = await analysis_service.run_structured_analysis(build_debug_request(intent, payload))
    selected_count = int((analysis.get("debug_summary") or {}).get("selected_ticker_count") or 0)

    next_state["analysis"] = analysis
    data_packages = dict(next_state.get("data_packages") or {})
    data_packages["market"] = {
        "items": list(analysis.get("comparison_matrix") or analysis.get("ticker_snapshots") or []),
        "status": analysis.get("market_data_status") or {},
        "source": (analysis.get("market_data_status") or {}).get("source"),
        "selected_count": selected_count,
    }
    next_state["data_packages"] = data_packages
    next_state = append_tool_invocation(
        next_state,
        tool_name="market.research_package",
        agent_name="MarketDataNode",
        permission_scope="market_data",
        started_at=started_at,
        started_perf=started_perf,
        arguments={"query": next_state.get("query"), "research_context": next_state.get("research_context")},
        output={"selected_ticker_count": selected_count},
    )
    trace = AgentTraceEntry(
        agent_name="MarketDataNode",
        input_summary="接收研究计划和结构化意图。",
        output_summary=f"已完成结构化分析，候选 {selected_count} 只。",
        confidence=0.82 if selected_count else 0.42,
        warnings=[] if selected_count else ["未筛选出候选股票。"],
        artifact_keys=["structured_analysis", "data_packages"],
        decision="复用现有结构化分析服务作为 LangGraph 数据入口。",
        tool_calls=list(next_state.get("tool_invocations") or [])[-1:],
    )
    finish_trace(trace, started_at=started_at, started_perf=started_perf)
    next_state = store_artifact(next_state, "analysis", "structured_analysis", analysis)
    next_state = store_artifact(next_state, "derived", "data_packages", data_packages)
    next_state = append_trace(next_state, trace, dependency_artifacts=["research_plan", "parsed_intent"])
    return append_stage(
        next_state,
        key="market_data",
        label="行情与候选",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="completed",
        summary=trace.output_summary,
    )


def run_fundamentals_node(state: FinancialGraphState) -> FinancialGraphState:
    """从结构化分析中拆出基本面数据包。"""
    started_at = utc_now_iso()
    started_perf = perf_counter()
    next_state = clone_state(state)
    analysis = next_state.get("analysis") or {}
    snapshots = list(analysis.get("ticker_snapshots") or [])
    data_packages = dict(next_state.get("data_packages") or {})
    data_packages["fundamentals"] = {
        "items": snapshots,
        "missing": [] if snapshots else ["fundamentals"],
    }
    next_state["data_packages"] = data_packages
    trace = AgentTraceEntry(
        agent_name="FundamentalsNode",
        input_summary="接收结构化分析结果。",
        output_summary=f"已拆出基本面快照 {len(snapshots)} 条。",
        confidence=0.78 if snapshots else 0.5,
        warnings=[] if snapshots else ["基本面快照缺失。"],
        artifact_keys=["data_packages"],
    )
    finish_trace(trace, started_at=started_at, started_perf=started_perf)
    next_state = store_artifact(next_state, "derived", "data_packages", data_packages)
    next_state = append_trace(next_state, trace, dependency_artifacts=["structured_analysis"])
    return append_stage(
        next_state,
        key="fundamentals",
        label="基本面拆分",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="completed",
        summary=trace.output_summary,
    )


def run_news_node(state: FinancialGraphState) -> FinancialGraphState:
    """从结构化分析中拆出新闻数据包。"""
    started_at = utc_now_iso()
    started_perf = perf_counter()
    next_state = clone_state(state)
    analysis = next_state.get("analysis") or {}
    news_items = list(analysis.get("raw_news_list") or [])
    if not news_items:
        for snapshot in analysis.get("ticker_snapshots") or []:
            news_items.extend(snapshot.get("news") or [])
    data_packages = dict(next_state.get("data_packages") or {})
    data_packages["news"] = {
        "items": news_items,
        "missing": [] if news_items else ["news"],
    }
    next_state["data_packages"] = data_packages
    trace = AgentTraceEntry(
        agent_name="NewsNode",
        input_summary="接收结构化分析结果。",
        output_summary=f"已拆出新闻资料 {len(news_items)} 条。",
        confidence=0.74 if news_items else 0.48,
        warnings=[] if news_items else ["新闻数据缺失或降级。"],
        artifact_keys=["data_packages"],
    )
    finish_trace(trace, started_at=started_at, started_perf=started_perf)
    next_state = store_artifact(next_state, "derived", "data_packages", data_packages)
    next_state = append_trace(next_state, trace, dependency_artifacts=["structured_analysis"])
    return append_stage(
        next_state,
        key="news",
        label="新闻资料拆分",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="completed",
        summary=trace.output_summary,
    )


def run_sec_macro_node(state: FinancialGraphState) -> FinancialGraphState:
    """从结构化分析中拆出 SEC、审计和宏观数据包。"""
    started_at = utc_now_iso()
    started_perf = perf_counter()
    next_state = clone_state(state)
    analysis = next_state.get("analysis") or {}
    macro = analysis.get("macro_data") or {}
    data_packages = dict(next_state.get("data_packages") or {})
    data_packages["sec_macro"] = {
        "items": {
            "macro_data": macro,
            "historical_archive_gaps": analysis.get("historical_archive_gaps") or [],
        },
        "missing": [] if macro else ["macro"],
    }
    next_state["data_packages"] = data_packages
    trace = AgentTraceEntry(
        agent_name="SecMacroNode",
        input_summary="接收结构化分析结果。",
        output_summary="已拆出宏观和披露相关资料。",
        confidence=0.74 if macro else 0.55,
        warnings=[] if macro else ["宏观资料缺失或降级。"],
        artifact_keys=["data_packages"],
    )
    finish_trace(trace, started_at=started_at, started_perf=started_perf)
    next_state = store_artifact(next_state, "derived", "data_packages", data_packages)
    next_state = append_trace(next_state, trace, dependency_artifacts=["structured_analysis"])
    return append_stage(
        next_state,
        key="sec_macro",
        label="披露与宏观拆分",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="completed",
        summary=trace.output_summary,
    )


def run_merge_data_node(state: FinancialGraphState) -> FinancialGraphState:
    """合并各数据包，供质量门和证据节点消费。"""
    started_at = utc_now_iso()
    started_perf = perf_counter()
    next_state = clone_state(state)
    packages = dict(next_state.get("data_packages") or {})
    trace = AgentTraceEntry(
        agent_name="DataMergeNode",
        input_summary="接收行情、基本面、新闻、披露和宏观数据包。",
        output_summary=f"已合并 {len(packages)} 类数据包。",
        confidence=0.8,
        artifact_keys=["data_packages"],
        decision="只合并数据包，不改写上游原始分析结果。",
    )
    finish_trace(trace, started_at=started_at, started_perf=started_perf)
    next_state = store_artifact(next_state, "derived", "data_packages", packages)
    next_state = append_trace(next_state, trace, dependency_artifacts=["structured_analysis", "data_packages"])
    return append_stage(
        next_state,
        key="merge_data",
        label="数据合并",
        elapsed_ms=(perf_counter() - started_perf) * 1000,
        status="completed",
        summary=trace.output_summary,
    )
