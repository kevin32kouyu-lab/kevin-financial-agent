"""
意图解析与长期记忆之间的桥接逻辑。
负责把长期偏好补回本次请求，并生成结果页需要的 memory 信息。
"""

from __future__ import annotations

from app.domain.contracts import RunMemory, UserProfile

from .intent import (
    _apply_assumptions,
    _build_missing_info,
    _is_intent_clear,
    _is_intent_usable,
    _is_speculative,
    _normalize_query,
    extract_explicit_intent,
)
from .models import AgentControl, ParsedIntent


PROFILE_FIELD_MAP = {
    "capital_amount": ("portfolio_sizing", "capital_amount"),
    "currency": ("portfolio_sizing", "currency"),
    "risk_tolerance": ("risk_profile", "tolerance_level"),
    "investment_horizon": ("investment_strategy", "horizon"),
    "investment_style": ("investment_strategy", "style"),
    "preferred_sectors": ("investment_strategy", "preferred_sectors"),
    "preferred_industries": ("investment_strategy", "preferred_industries"),
}


def build_user_profile_from_intent(intent: ParsedIntent) -> UserProfile:
    """从用户本次显式意图里抽取可长期记住的字段。"""
    return UserProfile(
        capital_amount=intent.portfolio_sizing.capital_amount,
        currency=intent.portfolio_sizing.currency,
        risk_tolerance=intent.risk_profile.tolerance_level,
        investment_horizon=intent.investment_strategy.horizon,
        investment_style=intent.investment_strategy.style,
        preferred_sectors=list(intent.investment_strategy.preferred_sectors),
        preferred_industries=list(intent.investment_strategy.preferred_industries),
    )


def apply_profile_to_intent(intent: ParsedIntent, profile: UserProfile) -> list[str]:
    """只在当前请求缺失时，用长期记忆补空字段。"""
    applied_fields: list[str] = []

    for field_name, path in PROFILE_FIELD_MAP.items():
        profile_value = getattr(profile, field_name)
        if not _has_value(profile_value):
            continue

        target = getattr(intent, path[0])
        current_value = getattr(target, path[1])
        if _has_value(current_value):
            continue

        setattr(target, path[1], profile_value if not isinstance(profile_value, list) else list(profile_value))
        applied_fields.append(field_name)

    return applied_fields


def parse_intent_with_memory(query: str, profile: UserProfile | None = None) -> tuple[ParsedIntent, RunMemory]:
    """按“显式输入 > 长期记忆 > 默认假设”的顺序构建最终意图。"""
    normalized_query = _normalize_query(query)
    resolved_profile = profile.model_copy(deep=True) if profile is not None else UserProfile()

    explicit_intent = extract_explicit_intent(normalized_query)
    intent = explicit_intent.model_copy(deep=True)
    applied_fields = apply_profile_to_intent(intent, resolved_profile)

    speculative = _is_speculative(normalized_query)
    assumptions = _apply_assumptions(intent, normalized_query)
    is_clear = _is_intent_clear(intent, speculative)
    is_usable = _is_intent_usable(intent, speculative)
    missing_info = [] if is_clear else _build_missing_info(intent)
    if speculative and "investment_style" not in missing_info:
        missing_info.insert(0, "investment_style")

    intent.agent_control = AgentControl(
        is_intent_clear=is_clear,
        is_intent_usable=is_usable,
        missing_critical_info=missing_info,
        assumptions=assumptions,
    )

    return intent, RunMemory(profile=resolved_profile, applied_fields=applied_fields, updated_fields=[])


def _has_value(value: object) -> bool:
    """判断字段是否已经有明确值。"""
    if value is None:
        return False
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, str):
        return bool(value.strip())
    return True
