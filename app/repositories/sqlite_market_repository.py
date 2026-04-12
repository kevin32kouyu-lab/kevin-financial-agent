from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


class SqliteMarketRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS security_universe (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    exchange TEXT,
                    asset_class TEXT,
                    asset_status TEXT,
                    tradable INTEGER,
                    marginable INTEGER,
                    shortable INTEGER,
                    easy_to_borrow INTEGER,
                    fractionable INTEGER,
                    sector TEXT,
                    industry TEXT,
                    market_cap REAL,
                    pe_ratio REAL,
                    ps_ratio REAL,
                    ev_to_ebitda REAL,
                    roe REAL,
                    profit_margin REAL,
                    debt_to_equity REAL,
                    dividend_yield REAL,
                    rev_growth_qoq REAL,
                    target_price REAL,
                    current_ratio REAL,
                    quick_ratio REAL,
                    proxy_peg REAL,
                    free_cash_flow REAL,
                    ebit REAL,
                    analyst_rec TEXT,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS security_snapshots (
                    ticker TEXT NOT NULL,
                    snapshot_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (ticker, snapshot_key)
                );

                CREATE TABLE IF NOT EXISTS macro_snapshots (
                    snapshot_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sec_filings (
                    ticker TEXT NOT NULL,
                    accession_no TEXT NOT NULL,
                    form_type TEXT,
                    filed_at TEXT,
                    primary_doc TEXT,
                    filing_url TEXT,
                    payload_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (ticker, accession_no)
                );

                CREATE TABLE IF NOT EXISTS data_refresh_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset TEXT NOT NULL,
                    source TEXT NOT NULL,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    refreshed_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_refresh_log_dataset_refreshed_at
                ON data_refresh_log(dataset, refreshed_at DESC);

                CREATE INDEX IF NOT EXISTS idx_sec_filings_ticker_filed_at
                ON sec_filings(ticker, filed_at DESC);

                CREATE TABLE IF NOT EXISTS sec_companyfacts (
                    cik TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    facts_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (cik, ticker)
                );

                CREATE INDEX IF NOT EXISTS idx_sec_companyfacts_ticker
                ON sec_companyfacts(ticker);
                """
            )
            self._ensure_security_universe_columns(conn)

    def _ensure_security_universe_columns(self, conn: sqlite3.Connection) -> None:
        expected_columns = {
            "exchange": "TEXT",
            "asset_class": "TEXT",
            "asset_status": "TEXT",
            "tradable": "INTEGER",
            "marginable": "INTEGER",
            "shortable": "INTEGER",
            "easy_to_borrow": "INTEGER",
            "fractionable": "INTEGER",
            "market_cap": "REAL",
            "ps_ratio": "REAL",
            "ev_to_ebitda": "REAL",
            "profit_margin": "REAL",
            "debt_to_equity": "REAL",
            "rev_growth_qoq": "REAL",
            "target_price": "REAL",
            "current_ratio": "REAL",
            "quick_ratio": "REAL",
            "proxy_peg": "REAL",
            "ebit": "REAL",
        }
        existing_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(security_universe)").fetchall()
        }
        for column_name, column_type in expected_columns.items():
            if column_name in existing_columns:
                continue
            conn.execute(f"ALTER TABLE security_universe ADD COLUMN {column_name} {column_type}")

    def universe_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM security_universe").fetchone()
        return int(row["total"]) if row else 0

    def replace_universe(self, frame: pd.DataFrame, *, source: str, refreshed_at: str) -> None:
        records = frame.to_dict(orient="records")
        with self._connect() as conn:
            conn.execute("DELETE FROM security_universe")
            conn.executemany(
                """
                INSERT INTO security_universe (
                    ticker, name, exchange, asset_class, asset_status, tradable, marginable,
                    shortable, easy_to_borrow, fractionable, sector, industry, market_cap,
                    pe_ratio, ps_ratio, ev_to_ebitda, roe, profit_margin, debt_to_equity,
                    dividend_yield, rev_growth_qoq, target_price, current_ratio, quick_ratio,
                    proxy_peg, free_cash_flow, ebit, analyst_rec, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(record.get("ticker", "")).upper(),
                        record.get("name"),
                        record.get("exchange"),
                        record.get("asset_class"),
                        record.get("asset_status"),
                        int(bool(record.get("tradable"))) if record.get("tradable") is not None else None,
                        int(bool(record.get("marginable"))) if record.get("marginable") is not None else None,
                        int(bool(record.get("shortable"))) if record.get("shortable") is not None else None,
                        int(bool(record.get("easy_to_borrow"))) if record.get("easy_to_borrow") is not None else None,
                        int(bool(record.get("fractionable"))) if record.get("fractionable") is not None else None,
                        record.get("sector"),
                        record.get("industry"),
                        record.get("market_cap"),
                        record.get("pe_ratio"),
                        record.get("ps_ratio"),
                        record.get("ev_to_ebitda"),
                        record.get("roe"),
                        record.get("profit_margin"),
                        record.get("debt_to_equity"),
                        record.get("dividend_yield"),
                        record.get("rev_growth_qoq"),
                        record.get("target_price"),
                        record.get("current_ratio"),
                        record.get("quick_ratio"),
                        record.get("proxy_peg"),
                        record.get("free_cash_flow"),
                        record.get("ebit"),
                        record.get("analyst_rec"),
                        source,
                        refreshed_at,
                    )
                    for record in records
                    if str(record.get("ticker", "")).strip()
                ],
            )
            conn.execute(
                """
                INSERT INTO data_refresh_log (dataset, source, row_count, refreshed_at)
                VALUES (?, ?, ?, ?)
                """,
                ("security_universe", source, len(records), refreshed_at),
            )

    def load_universe(self) -> pd.DataFrame:
        with self._connect() as conn:
            frame = pd.read_sql_query(
                """
                SELECT *
                FROM security_universe
                ORDER BY ticker ASC
                """,
                conn,
            )
        return frame

    def _log_refresh(self, conn: sqlite3.Connection, *, dataset: str, source: str, row_count: int, refreshed_at: str) -> None:
        conn.execute(
            """
            INSERT INTO data_refresh_log (dataset, source, row_count, refreshed_at)
            VALUES (?, ?, ?, ?)
            """,
            (dataset, source, row_count, refreshed_at),
        )

    def upsert_macro_snapshot(
        self,
        *,
        snapshot_key: str,
        payload: dict[str, Any],
        source: str,
        refreshed_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO macro_snapshots (snapshot_key, payload_json, source, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(snapshot_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (snapshot_key, json.dumps(payload, ensure_ascii=False), source, refreshed_at),
            )
            self._log_refresh(
                conn,
                dataset="macro_snapshot",
                source=source,
                row_count=1,
                refreshed_at=refreshed_at,
            )

    def get_macro_snapshot_status(self) -> dict[str, Any]:
        with self._connect() as conn:
            latest_row = conn.execute(
                """
                SELECT source, row_count, refreshed_at
                FROM data_refresh_log
                WHERE dataset = 'macro_snapshot'
                ORDER BY refreshed_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            snapshot_row = conn.execute(
                """
                SELECT payload_json
                FROM macro_snapshots
                WHERE snapshot_key = 'macro_regime'
                LIMIT 1
                """
            ).fetchone()

        payload = json.loads(snapshot_row["payload_json"]) if snapshot_row else {}
        return {
            "source": latest_row["source"] if latest_row else "empty",
            "last_refresh_at": latest_row["refreshed_at"] if latest_row else None,
            "last_refresh_count": int(latest_row["row_count"]) if latest_row else 0,
            "status": payload.get("Status"),
            "regime": payload.get("Global_Regime"),
        }

    def replace_sec_filings(
        self,
        *,
        ticker: str,
        filings: list[dict[str, Any]],
        source: str,
        refreshed_at: str,
    ) -> None:
        normalized_ticker = str(ticker).upper().strip()
        with self._connect() as conn:
            conn.execute("DELETE FROM sec_filings WHERE ticker = ?", (normalized_ticker,))
            conn.executemany(
                """
                INSERT INTO sec_filings (
                    ticker, accession_no, form_type, filed_at, primary_doc,
                    filing_url, payload_json, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        normalized_ticker,
                        str(item.get("accession_number", "")),
                        item.get("form"),
                        item.get("filed_at"),
                        item.get("primary_document"),
                        item.get("filing_url"),
                        json.dumps(item, ensure_ascii=False),
                        source,
                        refreshed_at,
                    )
                    for item in filings
                    if str(item.get("accession_number", "")).strip()
                ],
            )
            self._log_refresh(
                conn,
                dataset="sec_filings",
                source=source,
                row_count=len(filings),
                refreshed_at=refreshed_at,
            )

    def get_sec_filings_status(self) -> dict[str, Any]:
        with self._connect() as conn:
            latest_row = conn.execute(
                """
                SELECT source, row_count, refreshed_at
                FROM data_refresh_log
                WHERE dataset = 'sec_filings'
                ORDER BY refreshed_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            totals = conn.execute(
                """
                SELECT COUNT(*) AS total_records, COUNT(DISTINCT ticker) AS covered_tickers
                FROM sec_filings
                """
            ).fetchone()

        return {
            "source": latest_row["source"] if latest_row else "empty",
            "last_refresh_at": latest_row["refreshed_at"] if latest_row else None,
            "last_refresh_count": int(latest_row["row_count"]) if latest_row else 0,
            "records": int(totals["total_records"]) if totals else 0,
            "covered_tickers": int(totals["covered_tickers"]) if totals else 0,
        }

    def get_status(self) -> dict[str, Any]:
        with self._connect() as conn:
            latest_row = conn.execute(
                """
                SELECT source, row_count, refreshed_at
                FROM data_refresh_log
                WHERE dataset = 'security_universe'
                ORDER BY refreshed_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            universe_total = conn.execute("SELECT COUNT(*) AS total FROM security_universe").fetchone()

        return {
            "dataset": "security_universe",
            "records": int(universe_total["total"]) if universe_total else 0,
            "source": latest_row["source"] if latest_row else "empty",
            "last_refresh_at": latest_row["refreshed_at"] if latest_row else None,
            "last_refresh_count": int(latest_row["row_count"]) if latest_row else 0,
        }

    def get_cached_companyfacts(self, ticker: str, cik: str, ttl_hours: float = 24 * 7) -> dict[str, Any] | None:
        """Get cached SEC companyfacts if not expired"""
        from datetime import datetime, timedelta
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT facts_json, fetched_at
                FROM sec_companyfacts
                WHERE ticker = ? AND cik = ?
                """,
                (ticker.upper().strip(), str(cik).strip()),
            ).fetchone()
            if not row:
                return None
            # Check expiration - cache expires after one week
            fetched_at = datetime.fromisoformat(row["fetched_at"])
            if datetime.utcnow() - fetched_at < timedelta(hours=ttl_hours):
                import json
                return json.loads(row["facts_json"])
            return None

    def upsert_cached_companyfacts(self, ticker: str, cik: str, facts: dict[str, Any]) -> None:
        """Cache SEC companyfacts response"""
        from app.domain.contracts import utc_now_iso
        import json
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sec_companyfacts (cik, ticker, facts_json, fetched_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cik, ticker) DO UPDATE SET
                    facts_json = excluded.facts_json,
                    fetched_at = excluded.fetched_at
                """,
                (str(cik).strip(), ticker.upper().strip(), json.dumps(facts, ensure_ascii=False), utc_now_iso()),
            )

    def get_cached_snapshot(self, ticker: str, snapshot_key: str, ttl_minutes: float = 60) -> Any:
        """Get cached security snapshot if not expired"""
        from datetime import datetime, timedelta
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json, updated_at
                FROM security_snapshots
                WHERE ticker = ? AND snapshot_key = ?
                """,
                (ticker.upper().strip(), snapshot_key),
            ).fetchone()
            if not row:
                return None
            updated_at = datetime.fromisoformat(row["updated_at"])
            if datetime.utcnow() - updated_at < timedelta(minutes=ttl_minutes):
                import json
                return json.loads(row["payload_json"])
            return None

    def upsert_cached_snapshot(self, ticker: str, snapshot_key: str, payload: Any) -> None:
        """Update cached security snapshot"""
        from app.domain.contracts import utc_now_iso
        import json
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO security_snapshots (ticker, snapshot_key, payload_json, source, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ticker, snapshot_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (ticker.upper().strip(), snapshot_key, json.dumps(payload, ensure_ascii=False), "yfinance", utc_now_iso()),
            )
