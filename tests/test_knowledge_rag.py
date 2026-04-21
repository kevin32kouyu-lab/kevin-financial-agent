"""本地知识库 RAG 与结论校验测试。"""

from app.repositories.sqlite_knowledge_repository import KnowledgeDocument, SqliteKnowledgeRepository
from app.services.rag_service import KnowledgeRagService


def test_knowledge_repository_deduplicates_and_searches_by_ticker(tmp_path):
    """确认重复资料只保存一份，并能按股票检索。"""
    repository = SqliteKnowledgeRepository(tmp_path / "knowledge.sqlite3")
    repository.init_schema()
    document = KnowledgeDocument(
        ticker="AAPL",
        source_type="news",
        source_name="Yahoo Finance",
        title="Apple expands AI services",
        url="https://example.com/aapl-ai",
        published_at="2026-04-01",
        as_of_date="2026-04-21",
        research_mode="realtime",
        summary="Apple expanded AI services and management raised demand expectations.",
        content="Apple expanded AI services and management raised demand expectations.",
        metadata={"provider": "test"},
    )

    written = repository.upsert_documents([document, document])
    results = repository.search("AI demand", tickers=["AAPL"], as_of_date="2026-04-21", research_mode="realtime")

    assert written == 1
    assert len(results) == 1
    assert results[0].ticker == "AAPL"
    assert results[0].title == "Apple expands AI services"


def test_knowledge_repository_filters_future_evidence_for_historical_date(tmp_path):
    """确认历史研究不会检索到研究日期之后的资料。"""
    repository = SqliteKnowledgeRepository(tmp_path / "knowledge.sqlite3")
    repository.init_schema()
    repository.upsert_documents(
        [
            KnowledgeDocument(
                ticker="MSFT",
                source_type="news",
                source_name="Yahoo Finance",
                title="Microsoft cloud growth",
                url="https://example.com/msft-cloud",
                published_at="2026-03-10",
                as_of_date="2026-03-10",
                research_mode="historical",
                summary="Cloud demand stayed resilient before the research date.",
                content="Cloud demand stayed resilient before the research date.",
            ),
            KnowledgeDocument(
                ticker="MSFT",
                source_type="news",
                source_name="Yahoo Finance",
                title="Microsoft later guidance raise",
                url="https://example.com/msft-future",
                published_at="2026-05-01",
                as_of_date="2026-05-01",
                research_mode="historical",
                summary="This item is after the research date and must not be used.",
                content="This item is after the research date and must not be used.",
            ),
        ]
    )

    results = repository.search("Microsoft cloud guidance", tickers=["MSFT"], as_of_date="2026-04-21", research_mode="historical")

    assert [item.title for item in results] == ["Microsoft cloud growth"]


def test_rag_service_ingests_report_briefing_and_builds_citations(tmp_path):
    """确认报告摘要能转成证据，并回填引用列表。"""
    service = KnowledgeRagService(SqliteKnowledgeRepository(tmp_path / "knowledge.sqlite3"))
    briefing = _sample_briefing()

    written = service.ingest_run_evidence(
        query="Find durable AI compounders",
        report_briefing=briefing,
        research_context={"research_mode": "realtime", "as_of_date": "2026-04-21"},
    )
    evidence_payload = service.attach_retrieved_evidence(
        query="Find durable AI compounders",
        report_briefing=briefing,
        research_context={"research_mode": "realtime", "as_of_date": "2026-04-21"},
        limit=6,
    )

    assert written >= 3
    assert len(evidence_payload["retrieved_evidence"]) >= 3
    assert evidence_payload["citation_map"]
    assert briefing["meta"]["retrieved_evidence"] == evidence_payload["retrieved_evidence"]


def test_rag_validation_flags_missing_top_pick_and_lowers_confidence(tmp_path):
    """确认报告遗漏优先标的时会生成校验提示并降低可信度。"""
    service = KnowledgeRagService(SqliteKnowledgeRepository(tmp_path / "knowledge.sqlite3"))
    briefing = _sample_briefing()
    service.ingest_run_evidence(
        query="Find durable AI compounders",
        report_briefing=briefing,
        research_context={"research_mode": "realtime", "as_of_date": "2026-04-21"},
    )
    service.attach_retrieved_evidence(
        query="Find durable AI compounders",
        report_briefing=briefing,
        research_context={"research_mode": "realtime", "as_of_date": "2026-04-21"},
    )

    meta = service.apply_validation(
        final_report="# Research Report\n\n## Executive Verdict\n\nMSFT is the preferred action candidate.",
        report_briefing=briefing,
        language_code="en",
    )

    assert meta["confidence_level"] == "low"
    assert any(item["id"] == "report_mentions_top_pick" and item["status"] == "fail" for item in meta["validation_checks"])
    assert any("AAPL" in item for item in meta["validation_summary"]["items"])


def _sample_briefing():
    """构造最小但完整的报告摘要样本。"""
    return {
        "executive": {
            "top_pick": "AAPL",
            "top_pick_verdict": "Strong Buy",
            "mandate_fit_score": 84,
            "primary_call": "AAPL is the best fit for durable AI exposure.",
            "watchlist": ["MSFT"],
        },
        "macro": {
            "regime": "Selective risk-on",
            "risk_headline": "Rates remain the main sensitivity.",
            "vix": 16.2,
            "us10y": 4.1,
        },
        "scoreboard": [
            {
                "ticker": "AAPL",
                "composite_score": 88,
                "suitability_score": 84,
                "valuation_score": 66,
                "quality_score": 91,
                "risk_score": 72,
                "verdict_label": "Strong Buy",
            }
        ],
        "ticker_cards": [
            {
                "ticker": "AAPL",
                "thesis": "High quality cash flow and growing AI service attachment.",
                "fit_reason": "Strong balance sheet and resilient demand match the mandate.",
                "news_label": "AI services demand improved.",
                "audit_summary": "Recent SEC filing shows stable liquidity and buyback capacity.",
                "technical_summary": "Momentum remains constructive above long-term averages.",
                "source_points": ["Price and volume from Yahoo Finance.", "Disclosure metadata from SEC EDGAR."],
                "catalysts": ["AI service monetization", "Shareholder return update"],
                "risks": ["Valuation compression if rates rise"],
            }
        ],
        "meta": {
            "as_of_date": "2026-04-21",
            "data_provenance": {
                "source": "yfinance",
                "last_refresh_at": "2026-04-21T08:00:00Z",
                "macro_source": "FRED",
                "sec_filings_records": 3,
            },
            "validation_summary": {"level": "pass", "items": []},
            "validation_flags": [],
            "coverage_flags": [],
            "confidence_level": "high",
        },
    }
