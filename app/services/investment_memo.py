from __future__ import annotations

import json
import re
from typing import Any

from app.domain.contracts import ParsedIntent
from app.agent_runtime.reporting import (
    _build_merged_data_package as _base_build_merged_data_package,
    _build_report_briefing as _base_build_report_briefing,
    _build_report_input as _base_build_report_input,
    _format_scalar,
    _labels,
    _language_label,
)


def build_merged_data_package(query: str, intent: ParsedIntent, analysis: dict[str, Any]) -> dict[str, Any]:
    merged_data_package = _base_build_merged_data_package(query, intent, analysis)
    meta_data = merged_data_package.setdefault("Meta_Data", {})
    meta_data["Market_Data_Status"] = analysis.get("market_data_status", {}) or {}
    return merged_data_package


def build_report_input(query: str, intent: ParsedIntent, merged_data_package: dict[str, Any]) -> dict[str, Any]:
    payload = _base_build_report_input(query, intent, merged_data_package)
    merged_payload = payload.setdefault("Merged Data Package", {})
    merged_payload.setdefault("Meta_Data", {})["Market_Data_Status"] = (
        (merged_data_package.get("Meta_Data") or {}).get("Market_Data_Status") or {}
    )
    payload["Agent_Control"] = intent.agent_control.model_dump()
    return payload


def build_report_briefing(query: str, intent: ParsedIntent, merged_data_package: dict[str, Any]) -> dict[str, Any]:
    report_briefing = _base_build_report_briefing(query, intent, merged_data_package)
    meta = report_briefing.setdefault("meta", {})
    market_data_status = ((merged_data_package.get("Meta_Data") or {}).get("Market_Data_Status") or {})
    meta["mandate_summary"] = _build_mandate_summary(intent, intent.system_context.language)
    meta["data_provenance"] = {
        "source": market_data_status.get("source") or "unknown",
        "records": market_data_status.get("records"),
        "last_refresh_at": market_data_status.get("last_refresh_at"),
        "fallback_enabled": market_data_status.get("fallback_enabled"),
        "macro_source": ((market_data_status.get("macro_status") or {}).get("source") or "unknown"),
        "macro_last_refresh_at": (market_data_status.get("macro_status") or {}).get("last_refresh_at"),
        "sec_filings_records": (market_data_status.get("sec_filings_status") or {}).get("records"),
        "sec_filings_covered_tickers": (market_data_status.get("sec_filings_status") or {}).get("covered_tickers"),
    }
    meta["assumptions"] = intent.agent_control.assumptions
    meta["intent_quality"] = {
        "is_intent_clear": intent.agent_control.is_intent_clear,
        "is_intent_usable": intent.agent_control.is_intent_usable,
        "missing_critical_info": intent.agent_control.missing_critical_info,
    }
    _attach_user_facing_summaries(
        report_briefing=report_briefing,
        intent=intent,
        market_data_status=market_data_status,
    )
    return report_briefing


def build_report_system_prompt(language_code: str) -> str:
    labels = _labels(language_code)
    sections = labels["sections"]
    language_name = _language_label(language_code)
    return (
        "[SYSTEM CONTEXT]\n"
        "You are the Chief Portfolio Manager of a disciplined institutional investment team.\n"
        "Your task is to convert the merged research JSON into a professional investment memo.\n\n"
        "[NON-NEGOTIABLE RULES]\n"
        f"1. Write the entire report in {language_name}.\n"
        "2. Do not fabricate any number, thesis, catalyst or risk signal.\n"
        "3. You must mention every ticker from Price_Data.\n"
        "4. Put the verdict first, then the supporting evidence, then the execution guidance.\n"
        "5. Output Markdown only. Do not use fenced code blocks.\n\n"
        "6. If the JSON includes assumptions, surface them briefly in the executive section.\n\n"
        "[REQUIRED STRUCTURE]\n"
        f"# {labels['title']}\n"
        f"## {sections['executive']}\n"
        f"## {sections['market']}\n"
        f"## {sections['scoreboard']}\n"
        f"## {sections['cards']}\n"
        f"## {sections['risk']}\n\n"
        "[WRITING STYLE]\n"
        "Be concise, institutional, and directly useful for a portfolio decision meeting."
    )


