from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import ArtifactRecord, RunDetail, RunEventRecord, RunStepRecord, RunSummary, utc_now_iso

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "financial_agent_runs.sqlite3"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=30.0)
    connection.row_factory = sqlite3.Row
    return connection


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _load_json(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)


def _normalize_filter(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _build_run_where_clause(
    *,
    mode: str | None = None,
    status: str | None = None,
    search: str | None = None,
    include_active: bool = True,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    parameters: list[Any] = []

    normalized_mode = _normalize_filter(mode)
    normalized_status = _normalize_filter(status)
    normalized_search = _normalize_filter(search)

    if normalized_mode:
        clauses.append("mode = ?")
        parameters.append(normalized_mode)

    if normalized_status:
        clauses.append("status = ?")
        parameters.append(normalized_status)

    if normalized_search:
        pattern = f"%{normalized_search}%"
        clauses.append("(id LIKE ? OR title LIKE ?)")
        parameters.extend([pattern, pattern])

    if not include_active:
        clauses.append("status NOT IN ('queued', 'running')")

    if not clauses:
        return "", parameters

    return f"WHERE {' AND '.join(clauses)}", parameters


def init_db() -> None:
    with _connect() as conn:
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
            """
        )


def create_run(*, run_id: str, mode: str, title: str) -> None:
    timestamp = utc_now_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (id, mode, status, title, created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?, ?)
            """,
            (run_id, mode, title, timestamp, timestamp),
        )


def update_run_status(
    run_id: str,
    *,
    status: str,
    error_message: str | None = None,
    report_mode: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE runs
            SET status = ?,
                updated_at = ?,
                error_message = ?,
                report_mode = COALESCE(?, report_mode)
            WHERE id = ?
            """,
            (status, utc_now_iso(), error_message, report_mode, run_id),
        )


def upsert_step(run_id: str, step: dict[str, Any], *, position: int) -> None:
    timestamp = utc_now_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO run_steps (
                run_id, step_key, label, status, elapsed_ms, summary, position, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, step_key) DO UPDATE SET
                label = excluded.label,
                status = excluded.status,
                elapsed_ms = excluded.elapsed_ms,
                summary = excluded.summary,
                position = excluded.position,
                updated_at = excluded.updated_at
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
            ),
        )


def replace_artifact(run_id: str, *, kind: str, name: str, content: Any) -> None:
    timestamp = utc_now_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO artifacts (run_id, kind, name, content_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, kind, name) DO UPDATE SET
                content_json = excluded.content_json,
                updated_at = excluded.updated_at
            """,
            (run_id, kind, name, _dump_json(content), timestamp, timestamp),
        )


def add_event(run_id: str, *, event_type: str, payload: dict[str, Any]) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO run_events (run_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (run_id, event_type, _dump_json(payload), utc_now_iso()),
        )
        return int(cursor.lastrowid)


def get_run(run_id: str) -> RunSummary | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        return None
    return RunSummary(
        id=row["id"],
        mode=row["mode"],
        status=row["status"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error_message=row["error_message"],
        report_mode=row["report_mode"],
    )


def list_runs(
    limit: int = 20,
    *,
    mode: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[RunSummary]:
    where_clause, parameters = _build_run_where_clause(mode=mode, status=status, search=search)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM runs {where_clause} ORDER BY created_at DESC LIMIT ?",
            [*parameters, limit],
        ).fetchall()
    return [
        RunSummary(
            id=row["id"],
            mode=row["mode"],
            status=row["status"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error_message=row["error_message"],
            report_mode=row["report_mode"],
        )
        for row in rows
    ]


def delete_runs(
    *,
    mode: str | None = None,
    status: str | None = None,
    search: str | None = None,
    include_active: bool = False,
) -> int:
    where_clause, parameters = _build_run_where_clause(
        mode=mode,
        status=status,
        search=search,
        include_active=include_active,
    )

    with _connect() as conn:
        run_rows = conn.execute(
            f"SELECT id FROM runs {where_clause}",
            parameters,
        ).fetchall()
        run_ids = [row["id"] for row in run_rows]

        if not run_ids:
            return 0

        placeholders = ", ".join("?" for _ in run_ids)
        conn.execute(f"DELETE FROM run_steps WHERE run_id IN ({placeholders})", run_ids)
        conn.execute(f"DELETE FROM artifacts WHERE run_id IN ({placeholders})", run_ids)
        conn.execute(f"DELETE FROM run_events WHERE run_id IN ({placeholders})", run_ids)
        conn.execute(f"DELETE FROM runs WHERE id IN ({placeholders})", run_ids)
        return len(run_ids)


def list_steps(run_id: str) -> list[RunStepRecord]:
    with _connect() as conn:
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
        )
        for row in rows
    ]


def list_artifacts(run_id: str) -> list[ArtifactRecord]:
    with _connect() as conn:
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
            content=_load_json(row["content_json"]),
        )
        for row in rows
    ]


def get_artifact_content(run_id: str, *, kind: str, name: str) -> Any:
    with _connect() as conn:
        row = conn.execute(
            "SELECT content_json FROM artifacts WHERE run_id = ? AND kind = ? AND name = ?",
            (run_id, kind, name),
        ).fetchone()
    if not row:
        return None
    return _load_json(row["content_json"])


def list_events(run_id: str, *, after_id: int = 0) -> list[RunEventRecord]:
    with _connect() as conn:
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
            payload=_load_json(row["payload_json"]) or {},
            created_at=row["created_at"],
        )
        for row in rows
    ]


def build_run_detail(run_id: str) -> RunDetail | None:
    run = get_run(run_id)
    if run is None:
        return None

    steps = list_steps(run_id)
    artifacts = list_artifacts(run_id)
    result = get_artifact_content(run_id, kind="snapshot", name="current")

    return RunDetail(
        run=run,
        steps=steps,
        artifacts=artifacts,
        result=result,
    )
