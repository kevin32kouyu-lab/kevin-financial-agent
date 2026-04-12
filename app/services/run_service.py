from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.domain.contracts import RunCreateRequest
from app.repositories.sqlite_run_repository import SqliteRunRepository
from app.workflows.base import Workflow, WorkflowContext


@dataclass(slots=True)
class WorkflowRunner:
    repository: SqliteRunRepository
    workflows: dict[str, Workflow]
    _tasks: dict[str, asyncio.Task[Any]] = field(init=False, default_factory=dict)

    async def start(self) -> None:
        for run in self.repository.list_resumable_runs():
            self.schedule(run.id)

    async def stop(self) -> None:
        if not self._tasks:
            return
        for task in list(self._tasks.values()):
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    def schedule(self, run_id: str) -> None:
        task = self._tasks.get(run_id)
        if task and not task.done():
            return
        self._tasks[run_id] = asyncio.create_task(self._run(run_id))

    async def _run(self, run_id: str) -> None:
        try:
            run = self.repository.get_run(run_id)
            if run is None:
                return

            workflow_key = run.workflow_key or run.mode
            workflow = self.workflows.get(workflow_key)
            if workflow is None:
                raise RuntimeError(f"未找到 workflow: {workflow_key}")

            request_payload = self.repository.get_artifact_content(run_id, kind="input", name="request")
            if request_payload is None:
                raise RuntimeError("未找到原始输入，无法执行 workflow。")

            self.repository.mark_run_started(run_id, attempt_count=(run.attempt_count or 0) + 1)
            event_name = "run.resumed" if run.status == "running" else "run.started"
            self.repository.add_event(
                run_id,
                event_type=event_name,
                payload={"mode": run.mode, "workflow_key": workflow_key},
            )

            context = WorkflowContext(run_id=run_id, mode=run.mode, repository=self.repository)
            typed_payload = self._materialize_payload(run.mode, request_payload)
            result = await workflow.execute(typed_payload, context)

            self.repository.mark_run_finished(
                run_id,
                status=result.status,
                error_message=result.error_message,
                report_mode=result.report_mode,
            )
            self.repository.add_event(
                run_id,
                event_type=f"run.{result.status}",
                payload={
                    "status": result.status,
                    "report_mode": result.report_mode,
                },
            )
        except Exception as exc:
            self.repository.mark_run_finished(run_id, status="failed", error_message=str(exc))
            self.repository.replace_artifact(run_id, kind="output", name="error", content={"message": str(exc)})
            self.repository.add_event(run_id, event_type="run.failed", payload={"message": str(exc)})
        finally:
            self._tasks.pop(run_id, None)

    @staticmethod
    def _materialize_payload(mode: str, request_payload: dict[str, Any]) -> Any:
        request = RunCreateRequest.model_validate(request_payload)
        return request.agent if mode == "agent" else request.structured


class RunService:
    def __init__(self, repository: SqliteRunRepository, runner: WorkflowRunner):
        self.repository = repository
        self.runner = runner

    @staticmethod
    def _make_title(payload: RunCreateRequest) -> str:
        if payload.mode == "agent":
            query = (payload.agent.query if payload.agent else "").strip()
            return query[:80] or "自然语言研究任务"

        tickers = ", ".join((payload.structured.explicit_targets.tickers if payload.structured else [])[:3])
        return f"结构化筛选：{tickers}".strip("：") or "结构化筛选任务"

    async def create_run(self, payload: RunCreateRequest, *, parent_run_id: str | None = None) -> dict[str, Any]:
        if payload.mode == "agent" and payload.agent is None:
            raise HTTPException(status_code=400, detail="agent 模式需要提供 agent 请求体。")
        if payload.mode == "structured" and payload.structured is None:
            raise HTTPException(status_code=400, detail="structured 模式需要提供 structured 请求体。")

        run_id = uuid4().hex
        self.repository.create_run(
            run_id=run_id,
            mode=payload.mode,
            workflow_key=payload.mode,
            title=self._make_title(payload),
            parent_run_id=parent_run_id,
            metadata={"source": "api", "mode": payload.mode},
        )
        self.repository.replace_artifact(run_id, kind="input", name="request", content=payload.model_dump())
        self.repository.add_event(run_id, event_type="run.created", payload={"run_id": run_id, "mode": payload.mode})
        self.runner.schedule(run_id)
        return self.get_run_detail_or_404(run_id)

    def list_run_summaries(
        self,
        *,
        limit: int = 20,
        mode: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        return {
            "items": [
                item.model_dump()
                for item in self.repository.list_runs(limit=limit, mode=mode, status=status, search=search)
            ]
        }

    def clear_run_history(
        self,
        *,
        mode: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        deleted_count = self.repository.delete_runs(
            mode=mode,
            status=status,
            search=search,
            include_active=False,
        )
        return {"deleted_count": deleted_count}

    def get_run_or_404(self, run_id: str):
        run = self.repository.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="未找到对应的 run。")
        return run

    def get_run_detail_or_404(self, run_id: str) -> dict[str, Any]:
        detail = self.repository.build_run_detail(run_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="未找到对应的 run。")
        return {
            "run": detail.run.model_dump(),
            "steps": [step.model_dump() for step in detail.steps],
            "artifacts": [artifact.model_dump(exclude={"content"}) for artifact in detail.artifacts],
            "result": detail.result,
        }

    def get_run_artifacts_or_404(self, run_id: str) -> dict[str, Any]:
        self.get_run_or_404(run_id)
        detail = self.repository.build_run_detail(run_id)
        return {
            "run_id": run_id,
            "artifacts": [artifact.model_dump() for artifact in detail.artifacts],
        }

    async def retry_run_or_404(self, run_id: str) -> dict[str, Any]:
        payload_data = self.repository.get_artifact_content(run_id, kind="input", name="request")
        if payload_data is None:
            raise HTTPException(status_code=404, detail="未找到该 run 的原始输入，无法重试。")
        payload = RunCreateRequest.model_validate(payload_data)
        return await self.create_run(payload, parent_run_id=run_id)
