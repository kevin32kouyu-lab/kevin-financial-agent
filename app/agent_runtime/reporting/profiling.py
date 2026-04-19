"""Profile derivation functions for financial analysis.

This module contains functions that derive analysis profiles from raw data:
- News profiles: sentiment analysis and catalyst extraction
- Technical profiles: MA, RSI, and trend analysis
- Smart money profiles: positioning and institutional signals
- Audit profiles: solvency, liquidity, and risk assessment
"""

from typing import Any

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
    """Get localized labels for reporting."""
    if language_code == "zh":
        return {
            "empty": "暂无可展示内容。",
        }
    return {
        "empty": "No content available.",
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


def _coerce_float(value: Any) -> float | None:
    """Safely coerce a value to float."""
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


def _headline_score(title: str) -> int:
    """Calculate sentiment score from news headline."""
    lowered = title.lower()
    score = 0
    score += sum(1 for token in POSITIVE_HEADLINE_KEYWORDS if token in lowered)
    score -= sum(1 for token in NEGATIVE_HEADLINE_KEYWORDS if token in lowered)
    return score


def _derive_news_profile(ticker: str, news_items: list[dict[str, Any]], language_code: str) -> dict[str, Any]:
    """Derive news sentiment and catalyst profile.

    Args:
        ticker: Stock ticker symbol
        news_items: List of news items with 'title' and 'published_at' fields
        language_code: 'zh' for Chinese, 'en' for English

    Returns:
        Dictionary with sentiment score, label, catalysts, and narrative
    """
    headlines = [str(item.get("title", "")).strip() for item in news_items if str(item.get("title", "")).strip()]
    timestamps = [str(item.get("published_at", "")).strip() for item in news_items[:3]]
    links = [str(item.get("link", "")).strip() for item in news_items[:3]]
    sources = [
        str(item.get("source") or "").strip()
        for item in news_items
        if isinstance(item, dict) and str(item.get("source") or "").strip()
    ]
    news_entries = []
    for item in news_items[:5]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        news_entries.append(
            {
                "title": title,
                "url": str(item.get("link") or "").strip(),
                "source": str(item.get("source") or "").strip(),
                "published_at": str(item.get("published_at") or "").strip(),
            }
        )
    source_summary = " / ".join(list(dict.fromkeys(sources[:3]))) if sources else ("none" if language_code != "zh" else "无")
    labels = _labels(language_code)

    if not headlines:
        no_coverage = "暂无覆盖" if language_code == "zh" else "No Coverage"
        no_news_text = "暂无近期新闻。" if language_code == "zh" else "No recent headlines available."
        return {
            "Ticker": ticker,
            "Headline_Sentiment_Score": 0,
            "Headline_Sentiment_Label": no_coverage,
            "Catalysts": [],
            "Latest_Headlines": [],
            "Latest_Published_At": [],
            "Latest_Links": [],
            "News_Items": [],
            "News_Source": source_summary,
            "Narrative": no_news_text,
        }

    total_score = sum(_headline_score(title) for title in headlines[:5])
    if total_score >= 2:
        label = "Positive" if language_code != "zh" else "正面"
    elif total_score <= -2:
        label = "Negative" if language_code != "zh" else "负面"
    elif total_score == 0:
        label = "Neutral" if language_code != "zh" else "中性"
    else:
        label = "Mixed" if language_code != "zh" else "分化"

    narrative = (
        f"最新新闻情绪：{label}。"
        if language_code == "zh"
        else f"{label} headline tone from latest news set."
    )

    return {
        "Ticker": ticker,
        "Headline_Sentiment_Score": total_score,
        "Headline_Sentiment_Label": label,
        "Catalysts": headlines[:3],
        "Latest_Headlines": headlines[:3],
        "Latest_Published_At": timestamps,
        "Latest_Links": links,
        "News_Items": news_entries,
        "News_Source": source_summary,
        "Narrative": narrative,
    }


def _derive_tech_profile(technical: dict[str, Any], language_code: str) -> dict[str, Any]:
    """Derive technical analysis profile from indicators.

    Analyzes price vs moving averages and RSI to determine sentiment.

    Args:
        technical: Dictionary containing technical indicators
        language_code: 'zh' for Chinese, 'en' for English

    Returns:
        Dictionary with tech sentiment and signal summary
    """
    status = str(technical.get("Status") or "Unavailable")
    source = str(technical.get("Source") or "unavailable")
    latest_price = _coerce_float(technical.get("Latest_Price"))
    ma_20 = _coerce_float(technical.get("MA_20"))
    ma_50 = _coerce_float(technical.get("MA_50"))
    rsi_14 = _coerce_float(technical.get("RSI_14"))

    if status != "Success":
        summary = status
        lowered = status.lower()
        if "too many requests" in lowered or "temporarily unavailable" in lowered:
            summary = (
                "技术面数据暂时不可用：实时数据源触发限流。"
                if language_code == "zh"
                else "Technical data is temporarily unavailable because of rate-limiting."
            )
        elif lowered.startswith("cached"):
            summary = (
                "技术面数据当前来自最近一次成功缓存。"
                if language_code == "zh"
                else "Technical data is currently served from latest successful cache."
            )
        return {
            "Latest_Price": technical.get("Latest_Price"),
            "Trend_5D": technical.get("Trend_5D"),
            "Tech_Source": source,
            "Tech_Sentiment": "Unavailable" if language_code != "zh" else "不可用",
            "Tech_Signal_Summary": summary,
        }

    bullish = 0
    bearish = 0
    signals: list[str] = []

    # Price vs MA analysis
    if latest_price is not None and ma_20 is not None and ma_50 is not None:
        if latest_price > ma_20 > ma_50:
            bullish += 2
            signals.append("Price > MA20 > MA50" if language_code != "zh" else "价格 > MA20 > MA50")
        elif latest_price < ma_20 < ma_50:
            bearish += 2
            signals.append("Price < MA20 < MA50" if language_code != "zh" else "价格 < MA20 < MA50")
        elif latest_price > ma_20:
            bullish += 1
            signals.append("Price above MA20" if language_code != "zh" else "价格位于 MA20 上方")
        elif latest_price < ma_20:
            bearish += 1
            signals.append("Price below MA20" if language_code != "zh" else "价格位于 MA20 下方")

    # RSI analysis
    if rsi_14 is not None:
        if rsi_14 >= 70:
            bearish += 1
            signals.append(f"RSI {rsi_14:.1f} overbought" if language_code != "zh" else f"RSI {rsi_14:.1f} 过热")
        elif rsi_14 <= 30:
            bullish += 1
            signals.append(f"RSI {rsi_14:.1f} rebound zone" if language_code != "zh" else f"RSI {rsi_14:.1f} 反弹区")
        elif rsi_14 >= 55:
            bullish += 1
            signals.append(
                f"RSI {rsi_14:.1f} supports momentum"
                if language_code != "zh"
                else f"RSI {rsi_14:.1f} 支撑动量"
            )
        elif rsi_14 <= 45:
            bearish += 1
            signals.append(f"RSI {rsi_14:.1f} is soft" if language_code != "zh" else f"RSI {rsi_14:.1f} 偏弱")

    if bullish > bearish:
        sentiment = "Bullish" if language_code != "zh" else "看多"
    elif bearish > bullish:
        sentiment = "Bearish" if language_code != "zh" else "看空"
    else:
        sentiment = "Neutral" if language_code != "zh" else "中性"

    return {
        "Latest_Price": technical.get("Latest_Price"),
        "Trend_5D": technical.get("Trend_5D"),
        "Tech_Source": source,
        "Tech_Sentiment": sentiment,
        "Tech_Signal_Summary": "; ".join(signals)
        if signals
        else ("技术面信号分化。" if language_code == "zh" else "Technical posture is mixed."),
    }


def _derive_smart_money_profile(smart_money: dict[str, Any], language_code: str) -> dict[str, Any]:
    """Derive smart money/institutional positioning profile.

    Args:
        smart_money: Dictionary containing smart money signals
        language_code: 'zh' for Chinese, 'en' for English

    Returns:
        Dictionary with positioning and highlight flags
    """
    signal = str(
        smart_money.get("Smart_Money_Signal")
        or smart_money.get("Status")
        or ("Unavailable" if language_code != "zh" else "不可用")
    )
    status = str(smart_money.get("Status") or "")
    source = str(smart_money.get("Source") or "unavailable")
    lowered_status = status.lower()

    if "too many requests" in lowered_status or "temporarily unavailable" in lowered_status:
        signal = (
            "公开资金面代理信号暂时不可用：实时数据源触发限流。"
            if language_code == "zh"
            else "Public positioning proxy is temporarily unavailable because of rate-limiting."
        )
    elif lowered_status.startswith("cached"):
        signal = (
            "公开资金面代理信号当前来自最近一次成功缓存。"
            if language_code == "zh"
            else "Public positioning proxy is served from latest successful cache."
        )

    lowered = signal.lower()
    return {
        "Smart_Money_Source": source,
        "Smart_Money_Positioning": signal,
        "Highlight_Flag": any(token in lowered for token in SMART_MONEY_HOT_SIGNALS),
    }


def _derive_audit_profile(audit: dict[str, Any], language_code: str) -> dict[str, Any]:
    """Derive audit and solvency risk profile.

    Evaluates balance sheet health, liquidity, and financial risk.

    Args:
        audit: Dictionary containing audit metrics
        language_code: 'zh' for Chinese, 'en' for English

    Returns:
        Dictionary with risk level, audit text, and warning flags
    """
    status = str(audit.get("Status") or ("Unavailable" if language_code != "zh" else "不可用"))
    risk_level = str(audit.get("Overall_Risk_Level") or status or ("Unavailable" if language_code != "zh" else "不可用"))
    current_ratio = _coerce_float(audit.get("Current_Ratio"))
    retained_earnings = _coerce_float(audit.get("Retained_Earnings_B"))
    risk_flags = [str(flag) for flag in (audit.get("Risk_Flags") or []) if str(flag).strip()]
    filing_summary = str(audit.get("Recent_Filing_Summary") or "").strip()
    latest_filing_date = audit.get("Latest_Filing_Date")
    recent_filings = audit.get("Recent_Filings") if isinstance(audit.get("Recent_Filings"), list) else []

    # Determine if severe warning is triggered
    severe_warning = False
    if risk_level.lower() in {"high risk", "severe", "critical"}:
        severe_warning = True
    if current_ratio is not None and current_ratio < 1.0:
        severe_warning = True
    if retained_earnings is not None and retained_earnings < -1.0:
        severe_warning = True
    if any("liquidity" in flag.lower() or "default" in flag.lower() for flag in risk_flags):
        severe_warning = True

    # Build audit narrative
    if status != "Success":
        text = status
    elif severe_warning:
        if language_code == "zh":
            text = (
                f"流动性/偿债风险警示。D/E {_format_scalar(audit.get('Debt_to_Equity'))}，"
                f"流动比率 {_format_scalar(audit.get('Current_Ratio'))}，"
                f"留存收益 {_format_scalar(audit.get('Retained_Earnings_B'))}B。"
            )
        else:
            text = (
                f"Liquidity / solvency warning. D/E {_format_scalar(audit.get('Debt_to_Equity'))}, "
                f"Current Ratio {_format_scalar(audit.get('Current_Ratio'))}, "
                f"Retained Earnings {_format_scalar(audit.get('Retained_Earnings_B'))}B."
            )
    elif risk_level.lower() == "medium risk":
        if language_code == "zh":
            text = (
                f"资产负债表存在中等风险。D/E {_format_scalar(audit.get('Debt_to_Equity'))}，"
                f"流动比率 {_format_scalar(audit.get('Current_Ratio'))}，"
                f"留存收益 {_format_scalar(audit.get('Retained_Earnings_B'))}B。"
            )
        else:
            text = (
                f"Moderate balance-sheet caution. D/E {_format_scalar(audit.get('Debt_to_Equity'))}, "
                f"Current Ratio {_format_scalar(audit.get('Current_Ratio'))}, "
                f"Retained Earnings {_format_scalar(audit.get('Retained_Earnings_B'))}B."
            )
    else:
        if language_code == "zh":
            text = (
                f"当前未触发审计一票否决。D/E {_format_scalar(audit.get('Debt_to_Equity'))}，"
                f"流动比率 {_format_scalar(audit.get('Current_Ratio'))}，"
                f"留存收益 {_format_scalar(audit.get('Retained_Earnings_B'))}B。"
            )
        else:
            text = (
                f"No major audit veto. D/E {_format_scalar(audit.get('Debt_to_Equity'))}, "
                f"Current Ratio {_format_scalar(audit.get('Current_Ratio'))}, "
                f"Retained Earnings {_format_scalar(audit.get('Retained_Earnings_B'))}B."
            )

    if filing_summary:
        text = (
            f"{text} 近期披露：{filing_summary}。"
            if language_code == "zh"
            else f"{text} Recent filings: {filing_summary}."
        )

    return {
        "Overall_Risk_Level": risk_level,
        "Current_Ratio": audit.get("Current_Ratio"),
        "Audit_Text": text,
        "Severe_Audit_Warning": severe_warning,
        "Risk_Flags": risk_flags,
        "Recent_Filing_Summary": filing_summary,
        "Latest_Filing_Date": latest_filing_date,
        "Recent_Filings": recent_filings,
    }
