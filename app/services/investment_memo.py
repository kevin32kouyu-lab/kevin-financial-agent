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


def validate_report_output(report: str, report_briefing: dict[str, Any]) -> str | None:
    if not report.strip():
        return "LLM 未返回任何报告内容。"
    if "```" in report:
        return "LLM 输出了代码块，不符合报告格式要求。"
    if not report.lstrip().startswith("# "):
        return "LLM 报告缺少顶层标题。"
    if len(re.findall(r"^##\s+", report, flags=re.MULTILINE)) < 4:
        return "LLM 报告二级章节不足，结构不完整。"

    for row in report_briefing.get("scoreboard", []):
        ticker = str(row.get("ticker", "")).strip()
        if ticker and ticker not in report:
            return f"LLM 报告遗漏了股票 {ticker}。"
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
                f"- Mandate 摘要: {meta.get('mandate_summary', labels['empty'])}",
                f"- 策略适配度: {_format_scalar(executive.get('mandate_fit_score'))}",
                f"- 市场姿态: {executive.get('market_stance', 'N/A')}",
                f"- Top Pick: {_format_scalar(executive.get('top_pick'))} / {_format_scalar(executive.get('top_pick_verdict'))}",
                f"- 观察名单: {', '.join(executive.get('watchlist', [])) or 'N/A'}",
                f"- 回避名单: {', '.join(executive.get('avoid_list', [])) or 'N/A'}",
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
                    f"- 技术 / 新闻: {item.get('technical_summary', 'N/A')} | {item.get('news_label', 'N/A')} | {item.get('alignment', 'N/A')}",
                    f"- Smart Money: {item.get('smart_money_positioning', 'N/A')}",
                    f"- 审计与偿债: {item.get('audit_summary', 'N/A')}",
                    f"- 关键催化剂: {', '.join(item.get('catalysts', [])) or 'N/A'}",
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
