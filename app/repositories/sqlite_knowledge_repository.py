"""本地知识库仓库：用 SQLite + FTS5 保存和检索研究证据。"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain.contracts import utc_now_iso


@dataclass(slots=True)
class KnowledgeDocument:
    """统一的证据文档，承接新闻、SEC、评分、宏观和来源说明。"""

    ticker: str | None
    source_type: str
    source_name: str
    title: str
    url: str | None
    published_at: str | None
    as_of_date: str | None
    research_mode: str | None
    summary: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    document_id: str | None = None


@dataclass(slots=True)
class RetrievedEvidence:
    """检索返回的证据条目，供报告生成和前端展示使用。"""

    id: str
    ticker: str | None
    source_type: str
    source_name: str
    title: str
    url: str | None
    published_at: str | None
    as_of_date: str | None
    summary: str
    content: str
    metadata: dict[str, Any]
    score: float | None = None

    def to_public_dict(self) -> dict[str, Any]:
        """转换成可直接返回给前端的轻量字典。"""
        return {
            "id": self.id,
            "ticker": self.ticker,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at,
            "as_of_date": self.as_of_date,
            "summary": self.summary,
            "content": self.content,
            "metadata": self.metadata,
            "score": self.score,
        }


class SqliteKnowledgeRepository:
    """负责知识库建表、去重入库和 FTS 检索。"""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        """创建带 Row 工厂的 SQLite 连接。"""
        connection = sqlite3.connect(self.db_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection

    def init_schema(self) -> None:
        """初始化知识库表、索引和全文检索表。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    id TEXT PRIMARY KEY,
                    ticker TEXT,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    published_at TEXT,
                    retrieved_at TEXT NOT NULL,
                    as_of_date TEXT,
                    research_mode TEXT,
                    summary TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    checksum TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    ticker TEXT,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    published_at TEXT,
                    as_of_date TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(document_id) REFERENCES knowledge_documents(id)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(
                    content,
                    title,
                    ticker,
                    source_type,
                    document_id UNINDEXED,
                    chunk_id UNINDEXED
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_documents_ticker_date
                    ON knowledge_documents(ticker, published_at, as_of_date);
                CREATE INDEX IF NOT EXISTS idx_knowledge_documents_source
                    ON knowledge_documents(source_type, source_name);
                CREATE INDEX IF NOT EXISTS idx_knowledge_documents_checksum
                    ON knowledge_documents(checksum);
                CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document
                    ON knowledge_chunks(document_id, chunk_index);
                """
            )

    def upsert_documents(self, documents: list[KnowledgeDocument]) -> int:
        """去重写入证据文档，并同步重建对应 FTS 分块。"""
        if not documents:
            return 0
        self.init_schema()
        seen: set[str] = set()
        timestamp = utc_now_iso()
        with self._connect() as conn:
            for document in documents:
                normalized = self._normalize_document(document)
                if normalized["id"] in seen:
                    continue
                seen.add(normalized["id"])
                created_at = self._existing_created_at(conn, normalized["id"]) or timestamp
                conn.execute(
                    """
                    INSERT INTO knowledge_documents (
                        id, ticker, source_type, source_name, title, url, published_at,
                        retrieved_at, as_of_date, research_mode, summary, content,
                        metadata_json, checksum, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        ticker=excluded.ticker,
                        source_type=excluded.source_type,
                        source_name=excluded.source_name,
                        title=excluded.title,
                        url=excluded.url,
                        published_at=excluded.published_at,
                        retrieved_at=excluded.retrieved_at,
                        as_of_date=excluded.as_of_date,
                        research_mode=excluded.research_mode,
                        summary=excluded.summary,
                        content=excluded.content,
                        metadata_json=excluded.metadata_json,
                        checksum=excluded.checksum,
                        updated_at=excluded.updated_at
                    """,
                    (
                        normalized["id"],
                        normalized["ticker"],
                        normalized["source_type"],
                        normalized["source_name"],
                        normalized["title"],
                        normalized["url"],
                        normalized["published_at"],
                        timestamp,
                        normalized["as_of_date"],
                        normalized["research_mode"],
                        normalized["summary"],
                        normalized["content"],
                        normalized["metadata_json"],
                        normalized["checksum"],
                        created_at,
                        timestamp,
                    ),
                )
                self._replace_chunks(conn, normalized)
        return len(seen)

    def search(
        self,
        query: str,
        *,
        tickers: list[str] | None = None,
        as_of_date: str | None = None,
        research_mode: str | None = None,
        limit: int = 8,
    ) -> list[RetrievedEvidence]:
        """按问题、股票和研究日期检索相关证据。"""
        self.init_schema()
        ticker_values = [ticker.upper() for ticker in (tickers or []) if ticker]
        match_query = self._build_fts_query(query)
        if match_query:
            rows = self._search_fts(match_query, ticker_values, as_of_date, research_mode, limit)
            if rows:
                return [self._row_to_evidence(row) for row in rows]
        rows = self._search_recent(ticker_values, as_of_date, research_mode, limit)
        return [self._row_to_evidence(row) for row in rows]

    def _replace_chunks(self, conn: sqlite3.Connection, normalized: dict[str, Any]) -> None:
        """重建某个文档的全文检索分块。"""
        conn.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (normalized["id"],))
        conn.execute("DELETE FROM knowledge_chunks_fts WHERE document_id = ?", (normalized["id"],))
        chunks = self._split_chunks(normalized["content"] or normalized["summary"] or normalized["title"])
        for index, chunk in enumerate(chunks):
            chunk_id = f"{normalized['id']}:{index}"
            conn.execute(
                """
                INSERT INTO knowledge_chunks (
                    id, document_id, ticker, chunk_index, content, source_type,
                    published_at, as_of_date, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    normalized["id"],
                    normalized["ticker"],
                    index,
                    chunk,
                    normalized["source_type"],
                    normalized["published_at"],
                    normalized["as_of_date"],
                    normalized["metadata_json"],
                ),
            )
            conn.execute(
                """
                INSERT INTO knowledge_chunks_fts (
                    content, title, ticker, source_type, document_id, chunk_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk,
                    normalized["title"],
                    normalized["ticker"] or "",
                    normalized["source_type"],
                    normalized["id"],
                    chunk_id,
                ),
            )

    def _search_fts(
        self,
        match_query: str,
        tickers: list[str],
        as_of_date: str | None,
        research_mode: str | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        """执行 FTS 检索，并在 SQL 层过滤股票和日期。"""
        clauses = ["knowledge_chunks_fts MATCH ?"]
        params: list[Any] = [match_query]
        if tickers:
            placeholders = ", ".join("?" for _ in tickers)
            clauses.append(f"(d.ticker IN ({placeholders}) OR d.ticker IS NULL)")
            params.extend(tickers)
        if as_of_date:
            clauses.append("(d.published_at IS NULL OR d.published_at <= ?)")
            params.append(as_of_date)
        if research_mode:
            clauses.append("(d.research_mode IS NULL OR d.research_mode = ? OR d.research_mode = 'realtime')")
            params.append(research_mode)
        params.append(max(1, limit) * 4)
        sql = f"""
            SELECT
                d.*,
                bm25(knowledge_chunks_fts) AS rank_score
            FROM knowledge_chunks_fts
            JOIN knowledge_chunks c ON c.id = knowledge_chunks_fts.chunk_id
            JOIN knowledge_documents d ON d.id = c.document_id
            WHERE {' AND '.join(clauses)}
            ORDER BY rank_score ASC, d.published_at DESC, d.updated_at DESC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        deduped: list[sqlite3.Row] = []
        seen: set[str] = set()
        for row in rows:
            if row["id"] in seen:
                continue
            deduped.append(row)
            seen.add(row["id"])
            if len(deduped) >= limit:
                break
        return deduped

    def _search_recent(
        self,
        tickers: list[str],
        as_of_date: str | None,
        research_mode: str | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        """FTS 没有命中时，回退为最近的相关证据。"""
        clauses: list[str] = []
        params: list[Any] = []
        if tickers:
            placeholders = ", ".join("?" for _ in tickers)
            clauses.append(f"(ticker IN ({placeholders}) OR ticker IS NULL)")
            params.extend(tickers)
        if as_of_date:
            clauses.append("(published_at IS NULL OR published_at <= ?)")
            params.append(as_of_date)
        if research_mode:
            clauses.append("(research_mode IS NULL OR research_mode = ? OR research_mode = 'realtime')")
            params.append(research_mode)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, limit))
        with self._connect() as conn:
            return conn.execute(
                f"""
                SELECT *, NULL AS rank_score
                FROM knowledge_documents
                {where_sql}
                ORDER BY published_at DESC, updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

    def _row_to_evidence(self, row: sqlite3.Row) -> RetrievedEvidence:
        """把数据库行转换为证据对象。"""
        rank = row["rank_score"] if "rank_score" in row.keys() else None
        score = None if rank is None else round(1 / (1 + abs(float(rank))), 4)
        return RetrievedEvidence(
            id=row["id"],
            ticker=row["ticker"],
            source_type=row["source_type"],
            source_name=row["source_name"],
            title=row["title"],
            url=row["url"],
            published_at=row["published_at"],
            as_of_date=row["as_of_date"],
            summary=row["summary"],
            content=row["content"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            score=score,
        )

    def _normalize_document(self, document: KnowledgeDocument) -> dict[str, Any]:
        """清理文档字段并生成稳定 ID。"""
        ticker = (document.ticker or "").strip().upper() or None
        source_type = self._safe_text(document.source_type, "source")
        source_name = self._safe_text(document.source_name, "unknown")
        title = self._safe_text(document.title, "Untitled evidence")
        summary = self._safe_text(document.summary, title)
        content = self._safe_text(document.content, summary)
        metadata_json = json.dumps(document.metadata or {}, ensure_ascii=False, sort_keys=True, default=str)
        checksum = self._checksum([ticker or "", source_type, source_name, title, document.url or "", summary, content, metadata_json])
        document_id = document.document_id or "kd_" + self._checksum(
            [ticker or "", source_type, source_name, title, document.url or "", document.published_at or "", checksum]
        )
        return {
            "id": document_id,
            "ticker": ticker,
            "source_type": source_type,
            "source_name": source_name,
            "title": title,
            "url": (document.url or "").strip() or None,
            "published_at": (document.published_at or "").strip() or None,
            "as_of_date": (document.as_of_date or "").strip() or None,
            "research_mode": (document.research_mode or "").strip() or None,
            "summary": summary,
            "content": content,
            "metadata_json": metadata_json,
            "checksum": checksum,
        }

    @staticmethod
    def _existing_created_at(conn: sqlite3.Connection, document_id: str) -> str | None:
        """读取已有文档创建时间，避免 upsert 时丢失首入库时间。"""
        row = conn.execute("SELECT created_at FROM knowledge_documents WHERE id = ?", (document_id,)).fetchone()
        return row["created_at"] if row else None

    @staticmethod
    def _safe_text(value: Any, fallback: str) -> str:
        """把任意值转成非空字符串。"""
        text = str(value).strip() if value is not None else ""
        return text or fallback

    @staticmethod
    def _checksum(parts: list[str]) -> str:
        """生成稳定哈希，用于去重和文档 ID。"""
        raw = "\n".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _split_chunks(text: str, max_chars: int = 1200) -> list[str]:
        """把长文本切成适合 FTS 的块。"""
        clean = " ".join(text.split())
        if not clean:
            return [""]
        return [clean[index : index + max_chars] for index in range(0, len(clean), max_chars)]

    @staticmethod
    def _build_fts_query(query: str) -> str:
        """把自然语言问题转换成安全的 FTS5 查询。"""
        tokens = re.findall(r"[A-Za-z0-9]{2,}", query or "")
        unique: list[str] = []
        for token in tokens:
            lowered = token.lower()
            if lowered not in unique:
                unique.append(lowered)
        return " OR ".join(f"{token}*" for token in unique[:12])
