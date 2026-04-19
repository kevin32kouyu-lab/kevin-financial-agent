"""Scoring functions for financial candidate analysis.

This module contains functions that:
- Calculate component scores (valuation, quality, momentum, sentiment, risk)
- Determine composite and suitability scores
- Generate verdicts and allocation plans
"""

from typing import Any


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


def _coerce_percent_points(value: Any) -> float | None:
    """Coerce a value to percentage points."""
    number = _coerce_float(value)
    if number is None:
        return None
    if isinstance(value, str) and "%" in value:
        return number
    if abs(number) <= 1.0:
        return number * 100
    return number


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    """Clamp a value between bounds."""
    return max(lower, min(upper, value))


def _normalize_trend_score(value: Any) -> float:
    """Normalize trend score to 0-100 range."""
    if isinstance(value, list):
        series: list[float] = []
        for item in value:
            coerced = _coerce_float(item)
            if coerced is not None:
                series.append(coerced)
        if len(series) >= 2 and series[0] > 0:
            trend_pct = (series[-1] / series[0] - 1) * 100
            return _clamp(50 + trend_pct * 3, 15, 90)
        return 50.0
    trend = _coerce_percent_points(value)
    if trend is None:
        return 50.0
    return _clamp(50 + trend * 4, 15, 90)


def _analyst_bonus(analyst_rating: Any) -> float:
    """Get bonus score from analyst rating."""
    lowered = str(analyst_rating or "").strip().lower()
    if lowered == "strong_buy":
        return 10.0
    if lowered == "buy":
        return 6.0
    return 0.0


def _macro_is_severe(macro_data: dict[str, Any]) -> bool:
    """Determine if macro conditions are severe enough to veto trades.

    Args:
        macro_data: Dictionary containing macro indicators

    Returns:
        True if macro conditions warrant defensive stance
    """
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


def _localize_verdict(verdict_key: str, language_code: str) -> str:
    """Localize verdict key to display text."""
    verdicts_en = {
        "strong_buy": "Strong Buy",
        "accumulate": "Accumulate",
        "hold_watch": "Hold / Watch",
        "avoid": "Avoid",
        "veto_avoid": "Veto / Avoid",
    }
    verdicts_zh = {
        "strong_buy": "优先买入",
        "accumulate": "分批布局",
        "hold_watch": "继续观察",
        "avoid": "回避",
        "veto_avoid": "一票否决 / 回避",
    }
    return (verdicts_zh if language_code == "zh" else verdicts_en).get(verdict_key, verdict_key)


def _alignment_label(language_code: str, alignment: str) -> str:
    """Localize alignment label."""
    alignments_en = {
        "aligned": "Aligned",
        "mixed": "Mixed",
        "unclear": "Unclear",
    }
    alignments_zh = {
        "aligned": "一致",
        "mixed": "分化",
        "unclear": "暂不清晰",
    }
    return (alignments_zh if language_code == "zh" else alignments_en).get(alignment, alignment)


def _share_class_note(language_code: str, share_class: str | None) -> str | None:
    """将股权类别转成用户可读说明。"""
    if not share_class:
        return None
    if language_code == "zh":
        return f"该代码对应 {share_class} 股权类别。"
    return f"This ticker maps to {share_class} share class."


def _top_drivers(
    *,
    language_code: str,
    valuation_score: float,
    quality_score: float,
    momentum_score: float,
    risk_score: float,
    suitability_score: float,
) -> str:
    """返回前两项主驱动维度，减少文案同质化。"""
    labels_zh = {
        "valuation": "估值",
        "quality": "质量",
        "momentum": "动量",
        "risk": "风险控制",
        "fit": "目标匹配度",
    }
    labels_en = {
        "valuation": "valuation",
        "quality": "quality",
        "momentum": "momentum",
        "risk": "risk control",
        "fit": "mandate fit",
    }
    labels = labels_zh if language_code == "zh" else labels_en
    pairs = [
        ("valuation", valuation_score),
        ("quality", quality_score),
        ("momentum", momentum_score),
        ("risk", risk_score),
        ("fit", suitability_score),
    ]
    top = sorted(pairs, key=lambda item: item[1], reverse=True)[:2]
    return "、".join(labels[key] for key, _ in top) if language_code == "zh" else " and ".join(labels[key] for key, _ in top)


