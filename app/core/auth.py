from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.core.config import AppSettings


CLIENT_ID_HEADER = "X-Client-Id"


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
