from __future__ import annotations

from time import perf_counter

from app.analysis_runtime.screener import run_screener_analysis
from app.domain.contracts import DebugAnalysisRequest
from app.services.market_data_service import MarketDataService
from app.services.toolkit import MarketToolKit


def _build_stage(key: str, label: str, elapsed_ms: float, summary: str) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "status": "completed",
        "elapsed_ms": round(elapsed_ms, 2),
        "summary": summary,
    }


class AnalysisService:
    def __init__(self, toolkit: MarketToolKit, market_data_service: MarketDataService):
        self.toolkit = toolkit
        self.market_data_service = market_data_service

    def run_screener_only(self, payload: DebugAnalysisRequest) -> dict[str, object]:
        universe = self.market_data_service.load_security_universe()
        return run_screener_analysis(payload, universe)

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
        tickers = [item["Ticker"] for item in comparison_matrix if item.get("Ticker")]

        live_data_started = perf_counter()
        live_package = await self.toolkit.collect_live_package(
            tickers=tickers,
            fetch_live_data=payload.options.fetch_live_data,
        )
        if payload.options.fetch_live_data:
            self.market_data_service.persist_live_package(live_package)

        live_data_summary = (
            "已完成价格、技术、新闻、审计、宏观与公开持仓代理信号的多源聚合。"
            if payload.options.fetch_live_data
            else "当前 run 关闭了实时抓取，已使用缓存或占位数据完成聚合。"
        )
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
        stages.append(
            _build_stage(
                "assemble",
                "研究包组装",
                (perf_counter() - assemble_started) * 1000,
                f"已构建 {len(ticker_snapshots)} 条股票研究快照。",
            )
        )

        market_status = self.market_data_service.get_status()
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
            "debug_summary": {
                "selected_ticker_count": len(ticker_snapshots),
                "selected_tickers": tickers,
                "live_data_enabled": payload.options.fetch_live_data,
                "stage_count": len(stages),
                "universe_records": market_status["records"],
                "universe_source": market_status["source"],
            },
            "debug_stages": stages,
        }
