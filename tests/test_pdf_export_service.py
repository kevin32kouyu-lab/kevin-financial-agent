"""PDF 导出测试：确认后端能生成完整报告模板和真正 PDF 文件。"""

import pytest
from starlette.requests import Request
from types import SimpleNamespace

from app.api.history import export_run_pdf
from app.core.config import AppSettings
from app.services.pdf_export_service import PdfExportResult
from app.services.pdf_export_service import PdfExportService


def _sample_report_result() -> dict:
    """构造一份足够覆盖 PDF 导出核心内容的报告结果。"""
    return {
        "query": "Find a conservative long-term investment between AAPL and MSFT.",
        "research_context": {"research_mode": "realtime"},
        "final_report": "# Simple Investment Report\n\n## One-line Verdict\n\nPrefer AAPL first.",
        "report_outputs": {
            "simple_investment": {
                "markdown": "# Simple Investment Report\n\n## One-line Verdict\n\nPrefer AAPL first.",
                "charts": {
                    "portfolio_allocation": {"status": "ready", "items": [{"ticker": "AAPL", "weight": 60}]},
                    "candidate_score_comparison": {"status": "ready", "items": [{"ticker": "AAPL", "composite": 82}]},
                    "portfolio_vs_benchmark_backtest": {"status": "missing", "message": "No backtest available."},
                    "risk_contribution": {"status": "ready", "items": [{"name": "Valuation", "value": 55}]},
                },
            },
            "investment": {
                "markdown": "# Simple Investment Report\n\n## One-line Verdict\n\nPrefer AAPL first.",
                "charts": {
                    "portfolio_allocation": {"status": "ready", "items": [{"ticker": "AAPL", "weight": 60}]},
                    "candidate_score_comparison": {"status": "ready", "items": [{"ticker": "AAPL", "composite": 82}]},
                    "portfolio_vs_benchmark_backtest": {"status": "missing", "message": "No backtest available."},
                    "risk_contribution": {"status": "ready", "items": [{"name": "Valuation", "value": 55}]},
                },
            },
            "professional_investment": {
                "markdown": (
                    "# Professional Investment Report\n\n"
                    "## Executive Summary\n\nPrefer AAPL with valuation discipline.\n\n"
                    "## Valuation View\n\nAAPL is not cheap.\n\n"
                    "## Quality & Growth Analysis\n\nCash generation is resilient.\n\n"
                    "## Scenario Analysis\n\nBase case remains selective."
                ),
                "charts": {
                    "portfolio_allocation": {"status": "ready", "items": [{"ticker": "AAPL", "weight": 60}]},
                    "candidate_score_comparison": {"status": "ready", "items": [{"ticker": "AAPL", "composite": 82}]},
                    "portfolio_vs_benchmark_backtest": {"status": "missing", "message": "No backtest available."},
                    "risk_contribution": {"status": "ready", "items": [{"name": "Valuation", "value": 55}]},
                },
            },
            "development": {
                "markdown": "# Agentic Research Development Report\n\n## Agent Workflow\n\nEvidenceAgent retrieved evidence.",
                "diagnostics": {
                    "agent_count": 2,
                    "evidence_count": 1,
                    "validation_check_count": 0,
                    "backtest_status": "missing",
                },
            },
        },
        "report_briefing": {
            "meta": {
                "title": "Conservative Tech Investment Report",
                "subtitle": "PDF export test",
                "confidence_level": "medium",
                "evidence_summary": {
                    "headline": "Evidence supports AAPL as the more defensive choice.",
                    "items": ["AAPL has stronger cash generation."],
                    "source_points": ["Yahoo Finance", "SEC EDGAR"],
                },
                "validation_summary": {
                    "headline": "Conclusion is consistent with the score table.",
                    "items": ["Top pick appears in the scoreboard."],
                },
            },
            "executive": {
                "display_call": "Prefer AAPL, keep MSFT on watchlist.",
                "display_action_summary": "Start with a smaller position and review after earnings.",
                "top_pick": "AAPL",
                "market_stance": "selective",
                "mandate_fit_score": 82,
            },
            "macro": {"risk_headline": "Market is selective.", "regime": "neutral", "vix": 16.2},
            "scoreboard": [
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "latest_price": 180.0,
                    "composite_score": 82,
                    "verdict_label": "Accumulate",
                }
            ],
            "ticker_cards": [
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "verdict_label": "Accumulate",
                    "thesis": "Durable cash flow and shareholder returns.",
                    "fit_reason": "Matches conservative long-term style.",
                    "evidence_points": ["Cash flow remains resilient."],
                    "caution_points": ["Valuation is not cheap."],
                    "execution": "Build gradually.",
                }
            ],
            "risk_register": [{"category": "Valuation", "ticker": "AAPL", "summary": "Multiple compression risk."}],
        },
    }


