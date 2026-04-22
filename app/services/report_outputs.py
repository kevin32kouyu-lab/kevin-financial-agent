"""双报告输出构建：把同一次 run 的结构化结果整理成投资报告和开发报告。"""
from __future__ import annotations

from typing import Any


GenericRecord = dict[str, Any]


def build_dual_report_outputs(
    *,
    bundle: GenericRecord,
    query: str,
    language_code: str,
    agent_trace: list[GenericRecord] | None = None,
    research_plan: GenericRecord | None = None,
    backtest: Any = None,
) -> GenericRecord:
    """生成投资报告和开发报告，且两份报告共用同一份结构化数据。"""
    report_briefing = _record(bundle.get("report_briefing"))
    meta = _record(report_briefing.get("meta"))
    core_holdings = _select_core_holdings(report_briefing)
    satellite_holdings = _select_satellite_holdings(report_briefing, core_holdings)
    charts = _build_investment_charts(report_briefing, backtest)
    diagnostics = _build_development_diagnostics(
        bundle=bundle,
        agent_trace=agent_trace or [],
        research_plan=research_plan or {},
        backtest=backtest,
    )

    investment_markdown = _build_investment_markdown(
        query=query,
        language_code=language_code,
        bundle=bundle,
        core_holdings=core_holdings,
        satellite_holdings=satellite_holdings,
        charts=charts,
    )
    development_markdown = _build_development_markdown(
        language_code=language_code,
        bundle=bundle,
        agent_trace=agent_trace or [],
        research_plan=research_plan or {},
        diagnostics=diagnostics,
    )

    return {
        "investment": {
            "kind": "investment",
            "title": _text(meta.get("title"), _label(language_code, "投资研究报告", "Institutional Investment Research Report")),
            "markdown": investment_markdown,
            "charts": charts,
            "core_holdings": core_holdings,
            "satellite_holdings": satellite_holdings,
        },
        "development": {
            "kind": "development",
            "title": _label(language_code, "开发审计报告", "Development Report"),
            "markdown": development_markdown,
            "diagnostics": diagnostics,
        },
    }


def attach_dual_report_outputs(
    *,
    bundle: GenericRecord,
    query: str,
    language_code: str,
    agent_trace: list[GenericRecord] | None = None,
    research_plan: GenericRecord | None = None,
    backtest: Any = None,
) -> GenericRecord:
    """把双报告输出写回 bundle，并保持 final_report 兼容旧入口。"""
    outputs = build_dual_report_outputs(
        bundle=bundle,
        query=query,
        language_code=language_code,
        agent_trace=agent_trace,
        research_plan=research_plan,
        backtest=backtest,
    )
    bundle["report_outputs"] = outputs
    bundle["final_report"] = outputs["investment"]["markdown"]
    return outputs


