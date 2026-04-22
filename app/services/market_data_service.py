from __future__ import annotations

from io import StringIO
from pathlib import Path
import threading
import time
from typing import Any

import pandas as pd
import requests

from app.core.config import AppSettings
from app.domain.contracts import utc_now_iso
from app.repositories.sqlite_market_repository import SqliteMarketRepository
from app.tools.fetchers import fetch_alpaca_us_equities, fetch_macro_regime, has_alpaca_credentials, provider_statuses


REQUIRED_COLUMNS = [
    "ticker",
    "name",
    "exchange",
    "asset_class",
    "asset_status",
    "tradable",
    "marginable",
    "shortable",
    "easy_to_borrow",
    "fractionable",
    "sector",
    "industry",
    "market_cap",
    "pe_ratio",
    "ps_ratio",
    "ev_to_ebitda",
    "roe",
    "profit_margin",
    "debt_to_equity",
    "dividend_yield",
    "rev_growth_qoq",
    "target_price",
    "current_ratio",
    "quick_ratio",
    "proxy_peg",
    "free_cash_flow",
    "ebit",
    "analyst_rec",
]

DESCRIPTIVE_COLUMNS = {
    "ticker",
    "name",
    "exchange",
    "asset_class",
    "asset_status",
    "tradable",
    "marginable",
    "shortable",
    "easy_to_borrow",
    "fractionable",
    "sector",
    "industry",
}

WIKI_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
PACKAGED_SEED_PATH = Path(__file__).resolve().parents[1] / "assets" / "sp500_supabase_ready.csv"