def _sample_backtest() -> dict:
    """构造一份可用于 PDF 图表的回测结果。"""
    return {
        "summary": {
            "id": "bt-1",
            "source_run_id": "run-001",
            "entry_date": "2026-01-16",
            "end_date": "2026-04-22",
            "benchmark_ticker": "SPY",
            "metrics": {
                "total_return_pct": 8.4,
                "benchmark_return_pct": 5.1,
                "excess_return_pct": 3.3,
            },
        },
        "points": [
            {
                "point_date": "2026-01-16",
                "portfolio_value": 100.0,
                "benchmark_value": 100.0,
                "portfolio_return_pct": 0.0,
                "benchmark_return_pct": 0.0,
            },
            {
                "point_date": "2026-04-22",
                "portfolio_value": 108.4,
                "benchmark_value": 105.1,
                "portfolio_return_pct": 8.4,
                "benchmark_return_pct": 5.1,
            },
        ],
        "meta": {
            "assumptions": {
                "transaction_cost_bps": 10,
                "slippage_bps": 5,
                "dividend_mode": "cash_only",
                "rebalance": "buy_and_hold",
            }
        },
    }


def test_pdf_export_html_uses_simple_investment_layout_by_default():
    """默认 PDF 应使用简单版投资报告，保留关键图表但不重复长正文。"""
    service = PdfExportService(settings=AppSettings())
    html = service.build_report_html(run_id="run-001", result=_sample_report_result(), backtest=None)

    assert "Simple Investment Report" in html
    assert "Find a conservative long-term investment" in html
    assert "Prefer AAPL" in html
    assert "Apple Inc." in html
    assert "Recommended Portfolio Allocation" in html
    assert "Candidate Score Comparison" in html
    assert "Risk Contribution" in html
    assert "Portfolio vs Benchmark Backtest" not in html
    assert "Full memo body with portfolio action plan and risk notes." not in html
    assert "Full memo" not in html
    assert "Ticker research cards" not in html
    assert "系统理解" not in html
    assert "长期记忆" not in html


def test_pdf_export_professional_kind_uses_professional_report():
    """专业版 PDF 应读取 professional_investment 输出。"""
    service = PdfExportService(settings=AppSettings())
    html = service.build_report_html(
        run_id="run-001",
        result=_sample_report_result(),
        backtest=None,
        kind="professional_investment",
    )

    assert "Professional Investment Report" in html
    assert "Valuation View" in html
    assert "Quality &amp; Growth Analysis" in html or "Quality & Growth Analysis" in html
    assert "Simple Investment Report" not in html


def test_pdf_export_html_prefers_backtest_chart_when_backtest_is_available():
    """有回测时，第三张关键图表应切换成组合 vs 基准回测。"""
    service = PdfExportService(settings=AppSettings())
    html = service.build_report_html(run_id="run-001", result=_sample_report_result(), backtest=_sample_backtest())

    assert "Recommended Portfolio Allocation" in html
    assert "Candidate Score Comparison" in html
    assert "Portfolio vs Benchmark Backtest" in html
    assert "Risk Contribution" not in html


def test_pdf_export_simple_kind_reads_shared_display_model():
    """简单版 PDF 应读取网页同用的展示母版，而不是单独拼另一套内容。"""
    result = _sample_report_result()
    result["report_outputs"]["simple_investment"]["display_model"] = {
        "version": "simple_report_showcase_v1",
        "layout": "two_page_showcase",
        "title": "Shared Showcase Report",
        "subtitle": "Shared by web and PDF",
        "query": "Display model query marker.",
        "pages": [
            {"id": "decision", "title": "Decision page"},
            {"id": "credibility", "title": "Credibility page"},
        ],
        "decision": {
            "headline": "Display model verdict marker.",
            "action": "Display model action marker.",
            "top_pick": "AAPL",
            "confidence": "high",
            "risk_summary": "Display model risk marker.",
        },
        "key_metrics": [
            {"key": "mandate_fit", "label": "Mandate fit", "value": "82.0", "tone": "positive"},
            {"key": "evidence_count", "label": "Evidence", "value": "1", "tone": "neutral"},
        ],
        "holdings": [{"ticker": "AAPL", "weight": 60, "role": "Core", "reason": "Display model holding marker."}],
        "chart_slots": [
            {"key": "portfolio_allocation", "title": "Recommended Portfolio Allocation", "type": "bar"},
            {"key": "candidate_score_comparison", "title": "Candidate Score Comparison", "type": "bar"},
            {"key": "risk_contribution", "title": "Risk Contribution", "type": "bar"},
        ],
        "reasons": [{"ticker": "AAPL", "text": "Display model reason marker."}],
        "risks": [{"category": "Valuation", "summary": "Display model risk detail marker."}],
        "evidence": [{"title": "Display model evidence marker.", "source": "SEC EDGAR", "date": "2026-04-01"}],
        "validation": {"headline": "Display model validation marker.", "items": ["Shared model check."]},
        "footer_note": "Display model footer marker.",
    }

    service = PdfExportService(settings=AppSettings())
    html = service.build_report_html(run_id="run-001", result=result, backtest=None)

    assert "Shared Showcase Report" in html
    assert "simple-report-page decision-page" in html
    assert "simple-report-page credibility-page" in html
    assert "Display model verdict marker." in html
    assert "Display model evidence marker." in html
    assert "Display model footer marker." in html


