from __future__ import annotations

from app.domain.contracts import DebugAnalysisRequest
from app.services.analysis_service import AnalysisService
from app.workflows.base import Workflow, WorkflowContext, WorkflowResult


class StructuredAnalysisWorkflow(Workflow):
    key = "structured"

    def __init__(self, analysis_service: AnalysisService):
        self.analysis_service = analysis_service

    async def execute(self, payload: DebugAnalysisRequest, context: WorkflowContext) -> WorkflowResult:
        result = await self.analysis_service.run_structured_analysis(payload)

        context.stage_position = 0
        for stage in result.get("debug_stages", []):
            context.add_stage(stage, output_data=stage)

        snapshot = {"mode": "structured", "status": "completed", **result}
        context.store_snapshot(snapshot)
        context.store_artifact("analysis", "structured_result", result)
        context.store_artifact("output", "final_response", snapshot)
        return WorkflowResult(status="completed", response=snapshot)
