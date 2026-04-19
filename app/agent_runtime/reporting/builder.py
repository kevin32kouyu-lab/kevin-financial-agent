"""Builder functions for report construction.

This module contains functions that:
- Order and merge data from various sources
- Build merged data packages for LLM consumption
- Construct report briefings with structured sections
- Generate prompts for LLM report generation
- Validate and format final reports
"""

from datetime import date
import json
from typing import Any

from .profiling import (
    _derive_news_profile,
    _derive_tech_profile,
    _derive_smart_money_profile,
    _derive_audit_profile,
)
from .scoring import (
    _build_candidate_analysis,
    _build_allocation_plan,
    _macro_is_severe,
)


def _safe_max_results(value: Any, default: int = 5) -> int:
    """安全解析最大候选数，并限制在 1-5。"""
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(numeric, 5))


def _labels(language_code: str) -> dict[str, Any]:
    """Get localized labels for reporting."""
    if language_code == "zh":
        return {
            "title": "机构级投资研究报告",
            "subtitle": "研究终端 / 投资决策备忘录",
            "sections": {
                "executive": "一、执行结论",
                "market": "二、市场环境与风控",
                "scoreboard": "三、候选池评分板",
                "cards": "四、逐票研究卡",
                "risk": "五、风险与执行方案",
            },
            "table_headers": ["Ticker", "综合评分", "适配度", "估值", "质量", "动量", "风险控制", "结论"],
            "risk_titles": {
                "macro": "宏观环境",
                "audit": "审计与偿债",
                "news": "新闻与情绪",
                "execution": "执行约束",
            },
            "verdicts": {
                "strong_buy": "优先买入",
                "accumulate": "分批布局",
                "hold_watch": "继续观察",
                "avoid": "回避",
                "veto_avoid": "一票否决 / 回避",
            },
            "market_stance": {
                "defensive": "防守优先，等待更好入场位",
                "selective": "可精选布局，分批执行",
            },
            "alignment": {
                "aligned": "一致",
                "mixed": "分化",
                "unclear": "暂不清晰",
            },
            "metric_labels": {
                "fit": "策略适配度",
                "valuation": "估值",
                "quality": "质量",
                "momentum": "动量",
                "sentiment": "情绪",
                "risk": "风险控制",
                "allocation": "建议仓位",
            },
            "empty": "暂无可展示内容。",
        }
    return {
        "title": "Institutional Investment Research Report",
        "subtitle": "Research terminal / portfolio decision memo",
        "sections": {
            "executive": "1. Executive Verdict",
            "market": "2. Market Regime & Risk",
            "scoreboard": "3. Candidate Scoreboard",
            "cards": "4. Ticker Research Cards",
            "risk": "5. Risk Register & Execution",
        },
        "table_headers": ["Ticker", "Composite", "Fit", "Valuation", "Quality", "Momentum", "Risk Control", "Verdict"],
        "risk_titles": {
            "macro": "Macro regime",
            "audit": "Audit and solvency",
            "news": "News and sentiment",
            "execution": "Execution constraint",
        },
        "verdicts": {
            "strong_buy": "Strong Buy",
            "accumulate": "Accumulate",
            "hold_watch": "Hold / Watch",
            "avoid": "Avoid",
            "veto_avoid": "Veto / Avoid",
        },
        "market_stance": {
            "defensive": "Defensive, wait for better entries",
            "selective": "Selective deployment with staged entries",
        },
        "alignment": {
            "aligned": "Aligned",
            "mixed": "Mixed",
            "unclear": "Unclear",
        },
        "metric_labels": {
            "fit": "Mandate fit",
            "valuation": "Valuation",
            "quality": "Quality",
            "momentum": "Momentum",
            "sentiment": "Sentiment",
            "risk": "Risk control",
            "allocation": "Suggested allocation",
        },
        "empty": "No content available.",
    }


def _language_label(language_code: str) -> str:
    """Get language display name."""
    return "Chinese (Simplified)" if language_code == "zh" else "English"