def build_report_user_prompt(query: str, intent: ParsedIntent, merged_data_package: dict[str, Any]) -> str:
    payload = build_report_input(query, intent, merged_data_package)
    return (
        "[INPUT DATA]\n"
        f"User Financial Query:\n{query}\n\n"
        f"System Target Language:\n{_language_label(intent.system_context.language)}\n\n"
        "Merged Data Package:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _looks_like_wrong_language(report: str, language_code: str) -> bool:
    """简单语言一致性检测：用于在模型偏离目标语言时触发回退。"""
    if not report.strip():
        return False
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", report))
    latin_letters = len(re.findall(r"[A-Za-z]", report))

    if language_code == "zh":
        # 中文报告至少应包含一定比例中文字符，避免全文英文但侥幸通过结构校验
        return chinese_chars < max(40, latin_letters // 4)
    # 英文报告里若中文占比明显偏高，则判为语言偏离
    return chinese_chars > max(40, latin_letters // 2)


def validate_report_output(report: str, intent: ParsedIntent, report_briefing: dict[str, Any]) -> str | None:
    language_code = intent.system_context.language
    if not report.strip():
        return "LLM 未返回任何报告内容。" if language_code == "zh" else "LLM returned an empty report."
    if "```" in report:
        return (
            "LLM 输出了代码块，不符合报告格式要求。"
            if language_code == "zh"
            else "LLM returned fenced code blocks, which violates report format requirements."
        )
    if not report.lstrip().startswith("# "):
        return "LLM 报告缺少顶层标题。" if language_code == "zh" else "LLM report is missing the top-level title."
    if len(re.findall(r"^##\s+", report, flags=re.MULTILINE)) < 4:
        return (
            "LLM 报告二级章节不足，结构不完整。"
            if language_code == "zh"
            else "LLM report has insufficient section structure."
        )
    if _looks_like_wrong_language(report, language_code):
        return (
            "LLM 报告语言与用户问题语言不一致，已触发回退。"
            if language_code == "zh"
            else "LLM report language does not match the query language; fallback triggered."
        )

    for row in report_briefing.get("scoreboard", []):
        ticker = str(row.get("ticker", "")).strip()
        if ticker and ticker not in report:
            return (
                f"LLM 报告遗漏了股票 {ticker}。"
                if language_code == "zh"
                else f"LLM report omitted ticker {ticker}."
            )
    return None


def build_rule_based_report(intent: ParsedIntent, report_briefing: dict[str, Any]) -> str:
    language_code = intent.system_context.language
    labels = _labels(language_code)
    sections = labels["sections"]
    meta = report_briefing.get("meta", {})
    executive = report_briefing.get("executive", {})
    macro = report_briefing.get("macro", {})
    scoreboard = report_briefing.get("scoreboard", [])
    ticker_cards = report_briefing.get("ticker_cards", [])
    risk_register = report_briefing.get("risk_register", [])
    data_provenance = meta.get("data_provenance", {})
    assumptions = meta.get("assumptions", []) or []

    lines = [f"# {meta.get('title', labels['title'])}", ""]
    if language_code == "zh":
        lines.extend(
            [
                f"## {sections['executive']}",
                f"- 结论: {executive.get('primary_call', labels['empty'])}",
                f"- 投资目标摘要: {meta.get('mandate_summary', labels['empty'])}",
                f"- 策略适配度: {_format_scalar(executive.get('mandate_fit_score'))}",
                f"- 市场姿态: {executive.get('market_stance', '暂无')}",
                f"- 优先标的: {_format_scalar(executive.get('top_pick'))} / {_format_scalar(executive.get('top_pick_verdict'))}",
                f"- 观察名单: {', '.join(executive.get('watchlist', [])) or '暂无'}",
                f"- 回避名单: {', '.join(executive.get('avoid_list', [])) or '暂无'}",
                f"- 执行摘要: {executive.get('action_summary', labels['empty'])}",
                f"- 默认假设: {'；'.join(assumptions) if assumptions else '无'}",
                "",
                f"## {sections['market']}",
                f"- 宏观环境: {_format_scalar(macro.get('regime'))}",
                f"- VIX: {_format_scalar(macro.get('vix'))}",
                f"- 标普 500: {_format_scalar(macro.get('sp500'))}",
                f"- 美国 10Y: {_format_scalar(macro.get('us10y'))}",
                f"- 风险提示: {macro.get('risk_headline', labels['empty'])}",
                f"- 数据源: {_format_scalar(data_provenance.get('source'))}",
                f"- 股票池规模: {_format_scalar(data_provenance.get('records'))}",
                f"- 最后刷新: {_format_scalar(data_provenance.get('last_refresh_at'))}",
                "",
                f"## {sections['scoreboard']}",
                f"| {' | '.join(labels['table_headers'])} |",
                f"| {' | '.join(['---'] * len(labels['table_headers']))} |",
            ]
        )
    else:
        lines.extend(
            [
                f"## {sections['executive']}",
                f"- Verdict: {executive.get('primary_call', labels['empty'])}",
                f"- Mandate Summary: {meta.get('mandate_summary', labels['empty'])}",
                f"- {labels['metric_labels']['fit']}: {_format_scalar(executive.get('mandate_fit_score'))}",
                f"- Market Stance: {executive.get('market_stance', 'N/A')}",
                f"- Top Pick: {_format_scalar(executive.get('top_pick'))} / {_format_scalar(executive.get('top_pick_verdict'))}",
                f"- Watchlist: {', '.join(executive.get('watchlist', [])) or 'N/A'}",
                f"- Avoid List: {', '.join(executive.get('avoid_list', [])) or 'N/A'}",
                f"- Action Summary: {executive.get('action_summary', labels['empty'])}",
                f"- Assumptions: {'; '.join(assumptions) if assumptions else 'None'}",
                "",
                f"## {sections['market']}",
                f"- Regime: {_format_scalar(macro.get('regime'))}",
                f"- VIX: {_format_scalar(macro.get('vix'))}",
                f"- S&P 500: {_format_scalar(macro.get('sp500'))}",
                f"- US 10Y: {_format_scalar(macro.get('us10y'))}",
                f"- Risk Headline: {macro.get('risk_headline', labels['empty'])}",
                f"- Data Source: {_format_scalar(data_provenance.get('source'))}",
                f"- Universe Size: {_format_scalar(data_provenance.get('records'))}",
                f"- Last Refresh: {_format_scalar(data_provenance.get('last_refresh_at'))}",
                "",
                f"## {sections['scoreboard']}",
                f"| {' | '.join(labels['table_headers'])} |",
                f"| {' | '.join(['---'] * len(labels['table_headers']))} |",
            ]
        )

    for item in scoreboard:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("ticker", "N/A")),
                    _format_scalar(item.get("composite_score")),
                    _format_scalar(item.get("suitability_score")),
                    _format_scalar(item.get("valuation_score")),
                    _format_scalar(item.get("quality_score")),
                    _format_scalar(item.get("momentum_score")),
                    _format_scalar(item.get("risk_score")),
                    str(item.get("verdict_label", "N/A")),
                ]
            )
            + " |"
        )

    lines.extend(["", f"## {sections['cards']}"])
    for item in ticker_cards:
        if language_code == "zh":
            lines.extend(
                [
                    f"### {item.get('ticker', 'N/A')} - {item.get('verdict_label', 'N/A')}",
                    f"- 投资逻辑: {item.get('thesis', labels['empty'])}",
                    f"- 适配原因: {item.get('fit_reason', labels['empty'])}",
                    f"- 技术 / 新闻: {item.get('technical_summary', '暂无')} | {item.get('news_label', '暂无')} | {item.get('alignment', '暂无')}",
                    f"- 资金面: {item.get('smart_money_positioning', '暂无')}",
                    f"- 审计与偿债: {item.get('audit_summary', '暂无')}",
                    f"- 关键催化剂: {', '.join(item.get('catalysts', [])) or '暂无'}",
                    f"- 执行建议: {item.get('execution', labels['empty'])}",
                ]
            )
        else:
            lines.extend(
                [
                    f"### {item.get('ticker', 'N/A')} - {item.get('verdict_label', 'N/A')}",
                    f"- Thesis: {item.get('thesis', labels['empty'])}",
                    f"- Fit Reason: {item.get('fit_reason', labels['empty'])}",
                    f"- Technical / News: {item.get('technical_summary', 'N/A')} | {item.get('news_label', 'N/A')} | {item.get('alignment', 'N/A')}",
                    f"- Smart Money: {item.get('smart_money_positioning', 'N/A')}",
                    f"- Audit: {item.get('audit_summary', 'N/A')}",
                    f"- Catalysts: {', '.join(item.get('catalysts', [])) or 'N/A'}",
                    f"- Execution: {item.get('execution', labels['empty'])}",
                ]
            )

    lines.extend(["", f"## {sections['risk']}"])
    for item in risk_register:
        prefix = f"{item.get('category', 'Risk')}"
        if item.get("ticker"):
            prefix = f"{prefix} / {item['ticker']}"
        lines.append(f"- {prefix}: {item.get('summary', labels['empty'])}")

    allocation_plan = executive.get("allocation_plan", [])
    if allocation_plan:
        lines.append("")
        lines.append(f"- {labels['metric_labels']['allocation']}:")
        for item in allocation_plan:
            lines.append(f"  - {item.get('ticker')}: {_format_scalar(item.get('weight'))}% / {item.get('verdict')}")

    return "\n".join(lines)