class MarketDataService:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.repository = SqliteMarketRepository(settings.market_db_path)
        self._scheduler_stop = threading.Event()
        self._scheduler_thread: threading.Thread | None = None

    def startup(self) -> None:
        self.repository.init_schema()
        self.ensure_seeded()

    def start_refresh_scheduler(self) -> None:
        """按配置启动轻量后台刷新任务。"""
        if not self.settings.enable_refresh_jobs or self._scheduler_thread:
            return
        self._scheduler_stop.clear()
        self._scheduler_thread = threading.Thread(target=self._refresh_loop, name="financial-agent-refresh", daemon=True)
        self._scheduler_thread.start()

    def stop_refresh_scheduler(self) -> None:
        """停止后台刷新任务。"""
        if not self._scheduler_thread:
            return
        self._scheduler_stop.set()
        self._scheduler_thread.join(timeout=2)
        self._scheduler_thread = None

    def _refresh_loop(self) -> None:
        """简单定时刷新，Railway 可通过环境变量关闭。"""
        last_universe = 0.0
        last_macro = 0.0
        while not self._scheduler_stop.wait(30):
            now = time.monotonic()
            if now - last_universe >= self.settings.universe_refresh_interval_hours * 3600:
                self.refresh_universe()
                last_universe = now
            if now - last_macro >= self.settings.macro_refresh_interval_hours * 3600:
                self.refresh_macro_snapshot()
                last_macro = now

    def ensure_seeded(self) -> None:
        if self.repository.universe_count() > 0:
            return
        self.refresh_from_seed()

    def refresh_from_seed(self) -> dict[str, Any]:
        started_at = utc_now_iso()
        refreshed_at = utc_now_iso()
        frame = self._load_seed_frame()
        self.repository.replace_universe(frame, source="csv_seed", refreshed_at=refreshed_at)
        self.record_refresh_job(dataset="security_master", source="csv_seed", row_count=len(frame.index), started_at=started_at)
        return self.get_status()

    def refresh_universe(self) -> dict[str, Any]:
        started_at = utc_now_iso()
        refreshed_at = utc_now_iso()
        try:
            live_frame = self._load_alpaca_universe_frame()
            frame = self._merge_live_with_metrics(live_frame)
            source = "alpaca_us_equities"
        except Exception:
            try:
                live_frame = self._load_wikipedia_universe_frame()
                frame = self._merge_live_with_metrics(live_frame)
                source = "sp500_live_wikipedia_fallback"
            except Exception:
                frame = self._load_seed_frame()
                source = "csv_seed_fallback"

        self.repository.replace_universe(frame, source=source, refreshed_at=refreshed_at)
        self.record_refresh_job(dataset="security_master", source=source, row_count=len(frame.index), started_at=started_at)
        status = self.get_status()
        status["refresh_source"] = source
        return status

    def refresh_macro_snapshot(self) -> dict[str, Any]:
        started_at = utc_now_iso()
        refreshed_at = utc_now_iso()
        payload = fetch_macro_regime(self.settings)
        source = str(payload.get("Source") or "unknown")
        self.repository.upsert_macro_snapshot(
            snapshot_key="macro_regime",
            payload=payload,
            source=source,
            refreshed_at=refreshed_at,
        )
        self.record_refresh_job(dataset="macro", source=source, row_count=1, started_at=started_at)
        return self.repository.get_macro_snapshot_status()

    def refresh_core_datasets(self) -> dict[str, Any]:
        universe_status = self.refresh_universe()
        macro_status = self.refresh_macro_snapshot()
        status = self.get_status()
        status["refresh_summary"] = {
            "universe_source": universe_status.get("refresh_source"),
            "macro_source": macro_status.get("source"),
        }
        return status

    def record_refresh_job(
        self,
        *,
        dataset: str,
        source: str,
        row_count: int,
        status: str = "completed",
        message: str | None = None,
        started_at: str | None = None,
    ) -> dict[str, Any]:
        """记录一次数据刷新任务。"""
        return self.repository.add_refresh_job(
            dataset=dataset,
            source=source,
            status=status,
            row_count=row_count,
            message=message,
            started_at=started_at or utc_now_iso(),
            finished_at=utc_now_iso(),
        )

    def list_refresh_jobs(self, *, limit: int = 20) -> dict[str, Any]:
        """列出最近的数据刷新任务。"""
        return {"items": self.repository.list_refresh_jobs(limit=limit)}

    def persist_live_package(self, live_package: dict[str, Any]) -> None:
        refreshed_at = utc_now_iso()

        macro_payload = live_package.get("macro_data") or {}
        if macro_payload:
            source = str(macro_payload.get("Source") or "unknown")
            self.repository.upsert_macro_snapshot(
                snapshot_key="macro_regime",
                payload=macro_payload,
                source=source,
                refreshed_at=refreshed_at,
            )

        for audit_row in live_package.get("audit_data", []) or []:
            ticker = str(audit_row.get("Ticker", "")).upper().strip()
            filings = audit_row.get("Recent_Filings") or []
            if not ticker or not filings:
                continue
            self.repository.replace_sec_filings(
                ticker=ticker,
                filings=filings,
                source=str(audit_row.get("Source") or "sec_edgar"),
                refreshed_at=refreshed_at,
            )

    def load_security_universe(self) -> pd.DataFrame:
        self.ensure_seeded()
        frame = self.repository.load_universe()
        if not frame.empty:
            return frame
        seeded = self._load_seed_frame()
        self.repository.replace_universe(seeded, source="csv_fallback", refreshed_at=utc_now_iso())
        return seeded

    def get_status(self) -> dict[str, Any]:
        status = self.repository.get_status()
        status["seed_path"] = str(self._resolve_seed_path())
        status["database_path"] = str(self.settings.market_db_path)
        status["fallback_enabled"] = True
        status["macro_status"] = self.repository.get_macro_snapshot_status()
        status["sec_filings_status"] = self.repository.get_sec_filings_status()
        status["provider_statuses"] = provider_statuses(self.settings)
        status["live_sources"] = [
            "Alpaca assets (universe primary)",
            "Wikipedia S&P 500 (universe backup)",
            "yfinance (macro primary)",
            "FRED (macro backup)",
            "Yahoo RSS",
            "SEC EDGAR",
            "SEC submissions",
            "Alpha Vantage (price/tech backup)",
            "Finnhub (news backup)",
            "Public positioning proxy",
        ]
        status["universe_scope"] = "all_us_equities" if str(status.get("source", "")).startswith("alpaca") else "sp500_fallback"
        status["exchange_summary"] = self._build_exchange_summary()
        return status

    def _load_seed_frame(self) -> pd.DataFrame:
        seed_path = self._resolve_seed_path()

        frame = pd.read_csv(seed_path)
        for column in REQUIRED_COLUMNS:
            if column not in frame.columns:
                frame[column] = None

        cleaned = frame[REQUIRED_COLUMNS].copy()
        cleaned["ticker"] = cleaned["ticker"].astype(str).map(self._normalize_ticker)
        cleaned = cleaned[cleaned["ticker"] != ""]
        return cleaned.drop_duplicates(subset=["ticker"]).reset_index(drop=True)

    def _resolve_seed_path(self) -> Path:
        configured_path = self.settings.csv_universe_path
        if configured_path.exists():
            return configured_path
        if PACKAGED_SEED_PATH.exists():
            return PACKAGED_SEED_PATH
        raise FileNotFoundError(
            f"股票池种子文件不存在: {configured_path}；备用文件也不存在: {PACKAGED_SEED_PATH}"
        )

    def _load_alpaca_universe_frame(self) -> pd.DataFrame:
        if not has_alpaca_credentials(self.settings):
            raise ValueError("Alpaca credentials are not configured.")

        equities = fetch_alpaca_us_equities(self.settings)
        if len(equities) < 2000:
            raise ValueError("Alpaca universe returned too few US equities.")

        frame = pd.DataFrame(equities)
        for column in REQUIRED_COLUMNS:
            if column not in frame.columns:
                frame[column] = None
        frame = frame[REQUIRED_COLUMNS].copy()
        frame["ticker"] = frame["ticker"].astype(str).map(self._normalize_ticker)
        frame = frame[frame["ticker"] != ""].drop_duplicates(subset=["ticker"]).reset_index(drop=True)
        return frame

    def _load_wikipedia_universe_frame(self) -> pd.DataFrame:
        response = requests.get(
            WIKI_SP500_URL,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 FinancialAgent/1.0"},
        )
        response.raise_for_status()
        tables = pd.read_html(StringIO(response.text))
        if not tables:
            raise ValueError("No live S&P 500 table was returned from Wikipedia.")

        table = tables[0].rename(
            columns={
                "Symbol": "ticker",
                "Security": "name",
                "GICS Sector": "sector",
                "GICS Sub-Industry": "industry",
            }
        )
        live = table[["ticker", "name", "sector", "industry"]].copy()
        live["ticker"] = live["ticker"].astype(str).map(self._normalize_ticker)
        live = live[live["ticker"] != ""]
        if len(live.index) < 450:
            raise ValueError("Wikipedia returned too few S&P 500 rows.")
        for column in REQUIRED_COLUMNS:
            if column not in live.columns:
                live[column] = None
        return live[REQUIRED_COLUMNS].drop_duplicates(subset=["ticker"]).reset_index(drop=True)

    def _merge_live_with_metrics(self, live_frame: pd.DataFrame) -> pd.DataFrame:
        seed_frame = self._load_seed_frame()
        current_frame = self.repository.load_universe()
        metrics_source = current_frame if not current_frame.empty else seed_frame
        metric_columns = [column for column in REQUIRED_COLUMNS if column not in DESCRIPTIVE_COLUMNS]

        metrics = metrics_source[["ticker", *metric_columns]].copy()
        merged = live_frame.merge(metrics, on="ticker", how="left")

        seed_metrics = seed_frame[["ticker", *metric_columns]].copy()
        merged = merged.merge(seed_metrics, on="ticker", how="left", suffixes=("", "_seed"))
        for column in metric_columns:
            merged[column] = merged[column].where(merged[column].notna(), merged[f"{column}_seed"])
            merged = merged.drop(columns=[f"{column}_seed"])

        for column in REQUIRED_COLUMNS:
            if column not in merged.columns:
                merged[column] = None
        return merged[REQUIRED_COLUMNS].reset_index(drop=True)

    def _build_exchange_summary(self) -> dict[str, int]:
        frame = self.repository.load_universe()
        if frame.empty or "exchange" not in frame.columns:
            return {}
        counts = (
            frame["exchange"]
            .fillna("UNKNOWN")
            .astype(str)
            .str.upper()
            .value_counts()
            .head(8)
            .to_dict()
        )
        return {str(key): int(value) for key, value in counts.items()}

    @staticmethod
    def _normalize_ticker(value: str) -> str:
        return value.upper().strip().replace(".", "-")
