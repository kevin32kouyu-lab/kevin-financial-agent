from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from app.core.config import AppSettings
from app.repositories.sqlite_knowledge_repository import SqliteKnowledgeRepository
from app.repositories.sqlite_run_repository import SqliteRunRepository
from app.services.agent_coordinator import AgentCoordinator
from app.services.analysis_service import AnalysisService
from app.services.auth_service import AuthService
from app.services.backtest_service import BacktestService
from app.services.rag_service import KnowledgeRagService
from app.services.market_data_service import MarketDataService
from app.services.pdf_export_service import PdfExportService
from app.services.profile_service import ProfileService
from app.services.report_service import ReportService
from app.services.run_audit_service import RunAuditService
from app.services.run_service import RunService, WorkflowRunner
from app.services.toolkit import MarketToolKit
from app.workflows.financial_agent import FinancialAgentWorkflow
from app.workflows.structured_analysis import StructuredAnalysisWorkflow


@dataclass(slots=True)
class ApplicationRuntime:
    settings: AppSettings
    repository: SqliteRunRepository
    knowledge_repository: SqliteKnowledgeRepository
    market_data_service: MarketDataService
    toolkit: MarketToolKit
    analysis_service: AnalysisService
    report_service: ReportService
    agent_service: AgentCoordinator
    auth_service: AuthService
    profile_service: ProfileService
    run_audit_service: RunAuditService
    backtest_service: BacktestService
    pdf_export_service: PdfExportService
    rag_service: KnowledgeRagService
    workflow_runner: WorkflowRunner
    run_service: RunService

    async def startup(self) -> None:
        self.repository.init_schema()
        self.knowledge_repository.init_schema()
        self.market_data_service.startup()
        self.market_data_service.start_refresh_scheduler()
        await self.workflow_runner.start()

    async def shutdown(self) -> None:
        await self.workflow_runner.stop()
        self.market_data_service.stop_refresh_scheduler()


def build_runtime(settings: AppSettings | None = None) -> ApplicationRuntime:
    resolved_settings = settings or AppSettings.from_env()
    repository = SqliteRunRepository(resolved_settings.db_path)
    knowledge_repository = SqliteKnowledgeRepository(resolved_settings.knowledge_db_path)
    rag_service = KnowledgeRagService(knowledge_repository)
    market_data_service = MarketDataService(resolved_settings)
    toolkit = MarketToolKit()
    analysis_service = AnalysisService(toolkit=toolkit, market_data_service=market_data_service)
    report_service = ReportService(rag_service=rag_service)
    agent_service = AgentCoordinator(analysis_service, report_service)
    auth_service = AuthService(repository, resolved_settings)
    profile_service = ProfileService(repository=repository)
    run_audit_service = RunAuditService()
    backtest_service = BacktestService(repository=repository, settings=resolved_settings)
    pdf_export_service = PdfExportService(settings=resolved_settings)
    workflows = {
        "structured": StructuredAnalysisWorkflow(analysis_service),
        "agent": FinancialAgentWorkflow(agent_service, profile_service=profile_service),
    }
    workflow_runner = WorkflowRunner(repository=repository, workflows=workflows)
    run_service = RunService(repository=repository, runner=workflow_runner, profile_service=profile_service, run_audit_service=run_audit_service)
    return ApplicationRuntime(
        settings=resolved_settings,
        repository=repository,
        knowledge_repository=knowledge_repository,
        market_data_service=market_data_service,
        toolkit=toolkit,
        analysis_service=analysis_service,
        report_service=report_service,
        agent_service=agent_service,
        auth_service=auth_service,
        profile_service=profile_service,
        run_audit_service=run_audit_service,
        backtest_service=backtest_service,
        pdf_export_service=pdf_export_service,
        rag_service=rag_service,
        workflow_runner=workflow_runner,
        run_service=run_service,
    )


def get_runtime(app: FastAPI) -> ApplicationRuntime:
    runtime = getattr(app.state, "runtime", None)
    if runtime is None:
        settings = AppSettings.from_env()
        runtime = build_runtime(settings)
        app.state.runtime = runtime
        runtime.repository.init_schema()
        runtime.knowledge_repository.init_schema()
        runtime.market_data_service.startup()
    return runtime
