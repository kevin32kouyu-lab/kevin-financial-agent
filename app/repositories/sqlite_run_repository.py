from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.domain.contracts import ArtifactRecord, RunDetail, RunEventRecord, RunStepRecord, RunSummary, utc_now_iso


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

                CREATE INDEX IF NOT EXISTS idx_runs_status_created_at ON runs(status, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_run_events_run_id_id ON run_events(run_id, id);
                CREATE INDEX IF NOT EXISTS idx_run_steps_run_id_position ON run_steps(run_id, position);
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
