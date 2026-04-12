from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class AppSettings:
    app_name: str = "Financial Agent Lab"
    app_version: str = "1.2.0"
    host: str = "0.0.0.0"
    port: int = 8001
    db_path: Path = ROOT_DIR / "data" / "runtime" / "financial_agent_runs.sqlite3"
    market_db_path: Path = ROOT_DIR / "data" / "runtime" / "financial_agent_market.sqlite3"
    csv_universe_path: Path = ROOT_DIR / "data" / "seed" / "sp500_supabase_ready.csv"
    legacy_static_dir: Path = ROOT_DIR / "legacy" / "static"
    web_root_dir: Path = ROOT_DIR / "web"
    web_dist_dir: Path = ROOT_DIR / "web" / "dist"
    api_key: str | None = None
    api_key_header: str = "X-API-Key"

    alpha_vantage_api_key: str | None = None
    finnhub_api_key: str | None = None
    alpaca_api_key: str | None = None
    alpaca_api_secret: str | None = None
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    fred_api_key: str | None = None

    @classmethod
    def from_env(cls) -> "AppSettings":
        port_raw = os.getenv("PORT", "8001").strip()
        try:
            port = int(port_raw)
        except ValueError:
            port = 8001

        db_path = (
            Path(os.getenv("FINANCIAL_AGENT_DB_PATH", "")).expanduser()
            if os.getenv("FINANCIAL_AGENT_DB_PATH")
            else ROOT_DIR / "data" / "runtime" / "financial_agent_runs.sqlite3"
        )
        market_db_path = (
            Path(os.getenv("FINANCIAL_AGENT_MARKET_DB_PATH", "")).expanduser()
            if os.getenv("FINANCIAL_AGENT_MARKET_DB_PATH")
            else ROOT_DIR / "data" / "runtime" / "financial_agent_market.sqlite3"
        )
        csv_universe_path = (
            Path(os.getenv("FINANCIAL_AGENT_UNIVERSE_CSV", "")).expanduser()
            if os.getenv("FINANCIAL_AGENT_UNIVERSE_CSV")
            else ROOT_DIR / "data" / "seed" / "sp500_supabase_ready.csv"
        )

        api_key = os.getenv("API_KEY", "").strip() or None
        api_key_header = os.getenv("API_KEY_HEADER", "X-API-Key").strip() or "X-API-Key"

        alpha_vantage_api_key = (
            os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
            or os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
            or os.getenv("ALPHA_VANTAGE_KEY", "").strip()
        ) or None

        finnhub_api_key = (
            os.getenv("FINNHUB_API_KEY", "").strip()
            or os.getenv("FINNHUB_KEY", "").strip()
            or os.getenv("FINNHUB_TOKEN", "").strip()
        ) or None

        alpaca_api_key = (
            os.getenv("ALPACA_API_KEY", "").strip()
            or os.getenv("ALPACA_API_KEY_ID", "").strip()
            or os.getenv("APCA_API_KEY_ID", "").strip()
        ) or None

        alpaca_api_secret = (
            os.getenv("ALPACA_API_SECRET", "").strip()
            or os.getenv("ALPACA_API_SECRET_KEY", "").strip()
            or os.getenv("APCA_API_SECRET_KEY", "").strip()
        ) or None

        alpaca_base_url = (
            os.getenv("ALPACA_BASE_URL", "").strip()
            or os.getenv("ALPACA_API_BASE_URL", "").strip()
            or "https://paper-api.alpaca.markets"
        )

        fred_api_key = os.getenv("FRED_API_KEY", "").strip() or None

        return cls(
            host=os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0",
            port=port,
            db_path=db_path,
            market_db_path=market_db_path,
            csv_universe_path=csv_universe_path,
            api_key=api_key,
            api_key_header=api_key_header,
            alpha_vantage_api_key=alpha_vantage_api_key,
            finnhub_api_key=finnhub_api_key,
            alpaca_api_key=alpaca_api_key,
            alpaca_api_secret=alpaca_api_secret,
            alpaca_base_url=alpaca_base_url,
            fred_api_key=fred_api_key,
        )

    @property
    def alpaca_assets_url(self) -> str:
        return f"{self.alpaca_base_url.rstrip('/')}/v2/assets"

    @property
    def alpaca_configured(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_api_secret)

    @property
    def frontend_index_path(self) -> Path:
        return self.web_dist_dir / "index.html"

    @property
    def frontend_available(self) -> bool:
        return self.frontend_index_path.exists()

    @property
    def auth_enabled(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0
