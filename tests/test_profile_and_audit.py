"""偏好持久化与审计摘要测试。"""

from app.domain.contracts import PreferenceUpdateRequest, RunDetail, RunSummary
from app.repositories.sqlite_run_repository import SqliteRunRepository
from app.services.profile_service import ProfileService
from app.services.run_audit_service import RunAuditService


def test_profile_service_persists_preferences(tmp_path):
    """确认最近一次偏好会被稳定保存并可再次读取。"""
    repository = SqliteRunRepository(tmp_path / "runs.sqlite3")
    repository.init_schema()
    service = ProfileService(repository)

    saved = service.update_preferences(
        PreferenceUpdateRequest(
            capital_amount=50000,
            currency="USD",
            risk_tolerance="medium",
            investment_horizon="long_term",
            investment_style="quality",
            preferred_sectors=["Healthcare", "Consumer Defensive"],
            preferred_industries=["Beverages"],
            explicit_tickers=["JNJ", "KO"],
            excluded_sectors=["Energy"],
            excluded_tickers=["TSLA"],
            default_market="US",
            investment_goal="stable income",
            confirmed_fields=["capital_amount", "risk_tolerance", "investment_goal"],
            locale="zh",
            research_mode="realtime",
            source_query="我有 50000 美元，想找适合长期持有的低风险分红股。",
        )
    )

    assert saved.values.capital_amount == 50000
    assert saved.values.currency == "USD"
    assert saved.values.risk_tolerance == "medium"
    assert saved.values.explicit_tickers == ["JNJ", "KO"]
    assert saved.values.excluded_sectors == ["Energy"]
    assert saved.values.excluded_tickers == ["TSLA"]
    assert saved.values.default_market == "US"
    assert saved.values.investment_goal == "stable income"
    assert saved.values.confirmed_fields == ["capital_amount", "risk_tolerance", "investment_goal"]
    assert saved.research_mode == "realtime"

    restored = service.get_preferences()

    assert restored is not None
    assert restored.values.investment_style == "quality"
    assert restored.values.preferred_sectors == ["Healthcare", "Consumer Defensive"]
    assert restored.values.excluded_sectors == ["Energy"]
    assert restored.source_query == "我有 50000 美元，想找适合长期持有的低风险分红股。"


def test_profile_snapshot_requires_confirmation_for_critical_fields(tmp_path):
    """自动学习不能静默覆盖资金、风险和投资目标。"""
    repository = SqliteRunRepository(tmp_path / "runs.sqlite3")
    repository.init_schema()
    service = ProfileService(repository)
    service.update_preferences(
        PreferenceUpdateRequest(
            capital_amount=50000,
            currency="USD",
            risk_tolerance="medium",
            investment_goal="stable income",
            investment_style="quality",
            preferred_sectors=["Healthcare"],
            confirmed_fields=["capital_amount", "risk_tolerance", "investment_goal"],
        )
    )

    stored = service.save_snapshot(
        run_id="run-002",
        snapshot={
            "query": "I have 100000 USD and want aggressive growth.",
            "locale": "en",
            "research_mode": "realtime",
            "values": {
                "capital_amount": 100000,
                "currency": "USD",
                "risk_tolerance": "high",
                "investment_goal": "aggressive growth",
                "investment_style": "Growth",
                "preferred_sectors": ["Technology"],
                "default_market": "US",
            },
        },
    )

    assert stored.values.capital_amount == 50000
    assert stored.values.risk_tolerance == "medium"
    assert stored.values.investment_goal == "stable income"
    assert stored.values.investment_style == "Growth"
    assert stored.values.preferred_sectors == ["Technology"]
    assert stored.values.default_market == "US"
    assert stored.values.confirmed_fields == ["capital_amount", "risk_tolerance", "investment_goal"]
    assert stored.values.pending_confirmations == {
        "capital_amount": 100000,
        "risk_tolerance": "high",
        "investment_goal": "aggressive growth",
    }


def test_run_audit_service_builds_user_readable_summary():
    """确认历史页能拿到用户可读的审计摘要。"""
    service = RunAuditService()
    detail = RunDetail(
        run=RunSummary(
            id="run-001",
            mode="agent",
            workflow_key="financial_agent",
            status="completed",
            title="低风险分红股研究",
            created_at="2026-04-20T10:00:00Z",
            updated_at="2026-04-20T10:05:00Z",
            report_mode="final_report",
        ),
        result={
            "query": "我有 50000 美元，想找低风险分红股。",
            "report_mode": "final_report",
            "research_context": {
                "research_mode": "historical",
                "as_of_date": "2025-10-01",
            },
            "memory_applied_fields": ["risk_tolerance", "investment_horizon"],
            "report_briefing": {
                "meta": {
                    "confidence_level": "medium",
                    "validation_flags": ["估值处于历史中高位"],
                    "coverage_flags": ["历史新闻覆盖不足"],
                    "safety_summary": {
                        "used_sources": ["Yahoo Finance", "SEC EDGAR"],
                        "degraded_modules": ["historical_news"],
                    },
                },
                "executive": {
                    "top_pick": "JNJ",
                },
            },
        },
    )

    summary = service.build_summary(detail)

    assert summary.run_id == "run-001"
    assert summary.query == "我有 50000 美元，想找低风险分红股。"
    assert summary.research_mode == "historical"
    assert summary.as_of_date == "2025-10-01"
    assert summary.top_pick == "JNJ"
    assert summary.confidence_level == "medium"
    assert summary.validation_flags == ["估值处于历史中高位"]
    assert summary.coverage_flags == ["历史新闻覆盖不足"]
    assert summary.used_sources == ["Yahoo Finance", "SEC EDGAR"]
    assert summary.degraded_modules == ["historical_news"]
    assert summary.memory_applied_fields == ["risk_tolerance", "investment_horizon"]
