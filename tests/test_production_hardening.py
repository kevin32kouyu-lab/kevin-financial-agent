"""生产级补强测试：账户、审计、回测口径和数据刷新任务。"""

from datetime import date
from types import SimpleNamespace

import pandas as pd
from starlette.requests import Request

from app.core.auth import get_client_id
from app.core.config import AppSettings
from app.domain.contracts import (
    BacktestAssumptions,
    AuthLoginRequest,
    AuthRegisterRequest,
    PreferenceUpdateRequest,
)
from app.repositories.sqlite_run_repository import SqliteRunRepository
from app.services.auth_service import AuthService
from app.services.backtest_service import BacktestService
from app.services.market_data_service import MarketDataService
from app.services.profile_service import ProfileService


def test_auth_service_registers_logs_in_and_writes_audit_event(tmp_path):
    """账户注册和登录后应写入可追踪审计事件。"""
    repository = SqliteRunRepository(tmp_path / "runs.sqlite3")
    repository.init_schema()
    service = AuthService(repository, AppSettings(session_secret="test-secret"))

    registered = service.register(AuthRegisterRequest(email="user@example.com", password="secret123"))
    logged_in = service.login(AuthLoginRequest(email="user@example.com", password="secret123"))
    audit_events = repository.list_audit_events(actor_user_id=registered.user.id)

    assert registered.user.email == "user@example.com"
    assert logged_in.session_token
    assert logged_in.user.id == registered.user.id
    assert [item["action"] for item in audit_events] == ["auth.register", "auth.login"]


def test_profile_service_prefers_user_memory_and_can_link_client_memory(tmp_path):
    """登录后可以把浏览器记忆绑定到账户，之后优先读取账户记忆。"""
    repository = SqliteRunRepository(tmp_path / "runs.sqlite3")
    repository.init_schema()
    profile_service = ProfileService(repository)
    client_id = "browser-001"
    user_id = "user-001"

    profile_service.update_preferences(
        PreferenceUpdateRequest(
            capital_amount=50000,
            currency="USD",
            risk_tolerance="medium",
            investment_horizon="long_term",
            investment_style="quality",
            preferred_sectors=["Healthcare"],
            locale="zh",
            source_query="浏览器里的旧偏好",
        ),
        profile_id=client_id,
    )

    linked = profile_service.link_client_memory_to_user(client_id=client_id, user_id=user_id)
    restored = profile_service.get_preferences(profile_id=client_id, user_id=user_id)

    assert linked.profile_id == f"user:{user_id}"
    assert restored.profile_id == f"user:{user_id}"
    assert restored.values.capital_amount == 50000
    assert restored.source_query == "浏览器里的旧偏好"


def test_backtest_v2_assumptions_support_dividends_tax_and_rebalance():
    """回测 V2 应接受真实口径参数，并记录分红、税费和再平衡结果。"""
    service = BacktestService(repository=None, settings=AppSettings())  # type: ignore[arg-type]
    assumptions = BacktestAssumptions(
        transaction_cost_bps=10,
        slippage_bps=5,
        dividend_mode="reinvest",
        tax_mode="flat_rate",
        tax_rate_pct=15,
        rebalance="monthly",
    )
    frame = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 110.0, 120.0],
            "Close": [100.0, 110.0, 120.0, 130.0],
            "Dividend": [0.0, 1.0, 0.0, 0.0],
        },
        index=pd.to_datetime(["2026-01-02", "2026-01-31", "2026-02-02", "2026-02-28"]),
    )
    positions = service._materialize_portfolio_positions(
        positions_seed=[{"ticker": "AAPL", "weight": 100.0, "verdict": "Buy"}],
        capital_amount=10000.0,
        entry_date=date(2026, 1, 2),
        price_frames={"AAPL": frame},
        assumptions=assumptions.model_dump(),
    )

    points, _benchmark_value, rebalance_events, dividend_summary = service._build_backtest_points(
        positions=positions,
        price_frames={"AAPL": frame},
        benchmark_frame=None,
        common_dates=[date(2026, 1, 31), date(2026, 2, 2), date(2026, 2, 28)],
        capital_amount=10000.0,
        benchmark_entry_price=None,
        assumptions=assumptions.model_dump(),
    )
    tax_summary = service._build_tax_summary(
        final_value=points[-1]["portfolio_value"],
        capital_amount=10000.0,
        assumptions=assumptions.model_dump(),
    )

    assert points[-1]["portfolio_value"] > 12980
    assert dividend_summary["dividend_included"] is True
    assert dividend_summary["dividend_mode"] == "reinvest"
    assert rebalance_events
    assert tax_summary["tax_applied"] is True
    assert tax_summary["tax_amount"] > 0


def test_market_data_service_records_refresh_jobs(tmp_path):
    """手动刷新任务应留下任务状态，方便前台和运维查看。"""
    settings = AppSettings(market_db_path=tmp_path / "market.sqlite3")
    service = MarketDataService(settings)
    service.startup()

    result = service.record_refresh_job(dataset="security_master", source="unit_test", row_count=3)
    jobs = service.list_refresh_jobs()

    assert result["dataset"] == "security_master"
    assert jobs["items"][0]["dataset"] == "security_master"
    assert jobs["items"][0]["status"] == "completed"


def test_client_id_allows_event_stream_query_fallback():
    """事件流不能自定义请求头时，后端也应能从 query string 读取 client_id。"""
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/runs/demo-run/events",
            "query_string": b"client_id=browser-001",
            "headers": [],
            "app": SimpleNamespace(state=SimpleNamespace()),
        }
    )

    assert get_client_id(request) == "browser-001"
