from __future__ import annotations

from time import perf_counter
from typing import Any

from app.analysis_runtime.screener import run_screener_analysis
from app.domain.contracts import DebugAnalysisRequest
from app.services.market_data_service import MarketDataService
from app.services.toolkit import MarketToolKit


def _safe_max_results(value: Any, default: int = 5) -> int:
    """统一限制候选上限，避免下游出现超量标的。"""
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(numeric, 5))


def _build_stage(key: str, label: str, elapsed_ms: float, summary: str) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "status": "completed",
        "elapsed_ms": round(elapsed_ms, 2),
        "summary": summary,
    }


def _build_yfinance_route_diagnostics(live_package: dict[str, Any]) -> dict[str, Any]:
    """汇总 yfinance 路由轨迹，便于在产物里排查代理链路。"""
    diagnostics: dict[str, Any] = {}
    for section in ("price_data", "technical_data", "smart_money_data"):
        rows = live_package.get(section) or []
        with_route = [row for row in rows if isinstance(row, dict) and (row.get("Route_Attempts") or row.get("Route_Final"))]
        if not with_route:
            continue
        route_final_counts: dict[str, int] = {}
        failure_counts: dict[str, int] = {}
        proxy_source_counts: dict[str, int] = {}
        for row in with_route:
            route_final = str(row.get("Route_Final") or "unknown")
            route_final_counts[route_final] = route_final_counts.get(route_final, 0) + 1
            reason_code = str(row.get("Failure_Reason_Code") or "").strip()
            if reason_code:
                failure_counts[reason_code] = failure_counts.get(reason_code, 0) + 1
            proxy_source = str(row.get("Proxy_Source") or "").strip()
            if proxy_source:
                proxy_source_counts[proxy_source] = proxy_source_counts.get(proxy_source, 0) + 1
        diagnostics[section] = {
            "tracked_rows": len(with_route),
            "route_final_counts": route_final_counts,
            "failure_reason_counts": failure_counts,
            "proxy_source_counts": proxy_source_counts,
        }
    return diagnostics


def _sanitize_historical_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """历史模式下避免引用无法严格回放时间点的基本面数值。"""
    sanitized: list[dict[str, Any]] = []
    for item in rows:
        row = dict(item)
        row["PE_Ratio"] = "Historical unavailable"
        row["ROE"] = "Historical unavailable"
        row["Dividend_Yield"] = "Historical unavailable"
        row["Analyst_Rating"] = "Historical unavailable"
        row["Market_Cap"] = None
        row["Profit_Margin"] = None
        row["Debt_to_Equity"] = None
        row["Current_Ratio"] = None
        row["Free_Cash_Flow"] = None
        row["Revenue_Growth_QoQ"] = None
        row["Total_Quant_Score"] = 0.0
        sanitized.append(row)
    return sanitized


class AnalysisService:
    def __init__(self, toolkit: MarketToolKit, market_data_service: MarketDataService):
        self.toolkit = toolkit
        self.market_data_service = market_data_service

    def run_screener_only(self, payload: DebugAnalysisRequest) -> dict[str, object]:
        universe = self.market_data_service.load_security_universe()
        result = run_screener_analysis(payload, universe)
        if payload.research_mode == "historical":
            result["comparison_matrix"] = _sanitize_historical_matrix(result.get("comparison_matrix", []))
            result["analysis_context"] = "历史模式已启用：筛选仅用于候选覆盖，基本面分值不参与历史结论。"
        return result

    async def run_structured_analysis(self, payload: DebugAnalysisRequest) -> dict[str, object]:
        stages: list[dict[str, object]] = []

        screener_started = perf_counter()
        screener_result = self.run_screener_only(payload)
        stages.append(
            _build_stage(
                "screener",
                "股票池筛选",
                (perf_counter() - screener_started) * 1000,
                str(screener_result["analysis_context"]),
            )
        )

        comparison_matrix = screener_result["comparison_matrix"]
        max_results = _safe_max_results(payload.options.max_results)
        comparison_matrix = (comparison_matrix or [])[:max_results]
        tickers = [item["Ticker"] for item in comparison_matrix if item.get("Ticker")][:max_results]

        live_data_started = perf_counter()
        live_package = await self.toolkit.collect_package(
            tickers=tickers,
            fetch_live_data=payload.options.fetch_live_data,
            as_of_date=payload.as_of_date.isoformat() if payload.as_of_date else None,
        )
        if payload.options.fetch_live_data and payload.research_mode != "historical":
            self.market_data_service.persist_live_package(live_package)

        if payload.research_mode == "historical" and payload.as_of_date:
            live_data_summary = (
                f"已按 {payload.as_of_date.isoformat()} 历史时点聚合价格/技术/宏观；"
                "新闻、审计和 smart money 无可靠历史源时已显式降级。"
            )
        elif payload.options.fetch_live_data:
            live_data_summary = "已完成价格、技术、新闻、审计、宏观与公开仓位代理信号的多源聚合。"
        else:
            live_data_summary = "当前运行关闭实时抓取，已使用缓存或占位数据完成聚合。"

        stages.append(
            _build_stage(
                "live_data",
                "多源数据聚合",
                (perf_counter() - live_data_started) * 1000,
                live_data_summary,
            )
        )

        assemble_started = perf_counter()
        ticker_snapshots = self.toolkit.build_ticker_snapshots(comparison_matrix, live_package)
        ticker_snapshots = ticker_snapshots[:max_results]
        stages.append(
            _build_stage(
                "assemble",
                "研究包组装",
                (perf_counter() - assemble_started) * 1000,
                f"已构建 {len(ticker_snapshots)} 条股票研究快照。",
            )
        )

        market_status = self.market_data_service.get_status()
        yfinance_route_diagnostics = _build_yfinance_route_diagnostics(live_package)
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
            "market_data_status": market_status,
            "yfinance_route_diagnostics": yfinance_route_diagnostics,
            "debug_summary": {
                "selected_ticker_count": len(ticker_snapshots),
                "selected_tickers": tickers,
                "requested_max_results": max_results,
                "allocation_mode": payload.options.allocation_mode,
                "custom_weights": payload.options.custom_weights,
                "live_data_enabled": payload.options.fetch_live_data,
                "stage_count": len(stages),
                "universe_records": market_status["records"],
                "universe_source": market_status["source"],
                "research_mode": payload.research_mode,
                "as_of_date": payload.as_of_date.isoformat() if payload.as_of_date else None,
                "warning_flags": live_package.get("warning_flags", []),
                "yfinance_route_diagnostics": yfinance_route_diagnostics,
            },
            "debug_stages": stages,
        }
