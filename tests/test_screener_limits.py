"""筛选器候选数量限制回归测试。"""

import pandas as pd

from app.analysis_runtime.models import DebugAnalysisRequest
from app.analysis_runtime.screener import run_screener_analysis


def test_screener_respects_max_results_limit() -> None:
    """无论用户额外输入多少标的，最终结果都不超过 max_results。"""
    universe = pd.DataFrame(
        [
            {"ticker": "AAA", "name": "AAA", "sector": "Tech", "pe_ratio": 20, "roe": 0.20, "profit_margin": 0.18, "debt_to_equity": 0.5, "dividend_yield": 1.0, "market_cap": 10_000_000_000, "free_cash_flow": 100_000_000, "rev_growth_qoq": 0.05, "current_ratio": 1.6},
            {"ticker": "BBB", "name": "BBB", "sector": "Tech", "pe_ratio": 18, "roe": 0.22, "profit_margin": 0.20, "debt_to_equity": 0.4, "dividend_yield": 1.2, "market_cap": 12_000_000_000, "free_cash_flow": 120_000_000, "rev_growth_qoq": 0.06, "current_ratio": 1.7},
            {"ticker": "CCC", "name": "CCC", "sector": "Tech", "pe_ratio": 16, "roe": 0.24, "profit_margin": 0.22, "debt_to_equity": 0.3, "dividend_yield": 1.4, "market_cap": 15_000_000_000, "free_cash_flow": 150_000_000, "rev_growth_qoq": 0.07, "current_ratio": 1.8},
            {"ticker": "DDD", "name": "DDD", "sector": "Tech", "pe_ratio": 22, "roe": 0.18, "profit_margin": 0.16, "debt_to_equity": 0.6, "dividend_yield": 0.8, "market_cap": 9_000_000_000, "free_cash_flow": 90_000_000, "rev_growth_qoq": 0.04, "current_ratio": 1.5},
            {"ticker": "EEE", "name": "EEE", "sector": "Tech", "pe_ratio": 19, "roe": 0.21, "profit_margin": 0.19, "debt_to_equity": 0.45, "dividend_yield": 1.1, "market_cap": 11_000_000_000, "free_cash_flow": 110_000_000, "rev_growth_qoq": 0.055, "current_ratio": 1.65},
            {"ticker": "FFF", "name": "FFF", "sector": "Tech", "pe_ratio": 17, "roe": 0.23, "profit_margin": 0.21, "debt_to_equity": 0.35, "dividend_yield": 1.3, "market_cap": 13_000_000_000, "free_cash_flow": 130_000_000, "rev_growth_qoq": 0.065, "current_ratio": 1.75},
        ]
    )

    payload = DebugAnalysisRequest.model_validate(
        {
            "options": {"max_results": 3},
            "explicit_targets": {"tickers": ["FFF", "EEE", "ZZZ"]},
        }
    )

    result = run_screener_analysis(payload, universe)
    comparison_matrix = result.get("comparison_matrix") or []
    assert len(comparison_matrix) == 3
