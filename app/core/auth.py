from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.core.config import AppSettings
from app.domain.contracts import AuthUser


CLIENT_ID_HEADER = "X-Client-Id"
SESSION_COOKIE_NAME = "financial_agent_session"


def get_api_key(request: Request) -> None:
    settings = AppSettings.from_env()
    if not settings.auth_enabled:
        return

    api_key = request.headers.get(settings.api_key_header)
    if api_key == settings.api_key:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_client_id(request: Request) -> str:
    """读取浏览器侧 client_id，缺省时回退到默认档案。"""
    client_id = (request.headers.get(CLIENT_ID_HEADER) or "").strip()
    return client_id or "default"


def get_session_token(request: Request) -> str | None:
    """从 Authorization 或 Cookie 中读取账户会话。"""
    authorization = (request.headers.get("Authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip() or None
    return request.cookies.get(SESSION_COOKIE_NAME)


def get_current_user(request: Request) -> AuthUser | None:
    """读取当前登录用户；未登录时返回空，保持浏览器记忆兼容。"""
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or not hasattr(runtime, "auth_service"):
        return None
    return runtime.auth_service.get_user_for_token(get_session_token(request))


def require_admin(request: Request) -> AuthUser:
    """要求当前用户是管理员。"""
    user = get_current_user(request)
    if user and user.role == "admin":
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission is required.")
