"""LangGraph 版自然语言金融研究 workflow。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agent_graph.adapters import build_public_response
from app.agent_graph.graph import FinancialResearchGraph, open_sqlite_checkpointer
from app.agent_graph.state import build_initial_state
from app.domain.contracts import AgentRunRequest
from app.services.profile_service import ProfileService
from app.workflows.base import Workflow, WorkflowContext, WorkflowResult


class LangGraphFinancialAgentWorkflow(Workflow):
    """通过 LangGraph 执行受控多节点金融研究。"""

    key = "agent_v2"

    def __init__(
        self,
        analysis_service: Any,
        report_service: Any,
        *,
        profile_service: ProfileService | None,
    ):
        """绑定现有业务服务。"""
        self.analysis_service = analysis_service
        self.report_service = report_service
        self.profile_service = profile_service

    async def execute(self, payload: AgentRunRequest, context: WorkflowContext) -> WorkflowResult:
        """执行 LangGraph 研究图，并把状态同步到现有仓储。"""
        runtime = self.report_service.get_runtime_config(model=payload.llm.model, base_url=payload.llm.base_url)
        initial_state = build_initial_state(payload=payload, run_id=context.run_id, runtime=runtime)
        graph = FinancialResearchGraph(self.analysis_service, self.report_service)
        checkpoint_path = self._checkpoint_path(context)
        final_state: dict[str, Any] | None = None
        published_stage_count = 0
        published_artifacts: dict[tuple[str, str], str] = {}

        async with open_sqlite_checkpointer(checkpoint_path) as checkpointer:
            await checkpointer.setup()
            compiled = graph.compile(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": context.run_id}}
            async for state in compiled.astream(initial_state, config=config, stream_mode="values"):
                final_state = state
                published_stage_count, published_artifacts = self._publish_state_delta(
                    context,
                    state,
                    published_stage_count=published_stage_count,
                    published_artifacts=published_artifacts,
                )

        if final_state is None:
            final_state = initial_state
        response = final_state.get("final_response") or build_public_response(final_state)
        context.store_snapshot(response)
        context.store_artifact("output", "final_response", response)

        preference_snapshot = response.get("preference_snapshot")
        if self.profile_service is not None and isinstance(preference_snapshot, dict):
            run = context.repository.get_run(context.run_id)
            metadata = run.metadata if run else {}
            client_id = str(metadata.get("client_id") or "default")
            user_id = str(metadata.get("user_id") or "").strip() or None
            stored_preferences = self.profile_service.save_snapshot(
                run_id=context.run_id,
                snapshot=preference_snapshot,
                profile_id=client_id,
                user_id=user_id,
            )
            response["stored_preferences"] = stored_preferences.model_dump()
            context.store_artifact("derived", "stored_preferences", response["stored_preferences"])
            context.store_snapshot(response)
            context.store_artifact("output", "final_response", response)

        return WorkflowResult(
            status=str(response.get("status") or "completed"),
            response=response,
            report_mode=response.get("report_mode"),
            error_message=response.get("blocking_reason") or response.get("report_error"),
        )

    def _publish_state_delta(
        self,
        context: WorkflowContext,
        state: dict[str, Any],
        *,
        published_stage_count: int,
        published_artifacts: dict[tuple[str, str], str],
    ) -> tuple[int, dict[tuple[str, str], str]]:
        """把 LangGraph 状态增量写入现有 stage、artifact 和 snapshot。"""
        stages = list(state.get("stages") or [])
        for stage in stages[published_stage_count:]:
            context.add_stage(stage, output_data=stage)
        published_stage_count = len(stages)

        artifacts = state.get("artifacts") or {}
        for artifact in artifacts.values():
            key = (str(artifact.get("kind")), str(artifact.get("name")))
            signature = self._artifact_signature(artifact.get("content"))
            if published_artifacts.get(key) == signature:
                continue
            context.store_artifact(key[0], key[1], artifact.get("content"))
            published_artifacts[key] = signature

        context.store_snapshot(build_public_response(state))
        return published_stage_count, published_artifacts

    @staticmethod
    def _checkpoint_path(context: WorkflowContext) -> Path:
        """为 LangGraph checkpoint 选择独立 SQLite 文件。"""
        db_path = context.repository.db_path
        return db_path.with_name(f"{db_path.stem}_langgraph.sqlite3")

    @staticmethod
    def _artifact_signature(value: Any) -> str:
        """生成 artifact 内容签名，用于判断是否需要覆盖仓储记录。"""
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
