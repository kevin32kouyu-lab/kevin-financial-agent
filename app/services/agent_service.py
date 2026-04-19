from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from app.agent_runtime.memory import build_preference_snapshot, merge_memory_context
from app.agent_runtime.intent import _build_follow_up_question, _normalize_query, parse_intent
from app.domain.contracts import AgentRunRequest, DebugAnalysisRequest, ParsedIntent
from app.services.analysis_service import AnalysisService
from app.services.report_service import ReportService


AsyncHook = Callable[..., Any] | None


@dataclass(slots=True)
class AgentRunHooks:
    stage_callback: AsyncHook = None
    artifact_callback: AsyncHook = None
    snapshot_callback: AsyncHook = None


async def _maybe_call(callback: AsyncHook, *args: Any) -> None:
    if callback is None:
        return
    result = callback(*args)
    if asyncio.iscoroutine(result):
        await result


def _build_stage(key: str, label: str, elapsed_ms: float, status: str, summary: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 2),
        "summary": summary,
    }


def _build_debug_request(intent: ParsedIntent, payload: AgentRunRequest) -> DebugAnalysisRequest:
    return DebugAnalysisRequest(
        risk_profile=intent.risk_profile,
        investment_strategy=intent.investment_strategy,
        fundamental_filters=intent.fundamental_filters,
        explicit_targets=intent.explicit_targets,
        portfolio_sizing=intent.portfolio_sizing.model_dump(),
        options=payload.options,
        research_mode=payload.research_context.research_mode,
        as_of_date=payload.research_context.as_of_date,
    )


