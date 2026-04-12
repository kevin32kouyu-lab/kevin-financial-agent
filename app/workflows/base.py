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
    run_id: str
    mode: str
    repository: SqliteRunRepository
    stage_position: int = 0
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
        self.stage_position += 1
        self.stage_history.append(copy.deepcopy(stage))
        self.repository.upsert_step(
            self.run_id,
            stage,
            position=self.stage_position,
            input_data=input_data,
            output_data=output_data,
            error_data=error_data,
        )
        self.emit_event("step.completed", {"step": copy.deepcopy(stage), "position": self.stage_position})


class Workflow(Protocol):
    key: str

    async def execute(self, payload: Any, context: WorkflowContext) -> WorkflowResult:
        ...