def _build_mandate_summary(intent: ParsedIntent, language_code: str) -> str:
    capital_amount = intent.portfolio_sizing.capital_amount
    currency = intent.portfolio_sizing.currency or "USD"
    risk = intent.risk_profile.tolerance_level or "medium"
    horizon = intent.investment_strategy.horizon or "long_term"
    style = intent.investment_strategy.style or "general"
    tickers = intent.explicit_targets.tickers or []

    if language_code == "zh":
        parts = [
            f"资金规模 {capital_amount or '未说明'} {currency}",
            f"风险偏好 {risk}",
            f"持有期限 {horizon}",
            f"策略风格 {style}",
        ]
        if tickers:
            parts.append(f"指定标的 {', '.join(tickers)}")
        return "；".join(parts)

    parts = [
        f"Capital {capital_amount or 'unspecified'} {currency}",
        f"Risk profile {risk}",
        f"Horizon {horizon}",
        f"Style {style}",
    ]
    if tickers:
        parts.append(f"Explicit targets {', '.join(tickers)}")
    return " | ".join(parts)


def _source_label(language_code: str, raw: Any) -> str:
    source = str(raw or "").strip().lower()
    if language_code == "zh":
        mapping = {
            "yfinance": "Yahoo Finance",
            "yfinance_batch": "Yahoo Finance",
            "yfinance_proxy": "Yahoo Finance",
            "yahoo_rss": "Yahoo Finance 新闻",
            "finnhub": "Finnhub 新闻",
            "sec_edgar": "SEC EDGAR 披露",
            "alpha_vantage": "Alpha Vantage",
            "alpaca_iex": "Alpaca Market Data",
            "longbridge_daily": "Longbridge 行情",
            "historical_unavailable": "历史数据暂不可用",
            "unavailable": "暂不可用",
            "none": "暂无覆盖",
            "unknown": "未知来源",
        }
    else:
        mapping = {
            "yfinance": "Yahoo Finance",
            "yfinance_batch": "Yahoo Finance",
            "yfinance_proxy": "Yahoo Finance",
            "yahoo_rss": "Yahoo Finance News",
            "finnhub": "Finnhub News",
            "sec_edgar": "SEC EDGAR filings",
            "alpha_vantage": "Alpha Vantage",
            "alpaca_iex": "Alpaca Market Data",
            "longbridge_daily": "Longbridge market data",
            "historical_unavailable": "Historical data unavailable",
            "unavailable": "Unavailable",
            "none": "No coverage",
            "unknown": "Unknown source",
        }
    return mapping.get(source, str(raw or mapping["unknown"]))


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _build_user_profile(intent: ParsedIntent, language_code: str) -> dict[str, Any]:
    capital_amount = intent.portfolio_sizing.capital_amount
    currency = intent.portfolio_sizing.currency or "USD"
    preferred_sectors = intent.investment_strategy.preferred_sectors or []
    preferred_industries = intent.investment_strategy.preferred_industries or []
    explicit_tickers = intent.explicit_targets.tickers or []

    if language_code == "zh":
        parts = [
            f"资金规模：{capital_amount or '未说明'} {currency}",
            f"风险偏好：{intent.risk_profile.tolerance_level or '未说明'}",
            f"投资期限：{intent.investment_strategy.horizon or '未说明'}",
            f"研究风格：{intent.investment_strategy.style or '未说明'}",
        ]
        if preferred_sectors:
            parts.append(f"偏好板块：{', '.join(preferred_sectors)}")
        if preferred_industries:
            parts.append(f"偏好行业：{', '.join(preferred_industries)}")
        if explicit_tickers:
            parts.append(f"关注标的：{', '.join(explicit_tickers)}")
    else:
        parts = [
            f"Capital: {capital_amount or 'unspecified'} {currency}",
            f"Risk: {intent.risk_profile.tolerance_level or 'unspecified'}",
            f"Horizon: {intent.investment_strategy.horizon or 'unspecified'}",
            f"Style: {intent.investment_strategy.style or 'unspecified'}",
        ]
        if preferred_sectors:
            parts.append(f"Preferred sectors: {', '.join(preferred_sectors)}")
        if preferred_industries:
            parts.append(f"Preferred industries: {', '.join(preferred_industries)}")
        if explicit_tickers:
            parts.append(f"Focus tickers: {', '.join(explicit_tickers)}")

    return {
        "summary": "；".join(parts) if language_code == "zh" else " | ".join(parts),
        "capital_amount": capital_amount,
        "currency": currency,
        "risk_tolerance": intent.risk_profile.tolerance_level,
        "investment_horizon": intent.investment_strategy.horizon,
        "investment_style": intent.investment_strategy.style,
        "preferred_sectors": preferred_sectors,
        "preferred_industries": preferred_industries,
        "explicit_tickers": explicit_tickers,
    }


