"""Tests for BacktestService core logic."""

from datetime import date, datetime
import pytest

import pandas as pd

from app.services.backtest_service import BacktestService, PortfolioPosition
from app.core.config import AppSettings
from app.repositories.sqlite_run_repository import SqliteRunRepository


class TestAnnualizedReturnPct:
    """Test annualized return calculation."""

    def test_annualized_return_positive(self):
        """Test positive annualized return."""
        result = BacktestService._annualized_return_pct(
            initial_value=1000.0,
            final_value=1100.0,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        assert result is not None
        assert result > 0
        assert result < 20  # Should be around 10%

    def test_annualized_return_negative(self):
        """Test negative annualized return."""
        result = BacktestService._annualized_return_pct(
            initial_value=1000.0,
            final_value=900.0,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        assert result is not None
        assert result < 0

    def test_annualized_return_short_period(self):
        """Test that short period returns None."""
        result = BacktestService._annualized_return_pct(
            initial_value=1000.0,
            final_value=1100.0,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 10),
        )
        assert result is None

    def test_annualized_return_zero_initial(self):
        """Test that zero initial value returns None."""
        result = BacktestService._annualized_return_pct(
            initial_value=0.0,
            final_value=1100.0,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        assert result is None


class TestMaxDrawdownPct:
    """Test maximum drawdown calculation."""

    def test_max_drawdown_no_drawdown(self):
        """Test max drawdown with no drawdown."""
        points = [
            {"portfolio_value": 1000.0},
            {"portfolio_value": 1100.0},
            {"portfolio_value": 1200.0},
            {"portfolio_value": 1300.0},
        ]
        result = BacktestService._max_drawdown_pct(points)
        assert result == 0.0

    def test_max_drawdown_simple(self):
        """Test max drawdown with simple drawdown."""
        points = [
            {"portfolio_value": 1000.0},
            {"portfolio_value": 900.0},  # 10% drawdown
            {"portfolio_value": 950.0},
            {"portfolio_value": 1100.0},
        ]
        result = BacktestService._max_drawdown_pct(points)
        assert result == pytest.approx(-10.0, rel=0.01)

    def test_max_drawdown_multiple_peaks(self):
        """Test max drawdown with multiple peaks."""
        points = [
            {"portfolio_value": 1000.0},
            {"portfolio_value": 1100.0},  # Peak 1
            {"portfolio_value": 900.0},  # Drawdown
            {"portfolio_value": 1200.0},  # New peak
            {"portfolio_value": 1000.0},  # Drawdown from peak 2
            {"portfolio_value": 1300.0},
        ]
        result = BacktestService._max_drawdown_pct(points)
        # Should be larger than simple drawdown
        assert result < -15.0

    def test_max_drawdown_empty_points(self):
        """Test max drawdown with empty points."""
        result = BacktestService._max_drawdown_pct([])
        assert result is None


class TestResolveCapitalAndCurrency:
    """Test capital and currency resolution."""

    def test_resolve_capital_valid(self):
        """Test valid capital resolution."""
        settings = AppSettings()
        service = BacktestService(repository=None, settings=settings)  # type: ignore
        result = service._resolve_capital_and_currency(
            {
                "parsed_intent": {
                    "portfolio_sizing": {
                        "capital_amount": 100000.0,
                        "currency": "USD",
                    }
                }
            }
        )
        assert result == (100000.0, "USD")

    def test_resolve_capital_invalid_amount(self):
        """Test invalid capital amount falls back to default."""
        settings = AppSettings()
        service = BacktestService(repository=None, settings=settings)  # type: ignore
        result = service._resolve_capital_and_currency(
            {
                "parsed_intent": {
                    "portfolio_sizing": {
                        "capital_amount": "invalid",
                        "currency": "USD",
                    }
                }
            }
        )
        assert result == (10000.0, "USD")

    def test_resolve_capital_negative_amount(self):
        """Test negative capital amount falls back to default."""
        settings = AppSettings()
        service = BacktestService(repository=None, settings=settings)  # type: ignore
        result = service._resolve_capital_and_currency(
            {
                "parsed_intent": {
                    "portfolio_sizing": {
                        "capital_amount": -1000.0,
                        "currency": "USD",
                    }
                }
            }
        )
        assert result == (10000.0, "USD")

    def test_resolve_capital_missing(self):
        """Test missing capital falls back to default."""
        settings = AppSettings()
        service = BacktestService(repository=None, settings=settings)  # type: ignore
        result = service._resolve_capital_and_currency({})
        assert result == (10000.0, "USD")


class TestBuildPositionsSeed:
    """Test positions seed building."""

    def test_build_positions_from_allocation_plan(self):
        """Test building positions from allocation plan."""
        settings = AppSettings()
        service = BacktestService(repository=None, settings=settings)  # type: ignore

        executive = {
            "allocation_plan": [
                {"ticker": "AAPL", "weight": 40, "verdict": "Buy"},
                {"ticker": "MSFT", "weight": 30, "verdict": "Hold"},
            ]
        }

        result = service._build_positions_seed(executive=executive, scoreboard=[], report_briefing={})
        assert len(result) == 2
        assert result[0]["ticker"] == "AAPL"
        assert result[0]["weight"] == 57.142857142857146  # Normalized to 100
        assert result[1]["ticker"] == "MSFT"

    def test_build_positions_from_scoreboard(self):
        """Test building positions from scoreboard when no allocation plan."""
        settings = AppSettings()
        service = BacktestService(repository=None, settings=settings)  # type: ignore

        scoreboard = [
            {"ticker": "AAPL", "score": 80},
            {"ticker": "MSFT", "score": 75},
        ]

        result = service._build_positions_seed(executive={}, scoreboard=scoreboard, report_briefing={})
        assert len(result) == 2
        assert all(p["weight"] == 50.0 for p in result)  # Equal weights

    def test_build_positions_normalizes_weights(self):
        """Test that weights are normalized to 100."""
        settings = AppSettings()
        service = BacktestService(repository=None, settings=settings)  # type: ignore

        executive = {
            "allocation_plan": [
                {"ticker": "AAPL", "weight": 2, "verdict": "Buy"},
                {"ticker": "MSFT", "weight": 3, "verdict": "Hold"},
            ]
        }

        result = service._build_positions_seed(executive=executive, scoreboard=[], report_briefing={})
        total_weight = sum(p["weight"] for p in result)
        assert total_weight == pytest.approx(100.0, rel=0.01)


class TestMaterializePortfolioPositions:
    """Test portfolio position materialization."""

    def test_materialize_positions(self, sample_portfolio_data, sample_price_history):
        """Test materializing portfolio positions."""
        settings = AppSettings()
        service = BacktestService(repository=None, settings=settings)  # type: ignore

        positions_seed = [
            {"ticker": "AAPL", "weight": 40.0, "verdict": "Buy"},
            {"ticker": "MSFT", "weight": 60.0, "verdict": "Hold"},
        ]

        price_frames = {
            "AAPL": pd.DataFrame(
                {"Open": [140.0, 145.0, 150.0], "Close": [141.0, 146.0, 151.0]},
                index=pd.date_range("2026-01-01", periods=3, freq="D"),
            ),
            "MSFT": pd.DataFrame(
                {"Open": [280.0, 285.0, 290.0], "Close": [281.0, 286.0, 291.0]},
                index=pd.date_range("2026-01-01", periods=3, freq="D"),
            ),
        }

        entry_date = date(2026, 1, 1)
        capital_amount = 10000.0

        positions = service._materialize_portfolio_positions(
            positions_seed=positions_seed,
            capital_amount=capital_amount,
            entry_date=entry_date,
            price_frames=price_frames,
        )

        assert len(positions) == 2
        assert positions[0].ticker == "AAPL"
        assert positions[0].weight == 40.0
        assert positions[0].entry_price == 140.0
        assert positions[0].invested_amount == 4000.0
        assert positions[0].shares == pytest.approx(28.571428571428573, rel=0.01)


class TestFindCommonDates:
    """Test common date finding."""

    def test_find_common_dates(self, sample_price_history):
        """Test finding common dates across multiple frames."""
        settings = AppSettings()
        service = BacktestService(repository=None, settings=settings)  # type: ignore

        price_frames = {
            "AAPL": pd.DataFrame(
                {"Close": [140.0, 145.0, 150.0]},
                index=pd.date_range("2026-01-01", periods=3, freq="D"),
            ),
            "MSFT": pd.DataFrame(
                {"Close": [280.0, 285.0, 290.0]},
                index=pd.date_range("2026-01-01", periods=3, freq="D"),
            ),
        }

        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 3)

        common_dates = service._find_common_dates(
            price_frames=price_frames,
            start_date=start_date,
            end_date=end_date,
            include_start=False,
            benchmark_frame=None,
        )

        assert len(common_dates) == 2  # Excluding start date
        assert common_dates[0] == date(2026, 1, 2)
        assert common_dates[1] == date(2026, 1, 3)

    def test_find_common_dates_with_benchmark(self):
        """Test finding common dates including benchmark."""
        settings = AppSettings()
        service = BacktestService(repository=None, settings=settings)  # type: ignore

        price_frames = {
            "AAPL": pd.DataFrame(
                {"Close": [140.0, 145.0, 150.0]},
                index=pd.date_range("2026-01-01", periods=3, freq="D"),
            ),
        }

        benchmark_frame = pd.DataFrame(
            {"Close": [100.0, 101.0, 102.0]},
            index=pd.date_range("2026-01-01", periods=3, freq="D"),
        )

        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 3)

        common_dates = service._find_common_dates(
            price_frames=price_frames,
            start_date=start_date,
            end_date=end_date,
            include_start=False,
            benchmark_frame=benchmark_frame,
        )

        assert len(common_dates) == 2


class TestPortfolioPosition:
    """Test PortfolioPosition dataclass."""

    def test_portfolio_position_creation(self):
        """Test creating a portfolio position."""
        position = PortfolioPosition(
            ticker="AAPL",
            weight=40.0,
            verdict="Buy",
            entry_price=150.0,
            shares=26.666666666666668,
            invested_amount=4000.0,
        )
        assert position.ticker == "AAPL"
        assert position.weight == 40.0
        assert position.verdict == "Buy"
        assert position.entry_price == 150.0
        assert position.invested_amount == 4000.0