def _build_investment_markdown(
    *,
    query: str,
    language_code: str,
    bundle: GenericRecord,
    core_holdings: list[GenericRecord],
    satellite_holdings: list[GenericRecord],
    charts: GenericRecord,
) -> str:
    """构建投资者阅读的一份正式投资报告。"""
    report_briefing = _record(bundle.get("report_briefing"))
    meta = _record(report_briefing.get("meta"))
    executive = _record(report_briefing.get("executive"))
    macro = _record(report_briefing.get("macro"))
    scoreboard = _records(report_briefing.get("scoreboard"))
    risk_register = _records(report_briefing.get("risk_register"))
    evidence = _records(meta.get("retrieved_evidence"))
    validation_summary = _record(meta.get("validation_summary"))
    source_memo = _text(bundle.get("final_report"), "")

    if language_code == "zh":
        lines = [
            f"# {_text(meta.get('title'), '机构级投资研究报告')}",
            "",
            "## Executive Summary",
            f"- 原始问题：{query or '未提供'}",
            f"- 核心结论：{_text(executive.get('display_call') or executive.get('primary_call'), '暂无结论。')}",
            f"- 建议动作：{_text(executive.get('display_action_summary') or executive.get('action_summary'), '暂无建议。')}",
            f"- 可信度：{_text(meta.get('confidence_level'), '未评级')}",
            "",
            "## Investor Mandate",
            f"- {_text(meta.get('mandate_summary'), '暂无用户目标摘要。')}",
            "",
            "## Final Recommendation",
            f"- 首选方案：{', '.join(item['ticker'] for item in core_holdings) or '暂无'}",
            f"- 观察 / 卫星标的：{', '.join(item['ticker'] for item in satellite_holdings) or '暂无'}",
            "",
            "## Candidate Comparison",
            "| Ticker | Company | Composite | Fit | Valuation | Quality | Risk | Verdict |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    else:
        lines = [
            f"# {_text(meta.get('title'), 'Institutional Investment Research Report')}",
            "",
            "## Executive Summary",
            f"- Original request: {query or 'Not provided'}",
            f"- Core conclusion: {_text(executive.get('display_call') or executive.get('primary_call'), 'No conclusion available.')}",
            f"- Recommended action: {_text(executive.get('display_action_summary') or executive.get('action_summary'), 'No action summary available.')}",
            f"- Confidence: {_text(meta.get('confidence_level'), 'not rated')}",
            "",
            "## Investor Mandate",
            f"- {_text(meta.get('mandate_summary'), 'Mandate summary unavailable.')}",
            "",
            "## Final Recommendation",
            f"- Core holdings: {', '.join(item['ticker'] for item in core_holdings) or 'N/A'}",
            f"- Satellite / watchlist: {', '.join(item['ticker'] for item in satellite_holdings) or 'N/A'}",
            "",
            "## Candidate Comparison",
            "| Ticker | Company | Composite | Fit | Valuation | Quality | Risk | Verdict |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]

    for item in scoreboard:
        lines.append(
            "| "
            + " | ".join(
                [
                    _text(item.get("ticker")),
                    _text(item.get("company_name")),
                    _text(item.get("composite_score")),
                    _text(item.get("suitability_score")),
                    _text(item.get("valuation_score")),
                    _text(item.get("quality_score")),
                    _text(item.get("risk_score")),
                    _text(item.get("verdict_label")),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Core Holdings Deep Dive"])
    for item in core_holdings:
        lines.extend(_holding_deep_dive_lines(item, language_code))

    lines.extend(["", "## Satellite / Watchlist Brief Review"])
    if satellite_holdings:
        lines.append("| Ticker | Role | Why not core | Current action | Main risk |")
        lines.append("| --- | --- | --- | --- | --- |")
        for item in satellite_holdings:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _text(item.get("ticker")),
                        _label(language_code, "卫星 / 观察", "Satellite / Watch"),
                        _text(item.get("fit_reason"), _label(language_code, "适配度低于核心持仓。", "Lower fit than the core holdings.")),
                        _text(item.get("execution"), _label(language_code, "观察。", "Watch.")),
                        "; ".join(_strings(item.get("caution_points"))) or _label(language_code, "估值或基本面风险。", "Valuation or fundamental risk."),
                    ]
                )
                + " |"
            )
    else:
        lines.append(_label(language_code, "- 暂无额外观察标的。", "- No additional watchlist candidate."))

    lines.extend(
        [
            "",
            "## Portfolio Construction & Execution Plan",
            _portfolio_plan_text(report_briefing, language_code),
            "",
            "## Risk Register",
        ]
    )
    if risk_register:
        for item in risk_register:
            prefix = _text(item.get("category"), "Risk")
            if item.get("ticker"):
                prefix = f"{prefix} / {_text(item.get('ticker'))}"
            lines.append(f"- {prefix}: {_text(item.get('summary'))}")
    else:
        lines.append(_label(language_code, "- 暂无风险登记。", "- No risk register available."))

    lines.extend(["", "## Backtest Summary", _backtest_summary_text(charts, language_code)])
    lines.extend(["", "## Evidence Appendix"])
    if evidence:
        for item in evidence[:12]:
            source = _text(item.get("source_name") or item.get("source_type"), "Source")
            date = _text(item.get("published_at") or item.get("as_of_date"), "")
            title = _text(item.get("title") or item.get("summary"), "Evidence")
            lines.append(f"- [{_text(item.get('citation_key'), 'C')}] {title} — {source}{f' · {date}' if date else ''}")
    else:
        lines.append(_label(language_code, "- 暂无可引用证据。", "- No retrieved evidence available."))

    if source_memo:
        lines.extend(["", "## Source Memo Reference", source_memo])

    lines.extend(
        [
            "",
            "## Disclaimer",
            _label(
                language_code,
                "本报告仅用于研究辅助，不构成财务、法律或税务建议。",
                "This report is for research support only and is not financial, legal, or tax advice.",
            ),
        ]
    )
    return "\n".join(lines)


def _build_development_markdown(
    *,
    language_code: str,
    bundle: GenericRecord,
    agent_trace: list[GenericRecord],
    research_plan: GenericRecord,
    diagnostics: GenericRecord,
) -> str:
    """构建面向项目评审的确定性开发报告。"""
    report_briefing = _record(bundle.get("report_briefing"))
    meta = _record(report_briefing.get("meta"))
    runtime = _record(bundle.get("runtime"))
    checks = _records(meta.get("validation_checks"))
    evidence = _records(meta.get("retrieved_evidence"))
    citation_map = _record(meta.get("citation_map"))

    if language_code == "zh":
        lines = [
            "# 开发报告",
            "",
            "## Run Overview",
            f"- 报告模式：{_text(bundle.get('report_mode'), 'unknown')}",
            f"- 模型路由：{_text(runtime.get('provider'), 'unknown')} / {_text(runtime.get('route_mode'), 'unknown')}",
            f"- 可信度：{_text(meta.get('confidence_level'), 'not rated')}",
            "",
            "## Agent Workflow",
        ]
    else:
        lines = [
            "# Development Report",
            "",
            "## Run Overview",
            f"- Report mode: {_text(bundle.get('report_mode'), 'unknown')}",
            f"- Model route: {_text(runtime.get('provider'), 'unknown')} / {_text(runtime.get('route_mode'), 'unknown')}",
            f"- Confidence: {_text(meta.get('confidence_level'), 'not rated')}",
            "",
            "## Agent Workflow",
        ]

    if agent_trace:
        for item in agent_trace:
            lines.append(
                f"- {_text(item.get('agent_name'), 'Agent')}: {_text(item.get('status'), 'unknown')} · "
                f"{_text(item.get('output_summary'), '')} "
                f"({_text(item.get('elapsed_ms'), 'n/a')} ms)"
            )
    else:
        lines.append(_label(language_code, "- 当前 run 未提供 agent trace。", "- No agent trace was attached to this run."))

    lines.extend(
        [
            "",
            "## Tool and Data Source Summary",
            f"- Objective: {_text(research_plan.get('objective'), 'N/A')}",
            f"- Data requirements: {', '.join(_strings(research_plan.get('data_requirements'))) or 'N/A'}",
            f"- Expected outputs: {', '.join(_strings(research_plan.get('expected_outputs'))) or 'N/A'}",
            "",
            "## RAG Evidence Coverage",
            f"- Retrieved evidence count: {len(evidence)}",
            f"- Citation map sections: {', '.join(citation_map.keys()) or 'N/A'}",
            "",
            "## Validation Checks",
        ]
    )
    if checks:
        for item in checks:
            lines.append(f"- {_text(item.get('id') or item.get('name'), 'check')}: {_text(item.get('status'), 'unknown')} · {_text(item.get('message'), '')}")
    else:
        lines.append(_label(language_code, "- 暂无 validation checks。", "- No validation checks available."))

    lines.extend(
        [
            "",
            "## Backtest Reproducibility",
            f"- Status: {_text(diagnostics.get('backtest_status'), 'missing')}",
            f"- Assumptions: {', '.join(_strings(diagnostics.get('backtest_assumptions'))) or 'N/A'}",
            "",
            "## Model Routing and Fallback",
            f"- Report mode: {_text(bundle.get('report_mode'), 'unknown')}",
            f"- Report error: {_text(bundle.get('report_error'), 'none')}",
            "",
            "## Artifacts and Debug References",
            f"- Agent count: {_text(diagnostics.get('agent_count'))}",
            f"- Evidence count: {_text(diagnostics.get('evidence_count'))}",
            f"- Validation check count: {_text(diagnostics.get('validation_check_count'))}",
            "",
            "## Known Limitations",
            _label(
                language_code,
                "- 开发报告来自结构化 artifact 摘要，不展示 raw JSON；完整排障信息仍在 /debug。",
                "- This development report summarizes structured artifacts without exposing raw JSON; full debugging remains in /debug.",
            ),
        ]
    )
    return "\n".join(lines)


def _select_core_holdings(report_briefing: GenericRecord) -> list[GenericRecord]:
    """按用户风险画像、单票请求和评分接近程度选择核心持仓。"""
    meta = _record(report_briefing.get("meta"))
    user_profile = _record(meta.get("user_profile"))
    ticker_cards = _records(report_briefing.get("ticker_cards"))
    scoreboard = _records(report_briefing.get("scoreboard"))
    card_by_ticker = {_text(item.get("ticker")): item for item in ticker_cards}
    explicit_tickers = _strings(user_profile.get("explicit_tickers"))

    eligible = [
        item
        for item in sorted(scoreboard, key=lambda row: _number(row.get("composite_score")), reverse=True)
        if "avoid" not in _text(item.get("verdict_label")).lower()
    ] or scoreboard

    if len(explicit_tickers) == 1:
        ticker = explicit_tickers[0]
        selected = card_by_ticker.get(ticker) or next((item for item in eligible if _text(item.get("ticker")) == ticker), None)
        return [_merge_card(selected, card_by_ticker)] if selected else []

    target_min, target_max = _core_count_bounds(user_profile)
    if not eligible:
        return []
    top_score = _number(eligible[0].get("composite_score"))
    close_count = sum(1 for item in eligible if top_score - _number(item.get("composite_score")) <= 3)
    count = min(len(eligible), target_max, max(target_min, close_count))
    return [_merge_card(item, card_by_ticker) for item in eligible[:count]]


def _select_satellite_holdings(report_briefing: GenericRecord, core_holdings: list[GenericRecord]) -> list[GenericRecord]:
    """选择非核心候选作为卫星或观察名单。"""
    core_tickers = {_text(item.get("ticker")) for item in core_holdings}
    ticker_cards = _records(report_briefing.get("ticker_cards"))
    scoreboard = _records(report_briefing.get("scoreboard"))
    card_by_ticker = {_text(item.get("ticker")): item for item in ticker_cards}
    satellites = []
    for item in scoreboard:
        ticker = _text(item.get("ticker"))
        if ticker and ticker not in core_tickers:
            satellites.append(_merge_card(item, card_by_ticker))
    return satellites[:5]


def _core_count_bounds(user_profile: GenericRecord) -> tuple[int, int]:
    """把用户画像映射成核心持仓数量范围。"""
    risk = _text(user_profile.get("risk_tolerance")).lower()
    style = _text(user_profile.get("investment_style")).lower()
    horizon = _text(user_profile.get("investment_horizon")).lower()
    if any(token in risk + style + horizon for token in ["low", "低", "defensive", "income", "dividend", "分红", "防守", "long"]):
        return 3, 5
    if any(token in risk + style for token in ["high", "高", "growth", "aggressive", "进取", "成长"]):
        return 1, 3
    return 2, 4


def _build_investment_charts(report_briefing: GenericRecord, backtest: Any = None) -> GenericRecord:
    """构建投资报告第一版固定四类图表数据。"""
    executive = _record(report_briefing.get("executive"))
    scoreboard = _records(report_briefing.get("scoreboard"))
    risk_register = _records(report_briefing.get("risk_register"))
    allocation = _records(executive.get("allocation_plan"))
    backtest_payload = _plain(backtest)
    points = _records(_record(backtest_payload).get("points"))
    summary = _record(_record(backtest_payload).get("summary"))

    return {
        "portfolio_allocation": {
            "status": "available" if allocation else "missing",
            "items": [
                {"ticker": _text(item.get("ticker")), "weight": _number(item.get("weight")), "verdict": _text(item.get("verdict"))}
                for item in allocation
            ],
        },
        "candidate_score_comparison": {
            "status": "available" if scoreboard else "missing",
            "items": [
                {
                    "ticker": _text(item.get("ticker")),
                    "composite": _number(item.get("composite_score")),
                    "fit": _number(item.get("suitability_score")),
                    "valuation": _number(item.get("valuation_score")),
                    "quality": _number(item.get("quality_score")),
                    "risk": _number(item.get("risk_score")),
                }
                for item in scoreboard
            ],
        },
        "portfolio_vs_benchmark_backtest": {
            "status": "available" if points else "missing",
            "message": "" if points else "Backtest data is not available for this run.",
            "summary": summary,
            "points": points,
        },
        "risk_contribution": {
            "status": "available" if risk_register else "missing",
            "items": [
                {
                    "category": _text(item.get("category"), "Risk"),
                    "ticker": _text(item.get("ticker"), "Portfolio"),
                    "summary": _text(item.get("summary")),
                    "severity": _text(item.get("severity"), "medium"),
                }
                for item in risk_register
            ],
        },
    }


def _build_development_diagnostics(
    *,
    bundle: GenericRecord,
    agent_trace: list[GenericRecord],
    research_plan: GenericRecord,
    backtest: Any,
) -> GenericRecord:
    """整理开发报告需要的诊断摘要。"""
    report_briefing = _record(bundle.get("report_briefing"))
    meta = _record(report_briefing.get("meta"))
    evidence = _records(meta.get("retrieved_evidence"))
    checks = _records(meta.get("validation_checks"))
    backtest_payload = _record(_plain(backtest))
    assumptions = _record(_record(backtest_payload.get("meta")).get("assumptions"))
    return {
        "agent_count": len(agent_trace),
        "evidence_count": len(evidence),
        "validation_check_count": len(checks),
        "citation_section_count": len(_record(meta.get("citation_map"))),
        "research_plan_objective": research_plan.get("objective"),
        "backtest_status": "available" if backtest_payload else "missing",
        "backtest_assumptions": [f"{key}={value}" for key, value in assumptions.items()],
        "report_mode": bundle.get("report_mode"),
        "report_error": bundle.get("report_error"),
    }


def _holding_deep_dive_lines(item: GenericRecord, language_code: str) -> list[str]:
    """渲染核心持仓深度分析。"""
    ticker = _text(item.get("ticker"), "N/A")
    if language_code == "zh":
        return [
            f"### {ticker} — {_text(item.get('verdict_label'), 'N/A')}",
            f"- 投资逻辑：{_text(item.get('thesis'), '暂无。')}",
            f"- 用户适配：{_text(item.get('fit_reason'), '暂无。')}",
            f"- 基本面 / 质量：{_text(item.get('quality_summary') or item.get('audit_summary'), '暂无。')}",
            f"- 新闻 / 催化：{_text(item.get('news_narrative') or item.get('news_label'), '暂无。')}",
            f"- SEC / 审计风险：{_text(item.get('audit_summary'), '暂无。')}",
            f"- Smart money：{_text(item.get('smart_money_positioning'), '暂无。')}",
            f"- 执行建议：{_text(item.get('execution'), '暂无。')}",
            f"- 结论失效条件：{'; '.join(_strings(item.get('caution_points'))) or '暂无。'}",
        ]
    return [
        f"### {ticker} — {_text(item.get('verdict_label'), 'N/A')}",
        f"- Thesis: {_text(item.get('thesis'), 'N/A')}",
        f"- Mandate fit: {_text(item.get('fit_reason'), 'N/A')}",
        f"- Fundamentals / quality: {_text(item.get('quality_summary') or item.get('audit_summary'), 'N/A')}",
        f"- News / catalyst: {_text(item.get('news_narrative') or item.get('news_label'), 'N/A')}",
        f"- SEC / audit risk: {_text(item.get('audit_summary'), 'N/A')}",
        f"- Smart money: {_text(item.get('smart_money_positioning'), 'N/A')}",
        f"- Execution: {_text(item.get('execution'), 'N/A')}",
        f"- Invalidating risks: {'; '.join(_strings(item.get('caution_points'))) or 'N/A'}",
    ]


def _portfolio_plan_text(report_briefing: GenericRecord, language_code: str) -> str:
    """渲染组合执行计划。"""
    executive = _record(report_briefing.get("executive"))
    allocation = _records(executive.get("allocation_plan"))
    if not allocation:
        return _label(language_code, "- 暂无建议仓位。", "- No allocation plan available.")
    lines = [_label(language_code, "- 建议采用分批建仓，并按风险变化复盘。", "- Use staged entries and review as risks change.")]
    for item in allocation:
        lines.append(f"- {_text(item.get('ticker'))}: {_text(item.get('weight'))}% · {_text(item.get('verdict'))}")
    return "\n".join(lines)


def _backtest_summary_text(charts: GenericRecord, language_code: str) -> str:
    """渲染回测摘要或缺口说明。"""
    backtest = _record(charts.get("portfolio_vs_benchmark_backtest"))
    if backtest.get("status") != "available":
        return _label(language_code, "- 当前 run 暂无回测数据，未生成组合 vs 基准曲线。", "- Backtest data is not available for this run.")
    summary = _record(backtest.get("summary"))
    metrics = _record(summary.get("metrics"))
    return "\n".join(
        [
            f"- Portfolio return: {_text(metrics.get('total_return_pct'), 'N/A')}%",
            f"- Benchmark return: {_text(metrics.get('benchmark_return_pct'), 'N/A')}%",
            f"- Excess return: {_text(metrics.get('excess_return_pct'), 'N/A')}%",
            f"- Period: {_text(summary.get('entry_date'))} to {_text(summary.get('end_date'))}",
        ]
    )


def _merge_card(item: GenericRecord | None, card_by_ticker: dict[str, GenericRecord]) -> GenericRecord:
    """把评分行和逐票卡合并，保证核心持仓有足够字段。"""
    base = dict(item or {})
    ticker = _text(base.get("ticker"))
    if ticker in card_by_ticker:
        merged = dict(card_by_ticker[ticker])
        merged.update(base)
        return merged
    return base


def _record(value: Any) -> GenericRecord:
    """安全转换为字典。"""
    return value if isinstance(value, dict) else {}


def _records(value: Any) -> list[GenericRecord]:
    """安全转换为字典列表。"""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    """安全转换为字符串列表。"""
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _number(value: Any) -> float:
    """安全转换为数字。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0


def _text(value: Any, fallback: str = "N/A") -> str:
    """安全转换为非空文本。"""
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _label(language_code: str, zh: str, en: str) -> str:
    """按语言返回文案。"""
    return zh if language_code == "zh" else en


def _plain(value: Any) -> Any:
    """把 Pydantic 对象转换为普通字典。"""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value