def _build_candidate_evidence(candidate: dict[str, Any], language_code: str) -> tuple[list[str], list[str], list[str]]:
    evidence_points: list[str] = []
    caution_points: list[str] = []
    source_points: list[str] = []

    if language_code == "zh":
        if float(candidate.get("quality_score") or 0) >= 75:
            evidence_points.append(f"质量维度评分 {candidate.get('quality_score')}，说明盈利与稳定性较好。")
        if float(candidate.get("valuation_score") or 0) >= 70:
            evidence_points.append(f"估值维度评分 {candidate.get('valuation_score')}，当前估值没有明显失真。")
        if float(candidate.get("risk_score") or 0) >= 70:
            evidence_points.append(f"风险控制评分 {candidate.get('risk_score')}，资产负债表与现金流相对稳。")
        if _clean_text(candidate.get("technical_summary")):
            evidence_points.append(f"技术面观察：{candidate.get('technical_summary')}")
        if _clean_text(candidate.get("news_narrative")):
            evidence_points.append(f"新闻面观察：{candidate.get('news_narrative')}")

        if candidate.get("severe_audit_warning"):
            caution_points.append("审计与偿债层面触发高风险提示，需要优先谨慎。")
        alignment = _clean_text(candidate.get("alignment"))
        if alignment in {"分化", "暂不清晰"}:
            caution_points.append(f"技术面与新闻面当前为“{alignment}”，不适合把单一信号看得过强。")
        news_label = _clean_text(candidate.get("news_label"))
        if news_label in {"暂无覆盖", "历史不可用"}:
            caution_points.append("新闻覆盖不足，本次结论更多依赖价格、质量与风控维度。")
        if _clean_text(candidate.get("smart_money_positioning")) in {"Unavailable", "不可用"}:
            caution_points.append("资金面代理当前不可用，机构持仓结论需要保守解读。")

        source_points = [
            f"技术面：{_source_label(language_code, candidate.get('technical_source'))}",
            f"新闻面：{_source_label(language_code, candidate.get('news_source'))}",
            f"资金面：{_source_label(language_code, candidate.get('smart_money_source'))}",
        ]
    else:
        if float(candidate.get("quality_score") or 0) >= 75:
            evidence_points.append(f"Quality score is {candidate.get('quality_score')}, pointing to stronger profitability and resilience.")
        if float(candidate.get("valuation_score") or 0) >= 70:
            evidence_points.append(f"Valuation score is {candidate.get('valuation_score')}, so current pricing is still reasonable.")
        if float(candidate.get("risk_score") or 0) >= 70:
            evidence_points.append(f"Risk-control score is {candidate.get('risk_score')}, suggesting a steadier balance-sheet profile.")
        if _clean_text(candidate.get("technical_summary")):
            evidence_points.append(f"Technical read: {candidate.get('technical_summary')}")
        if _clean_text(candidate.get("news_narrative")):
            evidence_points.append(f"News read: {candidate.get('news_narrative')}")

        if candidate.get("severe_audit_warning"):
            caution_points.append("Audit and solvency checks still trigger a high-risk warning.")
        alignment = _clean_text(candidate.get("alignment"))
        if alignment in {"Mixed", "Unclear"}:
            caution_points.append(f"Technicals and news are currently '{alignment}', so the signal should be treated cautiously.")
        news_label = _clean_text(candidate.get("news_label"))
        if news_label in {"No Coverage", "Historical Unavailable"}:
            caution_points.append("News coverage is limited, so the conclusion leans more on price, quality and risk control.")
        if _clean_text(candidate.get("smart_money_positioning")) in {"Unavailable", "不可用"}:
            caution_points.append("Public positioning proxy is unavailable, so institutional-flow signals should be read conservatively.")

        source_points = [
            f"Technical: {_source_label(language_code, candidate.get('technical_source'))}",
            f"News: {_source_label(language_code, candidate.get('news_source'))}",
            f"Positioning: {_source_label(language_code, candidate.get('smart_money_source'))}",
        ]

    return evidence_points[:3], caution_points[:3], source_points


