from __future__ import annotations

import json
import re
from typing import Any

from .models import ParsedIntent


POSITIVE_HEADLINE_KEYWORDS = (
    "beat",
    "beats",
    "strong",
    "surge",
    "record",
    "growth",
    "upgrade",
    "approval",
    "approved",
    "partnership",
    "raises",
    "buyback",
    "dividend",
    "bullish",
)

NEGATIVE_HEADLINE_KEYWORDS = (
    "miss",
    "drop",
    "falls",
    "lawsuit",
    "probe",
    "downgrade",
    "warning",
    "fraud",
    "bankruptcy",
    "default",
    "layoff",
    "decline",
    "weak",
)

SMART_MONEY_HOT_SIGNALS = ("highly institutionalized", "heavy bearish betting", "short squeeze")


def _labels(language_code: str) -> dict[str, Any]:
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
    return "Chinese (Simplified)" if language_code == "zh" else "English"


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("%", "").replace(",", "").strip()
        if not cleaned or cleaned.upper() in {"N/A", "NONE", "NULL"}:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _coerce_percent_points(value: Any) -> float | None:
    number = _coerce_float(value)
    if number is None:
        return None
    if isinstance(value, str) and "%" in value:
        return number
    if abs(number) <= 1.0:
        return number * 100
    return number


