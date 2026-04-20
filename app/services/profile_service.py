"""
长期偏好服务。
负责统一清洗、覆盖更新和“显式输入写回记忆”逻辑。
"""

from __future__ import annotations

from app.domain.contracts import ProfileResponse, UserProfile
from app.repositories.sqlite_profile_repository import SqliteProfileRepository


PROFILE_FIELDS = (
    "capital_amount",
    "currency",
    "risk_tolerance",
    "investment_horizon",
    "investment_style",
    "preferred_sectors",
    "preferred_industries",
)


class ProfileService:
    """负责浏览器级长期偏好的读写与合并。"""

    def __init__(self, repository: SqliteProfileRepository):
        self.repository = repository

    def get_profile(self, client_id: str) -> ProfileResponse:
        """读取长期偏好；不存在时返回空对象。"""
        return self.repository.get_profile(client_id) or ProfileResponse(client_id=client_id, profile=UserProfile())

    def update_profile(self, client_id: str, profile: UserProfile) -> ProfileResponse:
        """用前端提交的完整对象覆盖当前偏好。"""
        normalized = UserProfile.model_validate(profile.model_dump())
        return self.repository.upsert_profile(client_id, normalized)

    def clear_profile(self, client_id: str) -> ProfileResponse:
        """清空当前浏览器的长期偏好。"""
        self.repository.delete_profile(client_id)
        return ProfileResponse(client_id=client_id, profile=UserProfile(), updated_at=None)

    def merge_explicit_profile(self, client_id: str, explicit_profile: UserProfile) -> tuple[ProfileResponse, list[str]]:
        """把用户本次明确写出的长期字段写回记忆。"""
        current = self.get_profile(client_id)
        merged = current.profile.model_copy(deep=True)
        updated_fields: list[str] = []

        for field_name in PROFILE_FIELDS:
            explicit_value = getattr(explicit_profile, field_name)
            if not self._has_value(explicit_value):
                continue
            if getattr(merged, field_name) == explicit_value:
                continue
            setattr(merged, field_name, explicit_value)
            updated_fields.append(field_name)

        if not updated_fields:
            return current, []

        return self.repository.upsert_profile(client_id, merged), updated_fields

    @staticmethod
    def _has_value(value: object) -> bool:
        """判断字段是否真的包含用户显式输入。"""
        if value is None:
            return False
        if isinstance(value, list):
            return len(value) > 0
        if isinstance(value, str):
            return bool(value.strip())
        return True
