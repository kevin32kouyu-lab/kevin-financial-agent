"""
测试显式意图、长期记忆和默认假设的优先级。
"""

from app.agent_runtime.intent import extract_explicit_intent
from app.agent_runtime.memory import build_user_profile_from_intent, parse_intent_with_memory
from app.repositories.sqlite_profile_repository import SqliteProfileRepository
from app.services.profile_service import ProfileService


def test_memory_fills_missing_fields_without_overwriting_explicit():
    stored_profile = build_user_profile_from_intent(
        extract_explicit_intent("我偏低风险，打算长期持有分红股")
    )

    intent, memory = parse_intent_with_memory("请给我推荐几只成长股", stored_profile)

    assert intent.investment_strategy.style == "Growth"
    assert intent.risk_profile.tolerance_level == "Low"
    assert intent.investment_strategy.horizon == "Long-term"
    assert "risk_tolerance" in memory.applied_fields
    assert "investment_horizon" in memory.applied_fields
    assert "investment_style" not in memory.applied_fields


def test_assumptions_are_not_written_back_to_profile(tmp_path):
    repo = SqliteProfileRepository(tmp_path / "runs.sqlite3")
    repo.init_schema()
    service = ProfileService(repo)

    explicit_intent = extract_explicit_intent("我想做红利股投资")
    explicit_profile = build_user_profile_from_intent(explicit_intent)
    _, updated_fields = service.merge_explicit_profile("browser-b", explicit_profile)
    saved_profile = service.get_profile("browser-b").profile

    assert updated_fields == ["investment_style"]
    assert saved_profile.investment_style == "Dividend"
    assert saved_profile.risk_tolerance is None
    assert saved_profile.investment_horizon is None

    parsed_intent, memory = parse_intent_with_memory("我想做红利股投资", saved_profile)
    assert parsed_intent.risk_profile.tolerance_level == "Medium"
    assert parsed_intent.investment_strategy.horizon == "Long-term"
    assert memory.profile.risk_tolerance is None
    assert memory.profile.investment_horizon is None


def test_saved_profile_reduces_repeat_questions(tmp_path):
    repo = SqliteProfileRepository(tmp_path / "runs.sqlite3")
    repo.init_schema()
    service = ProfileService(repo)

    first_intent = extract_explicit_intent("我偏低风险，想长期持有")
    service.merge_explicit_profile("browser-c", build_user_profile_from_intent(first_intent))
    saved_profile = service.get_profile("browser-c").profile

    next_intent, memory = parse_intent_with_memory("请给我推荐一些美股", saved_profile)

    assert next_intent.risk_profile.tolerance_level == "Low"
    assert next_intent.investment_strategy.horizon == "Long-term"
    assert "risk_tolerance" in memory.applied_fields
    assert "investment_horizon" in memory.applied_fields
    assert "risk_tolerance" not in next_intent.agent_control.missing_critical_info
    assert "investment_horizon" not in next_intent.agent_control.missing_critical_info