def _build_evidence_summary(report_briefing: dict[str, Any], language_code: str) -> dict[str, Any]:
    executive = report_briefing.get("executive", {}) or {}
    ticker_cards = report_briefing.get("ticker_cards", []) or []
    top_pick_ticker = str(executive.get("top_pick") or "")
    top_pick = next((item for item in ticker_cards if str(item.get("ticker") or "") == top_pick_ticker), ticker_cards[0] if ticker_cards else {})
    evidence_points = list(top_pick.get("evidence_points") or [])
    source_points = list(top_pick.get("source_points") or [])

    if language_code == "zh":
        headline = (
            f"这次结论主要由 {top_pick_ticker} 的综合评分、目标匹配度、风险控制和近期公开信息共同支持。"
            if top_pick_ticker
            else "这次结论主要基于当前候选池的综合评分与风险校验。"
        )
    else:
        headline = (
            f"The current verdict is mainly supported by {top_pick_ticker}'s overall score, mandate fit, risk control and recent public signals."
            if top_pick_ticker
            else "The current verdict is mainly supported by the candidate scoreboard and the risk checks."
        )

    evidence_items = []
    source_points = source_points[:3]
    for index, item in enumerate(evidence_points[:3]):
        source_label = source_points[index] if index < len(source_points) else None
        evidence_items.append(
            {
                "id": f"evidence-{index + 1}",
                "summary": item,
                "source_label": source_label,
                "source_type": "public_market_data",
                "time_hint": "current_run",
                "confidence": "high" if index == 0 else "medium",
            }
        )

    return {
        "headline": headline,
        "items": evidence_points,
        "source_points": source_points,
        "evidence_items": evidence_items,
    }


