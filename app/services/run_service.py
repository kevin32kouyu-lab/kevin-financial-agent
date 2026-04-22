from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.agent_runtime.models import AgentMemoryContext
from app.domain.contracts import PreferenceUpdateRequest
from app.domain.contracts import RunCreateRequest
from app.domain.contracts import AuthUser
from app.repositories.sqlite_run_repository import SqliteRunRepository
from app.services.profile_service import ProfileService
from app.services.run_audit_service import RunAuditService
from app.workflows.base import Workflow, WorkflowContext


@dataclass(slots=True)
class WorkflowRunner:
    repository: SqliteRunRepository
    workflows: dict[str, Workflow]
    _tasks: dict[str, asyncio.Task[Any]] = field(init=False, default_factory=dict)
    _terminal_statuses: set[str] = field(
        init=False,
        default_factory=lambda: {"completed", "failed", "needs_clarification", "cancelled"},
    )

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

    async def cancel(self, run_id: str) -> bool:
        run = self.repository.get_run(run_id)
        if run is None:
            return False
        if run.status in self._terminal_statuses:
            return False

        self.repository.mark_run_finished(
            run_id,
            status="cancelled",
            error_message="Cancelled by user.",
        )
        self.repository.add_event(
            run_id,
            event_type="run.cancelled",
            payload={"status": "cancelled", "message": "Cancelled by user."},
        )
        snapshot = self.repository.get_artifact_content(run_id, kind="snapshot", name="current")
        if isinstance(snapshot, dict):
            snapshot["status"] = "cancelled"
            snapshot["cancel_reason"] = "Cancelled by user."
            self.repository.replace_artifact(run_id, kind="snapshot", name="current", content=snapshot)

        task = self._tasks.get(run_id)
        if run.status == "queued" and task and not task.done():
            task.cancel()
        return True

    async def _run(self, run_id: str) -> None:
        try:
            run = self.repository.get_run(run_id)
            if run is None:
                return
            if run.status == "cancelled":
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

            latest_run = self.repository.get_run(run_id)
            if latest_run is None:
                return
            if latest_run.status == "cancelled":
                return

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
        except asyncio.CancelledError:
            latest_run = self.repository.get_run(run_id)
            if latest_run and latest_run.status != "cancelled":
                self.repository.mark_run_finished(
                    run_id,
                    status="cancelled",
                    error_message="Cancelled by user.",
                )
                self.repository.add_event(
                    run_id,
                    event_type="run.cancelled",
                    payload={"status": "cancelled", "message": "Cancelled by user."},
                )
            raise
        except Exception as exc:
            error_message = str(exc).strip() or "Workflow execution failed with an unknown error."
            self.repository.mark_run_finished(run_id, status="failed", error_message=error_message)
            self.repository.replace_artifact(run_id, kind="output", name="error", content={"message": error_message})
            self.repository.add_event(run_id, event_type="run.failed", payload={"message": error_message})
        finally:
            self._tasks.pop(run_id, None)

    @staticmethod
    def _materialize_payload(mode: str, request_payload: dict[str, Any]) -> Any:
        request = RunCreateRequest.model_validate(request_payload)
        return request.agent if mode == "agent" else request.structured


