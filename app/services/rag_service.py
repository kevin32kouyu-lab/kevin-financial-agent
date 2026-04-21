"""知识库 RAG 服务：负责证据入库、检索引用和结论一致性校验。"""

from __future__ import annotations

from typing import Any

from app.repositories.sqlite_knowledge_repository import (
    KnowledgeDocument,
    RetrievedEvidence,
    SqliteKnowledgeRepository,
)
from app.services.rag_validation import ReportValidationService


class KnowledgeRagService:
    """把结构化研究结果转成可检索证据，并校验最终报告。"""

    def __init__(self, repository: SqliteKnowledgeRepository):
        self.repository = repository
        self.validation_service = ReportValidationService()
        self.repository.init_schema()

    def ingest_run_evidence(
        self,
        *,
        query: str,
        report_briefing: dict[str, Any],
        research_context: dict[str, Any] | None = None,
    ) -> int:
        """把一次研究的摘要、评分、新闻、SEC、宏观和来源信息写入知识库。"""
        context = research_context or {}
        as_of_date = self._as_of_date(report_briefing, context)
        research_mode = self._research_mode(context)
        documents = self._build_documents(query, report_briefing, as_of_date=as_of_date, research_mode=research_mode)
        return self.repository.upsert_documents(documents)

    def attach_retrieved_evidence(
        self,
        *,
        query: str,
        report_briefing: dict[str, Any],
        research_context: dict[str, Any] | None = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        """检索本次报告可用证据，并写回 report_briefing.meta。"""
        context = research_context or {}
        as_of_date = self._as_of_date(report_briefing, context)
        research_mode = self._research_mode(context)
        tickers = self._collect_tickers(report_briefing)
        search_query = self._build_search_query(query, report_briefing, tickers)
        evidence = self.repository.search(
            search_query,
            tickers=tickers,
            as_of_date=as_of_date,
            research_mode=research_mode,
            limit=limit,
        )
        public_evidence = self._with_citation_keys(evidence)
        citation_map = {
            item["citation_key"]: {
                "evidence_id": item["id"],
                "ticker": item.get("ticker"),
                "source_type": item.get("source_type"),
                "source_name": item.get("source_name"),
                "title": item.get("title"),
                "url": item.get("url"),
                "published_at": item.get("published_at"),
            }
            for item in public_evidence
        }
        meta = report_briefing.setdefault("meta", {})
        meta["retrieved_evidence"] = public_evidence
        meta["citation_map"] = citation_map
        return {"retrieved_evidence": public_evidence, "citation_map": citation_map}

    def apply_validation(
        self,
        *,
        final_report: str,
        report_briefing: dict[str, Any],
        language_code: str,
    ) -> dict[str, Any]:
        """检查报告结论是否和结构化数据、RAG 证据一致。"""
        return self.validation_service.apply_validation(
            final_report=final_report,
            report_briefing=report_briefing,
            language_code=language_code,
        )

    def _build_documents(
        self,
        query: str,
        report_briefing: dict[str, Any],
        *,
        as_of_date: str | None,
        research_mode: str | None,
    ) -> list[KnowledgeDocument]:
        """从报告摘要中提取统一证据文档。"""
        documents: list[KnowledgeDocument] = []
        for row in self._as_list(report_briefing.get("scoreboard")):
            ticker = self._text(row.get("ticker")).upper()
            if not ticker:
                continue
            score_summary = self._join_parts(
                [
                    f"Composite score: {self._text(row.get('composite_score'), 'N/A')}",
                    f"Suitability score: {self._text(row.get('suitability_score'), 'N/A')}",
                    f"Valuation score: {self._text(row.get('valuation_score'), 'N/A')}",
                    f"Quality score: {self._text(row.get('quality_score'), 'N/A')}",
                    f"Risk score: {self._text(row.get('risk_score'), 'N/A')}",
                    f"Verdict: {self._text(row.get('verdict_label'), 'N/A')}",
                ]
            )
            documents.append(
                KnowledgeDocument(
                    ticker=ticker,
                    source_type="score_fact",
                    source_name="Financial Agent scoring",
                    title=f"{ticker} score snapshot",
                    url=None,
                    published_at=as_of_date,
                    as_of_date=as_of_date,
                    research_mode=research_mode,
                    summary=score_summary,
                    content=f"{query}\n{score_summary}",
                    metadata={"row": row},
                )
            )

        for card in self._as_list(report_briefing.get("ticker_cards")):
            ticker = self._text(card.get("ticker")).upper()
            if not ticker:
                continue
            self._append_research_card_documents(documents, query, card, ticker, as_of_date, research_mode)

        macro = self._as_dict(report_briefing.get("macro"))
        if macro:
            macro_summary = self._join_parts(
                [
                    f"Regime: {self._text(macro.get('regime'), 'N/A')}",
                    f"Risk headline: {self._text(macro.get('risk_headline'), 'N/A')}",
                    f"VIX: {self._text(macro.get('vix'), 'N/A')}",
                    f"US 10Y: {self._text(macro.get('us10y'), 'N/A')}",
                ]
            )
            documents.append(
                KnowledgeDocument(
                    ticker=None,
                    source_type="macro",
                    source_name="Financial Agent macro snapshot",
                    title="Macro regime snapshot",
                    url=None,
                    published_at=as_of_date,
                    as_of_date=as_of_date,
                    research_mode=research_mode,
                    summary=macro_summary,
                    content=f"{query}\n{macro_summary}",
                    metadata={"macro": macro},
                )
            )

        provenance = self._as_dict((report_briefing.get("meta") or {}).get("data_provenance"))
        if provenance:
            source_summary = self._join_parts(
                [
                    f"Market source: {self._text(provenance.get('source'), 'unknown')}",
                    f"Last refresh: {self._text(provenance.get('last_refresh_at'), 'unknown')}",
                    f"Macro source: {self._text(provenance.get('macro_source'), 'unknown')}",
                    f"SEC records: {self._text(provenance.get('sec_filings_records'), 'unknown')}",
                ]
            )
            documents.append(
                KnowledgeDocument(
                    ticker=None,
                    source_type="data_source",
                    source_name="Financial Agent provenance",
                    title="Data source snapshot",
                    url=None,
                    published_at=as_of_date,
                    as_of_date=as_of_date,
                    research_mode=research_mode,
                    summary=source_summary,
                    content=f"{query}\n{source_summary}",
                    metadata={"data_provenance": provenance},
                )
            )

        return documents

    def _append_research_card_documents(
        self,
        documents: list[KnowledgeDocument],
        query: str,
        card: dict[str, Any],
        ticker: str,
        as_of_date: str | None,
        research_mode: str | None,
    ) -> None:
        """把逐票卡片拆成研究、新闻和 SEC 证据。"""
        research_summary = self._join_parts(
            [
                self._text(card.get("thesis")),
                self._text(card.get("fit_reason")),
                self._text(card.get("technical_summary")),
                self._format_list("Catalysts", card.get("catalysts")),
                self._format_list("Risks", card.get("risks")),
                self._format_list("Sources", card.get("source_points")),
            ]
        )
        if research_summary:
            documents.append(
                KnowledgeDocument(
                    ticker=ticker,
                    source_type="research_card",
                    source_name="Financial Agent synthesis",
                    title=f"{ticker} research card",
                    url=None,
                    published_at=as_of_date,
                    as_of_date=as_of_date,
                    research_mode=research_mode,
                    summary=research_summary,
                    content=f"{query}\n{research_summary}",
                    metadata={"card": card},
                )
            )

        news_summary = self._text(card.get("news_label"))
        if news_summary:
            documents.append(
                KnowledgeDocument(
                    ticker=ticker,
                    source_type="news",
                    source_name="Market news summary",
                    title=f"{ticker} news signal",
                    url=self._first_url(card),
                    published_at=as_of_date,
                    as_of_date=as_of_date,
                    research_mode=research_mode,
                    summary=news_summary,
                    content=f"{query}\n{news_summary}",
                    metadata={"card_field": "news_label"},
                )
            )

        audit_summary = self._text(card.get("audit_summary"))
        if audit_summary:
            documents.append(
                KnowledgeDocument(
                    ticker=ticker,
                    source_type="sec",
                    source_name="SEC EDGAR",
                    title=f"{ticker} filing and audit signal",
                    url=self._first_url(card, preferred_keys=("filing_url", "sec_url", "url")),
                    published_at=as_of_date,
                    as_of_date=as_of_date,
                    research_mode=research_mode,
                    summary=audit_summary,
                    content=f"{query}\n{audit_summary}",
                    metadata={"card_field": "audit_summary"},
                )
            )

    def _with_citation_keys(self, evidence: list[RetrievedEvidence]) -> list[dict[str, Any]]:
        """给证据条目增加 C1/C2 形式引用编号。"""
        items: list[dict[str, Any]] = []
        for index, item in enumerate(evidence, start=1):
            payload = item.to_public_dict()
            payload["citation_key"] = f"C{index}"
            items.append(payload)
        return items

    def _build_search_query(self, query: str, report_briefing: dict[str, Any], tickers: list[str]) -> str:
        """组合用户问题、优先标的和摘要关键词，提升检索召回。"""
        executive = self._as_dict(report_briefing.get("executive"))
        parts = [
            query,
            self._text(executive.get("primary_call")),
            self._text(executive.get("top_pick")),
            " ".join(tickers),
        ]
        return " ".join(part for part in parts if part)

    def _collect_tickers(self, report_briefing: dict[str, Any]) -> list[str]:
        """从评分表、逐票卡和执行摘要中收集股票代码。"""
        tickers: list[str] = []
        for row in self._as_list(report_briefing.get("scoreboard")):
            tickers.append(self._text(row.get("ticker")).upper())
        for card in self._as_list(report_briefing.get("ticker_cards")):
            tickers.append(self._text(card.get("ticker")).upper())
        executive = self._as_dict(report_briefing.get("executive"))
        tickers.append(self._text(executive.get("top_pick")).upper())
        for item in executive.get("watchlist") or []:
            tickers.append(self._text(item).upper())
        return self._dedupe_texts([ticker for ticker in tickers if ticker])

    @staticmethod
    def _as_of_date(report_briefing: dict[str, Any], context: dict[str, Any]) -> str | None:
        """读取研究日期。"""
        meta = report_briefing.setdefault("meta", {})
        as_of_date = context.get("as_of_date") or meta.get("as_of_date")
        if as_of_date:
            meta["as_of_date"] = as_of_date
        return str(as_of_date).strip() if as_of_date else None

    @staticmethod
    def _research_mode(context: dict[str, Any]) -> str | None:
        """读取研究模式。"""
        mode = context.get("research_mode")
        return str(mode).strip() if mode else None

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        """安全转换字典。"""
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _as_list(value: Any) -> list[dict[str, Any]]:
        """安全转换字典列表。"""
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    @staticmethod
    def _text(value: Any, fallback: str = "") -> str:
        """安全转换文本。"""
        if value is None:
            return fallback
        text = str(value).strip()
        return text or fallback

    @staticmethod
    def _number(value: Any) -> float | None:
        """安全转换数字。"""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number

    @staticmethod
    def _join_parts(parts: list[str]) -> str:
        """合并非空说明。"""
        return " ".join(part.strip() for part in parts if part and part.strip())

    def _format_list(self, label: str, value: Any) -> str:
        """把列表字段转成证据文本。"""
        if not isinstance(value, list):
            return ""
        items = [self._text(item) for item in value if self._text(item)]
        return f"{label}: {', '.join(items)}" if items else ""

    def _first_url(self, value: dict[str, Any], preferred_keys: tuple[str, ...] = ("url", "news_url", "link")) -> str | None:
        """从卡片或嵌套列表里取第一个链接。"""
        for key in preferred_keys:
            text = self._text(value.get(key))
            if text.startswith("http"):
                return text
        for key in ("links", "news_links", "filings", "sources"):
            items = value.get(key)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        url = self._first_url(item, preferred_keys)
                        if url:
                            return url
                    text = self._text(item)
                    if text.startswith("http"):
                        return text
        return None

    @staticmethod
    def _dedupe_texts(values: list[str]) -> list[str]:
        """按原顺序去重文本。"""
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            if text and text not in seen:
                result.append(text)
                seen.add(text)
        return result
