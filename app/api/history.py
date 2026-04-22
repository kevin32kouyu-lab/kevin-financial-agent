from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.auth import get_api_key, get_client_id, get_current_user
from app.core.runtime import get_runtime
from app.services.pdf_export_service import PdfExportUnavailable


router = APIRouter(prefix="/api/v1/runs", tags=["run-history"], dependencies=[Depends(get_api_key)])


@router.get("/history")
async def list_run_history(
    request: Request,
    limit: int = 20,
    mode: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> dict:
    runtime = get_runtime(request.app)
    return runtime.run_service.list_run_summaries(
        limit=limit,
        mode=mode,
        status=status,
        search=search,
        user=get_current_user(request),
        client_id=get_client_id(request),
    )


@router.get("/{run_id}/audit-summary")
async def get_run_audit_summary(request: Request, run_id: str) -> dict:
    runtime = get_runtime(request.app)
    runtime.run_service.assert_run_visible(run_id, user=get_current_user(request), client_id=get_client_id(request))
    return runtime.run_service.get_run_audit_summary_or_404(run_id)


@router.get("/{run_id}/export/pdf")
@router.get("/{run_id}/export.pdf")
async def export_run_pdf(request: Request, run_id: str) -> Response:
    """把指定 run 的完整报告导出为后端生成的真实 PDF。"""
    runtime = get_runtime(request.app)
    user = get_current_user(request)
    client_id = get_client_id(request)
    detail = runtime.run_service.get_run_detail_or_404(run_id, user=user, client_id=client_id)
    result = detail.get("result")
    if not isinstance(result, dict):
        raise HTTPException(status_code=404, detail="这个 run 还没有可导出的报告。")

    latest_backtest = None
    backtest_summaries = runtime.repository.list_backtests(source_run_id=run_id, limit=1)
    if backtest_summaries:
        latest_backtest = runtime.repository.get_backtest(backtest_summaries[0].id)

    try:
        exported = await runtime.pdf_export_service.export_report_pdf(
            run_id=run_id,
            result=result,
            backtest=latest_backtest,
        )
    except PdfExportUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    runtime.repository.add_audit_event(
        actor_user_id=user.id if user else None,
        actor_role=user.role if user else None,
        action="run.export_pdf",
        target_type="run",
        target_id=run_id,
        metadata={"client_id": client_id},
    )
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{exported.filename}"',
            "Cache-Control": "no-store",
        },
    )
