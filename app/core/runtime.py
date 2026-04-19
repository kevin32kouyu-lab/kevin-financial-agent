from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from app.core.config import AppSettings
from app.repositories.sqlite_run_repository import SqliteRunRepository
from app.services.agent_service import AgentService
from app.services.analysis_service import AnalysisService
from app.services.backtest_service import BacktestService
from app.services.market_data_service import MarketDataService
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
    market_data_service: MarketDataService
    toolkit: MarketToolKit
    analysis_service: AnalysisService
    report_service: ReportService
    agent_service: AgentService
    profile_service: ProfileService
    run_audit_service: RunAuditService
    backtest_service: BacktestService
    workflow_runner: WorkflowRunner
    run_service: RunService

    async def startup(self) -> None:
        self.repository.init_schema()
        self.market_data_service.startup()
        await self.workflow_runner.start()

    async def shutdown(self) -> None:
        await self.workflow_runner.stop()


def build_runtime(settings: AppSettings | None = None) -> ApplicationRuntime:
    resolved_settings = settings or AppSettings.from_env()
    repository = SqliteRunRepository(resolved_settings.db_path)
    market_data_service = MarketDataService(resolved_settings)
    toolkit = MarketToolKit()
    analysis_service = AnalysisService(toolkit=toolkit, market_data_service=market_data_service)
    report_service = ReportService()
    agent_service = AgentService(analysis_service, report_service)
    profile_service = ProfileService(repository=repository)
    run_audit_service = RunAuditService()
    backtest_service = BacktestService(repository=repository, settings=resolved_settings)
    workflows = {
        "structured": StructuredAnalysisWorkflow(analysis_service),
        "agent": FinancialAgentWorkflow(agent_service, profile_service=profile_service),
    }
    workflow_runner = WorkflowRunner(repository=repository, workflows=workflows)
    run_service = RunService(repository=repository, runner=workflow_runner, profile_service=profile_service, run_audit_service=run_audit_service)
    return ApplicationRuntime(
        settings=resolved_settings,
        repository=repository,
        market_data_service=market_data_service,
        toolkit=toolkit,
        analysis_service=analysis_service,
        report_service=report_service,
        agent_service=agent_service,
        profile_service=profile_service,
        run_audit_service=run_audit_service,
        backtest_service=backtest_service,
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
        runtime.market_data_service.startup()
    return runtime
