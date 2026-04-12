from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .models import DebugAnalysisRequest


RISK_WEIGHTS = {
    "conservative": {"valuation": 0.18, "quality": 0.24, "stability": 0.24, "income": 0.12, "growth": 0.06, "size": 0.16},
    "low": {"valuation": 0.18, "quality": 0.24, "stability": 0.24, "income": 0.12, "growth": 0.06, "size": 0.16},
    "medium": {"valuation": 0.18, "quality": 0.24, "stability": 0.2, "income": 0.1, "growth": 0.12, "size": 0.16},
    "balanced": {"valuation": 0.18, "quality": 0.24, "stability": 0.2, "income": 0.1, "growth": 0.12, "size": 0.16},
    "aggressive": {"valuation": 0.16, "quality": 0.22, "stability": 0.14, "income": 0.08, "growth": 0.2, "size": 0.2},
    "high": {"valuation": 0.16, "quality": 0.22, "stability": 0.14, "income": 0.08, "growth": 0.2, "size": 0.2},
}

STYLE_BONUS = {
    "dividend": {"income": 0.12, "stability": 0.05, "size": 0.03},
    "quality": {"quality": 0.08, "stability": 0.08, "size": 0.08},
    "value": {"valuation": 0.14, "quality": 0.04},
    "growth": {"growth": 0.14, "quality": 0.04},
    "index": {"size": 0.06, "stability": 0.04},
}


def normalize(series: pd.Series) -> pd.Series:
    minimum = series.min()
    maximum = series.max()
    if pd.isna(minimum) or pd.isna(maximum) or minimum == maximum:
        return pd.Series([0.5] * len(series), index=series.index, dtype="float64")
    return (series - minimum) / (maximum - minimum)


