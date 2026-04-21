from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse

from app.core.auth import get_api_key, get_client_id
from app.core.runtime import get_runtime
from app.domain.contracts import AgentResumeRequest, RunCreateRequest


router = APIRouter(prefix="/api/runs", tags=["runs"], dependencies=[Depends(get_api_key)])

TERMINAL_STATUSES = {"completed", "failed", "needs_clarification", "cancelled"}


def _format_sse(event_id: int, event_type: str, payload: dict) -> str:
    return (
        f"id: {event_id}\n"
        f"event: {event_type}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


@router.get("")
async def list_runs(
    request: Request,
    limit: int = 20,
    mode: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> dict:
    runtime = get_runtime(request.app)
    return runtime.run_service.list_run_summaries(limit=limit, mode=mode, status=status, search=search)


@router.post("")
async def create_run(request: Request, payload: RunCreateRequest) -> dict:
    runtime = get_runtime(request.app)
    client_id = get_client_id(request)
    return await runtime.run_service.create_run(payload, client_id=client_id)


@router.delete("")
async def delete_runs(
    request: Request,
    mode: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> dict:
    runtime = get_runtime(request.app)
    return runtime.run_service.clear_run_history(mode=mode, status=status, search=search)


@router.get("/{run_id}")
async def get_run_detail(request: Request, run_id: str) -> dict:
    runtime = get_runtime(request.app)
    return runtime.run_service.get_run_detail_or_404(run_id)


@router.get("/{run_id}/artifacts")
async def get_run_artifacts(request: Request, run_id: str) -> dict:
    runtime = get_runtime(request.app)
    return runtime.run_service.get_run_artifacts_or_404(run_id)


@router.post("/{run_id}/retry")
async def retry_run(request: Request, run_id: str) -> dict:
    runtime = get_runtime(request.app)
    return await runtime.run_service.retry_run_or_404(run_id)


@router.post("/{run_id}/resume-from-agent")
async def resume_run_from_agent(request: Request, run_id: str, payload: AgentResumeRequest) -> dict:
    runtime = get_runtime(request.app)
    client_id = get_client_id(request)
    return await runtime.run_service.resume_from_agent_or_404(run_id, payload, client_id=client_id)


@router.post("/{run_id}/cancel")
async def cancel_run(request: Request, run_id: str) -> dict:
    runtime = get_runtime(request.app)
    return await runtime.run_service.cancel_run_or_404(run_id)


@router.get("/{run_id}/events")
async def stream_run_events(request: Request, run_id: str) -> StreamingResponse:
    runtime = get_runtime(request.app)
    run = runtime.run_service.get_run_or_404(run_id)

    header_value = request.headers.get("last-event-id")
    last_event_id = int(header_value) if header_value and header_value.isdigit() else 0

    async def event_generator():
        nonlocal last_event_id
        while True:
            if await request.is_disconnected():
                break

            events = runtime.repository.list_events(run_id, after_id=last_event_id)
            if events:
                for event in events:
                    last_event_id = event.id
                    yield _format_sse(event.id, event.event_type, event.payload)
                continue

            current_run = runtime.repository.get_run(run_id)
            if current_run is None:
                break
            if current_run.status in TERMINAL_STATUSES:
                break

            yield ": keepalive\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
