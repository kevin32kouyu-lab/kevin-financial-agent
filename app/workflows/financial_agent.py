from __future__ import annotations

from app.domain.contracts import AgentRunRequest
from app.services.agent_service import AgentRunHooks, AgentService
from app.services.profile_service import ProfileService
from app.workflows.base import Workflow, WorkflowContext, WorkflowResult


class FinancialAgentWorkflow(Workflow):
    key = "agent"

    def __init__(self, agent_service: AgentService, *, profile_service: ProfileService):
        self.agent_service = agent_service
        self.profile_service = profile_service

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
        response = await self.agent_service.run(payload, hooks=hooks)
        preference_snapshot = response.get("preference_snapshot")
        if isinstance(preference_snapshot, dict):
            stored_preferences = self.profile_service.save_snapshot(
                run_id=context.run_id,
                snapshot=preference_snapshot,
            )
            response["stored_preferences"] = stored_preferences.model_dump()
            context.store_artifact("derived", "stored_preferences", response["stored_preferences"])
        context.store_artifact("output", "final_response", response)
        return WorkflowResult(
            status=response.get("status", "completed"),
            response=response,
            report_mode=response.get("report_mode"),
            error_message=response.get("report_error"),
        )
