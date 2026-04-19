"""Pytest configuration and shared fixtures for Financial Agent tests."""

import pytest
from datetime import date
from typing import Any


@pytest.fixture
def sample_ticker_data() -> dict[str, Any]:
    """Sample ticker data for testing.

    Returns:
        Dictionary with basic ticker information
    """
    return {
        "ticker": "AAPL",
        "price": 150.0,
        "volume": 1000000,
        "market_cap": 2_500_000_000_000,
    }


@pytest.fixture
def sample_portfolio_data() -> dict[str, Any]:
    """Sample portfolio data for testing.

    Returns:
        Dictionary with portfolio information
    """
    return {
        "tickers": ["AAPL", "MSFT", "GOOGL"],
        "weights": [0.4, 0.35, 0.25],
        "total_value": 1_000_000.0,
    }


@pytest.fixture
def sample_price_history() -> dict[str, list[float]]:
    """Sample price history for backtest testing.

    Returns:
        Dictionary mapping tickers to price series
    """
    return {
        "AAPL": [140.0, 145.0, 150.0, 155.0, 160.0],
        "MSFT": [280.0, 285.0, 290.0, 295.0, 300.0],
        "GOOGL": [120.0, 125.0, 130.0, 135.0, 140.0],
    }


@pytest.fixture
def sample_scoring_data() -> dict[str, Any]:
    """Sample data for scoring algorithm testing.

    Returns:
        Dictionary with financial metrics for scoring
    """
    return {
        "ticker": "AAPL",
        "pe_ratio": 25.0,
        "pb_ratio": 5.0,
        "roe": 0.25,
        "debt_to_equity": 0.5,
        "current_ratio": 1.5,
        "momentum_3m": 0.15,
        "momentum_12m": 0.30,
        "volatility": 0.20,
    }


@pytest.fixture
def sample_run_result() -> dict[str, Any]:
    """Sample run result for testing.

    Returns:
        Dictionary mimicking a completed run result
    """
    return {
        "status": "completed",
        "mode": "agent",
        "query": "Find low-risk tech stocks",
        "research_context": {
            "research_mode": "agent",
            "as_of_date": "2026-04-14",
        },
        "analysis": {
            "candidates": [
                {
                    "ticker": "AAPL",
                    "weight": 0.4,
                    "rationale": "Strong fundamentals",
                },
            ],
        },
    }