def _format_scalar(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"
    return str(value)


def _headline_score(title: str) -> int:
    lowered = title.lower()
    score = 0
    score += sum(1 for token in POSITIVE_HEADLINE_KEYWORDS if token in lowered)
    score -= sum(1 for token in NEGATIVE_HEADLINE_KEYWORDS if token in lowered)
    return score


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _ordered_snapshots(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots = analysis.get("ticker_snapshots", []) or []
    ordered: list[dict[str, Any]] = []
    snapshot_map = {
        str(snapshot.get("ticker", "")).upper(): snapshot
        for snapshot in snapshots
        if snapshot.get("ticker")
    }
    seen: set[str] = set()

    for item in analysis.get("comparison_matrix", []) or []:
        ticker = str(item.get("Ticker", "")).upper()
        snapshot = snapshot_map.get(ticker)
        if snapshot and ticker not in seen:
            ordered.append(snapshot)
            seen.add(ticker)

    for snapshot in snapshots:
        ticker = str(snapshot.get("ticker", "")).upper()
        if ticker and ticker not in seen:
            ordered.append(snapshot)
            seen.add(ticker)
    return ordered


def _derive_news_profile(ticker: str, news_items: list[dict[str, Any]]) -> dict[str, Any]:
    headlines = [str(item.get("title", "")).strip() for item in news_items if str(item.get("title", "")).strip()]
    timestamps = [str(item.get("published_at", "")).strip() for item in news_items[:3]]
    if not headlines:
        return {
            "Ticker": ticker,
            "Headline_Sentiment_Score": 0,
            "Headline_Sentiment_Label": "No Coverage",
            "Catalysts": [],
            "Latest_Headlines": [],
            "Latest_Published_At": [],
            "Narrative": "No recent headlines available.",
        }

    total_score = sum(_headline_score(title) for title in headlines[:5])
    if total_score >= 2:
        label = "Positive"
    elif total_score <= -2:
        label = "Negative"
    elif total_score == 0:
        label = "Neutral"
    else:
        label = "Mixed"

    return {
        "Ticker": ticker,
        "Headline_Sentiment_Score": total_score,
        "Headline_Sentiment_Label": label,
        "Catalysts": headlines[:3],
        "Latest_Headlines": headlines[:3],
        "Latest_Published_At": timestamps,
        "Narrative": f"{label} headline tone from the latest news set.",
    }


def _derive_tech_profile(technical: dict[str, Any]) -> dict[str, Any]:
    status = str(technical.get("Status") or "Unavailable")
    latest_price = _coerce_float(technical.get("Latest_Price"))
    ma_20 = _coerce_float(technical.get("MA_20"))
    ma_50 = _coerce_float(technical.get("MA_50"))
    rsi_14 = _coerce_float(technical.get("RSI_14"))

    if status != "Success":
        summary = status
        lowered = status.lower()
        if "too many requests" in lowered or "temporarily unavailable" in lowered:
            summary = "Technical data is temporarily unavailable because the live provider is rate-limited."
        elif lowered.startswith("cached"):
            summary = "Technical data is currently served from the latest successful cache."
        return {
            "Latest_Price": technical.get("Latest_Price"),
            "Trend_5D": technical.get("Trend_5D"),
            "Tech_Sentiment": "Unavailable",
            "Tech_Signal_Summary": summary,
        }

    bullish = 0
    bearish = 0
    signals: list[str] = []

    if latest_price is not None and ma_20 is not None and ma_50 is not None:
        if latest_price > ma_20 > ma_50:
            bullish += 2
            signals.append("Price > MA20 > MA50")
        elif latest_price < ma_20 < ma_50:
            bearish += 2
            signals.append("Price < MA20 < MA50")
        elif latest_price > ma_20:
            bullish += 1
            signals.append("Price above MA20")
        elif latest_price < ma_20:
            bearish += 1
            signals.append("Price below MA20")

    if rsi_14 is not None:
        if rsi_14 >= 70:
            bearish += 1
            signals.append(f"RSI {rsi_14:.1f} overbought")
        elif rsi_14 <= 30:
            bullish += 1
            signals.append(f"RSI {rsi_14:.1f} rebound zone")
        elif rsi_14 >= 55:
            bullish += 1
            signals.append(f"RSI {rsi_14:.1f} supports momentum")
        elif rsi_14 <= 45:
            bearish += 1
            signals.append(f"RSI {rsi_14:.1f} is soft")

    if bullish > bearish:
        sentiment = "Bullish"
    elif bearish > bullish:
        sentiment = "Bearish"
    else:
        sentiment = "Neutral"

    return {
        "Latest_Price": technical.get("Latest_Price"),
        "Trend_5D": technical.get("Trend_5D"),
        "Tech_Sentiment": sentiment,
        "Tech_Signal_Summary": "; ".join(signals) if signals else "Technical posture is mixed.",
    }


def _derive_smart_money_profile(smart_money: dict[str, Any]) -> dict[str, Any]:
    signal = str(smart_money.get("Smart_Money_Signal") or smart_money.get("Status") or "Unavailable")
    status = str(smart_money.get("Status") or "")
    lowered_status = status.lower()
    if "too many requests" in lowered_status or "temporarily unavailable" in lowered_status:
        signal = "Public positioning proxy is temporarily unavailable because the live provider is rate-limited."
    elif lowered_status.startswith("cached"):
        signal = "Public positioning proxy is served from the latest successful cache."
    lowered = signal.lower()
    return {
        "Smart_Money_Positioning": signal,
        "Highlight_Flag": any(token in lowered for token in SMART_MONEY_HOT_SIGNALS),
    }


def _derive_audit_profile(audit: dict[str, Any]) -> dict[str, Any]:
    status = str(audit.get("Status") or "Unavailable")
    risk_level = str(audit.get("Overall_Risk_Level") or status or "Unavailable")
    current_ratio = _coerce_float(audit.get("Current_Ratio"))
    retained_earnings = _coerce_float(audit.get("Retained_Earnings_B"))
    risk_flags = [str(flag) for flag in (audit.get("Risk_Flags") or []) if str(flag).strip()]
    filing_summary = str(audit.get("Recent_Filing_Summary") or "").strip()
    latest_filing_date = audit.get("Latest_Filing_Date")

    severe_warning = False
    if risk_level.lower() in {"high risk", "severe", "critical"}:
        severe_warning = True
    if current_ratio is not None and current_ratio < 1.0:
        severe_warning = True
    if retained_earnings is not None and retained_earnings < -1.0:
        severe_warning = True
    if any("liquidity" in flag.lower() or "default" in flag.lower() for flag in risk_flags):
        severe_warning = True

    if status != "Success":
        text = status
    elif severe_warning:
        text = (
            f"Liquidity / solvency warning. D/E {_format_scalar(audit.get('Debt_to_Equity'))}, "
            f"Current Ratio {_format_scalar(audit.get('Current_Ratio'))}, "
            f"Retained Earnings {_format_scalar(audit.get('Retained_Earnings_B'))}B."
        )
    elif risk_level.lower() == "medium risk":
        text = (
            f"Moderate balance-sheet caution. D/E {_format_scalar(audit.get('Debt_to_Equity'))}, "
            f"Current Ratio {_format_scalar(audit.get('Current_Ratio'))}, "
            f"Retained Earnings {_format_scalar(audit.get('Retained_Earnings_B'))}B."
        )
    else:
        text = (
            f"No major audit veto. D/E {_format_scalar(audit.get('Debt_to_Equity'))}, "
            f"Current Ratio {_format_scalar(audit.get('Current_Ratio'))}, "
            f"Retained Earnings {_format_scalar(audit.get('Retained_Earnings_B'))}B."
        )

    if filing_summary:
        text = f"{text} Recent filings: {filing_summary}."

    return {
        "Overall_Risk_Level": risk_level,
        "Current_Ratio": audit.get("Current_Ratio"),
        "Audit_Text": text,
        "Severe_Audit_Warning": severe_warning,
        "Risk_Flags": risk_flags,
        "Recent_Filing_Summary": filing_summary,
        "Latest_Filing_Date": latest_filing_date,
    }


def _build_merged_data_package(query: str, intent: ParsedIntent, analysis: dict[str, Any]) -> dict[str, Any]:
    ordered_snapshots = _ordered_snapshots(analysis)
    price_data: list[dict[str, Any]] = []
    tech_data: list[dict[str, Any]] = []
    smart_data: list[dict[str, Any]] = []
    audit_data: list[dict[str, Any]] = []
    news_data: list[dict[str, Any]] = []

    for snapshot in ordered_snapshots:
        ticker = str(snapshot.get("ticker", "")).upper()
        quant = snapshot.get("quant", {}) or {}
        price = snapshot.get("price", {}) or {}
        tech_profile = _derive_tech_profile(snapshot.get("technical", {}) or {})
        smart_profile = _derive_smart_money_profile(snapshot.get("smart_money", {}) or {})
        audit_profile = _derive_audit_profile(snapshot.get("audit", {}) or {})
        news_profile = _derive_news_profile(ticker, snapshot.get("news", []) or [])
        common = {
            "Ticker": ticker,
            "Company_Name": snapshot.get("company_name"),
            "Sector": snapshot.get("sector"),
        }

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
            "Live_Data_Enabled": analysis.get("debug_summary", {}).get("live_data_enabled"),
            "Source_Query": query,
            "Market_Data_Status": analysis.get("market_data_status", {}),
        },
        "Macro_Data": analysis.get("macro_data", {}) or {},
        "Price_Data": price_data,
        "Tech_Data": tech_data,
        "Smart_Data": smart_data,
        "Audit_Data": audit_data,
        "News_Data": news_data,
    }