def _score_guide(language_code: str) -> dict[str, str]:
    """返回前端悬浮说明使用的评分定义与公式。"""
    if language_code == "zh":
        return {
            "composite": "综合评分：用于排序。公式=估值20%+质量24%+动量16%+新闻情绪12%+风险16%+目标匹配度12%。",
            "fit": "匹配度：衡量该股票与用户目标（风险、期限、风格、筛选约束）的贴合程度，范围 0-100。",
            "valuation": "估值：主要由 PE 与分析师评级映射，估值越合理分数越高。",
            "quality": "质量：由 ROE、利润率、市值稳定性和分红能力综合得到。",
            "momentum": "动量：由近5日价格变化与技术倾向（看多/看空）共同映射，50 为中性。",
            "risk": "风险：结合审计/偿债、杠杆、现金流与宏观环境，高分代表风险更可控。",
        }
    return {
        "composite": "Composite score for ranking = Valuation 20% + Quality 24% + Momentum 16% + News Sentiment 12% + Risk 16% + Mandate Fit 12%.",
        "fit": "Mandate fit measures alignment with user constraints (risk, horizon, style, filters), scaled 0-100.",
        "valuation": "Valuation is mainly mapped from PE and analyst stance; more reasonable valuation scores higher.",
        "quality": "Quality combines ROE, profit margin, scale stability, and dividend capacity.",
        "momentum": "Momentum is mapped from recent 5-day price move plus technical stance (bullish/bearish); 50 is neutral.",
        "risk": "Risk combines audit/solvency, leverage, cash flow, and macro regime; higher means better risk control.",
    }


def _format_scalar(value: Any) -> str:
    """Format a scalar value for display."""
    if value is None or value == "":
        return "N/A"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"
    return str(value)


