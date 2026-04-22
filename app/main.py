from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin_router, agent_router, auth_router, backtests_router, debug_router, history_router, profile_router, runs_router, tools_router
from app.core.config import AppSettings
from app.core.exceptions import FinancialAgentError
from app.core.logging import setup_logging
from app.core.runtime import build_runtime, get_runtime


logger = logging.getLogger(__name__)


ROOT_DIR = Path(__file__).resolve().parents[1]


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for consistent error responses."""

    @app.exception_handler(FinancialAgentError)
    async def financial_agent_exception_handler(request: Request, exc: FinancialAgentError) -> JSONResponse:
        """Handle custom Financial Agent errors."""
        logger.error(f"Financial Agent error: {exc.message}", extra=exc.details)
        return JSONResponse(
            status_code=400,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "error_code": "INTERNAL_ERROR",
                "error_type": exc.__class__.__name__,
            },
        )


def _register_routers(app: FastAPI) -> None:
    for router in (auth_router, admin_router, agent_router, backtests_router, history_router, profile_router, runs_router, debug_router, tools_router):
        app.include_router(router)


def _register_page_routes(app: FastAPI, settings: AppSettings) -> None:
    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "app": settings.app_name,
                "version": settings.app_version,
                "frontend_available": settings.frontend_available,
            },
        )

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> JSONResponse:
        runtime = get_runtime(app)
        return JSONResponse(
            status_code=200,
            content={
                "status": "ready",
                "database": str(runtime.settings.db_path),
                "market_database": str(runtime.settings.market_db_path),
                "frontend_available": settings.frontend_available,
            },
        )

    @app.get("/", include_in_schema=False)
    async def root() -> FileResponse:
        if settings.frontend_available:
            return FileResponse(settings.frontend_index_path)
        return FileResponse(settings.legacy_static_dir / "debug.html")

    @app.get("/terminal", include_in_schema=False)
    async def terminal_page() -> FileResponse:
        if settings.frontend_available:
            return FileResponse(settings.frontend_index_path)
        return FileResponse(settings.legacy_static_dir / "debug.html")

    @app.get("/terminal/{subpath:path}", include_in_schema=False)
    async def terminal_subpage(subpath: str) -> FileResponse:
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

    # Setup logging
    setup_logging(level=getattr(logging, settings.log_level, logging.INFO))
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

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
