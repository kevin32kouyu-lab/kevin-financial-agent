"""账户 API：提供注册、登录、退出和当前用户查询。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.core.auth import SESSION_COOKIE_NAME, get_api_key, get_current_user, get_session_token
from app.core.runtime import get_runtime
from app.domain.contracts import AuthLoginRequest, AuthRegisterRequest


router = APIRouter(prefix="/api/v1/auth", tags=["auth"], dependencies=[Depends(get_api_key)])


@router.post("/register")
async def register(request: Request, response: Response, payload: AuthRegisterRequest) -> dict:
    """注册账户并返回会话。"""
    runtime = get_runtime(request.app)
    session = runtime.auth_service.register(payload)
    response.set_cookie(SESSION_COOKIE_NAME, session.session_token, httponly=True, samesite="lax")
    return session.model_dump()


@router.post("/login")
async def login(request: Request, response: Response, payload: AuthLoginRequest) -> dict:
    """登录账户并返回会话。"""
    runtime = get_runtime(request.app)
    session = runtime.auth_service.login(payload)
    response.set_cookie(SESSION_COOKIE_NAME, session.session_token, httponly=True, samesite="lax")
    return session.model_dump()


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    """注销当前会话。"""
    runtime = get_runtime(request.app)
    runtime.auth_service.logout(get_session_token(request))
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
async def me(request: Request) -> dict:
    """读取当前用户。"""
    user = get_current_user(request)
    return {"user": user.model_dump() if user else None}