def _build_validation_summary(report_briefing: dict[str, Any], intent: ParsedIntent, language_code: str) -> tuple[dict[str, Any], str | None, str | None]:
    executive = report_briefing.get("executive", {}) or {}
    macro = report_briefing.get("macro", {}) or {}
    ticker_cards = report_briefing.get("ticker_cards", []) or []
    warning_flags = report_briefing.get("meta", {}).get("warning_flags") or []
    top_pick_ticker = str(executive.get("top_pick") or "")
    top_pick = next((item for item in ticker_cards if str(item.get("ticker") or "") == top_pick_ticker), None)

    items: list[str] = []
    level = "pass"
    if macro.get("severe_warning"):
        level = "warning"
        items.append(
            "宏观环境偏谨慎，本次结论更适合分批执行而不是一次性重仓。"
            if language_code == "zh"
            else "The macro backdrop is defensive, so staged entries are safer than a full-size entry."
        )
    if top_pick and top_pick.get("veto"):
        level = "warning"
        items.append(
            f"{top_pick_ticker} 的审计与偿债风险仍然偏高，不适合作为强结论。"
            if language_code == "zh"
            else f"{top_pick_ticker} still carries elevated audit / solvency risk and should not be framed as a strong conviction call."
        )
    if not intent.agent_control.is_intent_clear:
        if level != "warning":
            level = "caution"
        items.append(
            "用户目标并非完全结构化，系统用了可解释假设来补齐。"
            if language_code == "zh"
            else "The mandate was not fully explicit, so the system filled the gaps with explicit assumptions."
        )
    if warning_flags:
        if level == "pass":
            level = "caution"
        warning_text = "；".join(str(item) for item in warning_flags) if language_code == "zh" else "; ".join(str(item) for item in warning_flags)
        items.append(
            f"本次研究存在数据提醒：{warning_text}"
            if language_code == "zh"
            else f"Data warnings are present in this run: {warning_text}"
        )
    if top_pick and list(top_pick.get("caution_points") or []):
        if level == "pass":
            level = "caution"
        items.append(str((top_pick.get("caution_points") or [])[0]))

    if language_code == "zh":
        headline_map = {
            "pass": "本次结论与当前数据没有明显冲突，可作为正式研究起点。",
            "caution": "本次结论可以使用，但需要结合下方风险与数据提醒一起看。",
            "warning": "本次结论需要偏保守解读，建议先看风险与数据降级说明。",
        }
    else:
        headline_map = {
            "pass": "The current verdict is broadly consistent with the available data and can be used as a formal starting point.",
            "caution": "The current verdict is usable, but it should be read together with the risk and data caveats below.",
            "warning": "The current verdict should be read conservatively before acting on it.",
        }

    presentation_call = None
    presentation_action = None
    if top_pick and level == "warning":
        presentation_call = (
            f"当前更适合把 {top_pick_ticker} 视作相对更优候选，而不是直接下强结论。"
            if language_code == "zh"
            else f"{top_pick_ticker} is better framed as the relatively stronger candidate rather than a full-strength call."
        )
        presentation_action = (
            "先小步试探或继续观察，等待风险信号缓和后再加大仓位。"
            if language_code == "zh"
            else "Start small or stay on watch until the risk signals ease."
        )
    elif top_pick and level == "caution":
        presentation_call = (
            f"当前最匹配的候选仍是 {top_pick_ticker}，但更适合按分批、保守方式执行。"
            if language_code == "zh"
            else f"{top_pick_ticker} remains the best fit, but the execution should stay staged and conservative."
        )
        presentation_action = (
            "先按计划分批布局，并持续确认新闻、审计与宏观信号是否继续支持。"
            if language_code == "zh"
            else "Scale in gradually and keep confirming news, audit and macro signals."
        )

    return {
        "level": level,
        "headline": headline_map[level],
        "items": items[:4],
    }, presentation_call, presentation_action