class RunService:
    def __init__(
        self,
        repository: SqliteRunRepository,
        runner: WorkflowRunner,
        *,
        profile_service: ProfileService,
        run_audit_service: RunAuditService,
    ):
        self.repository = repository
        self.runner = runner
        self.profile_service = profile_service
        self.run_audit_service = run_audit_service

    @staticmethod
    def _make_title(payload: RunCreateRequest) -> str:
        if payload.mode == "agent":
            query = (payload.agent.query if payload.agent else "").strip()
            return query[:80] or "自然语言研究任务"

        tickers = ", ".join((payload.structured.explicit_targets.tickers if payload.structured else [])[:3])
        return f"结构化筛选：{tickers}".strip("：") or "结构化筛选任务"

    def _apply_stored_memory(self, payload: RunCreateRequest, *, client_id: str, user: AuthUser | None) -> RunCreateRequest:
        """新建研究时自动带上账户或浏览器长期记忆。"""
        if payload.mode != "agent" or payload.agent is None or payload.agent.memory_context is not None:
            return payload
        preferences = self.profile_service.get_preferences(profile_id=client_id, user_id=user.id if user else None)
        values = preferences.values
        if not any(
            [
                values.capital_amount,
                values.currency,
                values.risk_tolerance,
                values.investment_horizon,
                values.investment_style,
                values.preferred_sectors,
                values.preferred_industries,
                values.explicit_tickers,
            ]
        ):
            return payload
        next_agent = payload.agent.model_copy(
            update={
                "memory_context": AgentMemoryContext(
                    capital_amount=values.capital_amount,
                    currency=values.currency,
                    risk_tolerance=values.risk_tolerance,
                    investment_horizon=values.investment_horizon,
                    investment_style=values.investment_style,
                    preferred_sectors=values.preferred_sectors,
                    preferred_industries=values.preferred_industries,
                    explicit_tickers=values.explicit_tickers,
                )
            }
        )
        return payload.model_copy(update={"agent": next_agent})

    async def create_run(
        self,
        payload: RunCreateRequest,
        *,
        parent_run_id: str | None = None,
        client_id: str = "default",
        user: AuthUser | None = None,
    ) -> dict[str, Any]:
        if payload.mode == "agent" and payload.agent is None:
            raise HTTPException(status_code=400, detail="agent 模式需要提供 agent 请求体。")
        if payload.mode == "structured" and payload.structured is None:
            raise HTTPException(status_code=400, detail="structured 模式需要提供 structured 请求体。")

        payload = self._apply_stored_memory(payload, client_id=client_id, user=user)
        run_id = uuid4().hex
        self.repository.create_run(
            run_id=run_id,
            mode=payload.mode,
            workflow_key=payload.mode,
            title=self._make_title(payload),
            parent_run_id=parent_run_id,
            metadata={"source": "api", "mode": payload.mode, "client_id": client_id, "user_id": user.id if user else None},
        )
        self.repository.replace_artifact(run_id, kind="input", name="request", content=payload.model_dump())
        self.repository.add_event(run_id, event_type="run.created", payload={"run_id": run_id, "mode": payload.mode})
        self.repository.add_audit_event(
            actor_user_id=user.id if user else None,
            actor_role=user.role if user else None,
            action="run.create",
            target_type="run",
            target_id=run_id,
            metadata={"mode": payload.mode, "client_id": client_id},
        )
        self.runner.schedule(run_id)
        return self.get_run_detail_or_404(run_id, user=user, client_id=client_id)

    def list_run_summaries(
        self,
        *,
        limit: int = 20,
        mode: str | None = None,
        status: str | None = None,
        search: str | None = None,
        user: AuthUser | None = None,
        client_id: str | None = None,
    ) -> dict[str, Any]:
        if user or client_id:
            return {
                "items": [
                    item.model_dump()
                    for item in self.repository.list_runs_for_actor(
                        limit=limit,
                        mode=mode,
                        status=status,
                        search=search,
                        user_id=user.id if user else None,
                        client_id=client_id,
                        is_admin=bool(user and user.role == "admin"),
                    )
                ]
            }
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

    def assert_run_visible(self, run_id: str, *, user: AuthUser | None = None, client_id: str | None = None) -> None:
        """检查当前访问者是否能读取该 run。"""
        run = self.get_run_or_404(run_id)
        if user and user.role == "admin":
            return
        metadata = run.metadata or {}
        owner_user_id = str(metadata.get("user_id") or "").strip()
        owner_client_id = str(metadata.get("client_id") or "").strip()
        if owner_user_id:
            if user and owner_user_id == user.id:
                return
            raise HTTPException(status_code=403, detail="你没有权限访问这个 run。")
        if owner_client_id and client_id and owner_client_id != client_id:
            raise HTTPException(status_code=403, detail="你没有权限访问这个 run。")

    def get_run_detail_or_404(self, run_id: str, *, user: AuthUser | None = None, client_id: str | None = None) -> dict[str, Any]:
        self.assert_run_visible(run_id, user=user, client_id=client_id)
        detail = self.repository.build_run_detail(run_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="未找到对应的 run。")
        return {
            "run": detail.run.model_dump(),
            "steps": [step.model_dump() for step in detail.steps],
            "artifacts": [artifact.model_dump(exclude={"content"}) for artifact in detail.artifacts],
            "result": detail.result,
        }

    def get_run_artifacts_or_404(self, run_id: str, *, user: AuthUser | None = None, client_id: str | None = None) -> dict[str, Any]:
        self.assert_run_visible(run_id, user=user, client_id=client_id)
        detail = self.repository.build_run_detail(run_id)
        return {
            "run_id": run_id,
            "artifacts": [artifact.model_dump() for artifact in detail.artifacts],
        }

    async def retry_run_or_404(self, run_id: str, *, user: AuthUser | None = None, client_id: str | None = None) -> dict[str, Any]:
        self.assert_run_visible(run_id, user=user, client_id=client_id)
        payload_data = self.repository.get_artifact_content(run_id, kind="input", name="request")
        if payload_data is None:
            raise HTTPException(status_code=404, detail="未找到该 run 的原始输入，无法重试。")
        payload = RunCreateRequest.model_validate(payload_data)
        original_run = self.get_run_or_404(run_id)
        client_id = str((original_run.metadata or {}).get("client_id") or "default")
        return await self.create_run(payload, parent_run_id=run_id, client_id=client_id, user=user)

    async def cancel_run_or_404(self, run_id: str, *, user: AuthUser | None = None, client_id: str | None = None) -> dict[str, Any]:
        self.assert_run_visible(run_id, user=user, client_id=client_id)
        run = self.get_run_or_404(run_id)
        if run.status in {"completed", "failed", "needs_clarification", "cancelled"}:
            raise HTTPException(status_code=400, detail="当前任务已结束，无法撤回。")
        cancelled = await self.runner.cancel(run_id)
        if not cancelled:
            raise HTTPException(status_code=409, detail="任务状态已变化，请刷新后重试。")
        self.repository.add_audit_event(
            actor_user_id=user.id if user else None,
            actor_role=user.role if user else None,
            action="run.cancel",
            target_type="run",
            target_id=run_id,
            metadata={"client_id": client_id},
        )
        return self.get_run_detail_or_404(run_id, user=user, client_id=client_id)

    def get_user_preferences(self, *, client_id: str = "default", user: AuthUser | None = None) -> dict[str, Any]:
        preferences = self.profile_service.get_preferences(profile_id=client_id, user_id=user.id if user else None)
        return preferences.model_dump()

    def update_user_preferences(self, payload: PreferenceUpdateRequest, *, client_id: str = "default", user: AuthUser | None = None) -> dict[str, Any]:
        result = self.profile_service.update_preferences(payload, profile_id=client_id, user_id=user.id if user else None).model_dump()
        self.repository.add_audit_event(
            actor_user_id=user.id if user else None,
            actor_role=user.role if user else None,
            action="profile.update",
            target_type="profile",
            target_id=result.get("profile_id"),
            metadata={"client_id": client_id},
        )
        return result

    def clear_user_preferences(self, *, client_id: str = "default", user: AuthUser | None = None) -> dict[str, Any]:
        result = self.profile_service.clear_preferences(profile_id=client_id, user_id=user.id if user else None).model_dump()
        self.repository.add_audit_event(
            actor_user_id=user.id if user else None,
            actor_role=user.role if user else None,
            action="profile.clear",
            target_type="profile",
            target_id=result.get("profile_id"),
            metadata={"client_id": client_id},
        )
        return result

    def link_client_memory(self, *, client_id: str, user: AuthUser) -> dict[str, Any]:
        result = self.profile_service.link_client_memory_to_user(client_id=client_id, user_id=user.id).model_dump()
        self.repository.add_audit_event(
            actor_user_id=user.id,
            actor_role=user.role,
            action="profile.link_client_memory",
            target_type="profile",
            target_id=result.get("profile_id"),
            metadata={"client_id": client_id},
        )
        return result

    def list_run_history(self, *, limit: int = 20, mode: str | None = None, status: str | None = None, search: str | None = None) -> dict[str, Any]:
        return self.list_run_summaries(limit=limit, mode=mode, status=status, search=search)

    def get_run_audit_summary_or_404(self, run_id: str) -> dict[str, Any]:
        detail = self.repository.build_run_detail(run_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="未找到对应的 run。")
        return self.run_audit_service.build_summary(detail).model_dump()