def _build_report_input(query: str, intent: ParsedIntent, merged_data_package: dict[str, Any]) -> dict[str, Any]:
    return {
        "User Financial Query": query,
        "System Target Language": _language_label(intent.system_context.language),
        "Merged Data Package": merged_data_package,
    }


def _macro_is_severe(macro_data: dict[str, Any]) -> bool:
    regime = str(macro_data.get("Global_Regime") or "").lower()
    warning_text = str(macro_data.get("Systemic_Risk_Warning") or "").lower()
    vix = _coerce_float(macro_data.get("VIX_Volatility_Index"))
    return (
        "risk-off" in regime
        or "panic" in regime
        or "warning" in warning_text
        or "caution" in warning_text
        or (vix is not None and vix >= 20)
    )


def _normalize_trend_score(value: Any) -> float:
    trend = _coerce_percent_points(value)
    if trend is None:
        return 50.0
    return _clamp(50 + trend * 4, 15, 90)


def _analyst_bonus(analyst_rating: Any) -> float:
    lowered = str(analyst_rating or "").strip().lower()
    if lowered == "strong_buy":
        return 10.0
    if lowered == "buy":
        return 6.0
    return 0.0


def _localize_verdict(verdict_key: str, language_code: str) -> str:
    return _labels(language_code)["verdicts"].get(verdict_key, verdict_key)


def _market_stance(language_code: str, severe: bool) -> str:
    key = "defensive" if severe else "selective"
    return _labels(language_code)["market_stance"][key]


def _alignment_label(language_code: str, alignment: str) -> str:
    return _labels(language_code)["alignment"].get(alignment, alignment)