def _build_safety_summary(
    report_briefing: dict[str, Any],
    market_data_status: dict[str, Any],
    language_code: str,
) -> dict[str, Any]:
    meta = report_briefing.get("meta", {}) or {}
    ticker_cards = report_briefing.get("ticker_cards", []) or []
    warning_flags = meta.get("warning_flags") or []
    used_sources: list[str] = []
    for raw in [
        market_data_status.get("source"),
        (market_data_status.get("macro_status") or {}).get("source"),
        "sec_edgar" if (market_data_status.get("sec_filings_status") or {}).get("records") else None,
    ]:
        label = _source_label(language_code, raw)
        if label and label not in used_sources:
            used_sources.append(label)
    for item in ticker_cards[:5]:
        for raw in [item.get("technical_source"), item.get("news_source"), item.get("smart_money_source")]:
            label = _source_label(language_code, raw)
            if label and label not in used_sources:
                used_sources.append(label)

    degraded_modules: list[str] = []
    if market_data_status.get("fallback_enabled"):
        degraded_modules.append(
            "股票池当前允许回退到备用源或种子数据。"
            if language_code == "zh"
            else "The stock universe is allowed to fall back to backup or seed data."
        )
    if warning_flags:
        degraded_modules.extend(str(item) for item in warning_flags if str(item).strip())

    has_news_gap = any(str(item.get("news_source") or "").lower() in {"none", "historical_unavailable", "unavailable"} for item in ticker_cards)
    has_smart_gap = any(str(item.get("smart_money_source") or "").lower() in {"none", "unavailable"} for item in ticker_cards)
    has_tech_gap = any(str(item.get("technical_source") or "").lower() in {"unavailable"} for item in ticker_cards)
    if has_news_gap:
        degraded_modules.append(
            "部分新闻覆盖缺失或只能看到历史不可用提示。"
            if language_code == "zh"
            else "Some names have limited news coverage or historical news is unavailable."
        )
    if has_smart_gap:
        degraded_modules.append(
            "部分资金面代理不可用，因此机构持仓信号需要保守看待。"
            if language_code == "zh"
            else "Some positioning proxies are unavailable, so institutional-flow signals should be treated cautiously."
        )
    if has_tech_gap:
        degraded_modules.append(
            "部分技术面信号未成功刷新，系统使用了更保守的读法。"
            if language_code == "zh"
            else "Some technical signals were unavailable, so the system used a more conservative read."
        )

    if language_code == "zh":
        headline = (
            "本次研究使用了多源公开数据，并对缺失模块做了显式降级提示。"
            if not degraded_modules
            else "本次研究存在部分数据降级，建议先看下方提醒再使用结论。"
        )
    else:
        headline = (
            "This run used multiple public data sources with explicit fallbacks."
            if not degraded_modules
            else "This run contains some degraded data paths, so review the caveats before acting on the verdict."
        )

    return {
        "headline": headline,
        "used_sources": used_sources[:6],
        "degraded_modules": degraded_modules[:6],
    }