class AgentService:
    def __init__(self, analysis_service: AnalysisService, report_service: ReportService):
        self.analysis_service = analysis_service
        self.report_service = report_service

    async def _publish_snapshot(self, hooks: AgentRunHooks | None, response: dict[str, Any]) -> None:
        if hooks is None:
            return
        await _maybe_call(hooks.snapshot_callback, copy.deepcopy(response))

    async def _publish_artifact(self, hooks: AgentRunHooks | None, kind: str, name: str, value: Any) -> None:
        if hooks is None:
            return
        await _maybe_call(hooks.artifact_callback, kind, name, copy.deepcopy(value))

    async def _append_stage(
        self,
        hooks: AgentRunHooks | None,
        response: dict[str, Any],
        *,
        key: str,
        label: str,
        elapsed_ms: float,
        status: str,
        summary: str,
    ) -> None:
        stage = _build_stage(key, label, elapsed_ms, status, summary)
        response["stages"].append(stage)
        if hooks is not None:
            await _maybe_call(hooks.stage_callback, copy.deepcopy(stage))
        await self._publish_snapshot(hooks, response)

    def get_runtime_config(self, *, model: str | None = None, base_url: str | None = None) -> dict[str, Any]:
        return self.report_service.get_runtime_config(model=model, base_url=base_url)

    async def run(self, payload: AgentRunRequest, hooks: AgentRunHooks | None = None) -> dict[str, Any]:
        normalized_query = _normalize_query(payload.query)
        runtime_view = self.get_runtime_config(model=payload.llm.model, base_url=payload.llm.base_url)

        response: dict[str, Any] = {
            "mode": "natural_language",
            "query": normalized_query,
            "status": "running",
            "runtime": runtime_view,
            "research_context": payload.research_context.model_dump(),
            "stages": [],
            "llm_raw": {},
        }
        await self._publish_artifact(hooks, "runtime", "config", response["runtime"])
        await self._publish_artifact(hooks, "runtime", "research_context", response["research_context"])
        await self._publish_snapshot(hooks, response)

        intent_started = perf_counter()
        parsed_intent = parse_intent(normalized_query)
        memory_summary = merge_memory_context(
            parsed_intent,
            query=normalized_query,
            memory_context=payload.memory_context,
        )
        response["memory_applied_fields"] = list(memory_summary["applied_fields"])
        response["parsed_intent"] = parsed_intent.model_dump()
        await self._publish_artifact(hooks, "derived", "parsed_intent", response["parsed_intent"])
        if payload.memory_context is not None:
            response["memory_context"] = payload.memory_context.model_dump()
            await self._publish_artifact(hooks, "derived", "memory_context", response["memory_context"])
        if memory_summary["used"]:
            response["memory_summary"] = memory_summary
            await self._publish_artifact(hooks, "derived", "memory_summary", response["memory_summary"])
            await self._publish_artifact(hooks, "derived", "memory_applied_fields", response["memory_applied_fields"])
        await self._append_stage(
            hooks,
            response,
            key="intent_analysis",
            label="意图解析",
            elapsed_ms=(perf_counter() - intent_started) * 1000,
            status="completed",
            summary=(
                "已完成用户需求解析，并结合最近一次偏好补齐缺失约束。"
                if memory_summary["used"]
                else "已完成用户需求解析，并提取策略约束条件。"
            ),
        )

        if parsed_intent.agent_control.assumptions:
            response["assumptions"] = parsed_intent.agent_control.assumptions
            await self._publish_artifact(hooks, "derived", "assumptions", response["assumptions"])
            await self._append_stage(
                hooks,
                response,
                key="assumption_fill",
                label="默认假设补全",
                elapsed_ms=0.0,
                status="completed",
                summary="输入信息不完全时，已用可解释默认假设补齐。",
            )

        if not parsed_intent.agent_control.is_intent_clear and not parsed_intent.agent_control.is_intent_usable:
            follow_up_started = perf_counter()
            follow_up_question = _build_follow_up_question(parsed_intent)
            response["follow_up_question"] = follow_up_question
            response["preference_snapshot"] = build_preference_snapshot(
                parsed_intent,
                query=normalized_query,
                research_mode=payload.research_context.research_mode,
                applied_fields=response["memory_applied_fields"],
            )
            response["status"] = "needs_clarification"
            await self._publish_artifact(hooks, "derived", "follow_up_question", follow_up_question)
            await self._publish_artifact(hooks, "derived", "preference_snapshot", response["preference_snapshot"])
            await self._append_stage(
                hooks,
                response,
                key="follow_up",
                label="补充追问",
                elapsed_ms=(perf_counter() - follow_up_started) * 1000,
                status="completed",
                summary="核心约束信息不足，等待用户补充后再继续。",
            )
            return response

        analysis_started = perf_counter()
        analysis = await self.analysis_service.run_structured_analysis(_build_debug_request(parsed_intent, payload))
        response["analysis"] = analysis
        await self._publish_artifact(hooks, "analysis", "structured_analysis", analysis)
        await self._append_stage(
            hooks,
            response,
            key="structured_analysis",
            label="结构化分析",
            elapsed_ms=(perf_counter() - analysis_started) * 1000,
            status="completed",
            summary=f"已完成筛选与多源聚合，共 {analysis.get('debug_summary', {}).get('selected_ticker_count', 0)} 只股票。",
        )

        report_started = perf_counter()
        report_bundle = await self.report_service.generate_report(
            query=normalized_query,
            intent=parsed_intent,
            analysis=analysis,
            model=payload.llm.model,
            base_url=payload.llm.base_url,
        )
        response["report_input"] = report_bundle["report_input"]
        response["report_briefing"] = report_bundle["report_briefing"]
        response["final_report"] = report_bundle["final_report"]
        response["report_mode"] = report_bundle["report_mode"]
        response["report_error"] = report_bundle["report_error"]
        response["llm_raw"] = report_bundle["llm_raw"]
        response["preference_snapshot"] = build_preference_snapshot(
            parsed_intent,
            query=normalized_query,
            research_mode=payload.research_context.research_mode,
            applied_fields=response["memory_applied_fields"],
        )

        await self._publish_artifact(hooks, "report", "input", response["report_input"])
        await self._publish_artifact(hooks, "report", "briefing", response["report_briefing"])
        await self._publish_artifact(hooks, "report", "final_report", response["final_report"])
        if response["report_error"]:
            await self._publish_artifact(hooks, "report", "error", response["report_error"])
        if response["llm_raw"].get("report_response"):
            await self._publish_artifact(hooks, "llm", "report_response", response["llm_raw"]["report_response"])
        await self._publish_artifact(hooks, "derived", "preference_snapshot", response["preference_snapshot"])

        await self._append_stage(
            hooks,
            response,
            key="final_report",
            label="最终报告",
            elapsed_ms=(perf_counter() - report_started) * 1000,
            status="fallback" if response["report_mode"] == "fallback" else "completed",
            summary=(
                "报告已由模型生成。"
                if response["report_mode"] == "llm"
                else "模型不可用，已回落到结构化备选报告。"
            ),
        )

        response["status"] = "completed"
        await self._publish_snapshot(hooks, response)
        return response
