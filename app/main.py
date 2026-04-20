from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import agent_router, debug_router, profile_router, runs_router, tools_router
from app.core.config import AppSettings
from app.core.runtime import build_runtime


ROOT_DIR = Path(__file__).resolve().parents[1]


def _register_exception_handlers(app: FastAPI) -> None:
    """统一全局异常处理。"""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "error_code": "INTERNAL_ERROR",
            },
        )


def _register_routers(app: FastAPI) -> None:
    for router in (agent_router, runs_router, profile_router, debug_router, tools_router):
        app.include_router(router)


def _register_page_routes(app: FastAPI, settings: AppSettings) -> None:
    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/terminal")

    @app.get("/terminal", include_in_schema=False)
    async def terminal_page() -> FileResponse:
        if settings.frontend_available:
            return FileResponse(settings.frontend_index_path)
        return FileResponse(settings.legacy_static_dir / "debug.html")

    @app.get("/debug", include_in_schema=False)
    async def debug_page() -> FileResponse:
        if settings.frontend_available:
            return FileResponse(settings.frontend_index_path)
        return FileResponse(settings.legacy_static_dir / "debug.html")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)


def create_app() -> FastAPI:
    settings = AppSettings.from_env()
    runtime = build_runtime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        await runtime.startup()
        try:
            yield
        finally:
            await runtime.shutdown()

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

    if settings.frontend_available:
        app.mount("/assets", StaticFiles(directory=settings.web_dist_dir / "assets"), name="assets")
    if settings.legacy_static_dir.exists():
        app.mount("/static", StaticFiles(directory=settings.legacy_static_dir), name="static")

    _register_exception_handlers(app)
    _register_routers(app)
    _register_page_routes(app, settings)
    return app


app = create_app()