def test_pdf_export_refreshes_display_model_chart_slot_with_latest_backtest():
    """已有展示母版也要按最新回测刷新第三张图。"""
    result = _sample_report_result()
    result["report_outputs"]["simple_investment"]["display_model"] = {
        "version": "simple_report_showcase_v1",
        "layout": "two_page_showcase",
        "title": "Shared Showcase Report",
        "query": "Display model query marker.",
        "pages": [{"id": "decision", "title": "Decision page"}, {"id": "credibility", "title": "Credibility page"}],
        "decision": {"headline": "Decision", "action": "Action", "top_pick": "AAPL", "confidence": "medium", "risk_summary": "Risk"},
        "key_metrics": [],
        "holdings": [],
        "chart_slots": [
            {"key": "portfolio_allocation", "title": "Recommended Portfolio Allocation", "type": "bar"},
            {"key": "candidate_score_comparison", "title": "Candidate Score Comparison", "type": "bar"},
            {"key": "risk_contribution", "title": "Risk Contribution", "type": "bar"},
        ],
        "reasons": [],
        "risks": [],
        "evidence": [],
        "validation": {"headline": "Validation", "items": []},
    }

    service = PdfExportService(settings=AppSettings())
    html = service.build_report_html(run_id="run-001", result=result, backtest=_sample_backtest())

    assert "Portfolio vs Benchmark Backtest" in html
    assert "Risk Contribution" not in html


def test_pdf_export_development_kind_uses_development_report():
    """开发报告 PDF 应使用工程支撑报告内容，不混成投资正文。"""
    service = PdfExportService(settings=AppSettings())
    html = service.build_report_html(run_id="run-001", result=_sample_report_result(), backtest=None, kind="development")

    assert "Agentic Research Development Report" in html
    assert "Agent Workflow" in html
    assert "EvidenceAgent retrieved evidence" in html
    assert "Development diagnostics" in html
    assert "Evidence Count" in html
    assert "Validation Check Count" in html


@pytest.mark.asyncio
async def test_pdf_export_returns_real_pdf_bytes(monkeypatch):
    """导出服务应返回 application/pdf 文件，而不是 HTML 假下载。"""
    service = PdfExportService(settings=AppSettings())

    async def fake_renderer(html: str) -> bytes:
        assert "simple-report-page decision-page" in html
        assert "simple-report-page credibility-page" in html
        assert "Recommended Portfolio Allocation" in html
        return b"%PDF-1.4\n% test pdf\n"

    monkeypatch.setattr(service, "_render_html_to_pdf", fake_renderer)

    exported = await service.export_report_pdf(run_id="run-001", result=_sample_report_result(), backtest=None)

    assert exported.media_type == "application/pdf"
    assert exported.content.startswith(b"%PDF")
    assert exported.filename.endswith(".pdf")
    assert exported.filename.startswith("simple-investment-report-")


@pytest.mark.asyncio
async def test_pdf_export_investment_kind_aliases_simple_filename(monkeypatch):
    """旧 kind=investment 应兼容映射到简单版。"""
    service = PdfExportService(settings=AppSettings())

    async def fake_renderer(html: str) -> bytes:
        assert "Simple Investment Report" in html
        return b"%PDF-1.4\n% test pdf\n"

    monkeypatch.setattr(service, "_render_html_to_pdf", fake_renderer)

    exported = await service.export_report_pdf(run_id="run-001", result=_sample_report_result(), backtest=None, kind="investment")

    assert exported.filename.startswith("simple-investment-report-")


