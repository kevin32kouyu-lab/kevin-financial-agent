from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MARKET_NO_PROXY_HOSTS = (
    "query1.finance.yahoo.com",
    "query2.finance.yahoo.com",
    "finance.yahoo.com",
)


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        os.environ.setdefault(key, value)


def _split_csv(value: str) -> tuple[str, ...]:
    parts = [item.strip() for item in value.split(",")]
    return tuple(item for item in parts if item)


@dataclass(slots=True)
class AppSettings:
    app_name: str = "Financial Agent Lab"
    app_version: str = "1.2.0"
    host: str = "0.0.0.0"
    port: int = 8001
    db_path: Path = ROOT_DIR / "data" / "runtime" / "financial_agent_runs.sqlite3"
    market_db_path: Path = ROOT_DIR / "data" / "runtime" / "financial_agent_market.sqlite3"
    knowledge_db_path: Path = ROOT_DIR / "data" / "runtime" / "financial_agent_knowledge.sqlite3"
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
    longbridge_app_key: str | None = None
    longbridge_app_secret: str | None = None
    longbridge_access_token: str | None = None
    fred_api_key: str | None = None
    market_proxy_mode: str = "auto"
    market_proxy_url: str | None = None
    market_no_proxy_hosts: tuple[str, ...] = DEFAULT_MARKET_NO_PROXY_HOSTS

    @classmethod
    def from_env(cls) -> "AppSettings":
        _load_env_file(ROOT_DIR / ".env")
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
        knowledge_db_path = (
            Path(os.getenv("FINANCIAL_AGENT_KNOWLEDGE_DB_PATH", "")).expanduser()
            if os.getenv("FINANCIAL_AGENT_KNOWLEDGE_DB_PATH")
            else ROOT_DIR / "data" / "runtime" / "financial_agent_knowledge.sqlite3"
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

        longbridge_app_key = (
            os.getenv("LONGBRIDGE_APP_KEY", "").strip()
            or os.getenv("LB_APP_KEY", "").strip()
        ) or None
        longbridge_app_secret = (
            os.getenv("LONGBRIDGE_APP_SECRET", "").strip()
            or os.getenv("LB_APP_SECRET", "").strip()
        ) or None
        longbridge_access_token = (
            os.getenv("LONGBRIDGE_ACCESS_TOKEN", "").strip()
            or os.getenv("LB_ACCESS_TOKEN", "").strip()
        ) or None

        fred_api_key = os.getenv("FRED_API_KEY", "").strip() or None
        market_proxy_mode = (os.getenv("MARKET_PROXY_MODE", "auto").strip() or "auto").lower()
        if market_proxy_mode not in {"auto", "direct", "proxy"}:
            market_proxy_mode = "auto"
        market_proxy_url = os.getenv("MARKET_PROXY_URL", "").strip() or None
        market_no_proxy_hosts_raw = os.getenv("MARKET_NO_PROXY_HOSTS", "").strip()
        market_no_proxy_hosts = (
            _split_csv(market_no_proxy_hosts_raw)
            if market_no_proxy_hosts_raw
            else DEFAULT_MARKET_NO_PROXY_HOSTS
        )

        return cls(
            host=os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0",
            port=port,
            db_path=db_path,
            market_db_path=market_db_path,
            knowledge_db_path=knowledge_db_path,
            csv_universe_path=csv_universe_path,
            api_key=api_key,
            api_key_header=api_key_header,
            alpha_vantage_api_key=alpha_vantage_api_key,
            finnhub_api_key=finnhub_api_key,
            alpaca_api_key=alpaca_api_key,
            alpaca_api_secret=alpaca_api_secret,
            alpaca_base_url=alpaca_base_url,
            longbridge_app_key=longbridge_app_key,
            longbridge_app_secret=longbridge_app_secret,
            longbridge_access_token=longbridge_access_token,
            fred_api_key=fred_api_key,
            market_proxy_mode=market_proxy_mode,
            market_proxy_url=market_proxy_url,
            market_no_proxy_hosts=market_no_proxy_hosts,
        )

    @property
    def alpaca_assets_url(self) -> str:
        return f"{self.alpaca_base_url.rstrip('/')}/v2/assets"

    @property
    def alpaca_configured(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_api_secret)

    @property
    def longbridge_configured(self) -> bool:
        return bool(self.longbridge_app_key and self.longbridge_app_secret and self.longbridge_access_token)

    @property
    def frontend_index_path(self) -> Path:
        return self.web_dist_dir / "index.html"

    @property
    def frontend_available(self) -> bool:
        return self.frontend_index_path.exists()

    @property
    def auth_enabled(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0
