"""LangGraph 金融研究图的确定性质量门。"""

from __future__ import annotations

from typing import Any

from app.agent_graph.state import FinancialGraphState, QualityGateResult


def _as_list(value: Any) -> list[Any]:
    """安全读取列表。"""
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    """安全读取字典。"""
    return value if isinstance(value, dict) else {}


def _selected_count(analysis: dict[str, Any]) -> int:
    """读取结构化分析的候选数量。"""
    debug_summary = _as_dict(analysis.get("debug_summary"))
    raw_count = debug_summary.get("selected_ticker_count")
    if isinstance(raw_count, int):
        return raw_count
    return len(_as_list(analysis.get("comparison_matrix")) or _as_list(analysis.get("ticker_snapshots")))


def evaluate_data_quality(state: FinancialGraphState) -> QualityGateResult:
    """检查候选股票和核心行情数据是否足够继续研究。"""
    analysis = _as_dict(state.get("analysis"))
    packages = _as_dict(state.get("data_packages"))
    selected_count = _selected_count(analysis)
    market_items = _as_list(_as_dict(packages.get("market")).get("items"))
    news_package = _as_dict(packages.get("news"))
    news_items = _as_list(news_package.get("items"))
    warnings: list[str] = []

    if selected_count <= 0:
        return QualityGateResult(
            name="data_quality_gate",
            status="block",
            summary="没有候选股票，停止生成报告。",
            blocking_reason="没有候选股票，停止生成报告。",
        )

    if not market_items:
        return QualityGateResult(
            name="data_quality_gate",
            status="block",
            summary="核心行情数据缺失，停止生成报告。",
            blocking_reason="核心行情数据缺失，停止生成报告。",
        )

    if not news_items:
        warnings.append("新闻数据缺失或降级，结论会更多依赖价格、质量和风险控制。")

    if warnings:
        return QualityGateResult(
            name="data_quality_gate",
            status="warning",
            summary="核心数据可用，但存在资料降级。",
            warnings=warnings,
        )

    return QualityGateResult(
        name="data_quality_gate",
        status="pass",
        summary="核心数据质量检查通过。",
    )


def evaluate_evidence_quality(state: FinancialGraphState) -> QualityGateResult:
    """检查 RAG 证据是否足够支撑正式报告。"""
    evidence = _as_dict(state.get("evidence"))
    retrieved = _as_list(evidence.get("retrieved_evidence"))
    if not retrieved:
        return QualityGateResult(
            name="evidence_quality_gate",
            status="block",
            summary="没有可引用证据，停止生成正式投资报告。",
            blocking_reason="没有可引用证据，停止生成正式投资报告。",
        )
    if len(retrieved) < 2:
        return QualityGateResult(
            name="evidence_quality_gate",
            status="warning",
            summary="证据数量偏少，报告必须披露证据覆盖不足。",
            warnings=["证据数量偏少，报告可信度需要保守解读。"],
        )
    return QualityGateResult(
        name="evidence_quality_gate",
        status="pass",
        summary="证据质量检查通过。",
    )


def evaluate_report_quality(state: FinancialGraphState) -> QualityGateResult:
    """检查报告是否生成成功，并映射已有一致性校验结果。"""
    report_bundle = _as_dict(state.get("report_bundle"))
    final_report = str(report_bundle.get("final_report") or state.get("final_report") or "").strip()
    report_error = report_bundle.get("report_error") or state.get("report_error")
    if report_error or not final_report:
        reason = str(report_error or "正式报告为空，停止交付。")
        return QualityGateResult(
            name="report_quality_gate",
            status="block",
            summary=reason,
            blocking_reason=reason,
        )

    briefing = _as_dict(report_bundle.get("report_briefing") or state.get("report_briefing"))
    meta = _as_dict(briefing.get("meta"))
    checks = _as_list(meta.get("validation_checks"))
    warnings = []
    for item in checks:
        if not isinstance(item, dict) or item.get("status") in {None, "pass"}:
            continue
        label = str(item.get("message") or item.get("name") or "").strip()
        if label:
            warnings.append(label)
    if warnings:
        return QualityGateResult(
            name="report_quality_gate",
            status="warning",
            summary="报告已生成，但存在一致性提醒。",
            warnings=warnings,
        )
    return QualityGateResult(
        name="report_quality_gate",
        status="pass",
        summary="报告质量检查通过。",
    )