@pytest.mark.asyncio
async def test_pdf_export_professional_kind_uses_professional_filename(monkeypatch):
    """kind=professional_investment 时文件名应标识专业版。"""
    service = PdfExportService(settings=AppSettings())

    async def fake_renderer(html: str) -> bytes:
        assert "Professional Investment Report" in html
        return b"%PDF-1.4\n% test pdf\n"

    monkeypatch.setattr(service, "_render_html_to_pdf", fake_renderer)

    exported = await service.export_report_pdf(
        run_id="run-001",
        result=_sample_report_result(),
        backtest=None,
        kind="professional_investment",
    )

    assert exported.filename.startswith("professional-investment-report-")


@pytest.mark.asyncio
async def test_pdf_export_development_kind_uses_development_filename(monkeypatch):
    """kind=development 时文件名应清楚标识为开发报告。"""
    service = PdfExportService(settings=AppSettings())

    async def fake_renderer(html: str) -> bytes:
        assert "Agentic Research Development Report" in html
        return b"%PDF-1.4\n% test pdf\n"

    monkeypatch.setattr(service, "_render_html_to_pdf", fake_renderer)

    exported = await service.export_report_pdf(run_id="run-001", result=_sample_report_result(), backtest=None, kind="development")

    assert exported.filename.startswith("development-report-")


@pytest.mark.asyncio
async def test_pdf_export_endpoint_returns_download_response():
    """API 入口应返回 application/pdf 和下载文件头。"""
    audit_events: list[dict] = []

    class FakeRunService:
        def get_run_detail_or_404(self, run_id: str, *, user=None, client_id=None):
            return {"result": _sample_report_result()}

    class FakeRepository:
        def list_backtests(self, *, source_run_id: str, limit: int = 1):
            return []

        def add_audit_event(self, **payload):
            audit_events.append(payload)

    class FakePdfService:
        async def export_report_pdf(self, *, run_id: str, result: dict, backtest=None, kind: str = "investment"):
            assert kind == "simple_investment"
            return PdfExportResult(filename="simple-investment-report-latest.pdf", content=b"%PDF-1.4\n")

    fake_runtime = SimpleNamespace(
        run_service=FakeRunService(),
        repository=FakeRepository(),
        pdf_export_service=FakePdfService(),
        auth_service=SimpleNamespace(get_user_for_token=lambda token: None),
    )
    fake_app = SimpleNamespace(state=SimpleNamespace(runtime=fake_runtime))
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/runs/run-001/export/pdf",
            "headers": [(b"x-client-id", b"browser-001")],
            "app": fake_app,
        }
    )

    response = await export_run_pdf(request, "run-001")

    assert response.media_type == "application/pdf"
    assert response.body.startswith(b"%PDF")
    assert response.headers["content-disposition"] == 'attachment; filename="simple-investment-report-latest.pdf"'
    assert audit_events[0]["action"] == "run.export_pdf"


@pytest.mark.asyncio
async def test_pdf_export_endpoint_passes_kind_to_service():
    """API 入口要把 kind 参数传给 PDF 服务。"""
    captured: dict[str, str] = {}

    class FakeRunService:
        def get_run_detail_or_404(self, run_id: str, *, user=None, client_id=None):
            return {"result": _sample_report_result()}

    class FakeRepository:
        def list_backtests(self, *, source_run_id: str, limit: int = 1):
            return []

        def add_audit_event(self, **payload):
            captured["audit_kind"] = payload["metadata"]["kind"]

    class FakePdfService:
        async def export_report_pdf(self, *, run_id: str, result: dict, backtest=None, kind: str = "investment"):
            captured["kind"] = kind
            return PdfExportResult(filename="professional-investment-report-latest.pdf", content=b"%PDF-1.4\n")

    fake_runtime = SimpleNamespace(
        run_service=FakeRunService(),
        repository=FakeRepository(),
        pdf_export_service=FakePdfService(),
        auth_service=SimpleNamespace(get_user_for_token=lambda token: None),
    )
    fake_app = SimpleNamespace(state=SimpleNamespace(runtime=fake_runtime))
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/runs/run-001/export/pdf",
            "query_string": b"kind=professional_investment",
            "headers": [(b"x-client-id", b"browser-001")],
            "app": fake_app,
        }
    )

    response = await export_run_pdf(request, "run-001", kind="professional_investment")

    assert response.headers["content-disposition"] == 'attachment; filename="professional-investment-report-latest.pdf"'
    assert captured == {"kind": "professional_investment", "audit_kind": "professional_investment"}
