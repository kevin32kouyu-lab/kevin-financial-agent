"""轻量记忆合并逻辑。

这个文件负责把前端传来的最近一次偏好，安全地补到当前意图里。
它只会补“当前问题没有明确写出来”的字段，不会覆盖用户本次已经说明的信息。
"""

from __future__ import annotations

from typing import Any

from .intent import (
    _build_missing_info,
    _is_intent_clear,
    _is_intent_usable,
    _is_speculative,
    _localized_assumption,
)
from .models import AgentMemoryContext, ParsedIntent


def _clean_list(values: list[str] | None) -> list[str]:
    """清理并去重列表文本。"""
    cleaned: list[str] = []
    for item in values or []:
        text = str(item or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _field_labels(language_code: str) -> dict[str, str]:
    """返回记忆字段的人类可读名称。"""
    if language_code == "zh":
        return {
            "capital_amount": "投入金额",
            "risk_tolerance": "风险偏好",
            "investment_horizon": "投资期限",
            "investment_style": "研究风格",
            "preferred_sectors": "偏好板块",
            "preferred_industries": "偏好行业",
        }
    return {
        "capital_amount": "capital",
        "risk_tolerance": "risk preference",
        "investment_horizon": "investment horizon",
        "investment_style": "research style",
        "preferred_sectors": "preferred sectors",
        "preferred_industries": "preferred industries",
    }


def merge_memory_context(
    intent: ParsedIntent,
    *,
    query: str,
    memory_context: AgentMemoryContext | None,
) -> dict[str, Any]:
    """把轻量记忆补到当前意图里，并重新评估意图质量。"""
    if memory_context is None:
        return {
            "used": False,
            "applied_fields": [],
            "applied_labels": [],
            "note": None,
        }

    applied_fields: list[str] = []
    language_code = intent.system_context.language
    labels = _field_labels(language_code)

    if not intent.portfolio_sizing.capital_amount and memory_context.capital_amount:
        intent.portfolio_sizing.capital_amount = memory_context.capital_amount
        if not intent.portfolio_sizing.currency and memory_context.currency:
            intent.portfolio_sizing.currency = memory_context.currency
        applied_fields.append("capital_amount")

    if not intent.risk_profile.tolerance_level and memory_context.risk_tolerance:
        intent.risk_profile.tolerance_level = memory_context.risk_tolerance
        applied_fields.append("risk_tolerance")

    if not intent.investment_strategy.horizon and memory_context.investment_horizon:
        intent.investment_strategy.horizon = memory_context.investment_horizon
        applied_fields.append("investment_horizon")

    if not intent.investment_strategy.style and memory_context.investment_style:
        intent.investment_strategy.style = memory_context.investment_style
        applied_fields.append("investment_style")

    if not intent.investment_strategy.preferred_sectors and memory_context.preferred_sectors:
        intent.investment_strategy.preferred_sectors = _clean_list(memory_context.preferred_sectors)
        applied_fields.append("preferred_sectors")

    if not intent.investment_strategy.preferred_industries and memory_context.preferred_industries:
        intent.investment_strategy.preferred_industries = _clean_list(memory_context.preferred_industries)
        applied_fields.append("preferred_industries")

    note: str | None = None
    applied_labels = [labels[field] for field in applied_fields if field in labels]
    if applied_labels:
        joined = "、".join(applied_labels) if language_code == "zh" else ", ".join(applied_labels)
        note = _localized_assumption(
            language_code,
            f"本次沿用了最近一次会话中的{joined}设置。",
            f"This run reused your last {joined} settings.",
        )
        if note not in intent.agent_control.assumptions:
            intent.agent_control.assumptions.append(note)

    speculative = _is_speculative(query)
    intent.agent_control.is_intent_clear = _is_intent_clear(intent, speculative)
    intent.agent_control.is_intent_usable = _is_intent_usable(intent, speculative)
    intent.agent_control.missing_critical_info = [] if intent.agent_control.is_intent_clear else _build_missing_info(intent)
    if speculative and "investment_style" not in intent.agent_control.missing_critical_info:
        intent.agent_control.missing_critical_info.insert(0, "investment_style")

    return {
        "used": bool(applied_fields),
        "applied_fields": applied_fields,
        "applied_labels": applied_labels,
        "note": note,
    }


def build_preference_snapshot(
    intent: ParsedIntent,
    *,
    query: str,
    research_mode: str,
    applied_fields: list[str] | None = None,
) -> dict[str, Any]:
    """把当前意图转成可持久化的偏好快照。"""
    return {
        "query": query,
        "locale": intent.system_context.language,
        "research_mode": research_mode,
        "memory_applied_fields": list(applied_fields or []),
        "values": {
            "capital_amount": intent.portfolio_sizing.capital_amount,
            "currency": intent.portfolio_sizing.currency,
            "risk_tolerance": intent.risk_profile.tolerance_level,
            "investment_horizon": intent.investment_strategy.horizon,
            "investment_style": intent.investment_strategy.style,
            "preferred_sectors": _clean_list(intent.investment_strategy.preferred_sectors),
            "preferred_industries": _clean_list(intent.investment_strategy.preferred_industries),
            "explicit_tickers": _clean_list(intent.explicit_targets.tickers),
        },
    }
