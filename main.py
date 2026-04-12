from app.core.config import AppSettings
from app.main import app, create_app


__all__ = ["app", "create_app"]


if __name__ == "__main__":
    import uvicorn

    settings = AppSettings.from_env()
    uvicorn.run(create_app(), host=settings.host, port=settings.port)
