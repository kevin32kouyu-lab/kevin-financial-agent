from __future__ import annotations

from time import perf_counter
from typing import Any

from .live_data import build_ticker_snapshots, collect_live_data
from .models import DebugAnalysisRequest
from .screener import run_screener_analysis


def _build_stage(key: str, label: str, elapsed_ms: float, summary: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": "completed",
        "elapsed_ms": round(elapsed_ms, 2),
        "summary": summary,
    }


async def run_analysis_pipeline(payload: DebugAnalysisRequest) -> dict[str, Any]:
    stages: list[dict[str, Any]] = []

    screener_started = perf_counter()
    screener_result = run_screener_analysis(payload)
    stages.append(
        _build_stage(
            "screener",
            "Screener",
            (perf_counter() - screener_started) * 1000,
            screener_result["analysis_context"],
        )
    )

    comparison_matrix = screener_result["comparison_matrix"]
    tickers = [item["Ticker"] for item in comparison_matrix if item.get("Ticker")]

    live_data_started = perf_counter()
    live_package = await collect_live_data(
        tickers=tickers,
        fetch_live_data=payload.options.fetch_live_data,
    )
    live_data_summary = (
        "已完成价格、技术、新闻、审计、宏观和聪明钱数据聚合。"
        if payload.options.fetch_live_data
        else "已使用本地或占位数据完成价格、技术、新闻、审计、宏观和聪明钱聚合。"
    )
    stages.append(
        _build_stage(
            "live_data",
            "Live Data",
            (perf_counter() - live_data_started) * 1000,
            live_data_summary,
        )
    )

    assemble_started = perf_counter()
    ticker_snapshots = build_ticker_snapshots(comparison_matrix, live_package)
    stages.append(
        _build_stage(
            "assemble",
            "Assemble",
            (perf_counter() - assemble_started) * 1000,
            f"已构建 {len(ticker_snapshots)} 条股票快照。",
        )
    )

    return {
        "request_echo": payload.model_dump(),
        "analysis_context": screener_result["analysis_context"],
        "comparison_matrix": comparison_matrix,
        "macro_data": live_package["macro_data"],
        "price_data": live_package["price_data"],
        "technical_data": live_package["technical_data"],
        "audit_data": live_package["audit_data"],
        "smart_money_data": live_package["smart_money_data"],
        "raw_news_list": live_package["raw_news_list"],
        "ticker_snapshots": ticker_snapshots,
        "debug_summary": {
            "selected_ticker_count": len(ticker_snapshots),
            "selected_tickers": tickers,
            "live_data_enabled": payload.options.fetch_live_data,
            "stage_count": len(stages),
        },
        "debug_stages": stages,
    }
