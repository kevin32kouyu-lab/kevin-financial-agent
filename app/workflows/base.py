from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.repositories.sqlite_run_repository import SqliteRunRepository


@dataclass(slots=True)
class WorkflowResult:
    status: str
    response: dict[str, Any]
    report_mode: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class WorkflowContext:
    """保存单次 workflow 的落库上下文，并把阶段变化推送给前端。"""

    run_id: str
    mode: str
    repository: SqliteRunRepository
    stage_position: int = 0
    stage_positions: dict[str, int] = field(default_factory=dict)
    stage_history: list[dict[str, Any]] = field(default_factory=list)

    def emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self.repository.add_event(self.run_id, event_type=event_type, payload=payload)

    def store_artifact(self, kind: str, name: str, value: Any) -> None:
        self.repository.replace_artifact(self.run_id, kind=kind, name=name, content=copy.deepcopy(value))
        self.emit_event("artifact.updated", {"kind": kind, "name": name})

    def store_snapshot(self, value: dict[str, Any]) -> None:
        self.repository.replace_artifact(self.run_id, kind="snapshot", name="current", content=copy.deepcopy(value))

    def add_stage(
        self,
        stage: dict[str, Any],
        *,
        input_data: Any = None,
        output_data: Any = None,
        error_data: Any = None,
    ) -> None:
        """新增或更新一个阶段，running 和 completed 使用同一个位置。"""
        stage_key = str(stage.get("key") or stage.get("step_key") or "").strip()
        if stage_key and stage_key in self.stage_positions:
            position = self.stage_positions[stage_key]
        else:
            self.stage_position += 1
            position = self.stage_position
            if stage_key:
                self.stage_positions[stage_key] = position
        self.stage_history.append(copy.deepcopy(stage))
        self.repository.upsert_step(
            self.run_id,
            stage,
            position=position,
            input_data=input_data,
            output_data=output_data,
            error_data=error_data,
        )
        status = str(stage.get("status") or "").strip()
        event_type = "step.started" if status == "running" else "step.completed"
        self.emit_event(event_type, {"step": copy.deepcopy(stage), "position": position})


class Workflow(Protocol):
    key: str

    async def execute(self, payload: Any, context: WorkflowContext) -> WorkflowResult:
        ...