def _ordered_snapshots(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Order ticker snapshots by comparison matrix priority.

    Args:
        analysis: Analysis dictionary with ticker_snapshots and comparison_matrix

    Returns:
        Ordered list of snapshots, prioritized by comparison matrix
    """
    snapshots = analysis.get("ticker_snapshots", []) or []
    ordered: list[dict[str, Any]] = []
    snapshot_map = {
        str(snapshot.get("ticker", "")).upper(): snapshot
        for snapshot in snapshots
        if snapshot.get("ticker")
    }
    seen: set[str] = set()

    # First add tickers from comparison matrix
    for item in analysis.get("comparison_matrix", []) or []:
        ticker = str(item.get("Ticker", "")).upper()
        snapshot = snapshot_map.get(ticker)
        if snapshot and ticker not in seen:
            ordered.append(snapshot)
            seen.add(ticker)

    # Then add remaining snapshots
    for snapshot in snapshots:
        ticker = str(snapshot.get("ticker", "")).upper()
        if ticker and ticker not in seen:
            ordered.append(snapshot)
            seen.add(ticker)
    return ordered


def _build_merged_data_package(query: str, intent: Any, analysis: dict[str, Any]) -> dict[str, Any]:
    """Build merged data package for LLM consumption.

    Args:
        query: Original user query
        intent: ParsedIntent with investment parameters
        analysis: Analysis results from screening phase

    Returns:
        Structured data package with all derived profiles
    """
    max_results = _safe_max_results((analysis.get("debug_summary") or {}).get("requested_max_results"))
    ordered_snapshots = _ordered_snapshots(analysis)[:max_results]
    language_code = intent.system_context.language
    price_data: list[dict[str, Any]] = []
    tech_data: list[dict[str, Any]] = []
    smart_data: list[dict[str, Any]] = []
    audit_data: list[dict[str, Any]] = []
    news_data: list[dict[str, Any]] = []

    for snapshot in ordered_snapshots:
        ticker = str(snapshot.get("ticker", "")).upper()
        quant = snapshot.get("quant", {}) or {}
        price = snapshot.get("price", {}) or {}

        # Derive profiles
        tech_profile = _derive_tech_profile(snapshot.get("technical", {}) or {}, language_code)
        smart_profile = _derive_smart_money_profile(snapshot.get("smart_money", {}) or {}, language_code)
        audit_profile = _derive_audit_profile(snapshot.get("audit", {}) or {}, language_code)

        # Handle news profile
        news_status = str(snapshot.get("news_status") or "").strip().lower()
        if news_status == "historical_data_unavailable":
            news_profile = {
                "Ticker": ticker,
                "Headline_Sentiment_Score": 0,
                "Headline_Sentiment_Label": "历史不可用" if language_code == "zh" else "Historical Unavailable",
                "Catalysts": [],
                "Latest_Headlines": [],
                "Latest_Published_At": [],
                "Latest_Links": [],
                "News_Items": [],
                "News_Source": "historical_unavailable",
                "Narrative": (
                    f"截至 {snapshot.get('research_as_of_date') or 'N/A'}，历史新闻不可用。"
                    if language_code == "zh"
                    else f"Historical news is unavailable as of {snapshot.get('research_as_of_date') or 'N/A'}."
                ),
            }
        else:
            news_profile = _derive_news_profile(ticker, snapshot.get("news", []) or [], language_code)

        # Common fields
        common = {
            "Ticker": ticker,
            "Company_Name": snapshot.get("company_name"),
            "Issuer_Name": quant.get("Issuer_Name") or snapshot.get("company_name"),
            "Share_Class": quant.get("Share_Class"),
            "Sector": snapshot.get("sector"),
        }

        # Append to respective data lists
        price_data.append(
            {
                **common,
                "Latest_Price": price.get("Latest_Price"),
                "Trend_5D": price.get("Trend_5D"),
                "Total_Quant_Score": quant.get("Total_Quant_Score"),
                "PE_Ratio": quant.get("PE_Ratio"),
                "ROE": quant.get("ROE"),
                "Dividend_Yield": quant.get("Dividend_Yield"),
                "Analyst_Rating": quant.get("Analyst_Rating"),
                "Market_Cap": quant.get("Market_Cap"),
                "Profit_Margin": quant.get("Profit_Margin"),
                "Debt_to_Equity": quant.get("Debt_to_Equity"),
                "Current_Ratio": quant.get("Current_Ratio"),
                "Free_Cash_Flow": quant.get("Free_Cash_Flow"),
                "Revenue_Growth_QoQ": quant.get("Revenue_Growth_QoQ"),
                "Status": price.get("Status", "Unavailable"),
            }
        )
        tech_data.append({**common, **tech_profile})
        smart_data.append({**common, **smart_profile})
        audit_data.append({**common, **audit_profile})
        news_data.append({**common, **news_profile})

    return {
        "Intent_Context": {
            "Capital_Amount": intent.portfolio_sizing.capital_amount,
            "Currency": intent.portfolio_sizing.currency,
            "Risk_Tolerance": intent.risk_profile.tolerance_level,
            "Investment_Horizon": intent.investment_strategy.horizon,
            "Investment_Style": intent.investment_strategy.style,
            "Preferred_Sectors": intent.investment_strategy.preferred_sectors,
            "Preferred_Industries": intent.investment_strategy.preferred_industries,
            "Fundamental_Filters": intent.fundamental_filters.model_dump(),
            "Explicit_Tickers": intent.explicit_targets.tickers,
        },
        "Screening_Summary": {
            "Selected_Ticker_Count": len(price_data),
            "Requested_Max_Results": max_results,
            "Allocation_Mode": (analysis.get("debug_summary") or {}).get("allocation_mode", "score_weighted"),
            "Custom_Weights": (analysis.get("debug_summary") or {}).get("custom_weights", {}),
            "Live_Data_Enabled": analysis.get("debug_summary", {}).get("live_data_enabled"),
            "Source_Query": query,
            "Market_Data_Status": analysis.get("market_data_status", {}),
            "Research_Mode": analysis.get("debug_summary", {}).get("research_mode", "realtime"),
            "As_Of_Date": analysis.get("debug_summary", {}).get("as_of_date"),
            "Warning_Flags": analysis.get("debug_summary", {}).get("warning_flags", []),
        },
        "Macro_Data": analysis.get("macro_data", {}) or {},
        "Price_Data": price_data,
        "Tech_Data": tech_data,
        "Smart_Data": smart_data,
        "Audit_Data": audit_data,
        "News_Data": news_data,
    }


def _build_report_input(query: str, intent: Any, merged_data_package: dict[str, Any]) -> dict[str, Any]:
    """Build input dictionary for LLM report generation."""
    return {
        "User Financial Query": query,
        "System Target Language": _language_label(intent.system_context.language),
        "Merged Data Package": merged_data_package,
    }


def _market_stance(language_code: str, severe: bool) -> str:
    """Get market stance recommendation."""
    key = "defensive" if severe else "selective"
    return _labels(language_code)["market_stance"][key]


def _alignment_label(language_code: str, alignment: str) -> str:
    """Localize alignment label."""
    return _labels(language_code)["alignment"].get(alignment, alignment)


def _build_report_briefing(query: str, intent: Any, merged_data_package: dict[str, Any]) -> dict[str, Any]:
    """Build structured report briefing with all calculated scores.

    This function:
    1. Maps ticker data to derive profiles
    2. Calculates scores for each candidate
    3. Determines verdicts and allocations
    4. Builds executive summary and risk register

    Args:
        query: Original user query
        intent: ParsedIntent with investment parameters
        merged_data_package: Merged data with all profiles

    Returns:
        Structured briefing with meta, executive, macro, scoreboard, ticker_cards, risk_register, charts
    """
    language_code = intent.system_context.language
    labels = _labels(language_code)
    macro_data = merged_data_package.get("Macro_Data", {}) or {}
    price_rows = merged_data_package.get("Price_Data", []) or []

    # Build ticker maps for profile lookup
    tech_map = {str(item.get("Ticker", "")).upper(): item for item in merged_data_package.get("Tech_Data", [])}
    smart_map = {str(item.get("Ticker", "")).upper(): item for item in merged_data_package.get("Smart_Data", [])}
    audit_map = {str(item.get("Ticker", "")).upper(): item for item in merged_data_package.get("Audit_Data", [])}
    news_map = {str(item.get("Ticker", "")).upper(): item for item in merged_data_package.get("News_Data", [])}

    # Build candidate analyses
    candidates: list[dict[str, Any]] = []
    for price_row in price_rows:
        ticker = str(price_row.get("Ticker", "")).upper()
        candidates.append(
            _build_candidate_analysis(
                language_code,
                intent,
                macro_data,
                price_row,
                tech_map.get(ticker, {}),
                smart_map.get(ticker, {}),
                audit_map.get(ticker, {}),
                news_map.get(ticker, {}),
            )
        )

    # Sort candidates by composite score
    candidates.sort(key=lambda item: item["composite_score"], reverse=True)

    # Build screening summary
    screening_summary = merged_data_package.get("Screening_Summary", {}) or {}
    requested_max_results = _safe_max_results(
        screening_summary.get("Requested_Max_Results"),
        default=len(candidates) or 5,
    )
    allocation_mode = str(screening_summary.get("Allocation_Mode") or "score_weighted").strip().lower()
    custom_weights = screening_summary.get("Custom_Weights")
    if not isinstance(custom_weights, dict):
        custom_weights = {}
    research_mode = str(screening_summary.get("Research_Mode") or "realtime")
    as_of_date = screening_summary.get("As_Of_Date")
    warning_flags = screening_summary.get("Warning_Flags") or []

    # Determine overall state
    severe_macro = _macro_is_severe(macro_data)
    top_pick = next((item for item in candidates if not item["veto"]), candidates[0] if candidates else None)
    watchlist = [item["ticker"] for item in candidates if not item["veto"]][1:4]
    avoid_list = [item["ticker"] for item in candidates if item["veto"] or item["verdict_key"] == "avoid"]
    allocation_plan = _build_allocation_plan(
        candidates,
        max_positions=requested_max_results,
        allocation_mode=allocation_mode,
        custom_weights=custom_weights,
    )
    mandate_fit = round(sum(item["suitability_score"] for item in candidates) / len(candidates), 1) if candidates else 0.0

    # Build mandate summary
    if language_code == "zh":
        mandate_summary = (
            f"资金={intent.portfolio_sizing.capital_amount or 'N/A'} {intent.portfolio_sizing.currency or 'USD'}，"
            f"风险偏好={intent.risk_profile.tolerance_level or 'N/A'}，"
            f"投资期限={intent.investment_strategy.horizon or 'N/A'}，"
            f"投资风格={intent.investment_strategy.style or 'N/A'}"
        )
    else:
        mandate_summary = (
            f"Capital={intent.portfolio_sizing.capital_amount or 'N/A'} "
            f"{intent.portfolio_sizing.currency or 'USD'}, "
            f"Risk={intent.risk_profile.tolerance_level or 'N/A'}, "
            f"Horizon={intent.investment_strategy.horizon or 'N/A'}, "
            f"Style={intent.investment_strategy.style or 'N/A'}"
        )

    # Build executive calls
    if language_code == "zh":
        primary_call = (
            f"当前最匹配的候选是 {top_pick['ticker']}，建议结论为\"{top_pick['verdict_label']}\"。"
            if top_pick
            else "当前没有足够匹配投资目标的候选。"
        )
        action_summary = "优先配置高质量、低杠杆、分红稳定的标的，采用分批入场而不是一次性重仓。"
        risk_headline = (
            f"系统性风险提示：{macro_data.get('Systemic_Risk_Warning') or '当前未检测到强烈的宏观 veto。'}"
            if severe_macro
            else "当前未检测到会直接推翻策略的宏观 veto。"
        )
    else:
        primary_call = (
            f"The best-fit candidate is {top_pick['ticker']} with a '{top_pick['verdict_label']}' stance."
            if top_pick
            else "No candidate is sufficiently aligned with the current mandate."
        )
        action_summary = "Favor high-quality, lower-risk names and deploy capital in stages rather than forcing full-size entries."
        risk_headline = (
            f"Systemic risk warning: {macro_data.get('Systemic_Risk_Warning') or 'Macro regime is still defensive.'}"
            if severe_macro
            else "No macro veto is currently strong enough to override strategy."
        )

    # Build risk register
    risk_register = [
        {
            "category": labels["risk_titles"]["macro"],
            "severity": "high" if severe_macro else "medium",
            "summary": risk_headline,
        }
    ]
    for item in candidates:
        if item["veto"]:
            risk_register.append(
                {
                    "category": labels["risk_titles"]["audit"],
                    "severity": "high",
                    "ticker": item["ticker"],
                    "summary": item["audit_summary"],
                }
            )
        elif item["alignment"] == _alignment_label(language_code, "mixed"):
            risk_register.append(
                {
                    "category": labels["risk_titles"]["news"],
                    "severity": "medium",
                    "ticker": item["ticker"],
                    "summary": (
                        f"{item['ticker']}: 技术面与新闻叙事存在分化。"
                        if language_code == "zh"
                        else f"{item['ticker']}: technicals and news are not aligned."
                    ),
                }
            )

    return {
        "meta": {
            "title": labels["title"],
            "subtitle": labels["subtitle"],
            "language": language_code,
            "query": query,
            "ticker_count": len(candidates),
            "requested_max_results": requested_max_results,
            "allocation_mode": allocation_mode,
            "report_mode": None,
            "sections": labels["sections"],
            "table_headers": labels["table_headers"],
            "mandate_summary": mandate_summary,
            "assumptions": intent.agent_control.assumptions,
            "score_guide": _score_guide(language_code),
            "research_mode": research_mode,
            "as_of_date": as_of_date,
            "warning_flags": warning_flags,
            "data_provenance": {
                "source": screening_summary.get("Market_Data_Status", {}).get("source"),
                "records": screening_summary.get("Market_Data_Status", {}).get("records"),
                "last_refresh_at": screening_summary.get("Market_Data_Status", {}).get("last_refresh_at"),
                "research_mode": research_mode,
                "as_of_date": as_of_date,
                "warning_flags": warning_flags,
            },
        },
        "executive": {
            "primary_call": primary_call,
            "market_stance": _market_stance(language_code, severe_macro),
            "mandate_fit_score": mandate_fit,
            "top_pick": top_pick["ticker"] if top_pick else None,
            "top_pick_verdict": top_pick["verdict_label"] if top_pick else None,
            "watchlist": watchlist,
            "avoid_list": avoid_list,
            "action_summary": action_summary,
            "allocation_plan": allocation_plan,
            "allocation_mode": allocation_mode,
        },
        "screening_summary": {
            "requested_max_results": requested_max_results,
            "selected_ticker_count": len(candidates),
            "allocation_mode": allocation_mode,
            "custom_weights": custom_weights,
        },
        "macro": {
            "regime": macro_data.get("Global_Regime")
            or macro_data.get("Status")
            or ("未知" if language_code == "zh" else "Unknown"),
            "warning_text": macro_data.get("Systemic_Risk_Warning") or ("暂无" if language_code == "zh" else "N/A"),
            "risk_headline": risk_headline,
            "vix": macro_data.get("VIX_Volatility_Index"),
            "sp500": macro_data.get("SP500_Level"),
            "us10y": macro_data.get("US10Y_Treasury_Yield"),
            "severe_warning": severe_macro,
        },
        "scoreboard": candidates,
        "ticker_cards": candidates,
        "risk_register": risk_register,
        "charts": {
            "ranking": [
                {
                    "ticker": item["ticker"],
                    "score": item["composite_score"],
                    "fit": item["suitability_score"],
                    "verdict": item["verdict_label"],
                }
                for item in candidates
            ],
            "dimensions": [
                {
                    "ticker": item["ticker"],
                    "valuation": item["valuation_score"],
                    "quality": item["quality_score"],
                    "momentum": item["momentum_score"],
                    "sentiment": item["sentiment_score"],
                    "risk": item["risk_score"],
                    "fit": item["suitability_score"],
                }
                for item in candidates
            ],
            "allocation": allocation_plan,
        },
    }


def _build_report_system_prompt(language_code: str) -> str:
    """Build system prompt for LLM report generation."""
    labels = _labels(language_code)
    sections = labels["sections"]
    table_headers = " | ".join(labels["table_headers"])
    language_name = _language_label(language_code)
    return (
        "You are a Tier-1 hedge fund portfolio manager writing an institutional-grade investment memo. "
        f"Write the entire report in {language_name}. "
        "Do not hallucinate any number or narrative not present in the JSON package. "
        "Do not drop any ticker from Price_Data. "
        "Keep output in Markdown only. Do not start with fenced code blocks. "
        "Use this exact structure:\n"
        f"# {labels['title']}\n"
        f"## {sections['executive']}\n"
        f"## {sections['market']}\n"
        f"## {sections['scoreboard']}\n"
        f"## {sections['cards']}\n"
        f"## {sections['risk']}\n"
        f"For the scoreboard table, use this localized header row exactly: {table_headers}. "
        "Each ticker card must clearly state thesis, technical/news read-through, audit risk, and execution stance."
    )


def _build_report_user_prompt(query: str, intent: Any, merged_data_package: dict[str, Any]) -> str:
    """Build user prompt for LLM report generation."""
    payload = _build_report_input(query, intent, merged_data_package)
    return (
        "[SYSTEM CONTEXT]\n"
        "Generate a professional investment memo from the following data package.\n\n"
        "[OUTPUT CONTRACT]\n"
        "- Strict language lock.\n"
        "- Analyze every ticker in Price_Data.\n"
        "- No greetings or extra commentary.\n"
        "- No fabricated numbers.\n\n"
        "[INPUT JSON]\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _validate_report_output(report: str, intent: Any, report_briefing: dict[str, Any]) -> str | None:
    """Validate LLM-generated report.

    Checks:
    - Report is not empty
    - No code blocks in output
    - All required sections present
    - All tickers mentioned in report

    Args:
        report: Generated report text
        intent: ParsedIntent with language setting
        report_briefing: Briefing with expected content

    Returns:
        Error message if validation fails, None if valid
    """
    language_code = intent.system_context.language

    if not report.strip():
        return "LLM 未返回任何报告内容。" if language_code == "zh" else "LLM returned an empty report."

    if "```" in report:
        return (
            "LLM 输出了代码块，不符合报告格式要求。"
            if language_code == "zh"
            else "LLM returned fenced code blocks, which violates report format requirements."
        )

    labels = _labels(intent.system_context.language)
    sections = labels["sections"]
    required_headers = [
        f"# {labels['title']}",
        f"## {sections['executive']}",
        f"## {sections['market']}",
        f"## {sections['scoreboard']}",
        f"## {sections['cards']}",
        f"## {sections['risk']}",
    ]

    for header in required_headers:
        if header not in report:
            return (
                f"LLM 输出缺少固定标题：{header}"
                if language_code == "zh"
                else f"LLM output is missing a required section header: {header}"
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


def _build_rule_based_report(intent: Any, report_briefing: dict[str, Any]) -> str:
    """Build report using rule-based template (no LLM).

    This is a fallback when LLM is unavailable or as a reference output.

    Args:
        intent: ParsedIntent with language setting
        report_briefing: Structured briefing with all calculated data

    Returns:
        Markdown-formatted report string
    """
    language_code = intent.system_context.language
    labels = _labels(language_code)
    sections = labels["sections"]
    meta = report_briefing.get("meta", {})
    executive = report_briefing.get("executive", {})
    macro = report_briefing.get("macro", {})
    scoreboard = report_briefing.get("scoreboard", [])
    ticker_cards = report_briefing.get("ticker_cards", [])
    risk_register = report_briefing.get("risk_register", [])

    # Build localized field labels
    if language_code == "zh":
        fallback_na = "暂无"
        field_labels = {
            "market_stance": "市场观点",
            "top_pick": "优先关注",
            "watchlist": "关注名单",
            "avoid_list": "回避名单",
            "action_summary": "执行摘要",
            "regime": "市场环境",
            "sp500": "标普 500",
            "us10y": "美国10年国债收益率",
            "risk_headline": "风险提示",
            "thesis": "投资逻辑",
            "fit_reason": "匹配原因",
            "technical_news": "技术面 / 新闻",
            "smart_money": "资金面代理",
            "audit": "审计",
            "catalysts": "催化因素",
            "execution": "执行建议",
            "risk_prefix": "风险",
        }
    else:
        fallback_na = "N/A"
        field_labels = {
            "market_stance": "Market Stance",
            "top_pick": "Top Pick",
            "watchlist": "Watchlist",
            "avoid_list": "Avoid List",
            "action_summary": "Action Summary",
            "regime": "Regime",
            "sp500": "S&P 500",
            "us10y": "US 10Y",
            "risk_headline": "Risk Headline",
            "thesis": "Thesis",
            "fit_reason": "Fit Reason",
            "technical_news": "Technical / News",
            "smart_money": "Smart Money",
            "audit": "Audit",
            "catalysts": "Catalysts",
            "execution": "Execution",
            "risk_prefix": "Risk",
        }

    # Build report lines
    lines = [f"# {meta.get('title', labels['title'])}", ""]
    lines.extend(
        [
            f"## {sections['executive']}",
            f"- {executive.get('primary_call', labels['empty'])}",
            f"- {labels['metric_labels']['fit']}: {_format_scalar(executive.get('mandate_fit_score'))}",
            f"- {field_labels['market_stance']}: {executive.get('market_stance', fallback_na)}",
            f"- {field_labels['top_pick']}: {_format_scalar(executive.get('top_pick'))} / {_format_scalar(executive.get('top_pick_verdict'))}",
            f"- {field_labels['watchlist']}: {', '.join(executive.get('watchlist', [])) or fallback_na}",
            f"- {field_labels['avoid_list']}: {', '.join(executive.get('avoid_list', [])) or fallback_na}",
            f"- {field_labels['action_summary']}: {executive.get('action_summary', labels['empty'])}",
            "",
            f"## {sections['market']}",
            f"- {field_labels['regime']}: {_format_scalar(macro.get('regime'))}",
            f"- VIX: {_format_scalar(macro.get('vix'))}",
            f"- {field_labels['sp500']}: {_format_scalar(macro.get('sp500'))}",
            f"- {field_labels['us10y']}: {_format_scalar(macro.get('us10y'))}",
            f"- {field_labels['risk_headline']}: {macro.get('risk_headline', labels['empty'])}",
            "",
            f"## {sections['scoreboard']}",
            f"| {' | '.join(labels['table_headers'])} |",
            f"| {' | '.join(['---'] * len(labels['table_headers']))} |",
        ]
    )

    # Add scoreboard table rows
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
                    str(item.get("verdict_label", fallback_na)),
                ]
            )
            + " |"
        )

    # Add ticker cards
    lines.extend(["", f"## {sections['cards']}"])
    for item in ticker_cards:
        lines.extend(
            [
                f"### {item.get('ticker', 'N/A')} - {item.get('verdict_label', 'N/A')}",
                f"- {field_labels['thesis']}: {item.get('thesis', labels['empty'])}",
                f"- {field_labels['fit_reason']}: {item.get('fit_reason', labels['empty'])}",
                f"- {field_labels['technical_news']}: {item.get('technical_summary', fallback_na)} | {item.get('news_label', fallback_na)} | {item.get('alignment', fallback_na)}",
                f"- {field_labels['smart_money']}: {item.get('smart_money_positioning', fallback_na)}",
                f"- {field_labels['audit']}: {item.get('audit_summary', fallback_na)}",
                f"- {field_labels['catalysts']}: {', '.join(item.get('catalysts', [])) or fallback_na}",
                f"- {field_labels['execution']}: {item.get('execution', labels['empty'])}",
            ]
        )

    # Add risk register
    lines.extend(["", f"## {sections['risk']}"])
    for item in risk_register:
        prefix = f"{item.get('category', field_labels['risk_prefix'])}"
        if item.get("ticker"):
            prefix = f"{prefix} / {item['ticker']}"
        lines.append(f"- {prefix}: {item.get('summary', labels['empty'])}")

    # Add allocation plan
    allocation_plan = executive.get("allocation_plan", [])
    if allocation_plan:
        lines.append(f"- {labels['metric_labels']['allocation']}:")
        for item in allocation_plan:
            lines.append(f"  {item.get('ticker')}: {_format_scalar(item.get('weight'))}%")

    return "\n".join(lines)