def _build_candidate_analysis(
    language_code: str,
    intent: Any,
    macro_data: dict[str, Any],
    price_row: dict[str, Any],
    tech_row: dict[str, Any],
    smart_row: dict[str, Any],
    audit_row: dict[str, Any],
    news_row: dict[str, Any],
) -> dict[str, Any]:
    """Build comprehensive candidate analysis with all scores and verdict.

    This function calculates:
    - Valuation score (PE ratio, analyst rating)
    - Quality score (ROE, profit margin, market cap, dividend)
    - Momentum score (trend, technical indicators)
    - Sentiment score (news sentiment)
    - Risk score (audit risk, debt, cash flow)
    - Suitability score (alignment with investment mandate)
    - Composite score (weighted combination)
    - Verdict (strong_buy, accumulate, hold_watch, avoid, veto_avoid)

    Args:
        language_code: 'zh' for Chinese, 'en' for English
        intent: ParsedIntent containing investment parameters
        macro_data: Macro environment data
        price_row: Price and fundamental metrics
        tech_row: Technical analysis profile
        smart_row: Smart money positioning profile
        audit_row: Audit and solvency profile
        news_row: News sentiment profile

    Returns:
        Dictionary with all scores, verdict, and narrative text
    """
    ticker = str(price_row.get("Ticker", "")).upper()
    company_name = str(price_row.get("Company_Name") or ticker)
    issuer_name = str(price_row.get("Issuer_Name") or company_name)
    share_class = str(price_row.get("Share_Class") or "").strip() or None
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

    # Valuation Score
    valuation_score = 70.0
    if pe_ratio is not None:
        valuation_score = _clamp(100 - max(pe_ratio - 12, 0) * 2.2, 20, 95)
    valuation_score = _clamp(valuation_score + _analyst_bonus(analyst_rating), 10, 98)

    # Quality Score
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

    # Momentum Score
    momentum_score = _normalize_trend_score(trend_5d)
    tech_sentiment = str(tech_row.get("Tech_Sentiment") or "Unavailable")
    if tech_sentiment == "Bullish":
        momentum_score = _clamp(momentum_score + 12, 0, 100)
    elif tech_sentiment == "Bearish":
        momentum_score = _clamp(momentum_score - 12, 0, 100)

    # Sentiment Score
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

    # Risk Score
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

    # Suitability Score
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

    # Composite Score (weighted average)
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

    # Determine verdict
    if severe_audit:
        verdict_key = "veto_avoid"
    elif composite_score >= 72:
        verdict_key = "strong_buy"
    elif composite_score >= 66:
        verdict_key = "accumulate"
    elif composite_score >= 54:
        verdict_key = "hold_watch"
    else:
        verdict_key = "avoid"

    # Determine alignment between technicals and news
    news_label = str(news_row.get("Headline_Sentiment_Label") or "No Coverage")
    news_narrative = str(news_row.get("Narrative") or "")
    news_items = news_row.get("News_Items") if isinstance(news_row.get("News_Items"), list) else []
    audit_links = audit_row.get("Recent_Filings") if isinstance(audit_row.get("Recent_Filings"), list) else []
    alignment = "unclear"
    if tech_sentiment == "Bullish" and news_label == "Positive":
        alignment = "aligned"
    elif tech_sentiment == "Bearish" and news_label == "Negative":
        alignment = "aligned"
    elif tech_sentiment in {"Bullish", "Bearish"} and news_label in {"Positive", "Negative"}:
        alignment = "mixed"

    # Build narrative text
    if language_code == "zh":
        drivers = _top_drivers(
            language_code=language_code,
            valuation_score=valuation_score,
            quality_score=quality_score,
            momentum_score=momentum_score,
            risk_score=risk_score,
            suitability_score=suitability_score,
        )
        thesis = (
            f"{company_name} 当前综合评分 {composite_score:.1f}，核心优势来自质量 {quality_score:.1f}、"
            f"风险控制 {risk_score:.1f} 和策略适配度 {suitability_score:.1f}。"
        )
        thesis = f"{company_name} 当前综合评分 {composite_score:.1f}，主要驱动来自{drivers}。"
        if verdict_key == "veto_avoid":
            thesis = f"{company_name} 的审计与偿债风险已经触发一票否决，不适合作为当前组合候选。"
        fit_reason = (
            f"该标的与当前投资目标的匹配度为 {suitability_score:.1f}/100，"
            f"主要由风险偏好、持有期限、分红诉求和估值约束共同决定。"
        )
        execution = {
            "strong_buy": "适合作为核心仓位，建议分批建仓。",
            "accumulate": "可列入买入清单，等待更好的价格或确认信号后逐步布局。",
            "hold_watch": "先放入观察名单，避免在当前价位追高。",
            "avoid": "当前性价比不足，继续跟踪即可。",
            "veto_avoid": "暂不参与，除非后续审计或流动性风险明显改善。",
        }[verdict_key]
        market_note = "宏观层面偏谨慎。" if macro_severe else "宏观层面未出现系统性否决信号。"
    else:
        drivers = _top_drivers(
            language_code=language_code,
            valuation_score=valuation_score,
            quality_score=quality_score,
            momentum_score=momentum_score,
            risk_score=risk_score,
            suitability_score=suitability_score,
        )
        thesis = (
            f"{company_name} scores {composite_score:.1f} overall, supported mainly by quality "
            f"({quality_score:.1f}), risk control ({risk_score:.1f}) and mandate fit ({suitability_score:.1f})."
        )
        thesis = f"{company_name} scores {composite_score:.1f} overall, led mainly by {drivers}."
        if verdict_key == "veto_avoid":
            thesis = f"{company_name} triggers a hard veto because of audit and solvency stack weakness."
        fit_reason = (
            f"Mandate fit is {suitability_score:.1f}/100, driven by risk preference, horizon, income objective and valuation limits."
        )
        execution = {
            "strong_buy": "Suitable for core sizing with staged entries.",
            "accumulate": "Keep on buy list and scale in on better levels.",
            "hold_watch": "Keep on watch and avoid aggressive chasing.",
            "avoid": "Current risk / reward is not compelling enough.",
            "veto_avoid": "Do not initiate until audit and liquidity stack improves.",
        }[verdict_key]
        market_note = "Macro backdrop is defensive." if macro_severe else "No systemic macro veto is visible."

    return {
        "ticker": ticker,
        "company_name": company_name,
        "issuer_name": issuer_name,
        "share_class": share_class,
        "share_class_note": _share_class_note(language_code, share_class),
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
        "analystar_rating": analyst_rating,
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
        "technical_source": tech_row.get("Tech_Source", "unavailable"),
        "tech_sentiment": tech_sentiment,
        "news_narrative": news_narrative,
        "smart_money_positioning": smart_signal,
        "smart_money_source": smart_row.get("Smart_Money_Source", "unavailable"),
        "audit_summary": audit_text,
        "audit_links": audit_links,
        "audit_risk_level": audit_risk_level,
        "severe_audit_warning": severe_audit,
        "news_score": news_score,
        "news_label": news_label,
        "news_source": news_row.get("News_Source", "none"),
        "news_items": news_items,
        "catalysts": news_row.get("Catalysts", []),
        "alignment": _alignment_label(language_code, alignment),
        "market_note": market_note,
        "veto": verdict_key == "veto_avoid",
    }


