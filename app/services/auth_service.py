"""账户服务：负责本地用户、会话和操作审计。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import AppSettings
from app.domain.contracts import AuthLoginRequest, AuthRegisterRequest, AuthSessionResponse, AuthUser
from app.repositories.sqlite_run_repository import SqliteRunRepository


class AuthService:
    """管理本地账户、登录会话和审计事件。"""

    def __init__(self, repository: SqliteRunRepository, settings: AppSettings):
        self.repository = repository
        self.settings = settings

    def _hash_password(self, password: str, salt: str | None = None) -> str:
        """用标准库生成带盐密码哈希，避免额外依赖。"""
        resolved_salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            resolved_salt.encode("utf-8"),
            120_000,
        ).hex()
        return f"pbkdf2_sha256${resolved_salt}${digest}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """校验密码是否匹配。"""
        try:
            method, salt, expected = password_hash.split("$", 2)
        except ValueError:
            return False
        if method != "pbkdf2_sha256":
            return False
        actual = self._hash_password(password, salt).split("$", 2)[2]
        return hmac.compare_digest(actual, expected)

    @staticmethod
    def _hash_token(token: str) -> str:
        """把会话 token 哈希后入库，避免明文 token 持久化。"""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _to_user(payload: dict) -> AuthUser:
        """把数据库用户转成公开结构。"""
        return AuthUser(
            id=str(payload["id"]),
            email=str(payload["email"]),
            role=str(payload.get("role") or "user"),  # type: ignore[arg-type]
            created_at=str(payload["created_at"]),
        )

    def register(self, payload: AuthRegisterRequest) -> AuthSessionResponse:
        """注册本地账户，并立即创建登录会话。"""
        email = payload.email.lower().strip()
        if "@" not in email:
            raise HTTPException(status_code=400, detail="Email is invalid.")
        if self.repository.get_user_by_email(email):
            raise HTTPException(status_code=409, detail="Email is already registered.")
        user = self.repository.create_user(
            user_id=uuid4().hex,
            email=email,
            password_hash=self._hash_password(payload.password),
            role=payload.role,
        )
        self.repository.add_audit_event(
            actor_user_id=user["id"],
            actor_role=user["role"],
            action="auth.register",
            target_type="user",
            target_id=user["id"],
        )
        return self._create_session_response(user, action=None)

    def login(self, payload: AuthLoginRequest) -> AuthSessionResponse:
        """校验账号密码并创建会话。"""
        user = self.repository.get_user_by_email(payload.email)
        if not user or int(user.get("disabled") or 0):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        if not self._verify_password(payload.password, str(user.get("password_hash") or "")):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        return self._create_session_response(user, action="auth.login")

    def _create_session_response(self, user: dict, *, action: str | None) -> AuthSessionResponse:
        """生成会话响应。"""
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self.repository.create_session(token_hash=self._hash_token(token), user_id=str(user["id"]), expires_at=expires_at)
        if action:
            self.repository.add_audit_event(
                actor_user_id=str(user["id"]),
                actor_role=str(user.get("role") or "user"),
                action=action,
                target_type="session",
                target_id=str(user["id"]),
            )
        return AuthSessionResponse(user=self._to_user(user), session_token=token, expires_at=expires_at)

    def get_user_for_token(self, token: str | None) -> AuthUser | None:
        """按 token 查找当前用户。"""
        if not token:
            return None
        now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        user = self.repository.get_session_user(self._hash_token(token), now=now)
        return self._to_user(user) if user else None

    def logout(self, token: str | None) -> None:
        """注销当前会话。"""
        if not token:
            return
        user = self.get_user_for_token(token)
        self.repository.revoke_session(self._hash_token(token))
        if user:
            self.repository.add_audit_event(
                actor_user_id=user.id,
                actor_role=user.role,
                action="auth.logout",
                target_type="session",
                target_id=user.id,
            )
