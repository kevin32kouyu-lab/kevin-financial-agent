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

    @staticmethod
    def _empty_summary(profile_id: str = "default") -> UserPreferenceSummary:
        """返回空偏好，避免首次访问直接报错。"""
        return UserPreferenceSummary(
            profile_id=profile_id,
            updated_at=None,
            source_run_id=None,
            source_query=None,
            research_mode=None,
            locale="zh",
            memory_applied_fields=[],
            values={},
        )

    @staticmethod
    def user_profile_id(user_id: str | None) -> str | None:
        """把账户 ID 转成偏好档案 ID。"""
        return f"user:{user_id}" if user_id else None

    def _resolve_profile_id(self, profile_id: str = "default", user_id: str | None = None) -> str:
        """登录用户优先使用账户档案，未登录沿用浏览器档案。"""
        return self.user_profile_id(user_id) or profile_id

    def get_preferences(self, profile_id: str = "default", user_id: str | None = None) -> UserPreferenceSummary | None:
        """读取当前偏好。"""
        resolved_profile_id = self._resolve_profile_id(profile_id, user_id)
        payload = self.repository.get_user_preferences(resolved_profile_id)
        if payload is None:
            return self._empty_summary(resolved_profile_id)
        return UserPreferenceSummary.model_validate(payload)

    def update_preferences(
        self,
        payload: PreferenceUpdateRequest,
        profile_id: str = "default",
        user_id: str | None = None,
    ) -> UserPreferenceSummary:
        """手动更新偏好。"""
        resolved_profile_id = self._resolve_profile_id(profile_id, user_id)
        stored = self.repository.upsert_user_preferences(
            profile_id=resolved_profile_id,
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
        user_id: str | None = None,
    ) -> UserPreferenceSummary:
        """把运行结果里的偏好快照持久化。"""
        resolved_profile_id = self._resolve_profile_id(profile_id, user_id)
        stored = self.repository.upsert_user_preferences(
            profile_id=resolved_profile_id,
            values=snapshot.get("values") or {},
            source_run_id=run_id,
            source_query=str(snapshot.get("query") or "").strip() or None,
            research_mode=str(snapshot.get("research_mode") or "").strip() or None,
            locale=str(snapshot.get("locale") or "zh"),
            memory_applied_fields=list(snapshot.get("memory_applied_fields") or []),
        )
        return UserPreferenceSummary.model_validate(stored)

    def clear_preferences(self, profile_id: str = "default", user_id: str | None = None) -> UserPreferenceSummary:
        """清空当前档案的长期偏好。"""
        resolved_profile_id = self._resolve_profile_id(profile_id, user_id)
        stored = self.repository.upsert_user_preferences(
            profile_id=resolved_profile_id,
            values={},
            source_run_id=None,
            source_query=None,
            research_mode=None,
            locale="zh",
            memory_applied_fields=[],
        )
        return UserPreferenceSummary.model_validate(stored)

    def link_client_memory_to_user(self, *, client_id: str, user_id: str) -> UserPreferenceSummary:
        """把浏览器档案复制到账户档案。"""
        source = self.repository.get_user_preferences(client_id)
        target_profile_id = self.user_profile_id(user_id) or client_id
        if source is None:
            return self.get_preferences(profile_id=client_id, user_id=user_id)
        stored = self.repository.upsert_user_preferences(
            profile_id=target_profile_id,
            values=source.get("values") or {},
            source_run_id=source.get("source_run_id"),
            source_query=source.get("source_query"),
            research_mode=source.get("research_mode"),
            locale=source.get("locale") or "zh",
            memory_applied_fields=source.get("memory_applied_fields") or [],
        )
        return UserPreferenceSummary.model_validate(stored)