def _normalize_custom_weights(raw: dict[str, Any], tickers: list[str]) -> dict[str, float]:
    """规范化自定义仓位并仅保留当前候选池。"""
    normalized: dict[str, float] = {}
    ticker_set = {ticker.upper() for ticker in tickers}
    for ticker, value in (raw or {}).items():
        key = str(ticker or "").upper().strip()
        if not key or key not in ticker_set:
            continue
        weight = _coerce_float(value)
        if weight is None or weight < 0:
            continue
        normalized[key] = weight
    return normalized


def _build_allocation_plan(
    candidates: list[dict[str, Any]],
    *,
    max_positions: int | None = None,
    allocation_mode: str = "score_weighted",
    custom_weights: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build allocation plan from selected candidates.

    Args:
        candidates: Candidate analysis list (already sorted by score)
        max_positions: Maximum number of positions to include
        allocation_mode: score_weighted / equal_weight / custom_weight
        custom_weights: User custom weights when allocation_mode=custom_weight

    Returns:
        List of allocation dictionaries with ticker, weight, and verdict
    """
    selected = [item for item in candidates if item.get("ticker")]
    if max_positions is not None:
        selected = selected[: max(1, int(max_positions))]
    if not selected:
        return []

    tickers = [str(item.get("ticker", "")).upper() for item in selected]
    weights: dict[str, float] = {}
    mode = str(allocation_mode or "score_weighted").strip().lower()

    if mode == "equal_weight":
        equal_weight = 100.0 / len(selected)
        weights = {ticker: equal_weight for ticker in tickers}
    elif mode == "custom_weight":
        parsed = _normalize_custom_weights(custom_weights or {}, tickers)
        total = sum(parsed.values())
        if total > 0:
            weights = {ticker: value / total * 100 for ticker, value in parsed.items()}
            missing = [ticker for ticker in tickers if ticker not in weights]
            if missing:
                remaining = max(0.0, 100.0 - sum(weights.values()))
                fallback = remaining / len(missing) if missing else 0.0
                for ticker in missing:
                    weights[ticker] = fallback
        else:
            equal_weight = 100.0 / len(selected)
            weights = {ticker: equal_weight for ticker in tickers}
    else:
        weighted_base = {
            str(item.get("ticker", "")).upper(): max(float(item.get("composite_score") or 0.0), 0.01)
            for item in selected
        }
        total = sum(weighted_base.values()) or 1.0
        weights = {ticker: value / total * 100 for ticker, value in weighted_base.items()}

    return [
        {
            "ticker": item["ticker"],
            "weight": round(weights.get(str(item.get("ticker", "")).upper(), 0.0), 1),
            "verdict": item.get("verdict_label"),
        }
        for item in selected
    ]
