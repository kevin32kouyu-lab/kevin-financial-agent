"""可控多智能体协调器，负责串联固定角色 agent 并发布运行产物。"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from app.agent_runtime.controlled_agents import (
    DataAgent,
    EvidenceAgent,
    IntakeAgent,
    PlannerAgent,
    ReportAgent,
    ValidatorAgent,
)
from app.agent_runtime.memory import build_preference_snapshot
from app.domain.contracts import AgentRunRequest, utc_now_iso
from app.services.report_outputs import attach_dual_report_outputs


AsyncHook = Callable[..., Any] | None


@dataclass(slots=True)
class AgentRunHooks:
    """WorkflowRunner 注入的阶段、产物和快照回调。"""

    stage_callback: AsyncHook = None
    artifact_callback: AsyncHook = None
    snapshot_callback: AsyncHook = None


async def _maybe_call(callback: AsyncHook, *args: Any) -> None:
    """兼容同步和异步回调。"""
    if callback is None:
        return
    result = callback(*args)
    if asyncio.iscoroutine(result):
        await result


def _build_stage(key: str, label: str, elapsed_ms: float, status: str, summary: str) -> dict[str, Any]:
    """构造前端进度条可展示的阶段记录。"""
    return {
        "key": key,
        "label": label,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 2),
        "summary": summary,
    }


class AgentCoordinator:
    """串联 Intake、Planner、Data、Evidence、Report 和 Validator 六个角色 agent。"""

    def __init__(self, analysis_service: Any, report_service: Any):
        self.analysis_service = analysis_service
        self.report_service = report_service
        self.intake_agent = IntakeAgent()
        self.planner_agent = PlannerAgent()
        self.data_agent = DataAgent(analysis_service)
        self.evidence_agent = EvidenceAgent(report_service)
        self.report_agent = ReportAgent(report_service)
        self.validator_agent = ValidatorAgent(report_service)

    async def _publish_snapshot(self, hooks: AgentRunHooks | None, response: dict[str, Any]) -> None:
        """发布当前响应快照。"""
        if hooks is None:
            return
        await _maybe_call(hooks.snapshot_callback, copy.deepcopy(response))

    async def _publish_artifact(self, hooks: AgentRunHooks | None, kind: str, name: str, value: Any) -> None:
        """发布可被运行详情读取的 artifact。"""
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
        """追加阶段并同步快照。"""
        stage = _build_stage(key, label, elapsed_ms, status, summary)
        response["stages"].append(stage)
        if hooks is not None:
            await _maybe_call(hooks.stage_callback, copy.deepcopy(stage))
        await self._publish_snapshot(hooks, response)

    async def _append_trace(
        self,
        hooks: AgentRunHooks | None,
        response: dict[str, Any],
        trace: Any,
    ) -> None:
        """追加 agent 交接记录并发布完整 trace。"""
        response["agent_trace"].append(trace.to_dict())
        await self._publish_artifact(hooks, "derived", "agent_trace", response["agent_trace"])
        await self._publish_snapshot(hooks, response)

    @staticmethod
    def _finish_trace(
        trace: Any,
        *,
        started_at: str,
        started_perf: float,
        status: str = "completed",
        error_message: str | None = None,
    ) -> None:
        """补齐 agent trace 的时间、状态和错误字段。"""
        trace.status = status
        trace.started_at = started_at
        trace.finished_at = utc_now_iso()
        trace.elapsed_ms = (perf_counter() - started_perf) * 1000
        trace.error_message = error_message

    def get_runtime_config(self, *, model: str | None = None, base_url: str | None = None) -> dict[str, Any]:
        """读取模型运行配置的公开视图。"""
        return self.report_service.get_runtime_config(model=model, base_url=base_url)

    async def run(self, payload: AgentRunRequest, hooks: AgentRunHooks | None = None) -> dict[str, Any]:
        """执行完整的可控多智能体投研流程。"""
        runtime_view = self.get_runtime_config(model=payload.llm.model, base_url=payload.llm.base_url)
        response: dict[str, Any] = {
            "mode": "natural_language",
            "query": "",
            "status": "running",
            "runtime": runtime_view,
            "research_context": payload.research_context.model_dump(),
            "stages": [],
            "agent_trace": [],
            "llm_raw": {},
        }
        await self._publish_artifact(hooks, "runtime", "config", response["runtime"])
        await self._publish_artifact(hooks, "runtime", "research_context", response["research_context"])
        await self._publish_snapshot(hooks, response)

        intake_started_at = utc_now_iso()
        intake_started = perf_counter()
        intake = self.intake_agent.run(payload)
        self._finish_trace(intake.trace, started_at=intake_started_at, started_perf=intake_started)
        response["query"] = intake.normalized_query
        response["memory_applied_fields"] = intake.memory_applied_fields
        response["parsed_intent"] = intake.parsed_intent.model_dump()
        response["memory_resolution"] = {
            "reused_memory": bool(intake.memory_summary.get("used")),
            "applied_fields": intake.memory_applied_fields,
            "applied_labels": list(intake.memory_summary.get("applied_labels") or []),
            "note": intake.memory_summary.get("note"),
        }
        await self._publish_artifact(hooks, "derived", "parsed_intent", response["parsed_intent"])
        await self._publish_artifact(hooks, "derived", "memory_resolution", response["memory_resolution"])
        if payload.memory_context is not None:
            response["memory_context"] = payload.memory_context.model_dump()
            await self._publish_artifact(hooks, "derived", "memory_context", response["memory_context"])
        if intake.memory_summary["used"]:
            response["memory_summary"] = intake.memory_summary
            await self._publish_artifact(hooks, "derived", "memory_summary", response["memory_summary"])
            await self._publish_artifact(hooks, "derived", "memory_applied_fields", response["memory_applied_fields"])
        await self._append_trace(hooks, response, intake.trace)
        await self._append_stage(
            hooks,
            response,
            key="intent_analysis",
            label="意图解析",
            elapsed_ms=(perf_counter() - intake_started) * 1000,
            status="completed",
            summary=intake.trace.output_summary,
        )

        if intake.parsed_intent.agent_control.assumptions:
            response["assumptions"] = intake.parsed_intent.agent_control.assumptions
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

        if intake.follow_up_question:
            response["follow_up_question"] = intake.follow_up_question
            response["preference_snapshot"] = intake.preference_snapshot
            response["status"] = "needs_clarification"
            await self._publish_artifact(hooks, "derived", "follow_up_question", intake.follow_up_question)
            await self._publish_artifact(hooks, "derived", "preference_snapshot", response["preference_snapshot"])
            await self._append_stage(
                hooks,
                response,
                key="follow_up",
                label="补充追问",
                elapsed_ms=0.0,
                status="completed",
                summary="核心约束信息不足，等待用户补充后再继续。",
            )
            await self._publish_snapshot(hooks, response)
            return response

        planner_started_at = utc_now_iso()
        planner_started = perf_counter()
        planner = self.planner_agent.run(query=intake.normalized_query, intent=intake.parsed_intent, payload=payload)
        self._finish_trace(planner.trace, started_at=planner_started_at, started_perf=planner_started)
        response["research_plan"] = planner.plan
        await self._publish_artifact(hooks, "derived", "research_plan", response["research_plan"])
        await self._append_trace(hooks, response, planner.trace)
        await self._append_stage(
            hooks,
            response,
            key="research_plan",
            label="研究计划",
            elapsed_ms=(perf_counter() - planner_started) * 1000,
            status="completed",
            summary=planner.trace.output_summary,
        )

        data_started_at = utc_now_iso()
        data_started = perf_counter()
        data = await self.data_agent.run(intent=intake.parsed_intent, payload=payload)
        self._finish_trace(data.trace, started_at=data_started_at, started_perf=data_started)
        response["analysis"] = data.analysis
        await self._publish_artifact(hooks, "analysis", "structured_analysis", data.analysis)
        await self._append_trace(hooks, response, data.trace)
        await self._append_stage(
            hooks,
            response,
            key="structured_analysis",
            label="结构化分析",
            elapsed_ms=(perf_counter() - data_started) * 1000,
            status="completed",
            summary=data.trace.output_summary,
        )

        evidence_started_at = utc_now_iso()
        evidence_started = perf_counter()
        evidence = self.evidence_agent.run(
            query=intake.normalized_query,
            intent=intake.parsed_intent,
            analysis=data.analysis,
            payload=payload,
        )
        self._finish_trace(evidence.trace, started_at=evidence_started_at, started_perf=evidence_started)
        response["report_input"] = evidence.report_package["report_input"]
        response["report_briefing"] = evidence.report_package["report_briefing"]
        await self._publish_artifact(hooks, "report", "input", response["report_input"])
        await self._publish_artifact(hooks, "report", "briefing", response["report_briefing"])
        await self._publish_artifact(hooks, "report", "retrieved_evidence", evidence.evidence_payload.get("retrieved_evidence", []))
        await self._publish_artifact(hooks, "report", "citation_map", evidence.evidence_payload.get("citation_map", {}))
        await self._append_trace(hooks, response, evidence.trace)
        await self._append_stage(
            hooks,
            response,
            key="evidence_retrieval",
            label="证据检索",
            elapsed_ms=(perf_counter() - evidence_started) * 1000,
            status="completed",
            summary=evidence.trace.output_summary,
        )

        report_started_at = utc_now_iso()
        report_started = perf_counter()
        report = await self.report_agent.run(
            query=intake.normalized_query,
            intent=intake.parsed_intent,
            report_package=evidence.report_package,
            payload=payload,
        )
        self._finish_trace(report.trace, started_at=report_started_at, started_perf=report_started)
        response["report_input"] = report.bundle["report_input"]
        response["report_briefing"] = report.bundle["report_briefing"]
        response["final_report"] = report.bundle["final_report"]
        response["report_mode"] = report.bundle["report_mode"]
        response["report_error"] = report.bundle["report_error"]
        response["llm_raw"] = report.bundle["llm_raw"]
        await self._publish_artifact(hooks, "report", "input", response["report_input"])
        await self._publish_artifact(hooks, "report", "briefing", response["report_briefing"])
        await self._publish_artifact(hooks, "report", "final_report", response["final_report"])
        if response["report_error"]:
            await self._publish_artifact(hooks, "report", "error", response["report_error"])
        if response["llm_raw"].get("report_response"):
            await self._publish_artifact(hooks, "llm", "report_response", response["llm_raw"]["report_response"])
        await self._append_trace(hooks, response, report.trace)
        await self._append_stage(
            hooks,
            response,
            key="final_report",
            label="最终报告",
            elapsed_ms=(perf_counter() - report_started) * 1000,
            status="fallback" if response["report_mode"] == "fallback" else "completed",
            summary=report.trace.output_summary,
        )

        validation_started_at = utc_now_iso()
        validation_started = perf_counter()
        validation = self.validator_agent.run(bundle=report.bundle, language_code=intake.parsed_intent.system_context.language)
        self._finish_trace(validation.trace, started_at=validation_started_at, started_perf=validation_started)
        response["report_briefing"] = validation.bundle["report_briefing"]
        await self._append_trace(hooks, response, validation.trace)
        report_outputs = attach_dual_report_outputs(
            bundle=validation.bundle,
            query=intake.normalized_query,
            language_code=intake.parsed_intent.system_context.language,
            agent_trace=response["agent_trace"],
            research_plan=response.get("research_plan"),
            backtest=None,
        )
        response["report_outputs"] = report_outputs
        response["final_report"] = validation.bundle["final_report"]
        response["preference_snapshot"] = build_preference_snapshot(
            intake.parsed_intent,
            query=intake.normalized_query,
            research_mode=payload.research_context.research_mode,
            applied_fields=response["memory_applied_fields"],
        )
        await self._publish_artifact(hooks, "report", "briefing", response["report_briefing"])
        await self._publish_artifact(hooks, "report", "outputs", response["report_outputs"])
        await self._publish_artifact(hooks, "report", "final_report", response["final_report"])
        await self._publish_artifact(hooks, "derived", "validation_checks", validation.validation_meta.get("validation_checks", []))
        await self._publish_artifact(hooks, "derived", "preference_snapshot", response["preference_snapshot"])
        await self._append_stage(
            hooks,
            response,
            key="validation",
            label="结论校验",
            elapsed_ms=(perf_counter() - validation_started) * 1000,
            status="completed",
            summary=validation.trace.output_summary,
        )

        response["status"] = "completed"
        await self._publish_snapshot(hooks, response)
        return response


AgentService = AgentCoordinator
