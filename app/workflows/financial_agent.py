from __future__ import annotations

from app.domain.contracts import AgentRunRequest
from app.services.agent_service import AgentRunHooks, AgentService
from app.workflows.base import Workflow, WorkflowContext, WorkflowResult


class FinancialAgentWorkflow(Workflow):
    key = "agent"

    def __init__(self, agent_service: AgentService):
        self.agent_service = agent_service

    async def execute(self, payload: AgentRunRequest, context: WorkflowContext) -> WorkflowResult:
        async def on_stage(stage: dict) -> None:
            context.add_stage(stage, output_data=stage)

        async def on_artifact(kind: str, name: str, value: object) -> None:
            context.store_artifact(kind, name, value)

        async def on_snapshot(response: dict) -> None:
            context.store_snapshot(response)

        hooks = AgentRunHooks(
            stage_callback=on_stage,
            artifact_callback=on_artifact,
            snapshot_callback=on_snapshot,
        )
        run = context.repository.get_run(context.run_id)
        client_id = None
        if run is not None:
            client_id = str((run.metadata or {}).get("client_id") or "").strip() or None
        response = await self.agent_service.run(payload, hooks=hooks, client_id=client_id)
        context.store_artifact("output", "final_response", response)
        return WorkflowResult(
            status=response.get("status", "completed"),
            response=response,
            report_mode=response.get("report_mode"),
            error_message=response.get("report_error"),
        )
