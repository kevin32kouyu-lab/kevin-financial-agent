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
        "final_report": "Full memo body with portfolio action plan and risk notes.",
        "report_outputs": {
            "investment": {
                "markdown": "# Institutional Investment Research Report\n\nFull memo body with portfolio action plan and risk notes.",
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
                    "rag_evidence_count": 1,
                    "validation_warning_count": 0,
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


def test_pdf_export_html_contains_complete_user_report_sections():
    """PDF 专用 HTML 必须包含用户问题、结论、评分表、逐票卡和完整正文。"""
    service = PdfExportService(settings=AppSettings())
    html = service.build_report_html(run_id="run-001", result=_sample_report_result(), backtest=None)

    assert "Find a conservative long-term investment" in html
    assert "Prefer AAPL" in html
    assert "Apple Inc." in html
    assert "Full memo body" in html
    assert "系统理解" not in html
    assert "长期记忆" not in html


def test_pdf_export_development_kind_uses_development_report():
    """开发报告 PDF 应使用工程支撑报告内容，不混成投资正文。"""
    service = PdfExportService(settings=AppSettings())
    html = service.build_report_html(run_id="run-001", result=_sample_report_result(), backtest=None, kind="development")

    assert "Agentic Research Development Report" in html
    assert "Agent Workflow" in html
    assert "EvidenceAgent retrieved evidence" in html
    assert "Development diagnostics" in html


@pytest.mark.asyncio
async def test_pdf_export_returns_real_pdf_bytes(monkeypatch):
    """导出服务应返回 application/pdf 文件，而不是 HTML 假下载。"""
    service = PdfExportService(settings=AppSettings())

    async def fake_renderer(html: str) -> bytes:
        assert "Full memo body" in html
        return b"%PDF-1.4\n% test pdf\n"

    monkeypatch.setattr(service, "_render_html_to_pdf", fake_renderer)

    exported = await service.export_report_pdf(run_id="run-001", result=_sample_report_result(), backtest=None)

    assert exported.media_type == "application/pdf"
    assert exported.content.startswith(b"%PDF")
    assert exported.filename.endswith(".pdf")
    assert "investment-report" in exported.filename


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
            assert kind == "investment"
            return PdfExportResult(filename="investment-report-latest.pdf", content=b"%PDF-1.4\n")

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
    assert response.headers["content-disposition"] == 'attachment; filename="investment-report-latest.pdf"'
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
            return PdfExportResult(filename="development-report-latest.pdf", content=b"%PDF-1.4\n")

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
            "query_string": b"kind=development",
            "headers": [(b"x-client-id", b"browser-001")],
            "app": fake_app,
        }
    )

    response = await export_run_pdf(request, "run-001", kind="development")

    assert response.headers["content-disposition"] == 'attachment; filename="development-report-latest.pdf"'
    assert captured == {"kind": "development", "audit_kind": "development"}
