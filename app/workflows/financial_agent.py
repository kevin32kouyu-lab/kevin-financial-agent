from __future__ import annotations

from app.domain.contracts import AgentRunRequest
from app.services.agent_coordinator import AgentCoordinator, AgentRunHooks
from app.services.profile_service import ProfileService
from app.workflows.base import Workflow, WorkflowContext, WorkflowResult


class FinancialAgentWorkflow(Workflow):
    key = "agent"

    def __init__(self, agent_service: AgentCoordinator, *, profile_service: ProfileService):
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
        run = context.repository.get_run(context.run_id)
        metadata = run.metadata if run else {}
        resume_agent = str(metadata.get("resume_from_agent") or "").strip()
        source_run_id = str(metadata.get("source_run_id") or "").strip()
        if resume_agent and source_run_id:
            previous_result = (
                context.repository.get_artifact_content(source_run_id, kind="output", name="final_response")
                or context.repository.get_artifact_content(source_run_id, kind="snapshot", name="current")
                or {}
            )
            response = await self.agent_service.resume_from_agent(
                payload,
                previous_result=previous_result,
                agent_name=resume_agent,
                reason=str(metadata.get("resume_reason") or ""),
                hooks=hooks,
            )
        else:
            response = await self.agent_service.run(payload, hooks=hooks)
        preference_snapshot = response.get("preference_snapshot")
        if isinstance(preference_snapshot, dict):
            client_id = str((run.metadata if run else {}).get("client_id") or "default")
            user_id = str((run.metadata if run else {}).get("user_id") or "").strip() or None
            stored_preferences = self.profile_service.save_snapshot(
                run_id=context.run_id,
                snapshot=preference_snapshot,
                profile_id=client_id,
                user_id=user_id,
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
