from __future__ import annotations

import asyncio
import copy
from typing import Any, Callable
from uuid import uuid4

from fastapi import HTTPException

from app.agent_runtime import AgentRunHooks, AgentRunRequest, run_financial_agent
from app.analysis_runtime import DebugAnalysisRequest, run_analysis_pipeline

from .models import RunCreateRequest
from .store import (
    add_event,
    build_run_detail,
    create_run,
    delete_runs,
    get_artifact_content,
    get_run,
    init_db,
    list_runs,
    replace_artifact,
    update_run_status,
    upsert_step,
)

AsyncHook = Callable[..., Any] | None


async def _maybe_call(callback: AsyncHook, *args: Any) -> None:
    if callback is None:
        return
    result = callback(*args)
    if asyncio.iscoroutine(result):
        await result


def init_run_runtime() -> None:
    init_db()


def _make_title(payload: RunCreateRequest) -> str:
    if payload.mode == "agent":
        query = (payload.agent.query if payload.agent else "").strip()
        return query[:80] or "自然语言 Agent 运行"

    tickers = ", ".join((payload.structured.explicit_targets.tickers if payload.structured else [])[:3])
    return f"结构化调试 {tickers}".strip() or "结构化分析运行"


def _serialize_create_payload(payload: RunCreateRequest) -> dict[str, Any]:
    return payload.model_dump()


async def _store_snapshot(run_id: str, response: dict[str, Any]) -> None:
    replace_artifact(run_id, kind="snapshot", name="current", content=copy.deepcopy(response))


async def _store_agent_artifact(run_id: str, kind: str, name: str, value: Any) -> None:
    replace_artifact(run_id, kind=kind, name=name, content=value)
    add_event(run_id, event_type="artifact.updated", payload={"kind": kind, "name": name})


async def _store_agent_stage(run_id: str, stage: dict[str, Any], position: int) -> None:
    upsert_step(run_id, stage, position=position)
    add_event(run_id, event_type="step.completed", payload={"step": stage, "position": position})


async def _execute_agent_run(run_id: str, payload: AgentRunRequest) -> None:
    update_run_status(run_id, status="running")
    add_event(run_id, event_type="run.started", payload={"mode": "agent"})

    stage_position = 0

    async def on_stage(stage: dict[str, Any]) -> None:
        nonlocal stage_position
        stage_position += 1
        await _store_agent_stage(run_id, stage, stage_position)

    async def on_artifact(kind: str, name: str, value: Any) -> None:
        await _store_agent_artifact(run_id, kind, name, value)

    async def on_snapshot(response: dict[str, Any]) -> None:
        await _store_snapshot(run_id, response)

    hooks = AgentRunHooks(
        stage_callback=on_stage,
        artifact_callback=on_artifact,
        snapshot_callback=on_snapshot,
    )

    try:
        response = await run_financial_agent(payload, hooks=hooks)
        replace_artifact(run_id, kind="output", name="final_response", content=response)
        update_run_status(
            run_id,
            status=response.get("status", "completed"),
            error_message=response.get("report_error"),
            report_mode=response.get("report_mode"),
        )
        add_event(
            run_id,
            event_type=f"run.{response.get('status', 'completed')}",
            payload={
                "status": response.get("status", "completed"),
                "report_mode": response.get("report_mode"),
            },
        )
    except Exception as exc:
        update_run_status(run_id, status="failed", error_message=str(exc))
        replace_artifact(run_id, kind="output", name="error", content={"message": str(exc)})
        add_event(run_id, event_type="run.failed", payload={"message": str(exc)})


async def _execute_structured_run(run_id: str, payload: DebugAnalysisRequest) -> None:
    update_run_status(run_id, status="running")
    add_event(run_id, event_type="run.started", payload={"mode": "structured"})

    try:
        result = await run_analysis_pipeline(payload)
        for position, stage in enumerate(result.get("debug_stages", []), start=1):
            upsert_step(run_id, stage, position=position)
            add_event(run_id, event_type="step.completed", payload={"step": stage, "position": position})

        snapshot = {"mode": "structured", "status": "completed", **result}
        replace_artifact(run_id, kind="snapshot", name="current", content=snapshot)
        replace_artifact(run_id, kind="output", name="final_response", content=snapshot)
        update_run_status(run_id, status="completed")
        add_event(
            run_id,
            event_type="run.completed",
            payload={
                "status": "completed",
                "selected_ticker_count": result.get("debug_summary", {}).get("selected_ticker_count", 0),
            },
        )
    except Exception as exc:
        update_run_status(run_id, status="failed", error_message=str(exc))
        replace_artifact(run_id, kind="output", name="error", content={"message": str(exc)})
        add_event(run_id, event_type="run.failed", payload={"message": str(exc)})


async def create_and_start_run(payload: RunCreateRequest) -> dict[str, Any]:
    init_db()

    if payload.mode == "agent" and payload.agent is None:
        raise HTTPException(status_code=400, detail="agent 模式需要提供 agent 请求体。")
    if payload.mode == "structured" and payload.structured is None:
        raise HTTPException(status_code=400, detail="structured 模式需要提供 structured 请求体。")

    run_id = uuid4().hex
    create_run(run_id=run_id, mode=payload.mode, title=_make_title(payload))
    replace_artifact(run_id, kind="input", name="request", content=_serialize_create_payload(payload))
    add_event(run_id, event_type="run.created", payload={"run_id": run_id, "mode": payload.mode})

    if payload.mode == "agent":
        asyncio.create_task(_execute_agent_run(run_id, payload.agent))
    else:
        asyncio.create_task(_execute_structured_run(run_id, payload.structured))

    detail = build_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=500, detail="创建运行记录后读取失败。")
    return {
        "run": detail.run.model_dump(),
        "steps": [step.model_dump() for step in detail.steps],
        "artifacts": [artifact.model_dump(exclude={"content"}) for artifact in detail.artifacts],
        "result": detail.result,
    }


def get_run_detail_or_404(run_id: str) -> dict[str, Any]:
    detail = build_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="未找到对应的 run。")
    return {
        "run": detail.run.model_dump(),
        "steps": [step.model_dump() for step in detail.steps],
        "artifacts": [artifact.model_dump(exclude={"content"}) for artifact in detail.artifacts],
        "result": detail.result,
    }


def get_run_artifacts_or_404(run_id: str) -> dict[str, Any]:
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="未找到对应的 run。")
    detail = build_run_detail(run_id)
    return {
        "run_id": run_id,
        "artifacts": [artifact.model_dump() for artifact in detail.artifacts],
    }


async def retry_run_or_404(run_id: str) -> dict[str, Any]:
    payload_data = get_artifact_content(run_id, kind="input", name="request")
    if payload_data is None:
        raise HTTPException(status_code=404, detail="未找到该 run 的原始输入，无法重试。")
    payload = RunCreateRequest.model_validate(payload_data)
    return await create_and_start_run(payload)


def list_run_summaries(
    limit: int = 20,
    *,
    mode: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    return {
        "items": [
            item.model_dump()
            for item in list_runs(limit=limit, mode=mode, status=status, search=search)
        ],
    }


def clear_run_history(
    *,
    mode: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    deleted_count = delete_runs(mode=mode, status=status, search=search, include_active=False)
    return {
        "deleted_count": deleted_count,
    }
