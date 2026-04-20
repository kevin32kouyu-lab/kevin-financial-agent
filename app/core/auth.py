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


def get_optional_client_id(request: Request) -> str | None:
    raw_value = request.headers.get(CLIENT_ID_HEADER, "").strip()
    return raw_value or None


def get_required_client_id(request: Request) -> str:
    client_id = get_optional_client_id(request)
    if client_id is not None:
        return client_id
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Missing {CLIENT_ID_HEADER} header")