def inverse_normalize(series: pd.Series) -> pd.Series:
    return 1 - normalize(series)


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_values(values: list[str]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _safe_ticker_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in _clean_values(values):
        ticker = value.upper()
        if ticker not in seen:
            seen.add(ticker)
            output.append(ticker)
    return output


def _prepare_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy()
    if "ticker" in prepared.columns:
        prepared["ticker"] = prepared["ticker"].astype(str).str.upper().str.strip()
    return prepared


def _normalize_dividend_yield(value: float | None) -> float | None:
    if value is None:
        return None
    numeric = safe_float(value)
    if numeric is None:
        return None
    return numeric * 100 if abs(numeric) <= 1 else numeric


def _allowed_analyst_values(value: str | None) -> set[str]:
    normalized = str(value or "").strip().lower()
    if normalized == "strong_buy":
        return {"strong_buy"}
    if normalized == "buy":
        return {"buy", "strong_buy"}
    return set()


def _numeric_series(frame: pd.DataFrame, column: str, fallback: float) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([fallback] * len(frame), index=frame.index, dtype="float64")
    numeric = pd.to_numeric(frame[column], errors="coerce")
    clean = numeric.dropna()
    fill_value = float(clean.median()) if not clean.empty else fallback
    return numeric.fillna(fill_value)


def _percent_points_series(frame: pd.DataFrame, column: str, fallback: float, *, lower: float | None = None, upper: float | None = None) -> pd.Series:
    series = _numeric_series(frame, column, fallback)
    normalized = series.apply(lambda value: value * 100 if pd.notna(value) and abs(value) <= 1 else value)
    if lower is not None or upper is not None:
        return normalized.clip(lower=lower, upper=upper)
    return normalized


def _style_key(payload: DebugAnalysisRequest) -> str:
    return str(payload.investment_strategy.style or "").strip().lower()


def _metric_coverage(frame: pd.DataFrame) -> pd.Series:
    coverage_columns = [
        "market_cap",
        "pe_ratio",
        "roe",
        "profit_margin",
        "debt_to_equity",
        "dividend_yield",
        "free_cash_flow",
        "rev_growth_qoq",
    ]
    available_columns = [column for column in coverage_columns if column in frame.columns]
    if not available_columns:
        return pd.Series([0] * len(frame), index=frame.index, dtype="int64")
    coverage = pd.Series([0] * len(frame), index=frame.index, dtype="int64")
    for column in available_columns:
        coverage += pd.to_numeric(frame[column], errors="coerce").notna().astype(int)
    return coverage


def run_screener_analysis(payload: DebugAnalysisRequest, universe_df: pd.DataFrame) -> dict[str, Any]:
    if universe_df.empty:
        return {
            "analysis_context": "股票池当前不可用。",
            "comparison_matrix": [],
        }

    db_df = _prepare_dataframe(universe_df)
    filtered_df = db_df.copy()

    sectors = [value.lower() for value in _clean_values(payload.investment_strategy.preferred_sectors)]
    industries = [value.lower() for value in _clean_values(payload.investment_strategy.preferred_industries)]
    max_pe = safe_float(payload.fundamental_filters.max_pe_ratio, 999.0)
    min_roe = safe_float(payload.fundamental_filters.min_roe, -999.0)
    min_roe_threshold = (min_roe * 100) if min_roe is not None and abs(min_roe) <= 1 else min_roe
    min_dividend_yield = _normalize_dividend_yield(payload.fundamental_filters.min_dividend_yield)
    require_positive_fcf = bool(payload.fundamental_filters.require_positive_fcf)
    analyst_values = _allowed_analyst_values(payload.fundamental_filters.analyst_rating)
    user_tickers = _safe_ticker_list(payload.explicit_targets.tickers)
    risk_level = str(payload.risk_profile.tolerance_level or "medium").lower()
    style = _style_key(payload)
    weights = dict(RISK_WEIGHTS.get(risk_level, RISK_WEIGHTS["medium"]))
    for key, bonus in STYLE_BONUS.get(style, {}).items():
        weights[key] = weights.get(key, 0.0) + bonus

    if sectors or industries:
        sector_mask = pd.Series(False, index=filtered_df.index)
        industry_mask = pd.Series(False, index=filtered_df.index)
        if "sector" in filtered_df.columns and sectors:
            sector_mask = filtered_df["sector"].astype(str).str.lower().isin(sectors)
        if "industry" in filtered_df.columns and industries:
            industry_mask = filtered_df["industry"].astype(str).str.lower().isin(industries)
        filtered_df = filtered_df[sector_mask | industry_mask]

    if "pe_ratio" in filtered_df.columns:
        pe_series = pd.to_numeric(filtered_df["pe_ratio"], errors="coerce").fillna(999.0)
        filtered_df = filtered_df[pe_series <= max_pe]
    if "roe" in filtered_df.columns:
        roe_series = _percent_points_series(filtered_df, "roe", 10.0, lower=-50, upper=80)
        filtered_df = filtered_df[roe_series >= min_roe_threshold]
    if min_dividend_yield is not None and "dividend_yield" in filtered_df.columns:
        dividend_series = pd.to_numeric(filtered_df["dividend_yield"], errors="coerce").fillna(-999.0)
        filtered_df = filtered_df[dividend_series >= min_dividend_yield]
    if require_positive_fcf and "free_cash_flow" in filtered_df.columns:
        fcf_series = pd.to_numeric(filtered_df["free_cash_flow"], errors="coerce").fillna(-1.0)
        filtered_df = filtered_df[fcf_series > 0]
    if analyst_values and "analyst_rec" in filtered_df.columns:
        analyst_series = filtered_df["analyst_rec"].astype(str).str.lower()
        filtered_df = filtered_df[analyst_series.isin(analyst_values)]

    if filtered_df.empty and not user_tickers:
        return {
            "analysis_context": "当前筛选条件下没有匹配到股票。",
            "comparison_matrix": [],
        }

    score_df = filtered_df.copy()
    if not score_df.empty:
        score_df["metric_coverage"] = _metric_coverage(score_df)
        pe_series = _numeric_series(score_df, "pe_ratio", 24.0)
        roe_series = _percent_points_series(score_df, "roe", 12.0, lower=-20, upper=45)
        dividend_series = _percent_points_series(score_df, "dividend_yield", 0.0, lower=0, upper=10)
        market_cap_series = _numeric_series(score_df, "market_cap", 10_000_000_000.0).clip(lower=0)
        margin_series = _percent_points_series(score_df, "profit_margin", 8.0, lower=-15, upper=35)
        debt_series = _numeric_series(score_df, "debt_to_equity", 120.0).clip(lower=0, upper=400)
        growth_series = _percent_points_series(score_df, "rev_growth_qoq", 3.0, lower=-20, upper=30)
        current_ratio_series = _numeric_series(score_df, "current_ratio", 1.3).clip(lower=0)
        fcf_series = _numeric_series(score_df, "free_cash_flow", 0.0)

        valuation_score = inverse_normalize(pe_series.clip(lower=0))
        size_score = normalize(market_cap_series.map(lambda value: math.log10(value + 1)))
        roe_score = normalize(roe_series)
        margin_score = normalize(margin_series)
        quality_score = (roe_score * 0.58) + (margin_score * 0.42)
        debt_score = inverse_normalize(debt_series)
        liquidity_score = normalize(current_ratio_series)
        fcf_score = (fcf_series > 0).astype(float)
        stability_score = (debt_score * 0.45) + (liquidity_score * 0.25) + (fcf_score * 0.30)
        income_score = normalize(dividend_series.clip(lower=0))
        growth_score = normalize(growth_series)

        total_weight = sum(weights.values()) or 1.0
        raw_score = (
            valuation_score * weights["valuation"]
            + quality_score * weights["quality"]
            + stability_score * weights["stability"]
            + income_score * weights["income"]
            + growth_score * weights["growth"]
            + size_score * weights["size"]
        )
        score_df["total_score"] = (raw_score / total_weight) * 100
        score_df = score_df.sort_values(by="total_score", ascending=False)
        eligible_df = score_df[score_df["metric_coverage"] >= 3]
        if not eligible_df.empty:
            score_df = eligible_df

    db_candidates: list[str] = []
    if not score_df.empty and "ticker" in score_df.columns:
        db_candidates = score_df["ticker"].head(payload.options.max_results).tolist()

    final_pool = list(dict.fromkeys(db_candidates + user_tickers))
    comparison_matrix: list[dict[str, Any]] = []

    for ticker in final_pool:
        row_match = pd.DataFrame()
        if not score_df.empty and "ticker" in score_df.columns:
            row_match = score_df[score_df["ticker"] == ticker]
        if row_match.empty and "ticker" in db_df.columns:
            row_match = db_df[db_df["ticker"] == ticker]

        if row_match.empty:
            comparison_matrix.append(
                {
                    "Ticker": ticker,
                    "Company_Name": "Unknown",
                    "Sector": "Unknown",
                    "PE_Ratio": "N/A",
                    "ROE": "N/A",
                    "Dividend_Yield": "N/A",
                    "Analyst_Rating": "N/A",
                    "Market_Cap": None,
                    "Profit_Margin": None,
                    "Debt_to_Equity": None,
                    "Current_Ratio": None,
                    "Free_Cash_Flow": None,
                    "Revenue_Growth_QoQ": None,
                    "Total_Quant_Score": 0.0,
                }
            )
            continue

        row = row_match.iloc[0]
        pe_ratio = pd.to_numeric(pd.Series([row.get("pe_ratio")]), errors="coerce").iloc[0]
        roe = _percent_points_series(pd.DataFrame([row]), "roe", 12.0, lower=-20, upper=45).iloc[0]
        dividend_yield = _percent_points_series(pd.DataFrame([row]), "dividend_yield", 0.0, lower=0, upper=10).iloc[0]
        total_score = row.get("total_score", 0.0)

        comparison_matrix.append(
            {
                "Ticker": ticker,
                "Company_Name": row.get("name", "Unknown"),
                "Sector": row.get("sector", "Unknown"),
                "PE_Ratio": round(float(pe_ratio), 2) if pd.notna(pe_ratio) else "N/A",
                "ROE": f"{round(float(roe) * 100, 2)}%" if pd.notna(roe) else "N/A",
                "Dividend_Yield": f"{round(float(dividend_yield), 2)}%" if pd.notna(dividend_yield) else "N/A",
                "Analyst_Rating": row.get("analyst_rec", "N/A"),
                "Market_Cap": safe_float(row.get("market_cap")),
                "Profit_Margin": safe_float(row.get("profit_margin")),
                "Debt_to_Equity": safe_float(row.get("debt_to_equity")),
                "Current_Ratio": safe_float(row.get("current_ratio")),
                "Free_Cash_Flow": safe_float(row.get("free_cash_flow")),
                "Revenue_Growth_QoQ": safe_float(row.get("rev_growth_qoq")),
                "Total_Quant_Score": round(float(total_score), 1) if pd.notna(total_score) else 0.0,
            }
        )

    return {
        "analysis_context": "结构化筛选已完成。",
        "comparison_matrix": sorted(
            comparison_matrix,
            key=lambda item: item.get("Total_Quant_Score", 0),
            reverse=True,
        ),
    }