def _attach_user_facing_summaries(
    *,
    report_briefing: dict[str, Any],
    intent: ParsedIntent,
    market_data_status: dict[str, Any],
) -> None:
    language_code = intent.system_context.language
    meta = report_briefing.setdefault("meta", {})
    ticker_cards = report_briefing.get("ticker_cards", []) or []
    for item in ticker_cards:
        evidence_points, caution_points, source_points = _build_candidate_evidence(item, language_code)
        item["evidence_points"] = evidence_points
        item["caution_points"] = caution_points
        item["source_points"] = source_points
        item["source_summary"] = "；".join(source_points) if language_code == "zh" else " | ".join(source_points)

    meta["user_profile"] = _build_user_profile(intent, language_code)
    meta["evidence_summary"] = _build_evidence_summary(report_briefing, language_code)
    validation_summary, presentation_call, presentation_action = _build_validation_summary(
        report_briefing,
        intent,
        language_code,
    )
    meta["validation_summary"] = validation_summary
    meta["safety_summary"] = _build_safety_summary(report_briefing, market_data_status, language_code)
    meta["evidence_items"] = list((meta.get("evidence_summary") or {}).get("evidence_items") or [])
    meta["confidence_level"] = (
        "high"
        if validation_summary.get("level") == "pass"
        else "medium"
        if validation_summary.get("level") == "caution"
        else "low"
    )
    meta["validation_flags"] = list(validation_summary.get("items") or [])
    meta["coverage_flags"] = list((meta.get("safety_summary") or {}).get("degraded_modules") or [])

    executive = report_briefing.setdefault("executive", {})
    if presentation_call:
        executive["presentation_call"] = presentation_call
    if presentation_action:
        executive["presentation_action_summary"] = presentation_action
