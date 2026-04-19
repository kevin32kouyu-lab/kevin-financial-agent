"""偏好服务。

这个文件负责把最近一次可复用的用户偏好持久化，并提供读取与手动更新入口。
它和 SQLite 仓储配合工作，给 Terminal 提供“跨刷新仍然记得住”的基础能力。
"""

from __future__ import annotations

from typing import Any

from app.domain.contracts import PreferenceUpdateRequest, UserPreferenceSummary
from app.repositories.sqlite_run_repository import SqliteRunRepository


class ProfileService:
    """管理默认用户偏好档案。"""

    def __init__(self, repository: SqliteRunRepository):
        self.repository = repository

    def get_preferences(self, profile_id: str = "default") -> UserPreferenceSummary | None:
        """读取当前偏好。"""
        payload = self.repository.get_user_preferences(profile_id)
        if payload is None:
            return None
        return UserPreferenceSummary.model_validate(payload)

    def update_preferences(self, payload: PreferenceUpdateRequest, profile_id: str = "default") -> UserPreferenceSummary:
        """手动更新偏好。"""
        stored = self.repository.upsert_user_preferences(
            profile_id=profile_id,
            values={
                "capital_amount": payload.capital_amount,
                "currency": payload.currency,
                "risk_tolerance": payload.risk_tolerance,
                "investment_horizon": payload.investment_horizon,
                "investment_style": payload.investment_style,
                "preferred_sectors": payload.preferred_sectors,
                "preferred_industries": payload.preferred_industries,
                "explicit_tickers": payload.explicit_tickers,
            },
            source_query=payload.source_query,
            research_mode=payload.research_mode,
            locale=payload.locale or "zh",
        )
        return UserPreferenceSummary.model_validate(stored)

    def save_snapshot(
        self,
        *,
        run_id: str,
        snapshot: dict[str, Any],
        profile_id: str = "default",
    ) -> UserPreferenceSummary:
        """把运行结果里的偏好快照持久化。"""
        stored = self.repository.upsert_user_preferences(
            profile_id=profile_id,
            values=snapshot.get("values") or {},
            source_run_id=run_id,
            source_query=str(snapshot.get("query") or "").strip() or None,
            research_mode=str(snapshot.get("research_mode") or "").strip() or None,
            locale=str(snapshot.get("locale") or "zh"),
            memory_applied_fields=list(snapshot.get("memory_applied_fields") or []),
        )
        return UserPreferenceSummary.model_validate(stored)