def _build_candidate_analysis(
    language_code: str,
    intent: ParsedIntent,
    macro_data: dict[str, Any],
    price_row: dict[str, Any],
    tech_row: dict[str, Any],
    smart_row: dict[str, Any],
    audit_row: dict[str, Any],
    news_row: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(price_row.get("Ticker", "")).upper()
    company_name = str(price_row.get("Company_Name") or ticker)
    sector = str(price_row.get("Sector") or "Unknown")
    latest_price = price_row.get("Latest_Price")
    pe_ratio = _coerce_float(price_row.get("PE_Ratio"))
    roe = _coerce_percent_points(price_row.get("ROE"))
    dividend_yield = _coerce_percent_points(price_row.get("Dividend_Yield"))
    market_cap = _coerce_float(price_row.get("Market_Cap"))
    profit_margin = _coerce_float(price_row.get("Profit_Margin"))
    debt_to_equity = _coerce_float(price_row.get("Debt_to_Equity"))
    free_cash_flow = _coerce_float(price_row.get("Free_Cash_Flow"))
    revenue_growth = _coerce_float(price_row.get("Revenue_Growth_QoQ"))
    quant_score = _coerce_float(price_row.get("Total_Quant_Score")) or 0.0
    trend_5d = price_row.get("Trend_5D")
    analyst_rating = price_row.get("Analyst_Rating")
    style = str(intent.investment_strategy.style or "")

    valuation_score = 70.0
    if pe_ratio is not None:
        valuation_score = _clamp(100 - max(pe_ratio - 12, 0) * 2.2, 20, 95)
    valuation_score = _clamp(valuation_score + _analyst_bonus(analyst_rating), 10, 98)

    quality_score = 55.0
    if roe is not None:
        quality_score = _clamp(45 + roe * 1.4, 20, 98)
    if profit_margin is not None:
        quality_score = _clamp(quality_score + min(max(profit_margin, 0) * 45, 16), 20, 98)
    if market_cap is not None:
        if market_cap >= 100_000_000_000:
            quality_score = _clamp(quality_score + 10, 20, 98)
        elif market_cap >= 40_000_000_000:
            quality_score = _clamp(quality_score + 6, 20, 98)
        elif market_cap >= 15_000_000_000:
            quality_score = _clamp(quality_score + 2, 20, 98)
    if dividend_yield is not None:
        quality_score = _clamp(quality_score + min(dividend_yield * 4, 12), 20, 98)

    momentum_score = _normalize_trend_score(trend_5d)
    tech_sentiment = str(tech_row.get("Tech_Sentiment") or "Unavailable")
    if tech_sentiment == "Bullish":
        momentum_score = _clamp(momentum_score + 12, 0, 100)
    elif tech_sentiment == "Bearish":
        momentum_score = _clamp(momentum_score - 12, 0, 100)

    sentiment_score = 50.0
    news_score = _coerce_float(news_row.get("Headline_Sentiment_Score")) or 0.0
    if news_score >= 2:
        sentiment_score = 75.0
    elif news_score <= -2:
        sentiment_score = 28.0
    elif news_score == 0:
        sentiment_score = 52.0
    else:
        sentiment_score = 60.0 if news_score > 0 else 42.0

    risk_score = 72.0
    audit_text = str(audit_row.get("Audit_Text") or "Unavailable")
    severe_audit = bool(audit_row.get("Severe_Audit_Warning"))
    audit_risk_level = str(audit_row.get("Overall_Risk_Level") or "Unavailable")
    current_ratio = _coerce_float(audit_row.get("Current_Ratio"))
    smart_signal = str(smart_row.get("Smart_Money_Positioning") or "Unavailable")
    macro_severe = _macro_is_severe(macro_data)

    if severe_audit:
        risk_score = 18.0
    elif audit_risk_level.lower() == "medium risk":
        risk_score = 48.0
    if current_ratio is not None and current_ratio < 1.0:
        risk_score = min(risk_score, 24.0)
    if debt_to_equity is not None:
        if debt_to_equity >= 250:
            risk_score = min(risk_score, 28.0)
        elif debt_to_equity >= 140:
            risk_score = min(risk_score, 46.0)
        elif debt_to_equity <= 60:
            risk_score = max(risk_score, 78.0)
    if free_cash_flow is not None and free_cash_flow < 0:
        risk_score = min(risk_score, 44.0)
    if macro_severe:
        risk_score = max(12.0, risk_score - 8)

    suitability_score = 58.0
    if intent.risk_profile.tolerance_level == "Low":
        suitability_score += 10 if risk_score >= 65 else -16
    elif intent.risk_profile.tolerance_level == "High":
        suitability_score += 4 if momentum_score >= 60 else -2

    if intent.investment_strategy.style == "Dividend":
        if dividend_yield is not None:
            suitability_score += 12 if dividend_yield >= 2 else -10
        else:
            suitability_score -= 4
    elif style == "Quality":
        if market_cap is not None:
            if market_cap >= 100_000_000_000:
                suitability_score += 12
            elif market_cap >= 40_000_000_000:
                suitability_score += 7
            elif market_cap < 15_000_000_000:
                suitability_score -= 10
        if profit_margin is not None:
            suitability_score += 8 if profit_margin >= 0.12 else 2 if profit_margin >= 0.06 else -6
        if debt_to_equity is not None:
            suitability_score += 6 if debt_to_equity <= 120 else -8
        if dividend_yield is not None:
            suitability_score += 3 if dividend_yield >= 1.5 else 0
    elif style == "Value":
        if pe_ratio is not None:
            suitability_score += 10 if pe_ratio <= 18 else -6
    elif style == "Growth":
        if revenue_growth is not None:
            suitability_score += 8 if revenue_growth >= 0.08 else -4

    if intent.fundamental_filters.max_pe_ratio is not None and pe_ratio is not None:
        suitability_score += 8 if pe_ratio <= intent.fundamental_filters.max_pe_ratio else -10
    if intent.fundamental_filters.min_roe is not None and roe is not None:
        suitability_score += 8 if roe / 100 >= intent.fundamental_filters.min_roe else -12
    if intent.fundamental_filters.require_positive_fcf:
        suitability_score += 4 if not severe_audit else -8
    if ticker in intent.explicit_targets.tickers:
        suitability_score += 6
    if quant_score > 0:
        suitability_score += min(quant_score * 20, 8)
    suitability_score = _clamp(suitability_score, 5, 98)

    composite_score = _clamp(
        valuation_score * 0.2
        + quality_score * 0.24
        + momentum_score * 0.16
        + sentiment_score * 0.12
        + risk_score * 0.16
        + suitability_score * 0.12,
        0,
        100,
    )

    if severe_audit:
        verdict_key = "veto_avoid"
    elif composite_score >= 78 and risk_score >= 60:
        verdict_key = "strong_buy"
    elif composite_score >= 66:
        verdict_key = "accumulate"
    elif composite_score >= 54:
        verdict_key = "hold_watch"
    else:
        verdict_key = "avoid"

    news_label = str(news_row.get("Headline_Sentiment_Label") or "No Coverage")
    alignment = "unclear"
    if tech_sentiment == "Bullish" and news_label == "Positive":
        alignment = "aligned"
    elif tech_sentiment == "Bearish" and news_label == "Negative":
        alignment = "aligned"
    elif tech_sentiment in {"Bullish", "Bearish"} and news_label in {"Positive", "Negative"}:
        alignment = "mixed"

    if language_code == "zh":
        thesis = (
            f"{company_name} 当前综合评分 {composite_score:.1f}，核心优势来自质量 {quality_score:.1f}、"
            f"风险控制 {risk_score:.1f} 和策略适配度 {suitability_score:.1f}。"
        )
        if verdict_key == "veto_avoid":
            thesis = f"{company_name} 的审计与偿债风险已经触发一票否决，不适合作为当前组合候选。"
        fit_reason = (
            f"该标的与当前 mandate 的匹配度为 {suitability_score:.1f}/100，"
            f"主要由风险偏好、持有期限、分红诉求和估值约束共同决定。"
        )
        execution = {
            "strong_buy": "适合作为核心仓位，建议分批建仓。",
            "accumulate": "可列入买入清单，等待更好的价格或确认信号后逐步布局。",
            "hold_watch": "先放入观察名单，避免在当前价位追高。",
            "avoid": "当前性价比不足，继续跟踪即可。",
            "veto_avoid": "暂不参与，除非后续审计或流动性风险明显改善。",
        }[verdict_key]
        market_note = "宏观层面偏谨慎。" if macro_severe else "宏观层面没有出现系统性 veto。"
    else:
        thesis = (
            f"{company_name} scores {composite_score:.1f} overall, supported mainly by quality "
            f"({quality_score:.1f}), risk control ({risk_score:.1f}) and mandate fit ({suitability_score:.1f})."
        )
        if verdict_key == "veto_avoid":
            thesis = f"{company_name} triggers a hard veto because the audit and solvency stack is too weak."
        fit_reason = (
            f"Mandate fit is {suitability_score:.1f}/100, driven by risk preference, horizon, income objective and valuation limits."
        )
        execution = {
            "strong_buy": "Suitable for core sizing with staged entries.",
            "accumulate": "Keep on the buy list and scale in on better levels.",
            "hold_watch": "Keep on watch and avoid aggressive chasing.",
            "avoid": "Current risk / reward is not compelling enough.",
            "veto_avoid": "Do not initiate until the audit and liquidity stack improves.",
        }[verdict_key]
        market_note = "Macro backdrop is defensive." if macro_severe else "No systemic macro veto is visible."

    return {
        "ticker": ticker,
        "company_name": company_name,
        "sector": sector,
        "latest_price": latest_price,
        "trend_5d": trend_5d,
        "pe_ratio": price_row.get("PE_Ratio"),
        "roe": price_row.get("ROE"),
        "dividend_yield": price_row.get("Dividend_Yield"),
        "market_cap": price_row.get("Market_Cap"),
        "profit_margin": price_row.get("Profit_Margin"),
        "debt_to_equity": price_row.get("Debt_to_Equity"),
        "free_cash_flow": price_row.get("Free_Cash_Flow"),
        "analyst_rating": analyst_rating,
        "valuation_score": round(valuation_score, 1),
        "quality_score": round(quality_score, 1),
        "momentum_score": round(momentum_score, 1),
        "sentiment_score": round(sentiment_score, 1),
        "risk_score": round(risk_score, 1),
        "suitability_score": round(suitability_score, 1),
        "composite_score": round(composite_score, 1),
        "verdict_key": verdict_key,
        "verdict_label": _localize_verdict(verdict_key, language_code),
        "thesis": thesis,
        "fit_reason": fit_reason,
        "execution": execution,
        "technical_summary": tech_row.get("Tech_Signal_Summary", "Unavailable"),
        "tech_sentiment": tech_sentiment,
        "smart_money_positioning": smart_signal,
        "audit_summary": audit_text,
        "audit_risk_level": audit_risk_level,
        "severe_audit_warning": severe_audit,
        "news_score": news_score,
        "news_label": news_label,
        "catalysts": news_row.get("Catalysts", []),
        "alignment": _alignment_label(language_code, alignment),
        "market_note": market_note,
        "veto": verdict_key == "veto_avoid",
    }


def _build_allocation_plan(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [item for item in candidates if not item["veto"] and item["verdict_key"] in {"strong_buy", "accumulate"}][:3]
    if not eligible:
        return []
    total = sum(item["composite_score"] for item in eligible) or 1.0
    return [
        {
            "ticker": item["ticker"],
            "weight": round(item["composite_score"] / total * 100, 1),
            "verdict": item["verdict_label"],
        }
        for item in eligible
    ]


def _build_report_briefing(query: str, intent: ParsedIntent, merged_data_package: dict[str, Any]) -> dict[str, Any]:
    language_code = intent.system_context.language
    labels = _labels(language_code)
    macro_data = merged_data_package.get("Macro_Data", {}) or {}
    price_rows = merged_data_package.get("Price_Data", []) or []
    tech_map = {str(item.get("Ticker", "")).upper(): item for item in merged_data_package.get("Tech_Data", [])}
    smart_map = {str(item.get("Ticker", "")).upper(): item for item in merged_data_package.get("Smart_Data", [])}
    audit_map = {str(item.get("Ticker", "")).upper(): item for item in merged_data_package.get("Audit_Data", [])}
    news_map = {str(item.get("Ticker", "")).upper(): item for item in merged_data_package.get("News_Data", [])}

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

    candidates.sort(key=lambda item: item["composite_score"], reverse=True)
    severe_macro = _macro_is_severe(macro_data)
    top_pick = next((item for item in candidates if not item["veto"]), candidates[0] if candidates else None)
    watchlist = [item["ticker"] for item in candidates if not item["veto"]][1:4]
    avoid_list = [item["ticker"] for item in candidates if item["veto"] or item["verdict_key"] == "avoid"]
    allocation_plan = _build_allocation_plan(candidates)
    mandate_fit = round(sum(item["suitability_score"] for item in candidates) / len(candidates), 1) if candidates else 0.0

    if language_code == "zh":
        primary_call = (
            f"当前最匹配的候选是 {top_pick['ticker']}，建议结论为“{top_pick['verdict_label']}”。"
            if top_pick
            else "当前没有足够匹配 mandate 的候选。"
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
            else "No macro veto is currently strong enough to override the strategy."
        )

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
                    "summary": f"{item['ticker']}: technicals and news are not aligned.",
                }
            )

    return {
        "meta": {
            "title": labels["title"],
            "subtitle": labels["subtitle"],
            "language": language_code,
            "query": query,
            "ticker_count": len(candidates),
            "report_mode": None,
            "sections": labels["sections"],
            "table_headers": labels["table_headers"],
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
        },
        "macro": {
            "regime": macro_data.get("Global_Regime") or macro_data.get("Status") or "Unknown",
            "warning_text": macro_data.get("Systemic_Risk_Warning") or "N/A",
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
    labels = _labels(language_code)
    sections = labels["sections"]
    table_headers = " | ".join(labels["table_headers"])
    language_name = _language_label(language_code)
    return (
        "You are a Tier-1 hedge fund portfolio manager writing an institutional-grade investment memo. "
        f"Write the entire report in {language_name}. "
        "Do not hallucinate any number or narrative not present in the JSON package. "
        "Do not drop any ticker from Price_Data. "
        "Keep the output in Markdown only. Do not start with fenced code blocks. "
        "Use this exact structure:\n"
        f"# {labels['title']}\n"
        f"## {sections['executive']}\n"
        f"## {sections['market']}\n"
        f"## {sections['scoreboard']}\n"
        f"## {sections['cards']}\n"
        f"## {sections['risk']}\n"
        f"For the scoreboard table, use this localized header row exactly: {table_headers}. "
        "Each ticker card must clearly state thesis, technical/news read-through, audit risk and execution stance."
    )


def _build_report_user_prompt(query: str, intent: ParsedIntent, merged_data_package: dict[str, Any]) -> str:
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


def _validate_report_output(report: str, intent: ParsedIntent, report_briefing: dict[str, Any]) -> str | None:
    if not report.strip():
        return "LLM 未返回任何报告内容。"
    if "```" in report:
        return "LLM 输出了代码块，不符合报告格式要求。"

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
            return f"LLM 输出缺少固定标题：{header}"

    for row in report_briefing.get("scoreboard", []):
        ticker = str(row.get("ticker", "")).strip()
        if ticker and ticker not in report:
            return f"LLM 报告遗漏了股票 {ticker}。"
    return None


def _build_rule_based_report(intent: ParsedIntent, report_briefing: dict[str, Any]) -> str:
    language_code = intent.system_context.language
    labels = _labels(language_code)
    sections = labels["sections"]
    meta = report_briefing.get("meta", {})
    executive = report_briefing.get("executive", {})
    macro = report_briefing.get("macro", {})
    scoreboard = report_briefing.get("scoreboard", [])
    ticker_cards = report_briefing.get("ticker_cards", [])
    risk_register = report_briefing.get("risk_register", [])

    lines = [f"# {meta.get('title', labels['title'])}", ""]
    lines.extend(
        [
            f"## {sections['executive']}",
            f"- {executive.get('primary_call', labels['empty'])}",
            f"- {labels['metric_labels']['fit']}: {_format_scalar(executive.get('mandate_fit_score'))}",
            f"- Market Stance: {executive.get('market_stance', 'N/A')}",
            f"- Top Pick: {_format_scalar(executive.get('top_pick'))} / {_format_scalar(executive.get('top_pick_verdict'))}",
            f"- Watchlist: {', '.join(executive.get('watchlist', [])) or 'N/A'}",
            f"- Avoid List: {', '.join(executive.get('avoid_list', [])) or 'N/A'}",
            f"- Action Summary: {executive.get('action_summary', labels['empty'])}",
            "",
            f"## {sections['market']}",
            f"- Regime: {_format_scalar(macro.get('regime'))}",
            f"- VIX: {_format_scalar(macro.get('vix'))}",
            f"- S&P 500: {_format_scalar(macro.get('sp500'))}",
            f"- US 10Y: {_format_scalar(macro.get('us10y'))}",
            f"- Risk Headline: {macro.get('risk_headline', labels['empty'])}",
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
        lines.append(f"- {labels['metric_labels']['allocation']}:")
        for item in allocation_plan:
            lines.append(f"  {item.get('ticker')}: {_format_scalar(item.get('weight'))}%")

    return "\n".join(lines)
