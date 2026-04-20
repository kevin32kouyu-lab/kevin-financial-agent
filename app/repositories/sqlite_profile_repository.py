"""
长期用户偏好仓储。
与 run 仓储共用同一个 SQLite 文件，避免新增部署依赖。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.domain.contracts import ProfileResponse, UserProfile, utc_now_iso


class SqliteProfileRepository:
    """负责读写浏览器维度的长期偏好。"""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        """创建 SQLite 连接。"""
        connection = sqlite3.connect(self.db_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _dump_json(profile: UserProfile) -> str:
        """把偏好对象写成 JSON。"""
        return json.dumps(profile.model_dump(), ensure_ascii=False)

    @staticmethod
    def _load_profile(value: str | None) -> UserProfile:
        """把 JSON 恢复成偏好对象。"""
        if not value:
            return UserProfile()
        return UserProfile.model_validate(json.loads(value))

    def init_schema(self) -> None:
        """初始化长期偏好表。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS user_profiles (
                    client_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def get_profile(self, client_id: str) -> ProfileResponse | None:
        """读取指定浏览器的长期偏好。"""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM user_profiles WHERE client_id = ?", (client_id,)).fetchone()
        if row is None:
            return None
        return ProfileResponse(
            client_id=client_id,
            profile=self._load_profile(row["profile_json"]),
            updated_at=row["updated_at"],
        )

    def upsert_profile(self, client_id: str, profile: UserProfile) -> ProfileResponse:
        """新增或覆盖指定浏览器的长期偏好。"""
        timestamp = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_profiles (client_id, profile_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    profile_json = excluded.profile_json,
                    updated_at = excluded.updated_at
                """,
                (client_id, self._dump_json(profile), timestamp, timestamp),
            )
        return ProfileResponse(client_id=client_id, profile=profile, updated_at=timestamp)

    def delete_profile(self, client_id: str) -> None:
        """删除指定浏览器的长期偏好。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM user_profiles WHERE client_id = ?", (client_id,))
