"""可控多智能体协调器，负责串联固定角色 agent 并发布运行产物。"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from app.agent_runtime.controlled_agents import (
    AgentTraceEntry,
    ArbiterAgent,
    BearAnalystAgent,
    BullAnalystAgent,
    DataAgent,
    EvidenceAgent,
    IntakeAgent,
    PlannerAgent,
    ReportAgent,
    ValidatorAgent,
    build_debug_request,
)
from app.agent_runtime.memory import build_preference_snapshot
from app.agent_runtime.tool_registry import ToolRegistry, ToolRunner, ToolSpec
from app.domain.contracts import AgentRunRequest, ParsedIntent, utc_now_iso
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
    """串联受限自治多智能体，并发布工具审计、辩论和 checkpoint。"""

    AGENT_ORDER = [
        "IntakeAgent",
        "PlannerAgent",
        "DataAgent",
        "EvidenceAgent",
        "BullAnalystAgent",
        "BearAnalystAgent",
        "ArbiterAgent",
        "ReportAgent",
        "ValidatorAgent",
    ]
    RERUNNABLE_AGENTS = {
        "DataAgent",
        "EvidenceAgent",
        "BullAnalystAgent",
        "BearAnalystAgent",
        "ArbiterAgent",
        "ReportAgent",
        "ValidatorAgent",
    }

    def __init__(self, analysis_service: Any, report_service: Any):
        self.analysis_service = analysis_service
        self.report_service = report_service
        self.intake_agent = IntakeAgent()
        self.planner_agent = PlannerAgent()
        self.data_agent = DataAgent(analysis_service)
        self.evidence_agent = EvidenceAgent(report_service)
        self.bull_agent = BullAnalystAgent()
        self.bear_agent = BearAnalystAgent()
        self.arbiter_agent = ArbiterAgent()
        self.report_agent = ReportAgent(report_service)
        self.validator_agent = ValidatorAgent(report_service)

    def _build_tool_runner(self) -> ToolRunner:
        """把内部服务包装成 Planner 可授权的注册工具。"""
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="market.research_package",
                description="执行结构化筛选、行情、新闻、SEC、宏观和评分聚合。",
                permission_scope="market_data",
                timeout_seconds=60.0,
                max_retries=1,
                runner=lambda args: self.analysis_service.run_structured_analysis(
                    build_debug_request(args["intent"], args["payload"])
                ),
            )
        )
        registry.register(
            ToolSpec(
                name="report.build_package",
                description="把结构化分析转换成报告输入和报告摘要。",
                permission_scope="reporting",
                timeout_seconds=20.0,
                max_retries=0,
                runner=lambda args: self.report_service.build_report_package(**args),
            )
        )
        registry.register(
            ToolSpec(
                name="rag.attach_evidence",
                description="检索本地知识库证据并生成引用映射。",
                permission_scope="rag",
                timeout_seconds=20.0,
                max_retries=1,
                runner=lambda args: self.report_service.attach_evidence(**args),
            )
        )
        registry.register(
            ToolSpec(
                name="report.render",
                description="根据证据包生成用户可读正式报告。",
                permission_scope="reporting",
                timeout_seconds=90.0,
                max_retries=1,
                runner=lambda args: self.report_service.render_report(**args),
            )
        )
        registry.register(
            ToolSpec(
                name="report.validate",
                description="校验报告、评分、风险、证据和时间范围是否一致。",
                permission_scope="validation",
                timeout_seconds=20.0,
                max_retries=0,
                runner=lambda args: self.report_service.validate_report_bundle(
                    args["bundle"],
                    language_code=args["language_code"],
                ),
            )
        )
        return ToolRunner(registry)

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
        *,
        dependency_artifacts: list[str] | None = None,
    ) -> None:
        """追加 agent 交接记录并发布完整 trace。"""
        self._attach_checkpoint(response, trace, dependency_artifacts=dependency_artifacts or [])
        response["agent_trace"].append(trace.to_dict())
        await self._publish_artifact(hooks, "derived", "agent_trace", response["agent_trace"])
        await self._publish_artifact(hooks, "derived", "agent_checkpoints", response["agent_checkpoints"])
        await self._publish_snapshot(hooks, response)

    def _attach_checkpoint(self, response: dict[str, Any], trace: Any, *, dependency_artifacts: list[str]) -> None:
        """给 trace 写入 checkpoint，并保存可恢复的交接点。"""
        checkpoints = response.setdefault("agent_checkpoints", [])
        checkpoint_id = trace.checkpoint_id or f"ckpt-{len(checkpoints) + 1:02d}-{trace.agent_name}"
        trace.checkpoint_id = checkpoint_id
        trace.rerunnable = trace.agent_name in self.RERUNNABLE_AGENTS
        trace.dependency_artifacts = list(dependency_artifacts)
        checkpoints.append(
            {
                "checkpoint_id": checkpoint_id,
                "agent_name": trace.agent_name,
                "status": trace.status,
                "created_at": trace.finished_at or utc_now_iso(),
                "artifact_keys": list(trace.artifact_keys),
                "dependency_artifacts": list(dependency_artifacts),
                "rerunnable": trace.rerunnable,
                "resume_scope": self._downstream_agents(trace.agent_name) if trace.rerunnable else [],
                "summary": trace.output_summary,
                "error_message": trace.error_message,
            }
        )

    def _downstream_agents(self, agent_name: str) -> list[str]:
        """返回从某个 agent 开始需要重跑的后续链路。"""
        if agent_name not in self.AGENT_ORDER:
            return []
        return self.AGENT_ORDER[self.AGENT_ORDER.index(agent_name) :]

    async def _publish_tool_invocations(
        self,
        hooks: AgentRunHooks | None,
        response: dict[str, Any],
        tool_runner: ToolRunner,
    ) -> None:
        """同步工具调用审计 artifact。"""
        response["tool_invocations"] = [item.to_dict() for item in tool_runner.invocations]
        await self._publish_artifact(hooks, "derived", "tool_invocations", response["tool_invocations"])

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

    async def _append_failed_trace(
        self,
        hooks: AgentRunHooks | None,
        response: dict[str, Any],
        *,
        agent_name: str,
        started_at: str,
        started_perf: float,
        dependency_artifacts: list[str],
        error: Exception,
    ) -> None:
        """agent 失败时也写入 trace 和 checkpoint，方便 debug 定位并恢复。"""
        message = str(error).strip() or error.__class__.__name__
        trace = AgentTraceEntry(
            agent_name=agent_name,
            input_summary="执行过程中发生错误。",
            output_summary="该 agent 执行失败，可在 debug 中从这里或上游 checkpoint 恢复。",
            confidence=0.0,
            warnings=[message],
            artifact_keys=[],
            status="failed",
            error_message=message,
            decision="失败后停止当前链路，等待恢复或重试。",
        )
        self._finish_trace(trace, started_at=started_at, started_perf=started_perf, status="failed", error_message=message)
        response["status"] = "failed"
        response["error_message"] = message
        await self._append_trace(hooks, response, trace, dependency_artifacts=dependency_artifacts)

    def get_runtime_config(self, *, model: str | None = None, base_url: str | None = None) -> dict[str, Any]:
        """读取模型运行配置的公开视图。"""
        return self.report_service.get_runtime_config(model=model, base_url=base_url)

    async def run(self, payload: AgentRunRequest, hooks: AgentRunHooks | None = None) -> dict[str, Any]:
        """执行完整的受限自治多智能体投研流程。"""
        runtime_view = self.get_runtime_config(model=payload.llm.model, base_url=payload.llm.base_url)
        tool_runner = self._build_tool_runner()
        response: dict[str, Any] = {
            "mode": "natural_language",
            "query": "",
            "status": "running",
            "runtime": runtime_view,
            "research_context": payload.research_context.model_dump(),
            "stages": [],
            "agent_trace": [],
            "tool_invocations": [],
            "debate_rounds": [],
            "agent_checkpoints": [],
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
        await self._append_trace(hooks, response, intake.trace, dependency_artifacts=[])
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
        await self._append_trace(hooks, response, planner.trace, dependency_artifacts=["parsed_intent", "memory_resolution"])
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
        tool_policy = planner.plan.get("tool_policy") or {}
        try:
            data = await self.data_agent.run(
                intent=intake.parsed_intent,
                payload=payload,
                tool_runner=tool_runner,
                allowed_tools=list(tool_policy.get("DataAgent") or []),
            )
        except Exception as exc:
            await self._publish_tool_invocations(hooks, response, tool_runner)
            await self._append_failed_trace(
                hooks,
                response,
                agent_name="DataAgent",
                started_at=data_started_at,
                started_perf=data_started,
                dependency_artifacts=["research_plan", "parsed_intent"],
                error=exc,
            )
            raise
        self._finish_trace(data.trace, started_at=data_started_at, started_perf=data_started)
        response["analysis"] = data.analysis
        await self._publish_artifact(hooks, "analysis", "structured_analysis", data.analysis)
        await self._publish_tool_invocations(hooks, response, tool_runner)
        await self._append_trace(
            hooks,
            response,
            data.trace,
            dependency_artifacts=["research_plan", "parsed_intent"],
        )
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
        try:
            evidence = await self.evidence_agent.run(
                query=intake.normalized_query,
                intent=intake.parsed_intent,
                analysis=data.analysis,
                payload=payload,
                tool_runner=tool_runner,
                allowed_tools=list(tool_policy.get("EvidenceAgent") or []),
            )
        except Exception as exc:
            await self._publish_tool_invocations(hooks, response, tool_runner)
            await self._append_failed_trace(
                hooks,
                response,
                agent_name="EvidenceAgent",
                started_at=evidence_started_at,
                started_perf=evidence_started,
                dependency_artifacts=["structured_analysis", "research_plan"],
                error=exc,
            )
            raise
        self._finish_trace(evidence.trace, started_at=evidence_started_at, started_perf=evidence_started)
        response["report_input"] = evidence.report_package["report_input"]
        response["report_briefing"] = evidence.report_package["report_briefing"]
        response["merged_data_package"] = evidence.report_package["merged_data_package"]
        await self._publish_artifact(hooks, "report", "input", response["report_input"])
        await self._publish_artifact(hooks, "report", "briefing", response["report_briefing"])
        await self._publish_artifact(hooks, "report", "retrieved_evidence", evidence.evidence_payload.get("retrieved_evidence", []))
        await self._publish_artifact(hooks, "report", "citation_map", evidence.evidence_payload.get("citation_map", {}))
        await self._publish_tool_invocations(hooks, response, tool_runner)
        await self._append_trace(
            hooks,
            response,
            evidence.trace,
            dependency_artifacts=["structured_analysis", "research_plan"],
        )
        await self._append_stage(
            hooks,
            response,
            key="evidence_retrieval",
            label="证据检索",
            elapsed_ms=(perf_counter() - evidence_started) * 1000,
            status="completed",
            summary=evidence.trace.output_summary,
        )

        debate_started_at = utc_now_iso()
        debate_started = perf_counter()
        bull = self.bull_agent.run(
            report_briefing=response["report_briefing"],
            evidence_payload=evidence.evidence_payload,
        )
        self._finish_trace(bull.trace, started_at=debate_started_at, started_perf=debate_started)
        await self._append_trace(
            hooks,
            response,
            bull.trace,
            dependency_artifacts=["report_briefing", "retrieved_evidence"],
        )

        bear_started_at = utc_now_iso()
        bear_started = perf_counter()
        bear = self.bear_agent.run(
            report_briefing=response["report_briefing"],
            evidence_payload=evidence.evidence_payload,
        )
        self._finish_trace(bear.trace, started_at=bear_started_at, started_perf=bear_started)
        await self._append_trace(
            hooks,
            response,
            bear.trace,
            dependency_artifacts=["report_briefing", "retrieved_evidence"],
        )

        arbiter_started_at = utc_now_iso()
        arbiter_started = perf_counter()
        arbiter = self.arbiter_agent.run(
            bull=bull.payload,
            bear=bear.payload,
            report_briefing=response["report_briefing"],
        )
        self._finish_trace(arbiter.trace, started_at=arbiter_started_at, started_perf=arbiter_started)
        response["debate_rounds"] = [arbiter.payload]
        response["report_input"]["Debate_Rounds"] = response["debate_rounds"]
        evidence.report_package["report_input"] = response["report_input"]
        evidence.report_package["report_briefing"] = response["report_briefing"]
        await self._publish_artifact(hooks, "derived", "debate_rounds", response["debate_rounds"])
        await self._publish_artifact(hooks, "report", "input", response["report_input"])
        await self._publish_artifact(hooks, "report", "briefing", response["report_briefing"])
        await self._append_trace(
            hooks,
            response,
            arbiter.trace,
            dependency_artifacts=["debate_rounds", "report_briefing"],
        )
        await self._append_stage(
            hooks,
            response,
            key="debate_round",
            label="正反论证",
            elapsed_ms=(perf_counter() - debate_started) * 1000,
            status="completed",
            summary=arbiter.trace.output_summary,
        )

        report_started_at = utc_now_iso()
        report_started = perf_counter()
        try:
            report = await self.report_agent.run(
                query=intake.normalized_query,
                intent=intake.parsed_intent,
                report_package=evidence.report_package,
                payload=payload,
                tool_runner=tool_runner,
                allowed_tools=list(tool_policy.get("ReportAgent") or []),
            )
        except Exception as exc:
            await self._publish_tool_invocations(hooks, response, tool_runner)
            await self._append_failed_trace(
                hooks,
                response,
                agent_name="ReportAgent",
                started_at=report_started_at,
                started_perf=report_started,
                dependency_artifacts=["report_input", "report_briefing", "debate_rounds"],
                error=exc,
            )
            raise
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
        await self._publish_tool_invocations(hooks, response, tool_runner)
        await self._append_trace(
            hooks,
            response,
            report.trace,
            dependency_artifacts=["report_input", "report_briefing", "debate_rounds"],
        )
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
        try:
            validation = await self.validator_agent.run(
                bundle=report.bundle,
                language_code=intake.parsed_intent.system_context.language,
                tool_runner=tool_runner,
                allowed_tools=list(tool_policy.get("ValidatorAgent") or []),
            )
        except Exception as exc:
            await self._publish_tool_invocations(hooks, response, tool_runner)
            await self._append_failed_trace(
                hooks,
                response,
                agent_name="ValidatorAgent",
                started_at=validation_started_at,
                started_perf=validation_started,
                dependency_artifacts=["final_report", "report_briefing"],
                error=exc,
            )
            raise
        self._finish_trace(validation.trace, started_at=validation_started_at, started_perf=validation_started)
        response["report_briefing"] = validation.bundle["report_briefing"]
        await self._publish_tool_invocations(hooks, response, tool_runner)
        await self._append_trace(
            hooks,
            response,
            validation.trace,
            dependency_artifacts=["final_report", "report_briefing"],
        )
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

    async def resume_from_agent(
        self,
        payload: AgentRunRequest,
        *,
        previous_result: dict[str, Any],
        agent_name: str,
        reason: str,
        hooks: AgentRunHooks | None = None,
    ) -> dict[str, Any]:
        """从某个可恢复 agent 开始重跑，并复用上游 checkpoint。"""
        if agent_name not in self.RERUNNABLE_AGENTS or agent_name not in self.AGENT_ORDER:
            return await self.run(payload, hooks=hooks)

        response = copy.deepcopy(previous_result)
        response["status"] = "running"
        response["stages"] = []
        response["agent_trace"] = []
        response["tool_invocations"] = []
        response["debate_rounds"] = []
        response["agent_checkpoints"] = []
        response["resume_context"] = {
            "from_agent": agent_name,
            "reason": reason,
            "strategy": "reuse_upstream_checkpoint_and_rerun_downstream",
        }
        await self._publish_snapshot(hooks, response)

        parsed_intent = ParsedIntent.model_validate(response.get("parsed_intent") or {})
        query = str(response.get("query") or payload.query)
        plan = response.get("research_plan") or {}
        tool_policy = plan.get("tool_policy") or {}
        tool_runner = self._build_tool_runner()
        start_index = self.AGENT_ORDER.index(agent_name)

        for item in self._as_list(previous_result.get("agent_trace")):
            name = str(item.get("agent_name") or "")
            if name not in self.AGENT_ORDER or self.AGENT_ORDER.index(name) >= start_index:
                continue
            reused_trace = AgentTraceEntry(
                agent_name=name,
                input_summary=str(item.get("input_summary") or "复用上游 checkpoint。"),
                output_summary=f"已复用 {name} 的上游 checkpoint，未重新执行。",
                confidence=float(item.get("confidence") or 0.0),
                warnings=list(item.get("warnings") or []),
                artifact_keys=list(item.get("artifact_keys") or []),
                status="reused_checkpoint",
                started_at=utc_now_iso(),
                finished_at=utc_now_iso(),
                elapsed_ms=0.0,
                evidence_count=item.get("evidence_count"),
                decision="复用上游 checkpoint，避免重跑已成功 agent。",
                tool_calls=[],
                debate_refs=list(item.get("debate_refs") or []),
            )
            await self._append_trace(
                hooks,
                response,
                reused_trace,
                dependency_artifacts=list(item.get("dependency_artifacts") or []),
            )

        analysis = response.get("analysis")
        report_package = self._rebuild_report_package(response)
        evidence_payload = self._evidence_payload_from_response(response)

        if start_index <= self.AGENT_ORDER.index("DataAgent"):
            data_started_at = utc_now_iso()
            data_started = perf_counter()
            data = await self.data_agent.run(
                intent=parsed_intent,
                payload=payload,
                tool_runner=tool_runner,
                allowed_tools=list(tool_policy.get("DataAgent") or []),
            )
            self._finish_trace(data.trace, started_at=data_started_at, started_perf=data_started)
            analysis = data.analysis
            response["analysis"] = data.analysis
            await self._publish_artifact(hooks, "analysis", "structured_analysis", data.analysis)
            await self._publish_tool_invocations(hooks, response, tool_runner)
            await self._append_trace(
                hooks,
                response,
                data.trace,
                dependency_artifacts=["research_plan", "parsed_intent"],
            )
            await self._append_stage(
                hooks,
                response,
                key="structured_analysis",
                label="结构化分析",
                elapsed_ms=(perf_counter() - data_started) * 1000,
                status="completed",
                summary=data.trace.output_summary,
            )

        if start_index <= self.AGENT_ORDER.index("EvidenceAgent"):
            evidence_started_at = utc_now_iso()
            evidence_started = perf_counter()
            evidence = await self.evidence_agent.run(
                query=query,
                intent=parsed_intent,
                analysis=analysis or {},
                payload=payload,
                tool_runner=tool_runner,
                allowed_tools=list(tool_policy.get("EvidenceAgent") or []),
            )
            self._finish_trace(evidence.trace, started_at=evidence_started_at, started_perf=evidence_started)
            report_package = evidence.report_package
            evidence_payload = evidence.evidence_payload
            response["report_input"] = report_package["report_input"]
            response["report_briefing"] = report_package["report_briefing"]
            response["merged_data_package"] = report_package["merged_data_package"]
            await self._publish_artifact(hooks, "report", "input", response["report_input"])
            await self._publish_artifact(hooks, "report", "briefing", response["report_briefing"])
            await self._publish_artifact(hooks, "report", "retrieved_evidence", evidence_payload.get("retrieved_evidence", []))
            await self._publish_artifact(hooks, "report", "citation_map", evidence_payload.get("citation_map", {}))
            await self._publish_tool_invocations(hooks, response, tool_runner)
            await self._append_trace(
                hooks,
                response,
                evidence.trace,
                dependency_artifacts=["structured_analysis", "research_plan"],
            )
            await self._append_stage(
                hooks,
                response,
                key="evidence_retrieval",
                label="证据检索",
                elapsed_ms=(perf_counter() - evidence_started) * 1000,
                status="completed",
                summary=evidence.trace.output_summary,
            )

        if start_index <= self.AGENT_ORDER.index("ArbiterAgent"):
            report_package, evidence_payload = await self._rerun_debate(
                hooks=hooks,
                response=response,
                report_package=report_package,
                evidence_payload=evidence_payload,
            )

        if start_index <= self.AGENT_ORDER.index("ReportAgent"):
            report_started_at = utc_now_iso()
            report_started = perf_counter()
            report = await self.report_agent.run(
                query=query,
                intent=parsed_intent,
                report_package=report_package,
                payload=payload,
                tool_runner=tool_runner,
                allowed_tools=list(tool_policy.get("ReportAgent") or []),
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
            await self._publish_tool_invocations(hooks, response, tool_runner)
            await self._append_trace(
                hooks,
                response,
                report.trace,
                dependency_artifacts=["report_input", "report_briefing", "debate_rounds"],
            )
            await self._append_stage(
                hooks,
                response,
                key="final_report",
                label="最终报告",
                elapsed_ms=(perf_counter() - report_started) * 1000,
                status="fallback" if response["report_mode"] == "fallback" else "completed",
                summary=report.trace.output_summary,
            )
            report_package = self._rebuild_report_package(response)

        if start_index <= self.AGENT_ORDER.index("ValidatorAgent"):
            validation_started_at = utc_now_iso()
            validation_started = perf_counter()
            validation_bundle = self._rebuild_validation_bundle(response)
            validation = await self.validator_agent.run(
                bundle=validation_bundle,
                language_code=parsed_intent.system_context.language,
                tool_runner=tool_runner,
                allowed_tools=list(tool_policy.get("ValidatorAgent") or []),
            )
            self._finish_trace(validation.trace, started_at=validation_started_at, started_perf=validation_started)
            response["report_briefing"] = validation.bundle["report_briefing"]
            await self._publish_artifact(hooks, "report", "briefing", response["report_briefing"])
            await self._publish_artifact(hooks, "derived", "validation_checks", validation.validation_meta.get("validation_checks", []))
            await self._publish_tool_invocations(hooks, response, tool_runner)
            await self._append_trace(
                hooks,
                response,
                validation.trace,
                dependency_artifacts=["final_report", "report_briefing"],
            )
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

    async def _rerun_debate(
        self,
        *,
        hooks: AgentRunHooks | None,
        response: dict[str, Any],
        report_package: dict[str, Any],
        evidence_payload: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """重跑一轮正反论证和 Arbiter 裁决。"""
        debate_started = perf_counter()
        bull_started_at = utc_now_iso()
        bull_started = perf_counter()
        bull = self.bull_agent.run(report_briefing=response["report_briefing"], evidence_payload=evidence_payload)
        self._finish_trace(bull.trace, started_at=bull_started_at, started_perf=bull_started)
        await self._append_trace(hooks, response, bull.trace, dependency_artifacts=["report_briefing", "retrieved_evidence"])

        bear_started_at = utc_now_iso()
        bear_started = perf_counter()
        bear = self.bear_agent.run(report_briefing=response["report_briefing"], evidence_payload=evidence_payload)
        self._finish_trace(bear.trace, started_at=bear_started_at, started_perf=bear_started)
        await self._append_trace(hooks, response, bear.trace, dependency_artifacts=["report_briefing", "retrieved_evidence"])

        arbiter_started_at = utc_now_iso()
        arbiter_started = perf_counter()
        arbiter = self.arbiter_agent.run(
            bull=bull.payload,
            bear=bear.payload,
            report_briefing=response["report_briefing"],
        )
        self._finish_trace(arbiter.trace, started_at=arbiter_started_at, started_perf=arbiter_started)
        response["debate_rounds"] = [arbiter.payload]
        response["report_input"]["Debate_Rounds"] = response["debate_rounds"]
        report_package["report_input"] = response["report_input"]
        report_package["report_briefing"] = response["report_briefing"]
        await self._publish_artifact(hooks, "derived", "debate_rounds", response["debate_rounds"])
        await self._publish_artifact(hooks, "report", "input", response["report_input"])
        await self._publish_artifact(hooks, "report", "briefing", response["report_briefing"])
        await self._append_trace(hooks, response, arbiter.trace, dependency_artifacts=["debate_rounds", "report_briefing"])
        await self._append_stage(
            hooks,
            response,
            key="debate_round",
            label="正反论证",
            elapsed_ms=(perf_counter() - debate_started) * 1000,
            status="completed",
            summary=arbiter.trace.output_summary,
        )
        return report_package, evidence_payload

    @staticmethod
    def _rebuild_report_package(response: dict[str, Any]) -> dict[str, Any]:
        """从运行快照重建 ReportAgent 需要的报告包。"""
        return {
            "runtime": response.get("runtime") or {},
            "merged_data_package": response.get("merged_data_package") or {"Analysis": response.get("analysis") or {}},
            "report_input": response.get("report_input") or {},
            "report_briefing": response.get("report_briefing") or {},
        }

    @staticmethod
    def _rebuild_validation_bundle(response: dict[str, Any]) -> dict[str, Any]:
        """从运行快照重建 ValidatorAgent 需要的报告 bundle。"""
        return {
            "runtime": response.get("runtime") or {},
            "report_input": response.get("report_input") or {},
            "report_briefing": response.get("report_briefing") or {},
            "report_mode": response.get("report_mode"),
            "report_error": response.get("report_error"),
            "final_report": response.get("final_report") or "",
            "llm_raw": response.get("llm_raw") or {},
        }

    @staticmethod
    def _evidence_payload_from_response(response: dict[str, Any]) -> dict[str, Any]:
        """从报告摘要里恢复证据 payload。"""
        meta = (response.get("report_briefing") or {}).get("meta") or {}
        return {
            "retrieved_evidence": list(meta.get("retrieved_evidence") or []),
            "citation_map": dict(meta.get("citation_map") or {}),
        }

    @staticmethod
    def _as_list(value: Any) -> list[dict[str, Any]]:
        """安全读取字典列表。"""
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


AgentService = AgentCoordinator
