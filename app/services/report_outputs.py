"""三报告输出构建：把同一次 run 的结构化结果整理成两类投资报告和开发报告。"""
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
    """生成简单版、专业版和开发者报告，且三份报告共用同一份结构化数据。"""
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

    simple_markdown = _build_simple_investment_markdown(
        query=query,
        language_code=language_code,
        bundle=bundle,
        core_holdings=core_holdings,
        charts=charts,
    )
    simple_display_model = build_simple_report_display_model(
        query=query,
        language_code=language_code,
        bundle=bundle,
        core_holdings=core_holdings,
        charts=charts,
        backtest=backtest,
    )
    professional_markdown = _build_professional_investment_markdown(
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
        "simple_investment": {
            "kind": "simple_investment",
            "title": _label(language_code, "简单版投资报告", "Simple Investment Report"),
            "markdown": simple_markdown,
            "charts": charts,
            "display_model": simple_display_model,
            "core_holdings": core_holdings,
            "satellite_holdings": satellite_holdings,
        },
        "professional_investment": {
            "kind": "professional_investment",
            "title": _label(language_code, "专业版投资报告", "Professional Investment Report"),
            "markdown": professional_markdown,
            "charts": charts,
            "core_holdings": core_holdings,
            "satellite_holdings": satellite_holdings,
        },
        "investment": {
            "kind": "simple_investment",
            "title": _label(language_code, "简单版投资报告", "Simple Investment Report"),
            "markdown": simple_markdown,
            "charts": charts,
            "display_model": simple_display_model,
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
    """把三报告输出写回 bundle，并保持 final_report 兼容旧入口。"""
    outputs = build_dual_report_outputs(
        bundle=bundle,
        query=query,
        language_code=language_code,
        agent_trace=agent_trace,
        research_plan=research_plan,
        backtest=backtest,
    )
    bundle["report_outputs"] = outputs
    bundle["final_report"] = outputs["simple_investment"]["markdown"]
    return outputs


def build_simple_report_display_model(
    *,
    query: str,
    language_code: str,
    bundle: GenericRecord,
    core_holdings: list[GenericRecord],
    charts: GenericRecord | None = None,
    backtest: Any = None,
) -> GenericRecord:
    """构建网页和 PDF 共用的简单版两页展示母版。"""
    report_briefing = _record(bundle.get("report_briefing"))
    meta = _record(report_briefing.get("meta"))
    executive = _record(report_briefing.get("executive"))
    macro = _record(report_briefing.get("macro"))
    scoreboard = _records(report_briefing.get("scoreboard"))
    risk_register = _records(report_briefing.get("risk_register"))
    validation_summary = _record(meta.get("validation_summary"))
    evidence_summary = _record(meta.get("evidence_summary"))
    evidence = _records(meta.get("retrieved_evidence"))
    checks = _records(meta.get("validation_checks"))
    effective_charts = _effective_display_charts(report_briefing, charts or {}, backtest)
    chart_slots = _display_chart_slots(effective_charts, language_code)

    title = _label(language_code, "简单版投资报告", "Simple Investment Report")
    subtitle = _label(
        language_code,
        "展示型投资结论：先看结论，再看图表和证据。",
        "Showcase investment summary: decision first, charts and evidence second.",
    )
    risk_summary = _text(macro.get("risk_headline"), "")
    if not risk_summary and risk_register:
        risk_summary = _text(risk_register[0].get("summary"), "")

    return {
        "version": "simple_report_showcase_v1",
        "layout": "two_page_showcase",
        "title": title,
        "subtitle": subtitle,
        "query": query or _text(bundle.get("query"), _label(language_code, "未提供原始问题。", "No original request.")),
        "generated_at": _text(meta.get("generated_at") or bundle.get("updated_at"), ""),
        "as_of_date": _text(meta.get("as_of_date") or _record(bundle.get("research_context")).get("as_of_date"), ""),
        "pages": [
            {
                "id": "decision",
                "title": _label(language_code, "第 1 页：决策总览", "Decision page"),
                "summary": _label(language_code, "直接说明结论、动作、仓位和关键数字。", "Shows the verdict, action, sizing and key numbers."),
            },
            {
                "id": "credibility",
                "title": _label(language_code, "第 2 页：可信依据", "Credibility page"),
                "summary": _label(language_code, "用评分、回测、风险、证据和校验解释为什么可信。", "Explains trust with scores, backtest, risks, evidence and checks."),
            },
        ],
        "decision": {
            "headline": _text(executive.get("display_call") or executive.get("primary_call"), _label(language_code, "暂无结论。", "No conclusion available.")),
            "action": _text(executive.get("display_action_summary") or executive.get("action_summary"), _label(language_code, "暂无执行建议。", "No action summary available.")),
            "top_pick": _text(executive.get("top_pick"), "N/A"),
            "confidence": _text(meta.get("confidence_level"), _label(language_code, "未评级", "not rated")),
            "risk_summary": risk_summary or _label(language_code, "暂无主要风险摘要。", "No primary risk summary available."),
        },
        "key_metrics": _display_key_metrics(
            language_code=language_code,
            executive=executive,
            scoreboard=scoreboard,
            evidence=evidence,
            checks=checks,
            charts=effective_charts,
        ),
        "holdings": _display_holdings(executive=executive, scoreboard=scoreboard, core_holdings=core_holdings, language_code=language_code),
        "chart_slots": chart_slots,
        "reasons": _display_reasons(core_holdings=core_holdings, scoreboard=scoreboard, language_code=language_code),
        "risks": _display_risks(risk_register, language_code),
        "evidence": _display_evidence(evidence=evidence, evidence_summary=evidence_summary, language_code=language_code),
        "validation": {
            "headline": _text(validation_summary.get("headline"), _label(language_code, "暂无校验摘要。", "No validation summary available.")),
            "items": _strings(validation_summary.get("items"))[:3],
        },
        "footer_note": _label(
            language_code,
            "本报告仅用于研究辅助，不构成财务、法律或税务建议。",
            "This report is for research support only and is not financial, legal, or tax advice.",
        ),
    }


def _effective_display_charts(report_briefing: GenericRecord, charts: GenericRecord, backtest: Any) -> GenericRecord:
    """把最新回测合入展示母版图表，保证页面和 PDF 看同一组图。"""
    effective = dict(charts or {})
    backtest_payload = _record(_plain(backtest))
    points = _records(backtest_payload.get("points"))
    summary = _record(backtest_payload.get("summary"))
    if points or summary:
        current = _record(effective.get("portfolio_vs_benchmark_backtest"))
        effective["portfolio_vs_benchmark_backtest"] = {
            **current,
            "status": "available" if points else current.get("status", "missing"),
            "summary": summary or _record(current.get("summary")),
            "points": points or _records(current.get("points")),
            "message": "" if points else _text(current.get("message"), "Backtest data is not available for this run."),
        }
    if not effective:
        return _build_investment_charts(report_briefing, backtest)
    return effective


def _display_chart_slots(charts: GenericRecord, language_code: str) -> list[GenericRecord]:
    """固定简单版报告的三张核心图。"""
    backtest_chart = _record(charts.get("portfolio_vs_benchmark_backtest"))
    backtest_points = _records(backtest_chart.get("points"))
    third_key = "portfolio_vs_benchmark_backtest" if backtest_chart.get("status") == "available" and len(backtest_points) >= 2 else "risk_contribution"
    labels = {
        "portfolio_allocation": _label(language_code, "推荐仓位", "Recommended Portfolio Allocation"),
        "candidate_score_comparison": _label(language_code, "候选评分", "Candidate Score Comparison"),
        "portfolio_vs_benchmark_backtest": _label(language_code, "组合 vs SPY", "Portfolio vs Benchmark Backtest"),
        "risk_contribution": _label(language_code, "风险来源", "Risk Contribution"),
    }
    return [
        {"key": "portfolio_allocation", "title": labels["portfolio_allocation"], "type": "bar"},
        {"key": "candidate_score_comparison", "title": labels["candidate_score_comparison"], "type": "bar"},
        {"key": third_key, "title": labels[third_key], "type": "line" if third_key == "portfolio_vs_benchmark_backtest" else "bar"},
    ]


def _display_key_metrics(
    *,
    language_code: str,
    executive: GenericRecord,
    scoreboard: list[GenericRecord],
    evidence: list[GenericRecord],
    checks: list[GenericRecord],
    charts: GenericRecord,
) -> list[GenericRecord]:
    """提炼第一页可扫描的 3 到 5 个关键数字。"""
    metrics: list[GenericRecord] = []
    mandate_fit = _optional_number(executive.get("mandate_fit_score"))
    if mandate_fit is not None:
        metrics.append(
            {
                "key": "mandate_fit",
                "label": _label(language_code, "适配分", "Mandate fit"),
                "value": f"{mandate_fit:.1f}",
                "tone": _score_tone(mandate_fit),
            }
        )
    backtest_metrics = _record(_record(_record(charts.get("portfolio_vs_benchmark_backtest")).get("summary")).get("metrics"))
    total_return = _optional_number(backtest_metrics.get("total_return_pct"))
    excess_return = _optional_number(backtest_metrics.get("excess_return_pct"))
    if total_return is not None:
        metrics.append(
            {
                "key": "portfolio_return",
                "label": _label(language_code, "组合回测", "Portfolio return"),
                "value": f"{total_return:.1f}%",
                "tone": "positive" if total_return >= 0 else "negative",
            }
        )
    if excess_return is not None:
        metrics.append(
            {
                "key": "excess_return",
                "label": _label(language_code, "相对 SPY", "Excess vs SPY"),
                "value": f"{excess_return:.1f}%",
                "tone": "positive" if excess_return >= 0 else "negative",
            }
        )
    if total_return is None and excess_return is None:
        metrics.append(
            {
                "key": "backtest_status",
                "label": _label(language_code, "回测", "Backtest"),
                "value": _label(language_code, "未生成", "Not ready"),
                "tone": "neutral",
            }
        )
    metrics.append(
        {
            "key": "evidence_count",
            "label": _label(language_code, "证据数", "Evidence"),
            "value": str(len(evidence)),
            "tone": "neutral",
        }
    )
    metrics.append(
        {
            "key": "validation_checks",
            "label": _label(language_code, "校验数", "Checks"),
            "value": str(len(checks)),
            "tone": "neutral",
        }
    )
    if len(metrics) < 5:
        metrics.append(
            {
                "key": "candidate_count",
                "label": _label(language_code, "候选数", "Candidates"),
                "value": str(len(scoreboard)),
                "tone": "neutral",
            }
        )
    return metrics[:5]


def _display_holdings(
    *,
    executive: GenericRecord,
    scoreboard: list[GenericRecord],
    core_holdings: list[GenericRecord],
    language_code: str,
) -> list[GenericRecord]:
    """整理第一页推荐组合，每个标的只保留一句能解释角色的话。"""
    card_by_ticker = {_text(item.get("ticker")): item for item in core_holdings}
    score_by_ticker = {_text(item.get("ticker")): item for item in scoreboard}
    allocation = _records(executive.get("allocation_plan"))
    rows = allocation or core_holdings[:4] or scoreboard[:4]
    holdings: list[GenericRecord] = []
    for item in rows[:5]:
        ticker = _text(item.get("ticker"))
        card = card_by_ticker.get(ticker) or score_by_ticker.get(ticker) or item
        holdings.append(
            {
                "ticker": ticker,
                "company": _text(card.get("company_name"), ticker),
                "weight": _optional_number(item.get("weight")),
                "role": _text(item.get("verdict") or item.get("verdict_label"), _label(language_code, "建议关注", "Review")),
                "reason": _text(card.get("thesis") or card.get("fit_reason"), _label(language_code, "暂无一句话理由。", "No one-line reason available.")),
            }
        )
    return holdings


def _display_reasons(core_holdings: list[GenericRecord], scoreboard: list[GenericRecord], language_code: str) -> list[GenericRecord]:
    """整理第二页核心理由。"""
    rows = core_holdings[:4] or scoreboard[:4]
    return [
        {
            "ticker": _text(item.get("ticker")),
            "company": _text(item.get("company_name"), _text(item.get("ticker"))),
            "text": _text(item.get("thesis") or item.get("fit_reason") or item.get("verdict_label"), _label(language_code, "暂无核心理由。", "No core reason available.")),
        }
        for item in rows
    ]


def _display_risks(risk_register: list[GenericRecord], language_code: str) -> list[GenericRecord]:
    """整理第二页关键风险。"""
    if not risk_register:
        return [{"category": _label(language_code, "风险", "Risk"), "ticker": "", "summary": _label(language_code, "暂无明确风险登记。", "No specific risk register is available.")}]
    return [
        {
            "category": _text(item.get("category"), _label(language_code, "风险", "Risk")),
            "ticker": _text(item.get("ticker"), ""),
            "summary": _text(item.get("summary"), _label(language_code, "暂无风险说明。", "No risk detail available.")),
        }
        for item in risk_register[:3]
    ]


def _display_evidence(evidence: list[GenericRecord], evidence_summary: GenericRecord, language_code: str) -> list[GenericRecord]:
    """整理第二页证据摘要，保持可追溯但不过长。"""
    if evidence:
        return [
            {
                "title": _text(item.get("title") or item.get("summary"), _label(language_code, "未命名证据", "Untitled evidence")),
                "source": _text(item.get("source_name") or item.get("source_type") or item.get("source"), _label(language_code, "来源未知", "Unknown source")),
                "date": _text(item.get("published_at") or item.get("as_of_date"), ""),
                "ticker": _text(item.get("ticker"), ""),
                "url": _text(item.get("url"), ""),
            }
            for item in evidence[:5]
        ]
    summary_points = _strings(evidence_summary.get("items")) or _strings(evidence_summary.get("source_points"))
    return [
        {
            "title": point,
            "source": _label(language_code, "报告摘要", "Report summary"),
            "date": "",
            "ticker": "",
            "url": "",
        }
        for point in summary_points[:5]
    ]


def _score_tone(score: float) -> str:
    """把评分映射为展示色调。"""
    if score >= 75:
        return "positive"
    if score >= 55:
        return "neutral"
    return "negative"


def _build_simple_investment_markdown(
    *,
    query: str,
    language_code: str,
    bundle: GenericRecord,
    core_holdings: list[GenericRecord],
    charts: GenericRecord,
) -> str:
    """构建给普通用户快速决策的简单版投资报告。"""
    report_briefing = _record(bundle.get("report_briefing"))
    meta = _record(report_briefing.get("meta"))
    executive = _record(report_briefing.get("executive"))
    risk_register = _records(report_briefing.get("risk_register"))
    evidence = _records(meta.get("retrieved_evidence"))
    evidence_summary = _record(meta.get("evidence_summary"))

    title = _label(language_code, "简单版投资报告", "Simple Investment Report")
    verdict_label = _label(language_code, "一句话结论", "One-line Verdict")
    portfolio_label = _label(language_code, "推荐组合与权重", "Recommended Portfolio")
    why_label = _label(language_code, "为什么选这些标的", "Why These Holdings")
    risk_label = _label(language_code, "最大 3 条关键风险", "Top 3 Key Risks")
    fit_label = _label(language_code, "适合什么用户", "Investor Fit")
    execution_label = _label(language_code, "怎么执行", "Execution Plan")
    evidence_label = _label(language_code, "关键依据", "Key Evidence")
    chart_label = _label(language_code, "核心图表", "Core Charts")
    disclaimer_label = _label(language_code, "简短免责声明", "Short Disclaimer")

    lines = [
        f"# {title}",
        "",
        f"## {verdict_label}",
        f"- {_text(executive.get('display_call') or executive.get('primary_call'), _label(language_code, '暂无结论。', 'No conclusion available.'))}",
        "",
        f"## {portfolio_label}",
    ]

    allocation = _records(executive.get("allocation_plan"))
    if allocation:
        for item in allocation[:5]:
            lines.append(f"- {_text(item.get('ticker'))}: {_text(item.get('weight'), 'N/A')}% · {_text(item.get('verdict'), _label(language_code, '建议关注', 'Review'))}")
    elif core_holdings:
        for item in core_holdings[:5]:
            lines.append(f"- {_text(item.get('ticker'))}: {_text(item.get('verdict_label'), _label(language_code, '核心观察', 'Core candidate'))}")
    else:
        lines.append(_label(language_code, "- 暂无可执行仓位建议。", "- No actionable allocation is available yet."))

    lines.extend(["", f"## {why_label}"])
    for item in core_holdings[:5]:
        lines.append(f"- {_text(item.get('ticker'))}: {_text(item.get('thesis') or item.get('fit_reason'), _label(language_code, '暂无核心理由。', 'No core reason available.'))}")
    if not core_holdings:
        lines.append(_label(language_code, "- 当前候选数据不足，暂不做强推荐。", "- Candidate data is insufficient, so no strong recommendation is made."))

    lines.extend(["", f"## {risk_label}"])
    if risk_register:
        for item in risk_register[:3]:
            prefix = _text(item.get("category"), "Risk")
            if item.get("ticker"):
                prefix = f"{prefix} / {_text(item.get('ticker'))}"
            lines.append(f"- {prefix}: {_text(item.get('summary'))}")
    else:
        lines.append(_label(language_code, "- 暂无明确风险登记。", "- No specific risk register is available."))

    lines.extend(
        [
            "",
            f"## {fit_label}",
            f"- {_text(meta.get('mandate_summary') or _record(meta.get('user_profile')).get('summary'), _label(language_code, '适合愿意按风险提示分批执行的用户。', 'Suitable for users who can follow staged execution and risk limits.'))}",
            "",
            f"## {execution_label}",
            f"- {_text(executive.get('display_action_summary') or executive.get('action_summary'), _label(language_code, '分批执行，并在关键数据更新后复盘。', 'Build gradually and review after key data updates.'))}",
            "",
            f"## {evidence_label}",
        ]
    )
    evidence_points = _strings(evidence_summary.get("items")) or _strings(evidence_summary.get("source_points"))
    if evidence:
        for item in evidence[:5]:
            source = _text(item.get("source_name") or item.get("source_type"), "Source")
            date = _text(item.get("published_at") or item.get("as_of_date"), "")
            title_text = _text(item.get("title") or item.get("summary"), "Evidence")
            lines.append(f"- {title_text} — {source}{f' · {date}' if date else ''}")
    elif evidence_points:
        lines.extend(f"- {item}" for item in evidence_points[:5])
    else:
        lines.append(_label(language_code, "- 暂无可引用依据。", "- No evidence item is available."))

    lines.extend(
        [
            "",
            f"## {chart_label}",
            f"- {_chart_status_text(charts, language_code)}",
            "",
            f"## {disclaimer_label}",
            _label(
                language_code,
                "本报告仅用于研究辅助，不构成财务、法律或税务建议。",
                "This report is for research support only and is not financial, legal, or tax advice.",
            ),
        ]
    )
    return "\n".join(lines)


def _build_professional_investment_markdown(
    *,
    query: str,
    language_code: str,
    bundle: GenericRecord,
    core_holdings: list[GenericRecord],
    satellite_holdings: list[GenericRecord],
    charts: GenericRecord,
) -> str:
    """构建机构研究型专业投资报告。"""
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
            "# 专业版投资报告",
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
            "# Professional Investment Report",
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

    lines.extend(["", "## Valuation View"])
    lines.extend(_score_dimension_lines(scoreboard, "valuation_score", language_code, _label(language_code, "估值", "valuation")))

    lines.extend(["", "## Quality & Growth Analysis"])
    lines.extend(_score_dimension_lines(scoreboard, "quality_score", language_code, _label(language_code, "质量与成长", "quality and growth")))

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
    lines.extend(["", "## Scenario Analysis"])
    lines.extend(_scenario_lines(core_holdings, risk_register, language_code))
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

    lines.extend(["", "## Methodology and Data Notes"])
    lines.extend(
        [
            _label(
                language_code,
                "- 本报告使用同一次 run 的评分表、证据、校验结果和回测摘要生成；不重新执行研究。",
                "- This report is generated from the same run-level scorecard, evidence, validation checks and backtest summary; it does not rerun research.",
            ),
            _label(
                language_code,
                "- 数据不足或降级时应优先阅读风险登记、证据附录和校验提示。",
                "- When data is missing or degraded, prioritize the risk register, evidence appendix and validation notes.",
            ),
        ]
    )

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
            "items": _build_risk_contribution_items(risk_register),
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
    backtest_summary = _record(backtest_payload.get("summary"))
    backtest_points = _records(backtest_payload.get("points"))
    assumptions = _record(_record(backtest_payload.get("meta")).get("assumptions"))
    evidence_count = len(evidence)
    validation_check_count = len(checks)
    return {
        "agent_count": len(agent_trace),
        "evidence_count": evidence_count,
        "validation_check_count": validation_check_count,
        "rag_evidence_count": evidence_count,
        "validation_warning_count": validation_check_count,
        "citation_section_count": len(_record(meta.get("citation_map"))),
        "research_plan_objective": research_plan.get("objective"),
        "backtest_status": "available" if backtest_summary or backtest_points else "missing",
        "backtest_assumptions": [f"{key}={value}" for key, value in assumptions.items()],
        "report_mode": bundle.get("report_mode"),
        "report_error": bundle.get("report_error"),
    }


def _build_risk_contribution_items(risk_register: list[GenericRecord]) -> list[GenericRecord]:
    """把风险登记整理成可渲染的数值图表数据。"""
    aggregated: dict[str, GenericRecord] = {}
    for item in risk_register:
        label = _text(item.get("category"), "Risk")
        ticker = _text(item.get("ticker"), "")
        name = f"{label} / {ticker}" if ticker else label
        value = _risk_value(item)
        if name in aggregated:
            aggregated[name]["value"] = max(_number(aggregated[name].get("value")), value)
            continue
        aggregated[name] = {
            "name": name,
            "category": label,
            "ticker": ticker or "Portfolio",
            "summary": _text(item.get("summary")),
            "severity": _text(item.get("severity"), "medium"),
            "value": value,
        }
    return list(aggregated.values())[:8]


def _risk_value(item: GenericRecord) -> float:
    """把风险登记中的显式数值或风险等级映射成稳定分值。"""
    for key in ("value", "risk", "risk_score", "weight", "severity_score"):
        number = _optional_number(item.get(key))
        if number is not None and number > 0:
            return number
    severity = _text(item.get("severity"), "medium").lower()
    if severity in {"high", "严重", "高"}:
        return 85.0
    if severity in {"low", "较低", "低"}:
        return 35.0
    return 60.0


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


def _chart_status_text(charts: GenericRecord, language_code: str) -> str:
    """给简单版报告说明三张核心图表是否可用。"""
    backtest = _record(charts.get("portfolio_vs_benchmark_backtest"))
    third_chart = (
        _label(language_code, "组合 vs 基准回测曲线", "portfolio vs benchmark backtest")
        if backtest.get("status") == "available"
        else _label(language_code, "风险贡献图", "risk contribution")
    )
    return _label(
        language_code,
        f"本报告优先展示推荐仓位、候选评分对比和{third_chart}。",
        f"This report prioritizes recommended allocation, candidate score comparison and {third_chart}.",
    )


def _score_dimension_lines(scoreboard: list[GenericRecord], key: str, language_code: str, label: str) -> list[str]:
    """按评分维度生成专业版的排序观察。"""
    rows = [item for item in scoreboard if _optional_number(item.get(key)) is not None]
    if not rows:
        return [_label(language_code, f"- 暂无{label}评分。", f"- No {label} score is available.")]
    sorted_rows = sorted(rows, key=lambda item: _number(item.get(key)), reverse=True)[:5]
    return [
        f"- {_text(item.get('ticker'))}: {_text(item.get(key))} · {_text(item.get('verdict_label'))}"
        for item in sorted_rows
    ]


def _scenario_lines(core_holdings: list[GenericRecord], risk_register: list[GenericRecord], language_code: str) -> list[str]:
    """生成不编造预测的基础场景分析。"""
    holdings = ", ".join(_text(item.get("ticker")) for item in core_holdings) or "N/A"
    main_risk = _text(risk_register[0].get("summary"), _label(language_code, "暂无主要风险。", "No primary risk available.")) if risk_register else _label(language_code, "暂无主要风险。", "No primary risk available.")
    if language_code == "zh":
        return [
            f"- 基准情景：核心持仓 {holdings} 延续当前评分优势，按建议仓位分批执行。",
            f"- 下行情景：若出现 {main_risk}，应降低仓位或转入观察。",
            "- 上行情景：若证据新鲜度、盈利质量和回测表现同步改善，可考虑提高核心持仓权重。",
        ]
    return [
        f"- Base case: core holdings {holdings} keep their current score advantage and are built gradually.",
        f"- Downside case: if {main_risk}, reduce sizing or move the idea to watchlist.",
        "- Upside case: if evidence freshness, earnings quality and backtest behavior improve together, consider higher core sizing.",
    ]


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


def _optional_number(value: Any) -> float | None:
    """安全读取可选数字，没有值时返回 None。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


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
