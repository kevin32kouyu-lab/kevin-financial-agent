from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.domain.contracts import (
    ArtifactRecord,
    BacktestDetail,
    BacktestMetrics,
    BacktestPoint,
    BacktestPosition,
    BacktestSummary,
    RunDetail,
    RunEventRecord,
    RunStepRecord,
    RunSummary,
    utc_now_iso,
)


class SqliteRunRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _dump_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _load_json(value: str | None) -> Any:
        if not value:
            return None
        return json.loads(value)

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if any(row["name"] == column for row in rows):
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_message TEXT,
                    report_mode TEXT
                );

                CREATE TABLE IF NOT EXISTS run_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    step_key TEXT NOT NULL,
                    label TEXT NOT NULL,
                    status TEXT NOT NULL,
                    elapsed_ms REAL,
                    summary TEXT,
                    position INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(run_id, step_key)
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(run_id, kind, name)
                );

                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS backtests (
                    id TEXT PRIMARY KEY,
                    source_run_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    benchmark_ticker TEXT NOT NULL DEFAULT 'SPY',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    positions_json TEXT NOT NULL,
                    meta_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS backtest_points (
                    backtest_id TEXT NOT NULL,
                    point_date TEXT NOT NULL,
                    portfolio_value REAL NOT NULL,
                    benchmark_value REAL NOT NULL,
                    portfolio_return_pct REAL NOT NULL,
                    benchmark_return_pct REAL NOT NULL,
                    PRIMARY KEY (backtest_id, point_date)
                );

                CREATE TABLE IF NOT EXISTS user_preferences (
                    profile_id TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    source_run_id TEXT,
                    source_query TEXT,
                    research_mode TEXT,
                    locale TEXT NOT NULL DEFAULT 'zh',
                    memory_applied_fields_json TEXT NOT NULL DEFAULT '[]',
                    values_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    disabled INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_user_id TEXT,
                    actor_role TEXT,
                    action TEXT NOT NULL,
                    target_type TEXT,
                    target_id TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_runs_status_created_at ON runs(status, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_run_events_run_id_id ON run_events(run_id, id);
                CREATE INDEX IF NOT EXISTS idx_run_steps_run_id_position ON run_steps(run_id, position);
                CREATE INDEX IF NOT EXISTS idx_backtests_source_run_updated_at ON backtests(source_run_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id_expires_at ON sessions(user_id, expires_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_events_actor_created_at ON audit_events(actor_user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_events_action_created_at ON audit_events(action, created_at DESC);
                """
            )

            self._ensure_column(conn, "runs", "workflow_key", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "runs", "started_at", "TEXT")
            self._ensure_column(conn, "runs", "finished_at", "TEXT")
            self._ensure_column(conn, "runs", "parent_run_id", "TEXT")
            self._ensure_column(conn, "runs", "attempt_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "runs", "metadata_json", "TEXT NOT NULL DEFAULT '{}'")

            self._ensure_column(conn, "run_steps", "input_json", "TEXT")
            self._ensure_column(conn, "run_steps", "output_json", "TEXT")
            self._ensure_column(conn, "run_steps", "error_json", "TEXT")
            self._ensure_column(conn, "user_preferences", "source_query", "TEXT")
            self._ensure_column(conn, "user_preferences", "research_mode", "TEXT")
            self._ensure_column(conn, "user_preferences", "locale", "TEXT NOT NULL DEFAULT 'zh'")
            self._ensure_column(conn, "user_preferences", "memory_applied_fields_json", "TEXT NOT NULL DEFAULT '[]'")

    def create_run(
        self,
        *,
        run_id: str,
        mode: str,
        workflow_key: str,
        title: str,
        parent_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        timestamp = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, mode, workflow_key, status, title, created_at, updated_at,
                    parent_run_id, attempt_count, metadata_json
                )
                VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, 0, ?)
                """,
                (
                    run_id,
                    mode,
                    workflow_key,
                    title,
                    timestamp,
                    timestamp,
                    parent_run_id,
                    self._dump_json(metadata or {}),
                ),
            )

    def update_run(self, run_id: str, **fields: Any) -> None:
        if not fields:
            return

        if "metadata" in fields:
            fields["metadata_json"] = self._dump_json(fields.pop("metadata") or {})

        fields["updated_at"] = utc_now_iso()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = [fields[key] for key in fields]
        values.append(run_id)

        with self._connect() as conn:
            conn.execute(f"UPDATE runs SET {assignments} WHERE id = ?", values)

    def mark_run_started(self, run_id: str, *, attempt_count: int) -> None:
        timestamp = utc_now_iso()
        self.update_run(
            run_id,
            status="running",
            started_at=timestamp,
            finished_at=None,
            error_message=None,
            attempt_count=attempt_count,
        )

    def mark_run_finished(
        self,
        run_id: str,
        *,
        status: str,
        error_message: str | None = None,
        report_mode: str | None = None,
    ) -> None:
        self.update_run(
            run_id,
            status=status,
            error_message=error_message,
            report_mode=report_mode,
            finished_at=utc_now_iso(),
        )

    def upsert_step(
        self,
        run_id: str,
        step: dict[str, Any],
        *,
        position: int,
        input_data: Any = None,
        output_data: Any = None,
        error_data: Any = None,
    ) -> None:
        timestamp = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_steps (
                    run_id, step_key, label, status, elapsed_ms, summary, position,
                    created_at, updated_at, input_json, output_json, error_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, step_key) DO UPDATE SET
                    label = excluded.label,
                    status = excluded.status,
                    elapsed_ms = excluded.elapsed_ms,
                    summary = excluded.summary,
                    position = excluded.position,
                    updated_at = excluded.updated_at,
                    input_json = excluded.input_json,
                    output_json = excluded.output_json,
                    error_json = excluded.error_json
                """,
                (
                    run_id,
                    step.get("key", ""),
                    step.get("label", step.get("key", "")),
                    step.get("status", "completed"),
                    step.get("elapsed_ms"),
                    step.get("summary"),
                    position,
                    timestamp,
                    timestamp,
                    self._dump_json(input_data),
                    self._dump_json(output_data),
                    self._dump_json(error_data),
                ),
            )

    def replace_artifact(self, run_id: str, *, kind: str, name: str, content: Any) -> None:
        timestamp = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts (run_id, kind, name, content_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, kind, name) DO UPDATE SET
                    content_json = excluded.content_json,
                    updated_at = excluded.updated_at
                """,
                (run_id, kind, name, self._dump_json(content), timestamp, timestamp),
            )

    def add_event(self, run_id: str, *, event_type: str, payload: dict[str, Any]) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO run_events (run_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, event_type, self._dump_json(payload), utc_now_iso()),
            )
            return int(cursor.lastrowid)

    def get_run(self, run_id: str) -> RunSummary | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return RunSummary(
            id=row["id"],
            mode=row["mode"],
            workflow_key=row["workflow_key"] or row["mode"],
            status=row["status"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            parent_run_id=row["parent_run_id"],
            error_message=row["error_message"],
            report_mode=row["report_mode"],
            attempt_count=row["attempt_count"] or 0,
            metadata=self._load_json(row["metadata_json"]) or {},
        )

    @staticmethod
    def _normalize_filter(value: str | None) -> str | None:
        text = (value or "").strip()
        return text or None

    def _build_run_where_clause(
        self,
        *,
        mode: str | None = None,
        status: str | None = None,
        search: str | None = None,
        include_active: bool = True,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []

        if normalized_mode := self._normalize_filter(mode):
            clauses.append("mode = ?")
            parameters.append(normalized_mode)
        if normalized_status := self._normalize_filter(status):
            clauses.append("status = ?")
            parameters.append(normalized_status)
        if normalized_search := self._normalize_filter(search):
            pattern = f"%{normalized_search}%"
            clauses.append("(id LIKE ? OR title LIKE ?)")
            parameters.extend([pattern, pattern])
        if not include_active:
            clauses.append("status NOT IN ('queued', 'running')")

        if not clauses:
            return "", parameters
        return f"WHERE {' AND '.join(clauses)}", parameters

    def list_runs(
        self,
        limit: int = 20,
        *,
        mode: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> list[RunSummary]:
        where_clause, parameters = self._build_run_where_clause(mode=mode, status=status, search=search)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM runs {where_clause} ORDER BY created_at DESC LIMIT ?",
                [*parameters, limit],
            ).fetchall()
        return [
            RunSummary(
                id=row["id"],
                mode=row["mode"],
                workflow_key=row["workflow_key"] or row["mode"],
                status=row["status"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                parent_run_id=row["parent_run_id"],
                error_message=row["error_message"],
                report_mode=row["report_mode"],
                attempt_count=row["attempt_count"] or 0,
                metadata=self._load_json(row["metadata_json"]) or {},
            )
            for row in rows
        ]

    @staticmethod
    def _run_visible_to(row: sqlite3.Row, *, user_id: str | None, client_id: str | None, is_admin: bool) -> bool:
        if is_admin:
            return True
        metadata = SqliteRunRepository._load_json(row["metadata_json"]) or {}
        owner_user_id = str(metadata.get("user_id") or "").strip()
        owner_client_id = str(metadata.get("client_id") or "").strip()
        if owner_user_id:
            return bool(user_id and owner_user_id == user_id)
        if owner_client_id:
            return bool(client_id and owner_client_id == client_id)
        return user_id is None

    def list_runs_for_actor(
        self,
        *,
        limit: int = 20,
        mode: str | None = None,
        status: str | None = None,
        search: str | None = None,
        user_id: str | None = None,
        client_id: str | None = None,
        is_admin: bool = False,
    ) -> list[RunSummary]:
        """按账户或浏览器身份过滤历史 run。"""
        where_clause, parameters = self._build_run_where_clause(mode=mode, status=status, search=search)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM runs {where_clause} ORDER BY created_at DESC LIMIT ?",
                [*parameters, max(limit * 5, limit)],
            ).fetchall()
        visible = [
            row
            for row in rows
            if self._run_visible_to(row, user_id=user_id, client_id=client_id, is_admin=is_admin)
        ][:limit]
        return [
            RunSummary(
                id=row["id"],
                mode=row["mode"],
                workflow_key=row["workflow_key"] or row["mode"],
                status=row["status"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                parent_run_id=row["parent_run_id"],
                error_message=row["error_message"],
                report_mode=row["report_mode"],
                attempt_count=row["attempt_count"] or 0,
                metadata=self._load_json(row["metadata_json"]) or {},
            )
            for row in visible
        ]

    def list_resumable_runs(self) -> list[RunSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM runs
                WHERE status IN ('queued', 'running')
                ORDER BY created_at ASC
                """
            ).fetchall()
        return [
            RunSummary(
                id=row["id"],
                mode=row["mode"],
                workflow_key=row["workflow_key"] or row["mode"],
                status=row["status"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                parent_run_id=row["parent_run_id"],
                error_message=row["error_message"],
                report_mode=row["report_mode"],
                attempt_count=row["attempt_count"] or 0,
                metadata=self._load_json(row["metadata_json"]) or {},
            )
            for row in rows
        ]

    def list_steps(self, run_id: str) -> list[RunStepRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM run_steps WHERE run_id = ? ORDER BY position ASC, id ASC",
                (run_id,),
            ).fetchall()
        return [
            RunStepRecord(
                step_key=row["step_key"],
                label=row["label"],
                status=row["status"],
                elapsed_ms=row["elapsed_ms"],
                summary=row["summary"],
                position=row["position"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                input_data=self._load_json(row["input_json"]),
                output_data=self._load_json(row["output_json"]),
                error_data=self._load_json(row["error_json"]),
            )
            for row in rows
        ]

    def list_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
        return [
            ArtifactRecord(
                id=row["id"],
                kind=row["kind"],
                name=row["name"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                content=self._load_json(row["content_json"]),
            )
            for row in rows
        ]

    def get_artifact_content(self, run_id: str, *, kind: str, name: str) -> Any:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT content_json FROM artifacts WHERE run_id = ? AND kind = ? AND name = ?",
                (run_id, kind, name),
            ).fetchone()
        if not row:
            return None
        return self._load_json(row["content_json"])

    def list_events(self, run_id: str, *, after_id: int = 0) -> list[RunEventRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM run_events
                WHERE run_id = ? AND id > ?
                ORDER BY id ASC
                """,
                (run_id, after_id),
            ).fetchall()
        return [
            RunEventRecord(
                id=row["id"],
                run_id=row["run_id"],
                event_type=row["event_type"],
                payload=self._load_json(row["payload_json"]) or {},
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def build_run_detail(self, run_id: str) -> RunDetail | None:
        run = self.get_run(run_id)
        if run is None:
            return None
        return RunDetail(
            run=run,
            steps=self.list_steps(run_id),
            artifacts=self.list_artifacts(run_id),
            result=self.get_artifact_content(run_id, kind="snapshot", name="current"),
        )

    def replace_backtest(
        self,
        *,
        backtest_id: str,
        source_run_id: str,
        title: str,
        status: str,
        entry_date: str,
        end_date: str,
        metrics: dict[str, Any],
        positions: list[dict[str, Any]],
        points: list[dict[str, Any]],
        meta: dict[str, Any] | None = None,
        benchmark_ticker: str = "SPY",
    ) -> None:
        timestamp = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO backtests (
                    id, source_run_id, title, status, entry_date, end_date, benchmark_ticker,
                    created_at, updated_at, metrics_json, positions_json, meta_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_run_id = excluded.source_run_id,
                    title = excluded.title,
                    status = excluded.status,
                    entry_date = excluded.entry_date,
                    end_date = excluded.end_date,
                    benchmark_ticker = excluded.benchmark_ticker,
                    updated_at = excluded.updated_at,
                    metrics_json = excluded.metrics_json,
                    positions_json = excluded.positions_json,
                    meta_json = excluded.meta_json
                """,
                (
                    backtest_id,
                    source_run_id,
                    title,
                    status,
                    entry_date,
                    end_date,
                    benchmark_ticker,
                    timestamp,
                    timestamp,
                    self._dump_json(metrics),
                    self._dump_json(positions),
                    self._dump_json(meta or {}),
                ),
            )
            conn.execute("DELETE FROM backtest_points WHERE backtest_id = ?", (backtest_id,))
            conn.executemany(
                """
                INSERT INTO backtest_points (
                    backtest_id, point_date, portfolio_value, benchmark_value,
                    portfolio_return_pct, benchmark_return_pct
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        backtest_id,
                        point["point_date"],
                        point["portfolio_value"],
                        point["benchmark_value"],
                        point["portfolio_return_pct"],
                        point["benchmark_return_pct"],
                    )
                    for point in points
                ],
            )

    def _build_backtest_summary(self, row: sqlite3.Row) -> BacktestSummary:
        metrics = BacktestMetrics.model_validate(self._load_json(row["metrics_json"]) or {})
        meta_payload = self._load_json(row["meta_json"]) or {}
        return BacktestSummary(
            id=row["id"],
            source_run_id=row["source_run_id"],
            title=row["title"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            entry_date=row["entry_date"],
            end_date=row["end_date"],
            benchmark_ticker=row["benchmark_ticker"] or "SPY",
            metrics=metrics,
            requested_count=int(meta_payload.get("requested_count") or 0),
            coverage_count=int(meta_payload.get("coverage_count") or 0),
            dropped_tickers=meta_payload.get("dropped_tickers") or [],
        )

    def list_backtests(self, *, source_run_id: str | None = None, limit: int = 20) -> list[BacktestSummary]:
        query = "SELECT * FROM backtests"
        params: list[Any] = []
        if source_run_id:
            query += " WHERE source_run_id = ?"
            params.append(source_run_id)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._build_backtest_summary(row) for row in rows]

    def get_user_preferences(self, profile_id: str = "default") -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_preferences WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "profile_id": row["profile_id"],
            "updated_at": row["updated_at"],
            "source_run_id": row["source_run_id"],
            "source_query": row["source_query"],
            "research_mode": row["research_mode"],
            "locale": row["locale"] or "zh",
            "memory_applied_fields": self._load_json(row["memory_applied_fields_json"]) or [],
            "values": self._load_json(row["values_json"]) or {},
        }

    def create_user(self, *, user_id: str, email: str, password_hash: str, role: str = "user") -> dict[str, Any]:
        timestamp = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (id, email, password_hash, role, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, email.lower().strip(), password_hash, role, timestamp, timestamp),
            )
        return {"id": user_id, "email": email.lower().strip(), "role": role, "created_at": timestamp}

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email.lower().strip(),),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return None
        return dict(row)

    def create_session(self, *, token_hash: str, user_id: str, expires_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (token_hash, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token_hash, user_id, utc_now_iso(), expires_at),
            )

    def get_session_user(self, token_hash: str, *, now: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT users.*
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ?
                  AND sessions.revoked_at IS NULL
                  AND sessions.expires_at > ?
                  AND users.disabled = 0
                """,
                (token_hash, now),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def revoke_session(self, token_hash: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE token_hash = ?",
                (utc_now_iso(), token_hash),
            )

    def add_audit_event(
        self,
        *,
        action: str,
        actor_user_id: str | None = None,
        actor_role: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_events (
                    actor_user_id, actor_role, action, target_type, target_id,
                    metadata_json, ip_address, user_agent, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actor_user_id,
                    actor_role,
                    action,
                    target_type,
                    target_id,
                    self._dump_json(metadata or {}),
                    ip_address,
                    user_agent,
                    utc_now_iso(),
                ),
            )
            return int(cursor.lastrowid)

    def list_audit_events(
        self,
        *,
        actor_user_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM audit_events"
        params: list[Any] = []
        if actor_user_id:
            query += " WHERE actor_user_id = ?"
            params.append(actor_user_id)
        query += " ORDER BY id ASC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "actor_user_id": row["actor_user_id"],
                "actor_role": row["actor_role"],
                "action": row["action"],
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "metadata": self._load_json(row["metadata_json"]) or {},
                "ip_address": row["ip_address"],
                "user_agent": row["user_agent"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def upsert_user_preferences(
        self,
        *,
        profile_id: str = "default",
        values: dict[str, Any],
        source_run_id: str | None = None,
        source_query: str | None = None,
        research_mode: str | None = None,
        locale: str = "zh",
        memory_applied_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        timestamp = utc_now_iso()
        payload = {
            "profile_id": profile_id,
            "updated_at": timestamp,
            "source_run_id": source_run_id,
            "source_query": source_query,
            "research_mode": research_mode,
            "locale": locale,
            "memory_applied_fields": list(memory_applied_fields or []),
            "values": values,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences (
                    profile_id, updated_at, source_run_id, source_query, research_mode,
                    locale, memory_applied_fields_json, values_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    source_run_id = excluded.source_run_id,
                    source_query = excluded.source_query,
                    research_mode = excluded.research_mode,
                    locale = excluded.locale,
                    memory_applied_fields_json = excluded.memory_applied_fields_json,
                    values_json = excluded.values_json
                """,
                (
                    profile_id,
                    timestamp,
                    source_run_id,
                    source_query,
                    research_mode,
                    locale,
                    self._dump_json(payload["memory_applied_fields"]),
                    self._dump_json(values),
                ),
            )
        return payload

    def get_backtest(self, backtest_id: str) -> BacktestDetail | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM backtests WHERE id = ?", (backtest_id,)).fetchone()
            if not row:
                return None
            point_rows = conn.execute(
                """
                SELECT * FROM backtest_points
                WHERE backtest_id = ?
                ORDER BY point_date ASC
                """,
                (backtest_id,),
            ).fetchall()

        summary = self._build_backtest_summary(row)
        positions_payload = self._load_json(row["positions_json"]) or []
        meta_payload = self._load_json(row["meta_json"]) or {}
        return BacktestDetail(
            summary=summary,
            positions=[BacktestPosition.model_validate(item) for item in positions_payload],
            points=[
                BacktestPoint(
                    point_date=item["point_date"],
                    portfolio_value=float(item["portfolio_value"]),
                    benchmark_value=float(item["benchmark_value"]),
                    portfolio_return_pct=float(item["portfolio_return_pct"]),
                    benchmark_return_pct=float(item["benchmark_return_pct"]),
                )
                for item in point_rows
            ],
            meta=meta_payload,
        )

    def delete_runs(
        self,
        *,
        mode: str | None = None,
        status: str | None = None,
        search: str | None = None,
        include_active: bool = False,
    ) -> int:
        where_clause, parameters = self._build_run_where_clause(
            mode=mode,
            status=status,
            search=search,
            include_active=include_active,
        )
        with self._connect() as conn:
            rows = conn.execute(f"SELECT id FROM runs {where_clause}", parameters).fetchall()
            run_ids = [row["id"] for row in rows]
            if not run_ids:
                return 0

            placeholders = ", ".join("?" for _ in run_ids)
            conn.execute(f"DELETE FROM run_steps WHERE run_id IN ({placeholders})", run_ids)
            conn.execute(f"DELETE FROM artifacts WHERE run_id IN ({placeholders})", run_ids)
            conn.execute(f"DELETE FROM run_events WHERE run_id IN ({placeholders})", run_ids)
            conn.execute(f"DELETE FROM runs WHERE id IN ({placeholders})", run_ids)
            return len(run_ids)
