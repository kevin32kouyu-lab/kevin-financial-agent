"""运行审计摘要服务。

这个文件负责把一条 run 的结果整理成用户可读的审计摘要，
方便前台历史页快速说明：用了哪些数据、哪里降级了、最终为什么这样判断。
"""

from __future__ import annotations

from typing import Any

from app.domain.contracts import RunAuditSummary, RunDetail


def _as_record(value: Any) -> dict[str, Any]:
    """把未知值安全转成对象。"""
    return value if isinstance(value, dict) else {}


def _as_string_list(value: Any) -> list[str]:
    """把未知值安全转成字符串列表。"""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


class RunAuditService:
    """把完整 run 结果压缩成前台可读摘要。"""

    def build_summary(self, detail: RunDetail) -> RunAuditSummary:
        """生成一条 run 的审计摘要。"""
        result = _as_record(detail.result)
        report_briefing = _as_record(result.get("report_briefing"))
        meta = _as_record(report_briefing.get("meta"))
        executive = _as_record(report_briefing.get("executive"))
        validation_summary = _as_record(meta.get("validation_summary"))
        safety_summary = _as_record(meta.get("safety_summary"))
        research_context = _as_record(result.get("research_context"))

        return RunAuditSummary(
            run_id=detail.run.id,
            title=detail.run.title,
            status=detail.run.status,
            query=str(result.get("query") or "").strip() or None,
            report_mode=str(result.get("report_mode") or detail.run.report_mode or "").strip() or None,
            research_mode=str(meta.get("research_mode") or research_context.get("research_mode") or "").strip() or None,
            as_of_date=str(meta.get("as_of_date") or research_context.get("as_of_date") or "").strip() or None,
            top_pick=str(executive.get("top_pick") or "").strip() or None,
            confidence_level=str(meta.get("confidence_level") or validation_summary.get("level") or "").strip() or None,
            validation_flags=_as_string_list(meta.get("validation_flags") or validation_summary.get("items")),
            coverage_flags=_as_string_list(meta.get("coverage_flags")),
            used_sources=_as_string_list(safety_summary.get("used_sources")),
            degraded_modules=_as_string_list(safety_summary.get("degraded_modules")),
            memory_applied_fields=_as_string_list(result.get("memory_applied_fields")),
            follow_up_question=str(result.get("follow_up_question") or "").strip() or None,
        )
