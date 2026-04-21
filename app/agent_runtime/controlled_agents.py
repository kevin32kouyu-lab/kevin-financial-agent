"""可控多智能体角色定义，负责把投研主流程拆成可追踪的固定职责。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agent_runtime.intent import _build_follow_up_question, _normalize_query, parse_intent
from app.agent_runtime.memory import build_preference_snapshot, merge_memory_context
from app.agent_runtime.tool_registry import ToolInvocationRequest, ToolRunner
from app.domain.contracts import AgentRunRequest, DebugAnalysisRequest, ParsedIntent


@dataclass(slots=True)
class AgentTraceEntry:
    """记录单个 agent 的输入、输出、可信度和产物，供 debug 排查。"""

    agent_name: str
    input_summary: str
    output_summary: str
    confidence: float
    warnings: list[str] = field(default_factory=list)
    artifact_keys: list[str] = field(default_factory=list)
    status: str = "completed"
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_ms: float = 0.0
    evidence_count: int | None = None
    error_message: str | None = None
    decision: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    checkpoint_id: str | None = None
    debate_refs: list[str] = field(default_factory=list)
    rerunnable: bool = False
    dependency_artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为前端和 artifact 可直接保存的字典。"""
        return {
            "agent_name": self.agent_name,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_ms": round(max(float(self.elapsed_ms or 0.0), 0.0), 2),
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "confidence": round(max(0.0, min(self.confidence, 1.0)), 2),
            "warnings": list(self.warnings),
            "artifact_keys": list(self.artifact_keys),
            "evidence_count": self.evidence_count,
            "error_message": self.error_message,
            "decision": self.decision,
            "tool_calls": list(self.tool_calls),
            "checkpoint_id": self.checkpoint_id,
            "debate_refs": list(self.debate_refs),
            "rerunnable": self.rerunnable,
            "dependency_artifacts": list(self.dependency_artifacts),
        }


@dataclass(slots=True)
class IntakeResult:
    """IntakeAgent 的标准输出。"""

    normalized_query: str
    parsed_intent: ParsedIntent
    memory_summary: dict[str, Any]
    memory_applied_fields: list[str]
    follow_up_question: str | None
    preference_snapshot: dict[str, Any] | None
    trace: AgentTraceEntry


@dataclass(slots=True)
class PlannerResult:
    """PlannerAgent 的标准输出。"""

    plan: dict[str, Any]
    trace: AgentTraceEntry


@dataclass(slots=True)
class DataResult:
    """DataAgent 的标准输出。"""

    analysis: dict[str, Any]
    trace: AgentTraceEntry


@dataclass(slots=True)
class EvidenceResult:
    """EvidenceAgent 的标准输出。"""

    report_package: dict[str, Any]
    evidence_payload: dict[str, Any]
    trace: AgentTraceEntry


@dataclass(slots=True)
class ReportResult:
    """ReportAgent 的标准输出。"""

    bundle: dict[str, Any]
    trace: AgentTraceEntry


@dataclass(slots=True)
class ValidationResult:
    """ValidatorAgent 的标准输出。"""

    bundle: dict[str, Any]
    validation_meta: dict[str, Any]
    trace: AgentTraceEntry


@dataclass(slots=True)
class DebateResult:
    """正反论证 agent 的标准输出。"""

    payload: dict[str, Any]
    trace: AgentTraceEntry


def build_debug_request(intent: ParsedIntent, payload: AgentRunRequest) -> DebugAnalysisRequest:
    """把自然语言意图转换为结构化分析服务可执行的请求。"""
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


class IntakeAgent:
    """负责理解用户问题、合并记忆，并判断是否需要补充信息。"""

    name = "IntakeAgent"

    def run(self, payload: AgentRunRequest) -> IntakeResult:
        """解析输入并输出后续流程需要的标准意图。"""
        normalized_query = _normalize_query(payload.query)
        parsed_intent = parse_intent(normalized_query)
        memory_summary = merge_memory_context(
            parsed_intent,
            query=normalized_query,
            memory_context=payload.memory_context,
        )
        memory_applied_fields = list(memory_summary["applied_fields"])
        follow_up_question: str | None = None
        preference_snapshot: dict[str, Any] | None = None
        warnings = list(parsed_intent.agent_control.missing_critical_info)

        if not parsed_intent.agent_control.is_intent_clear and not parsed_intent.agent_control.is_intent_usable:
            follow_up_question = _build_follow_up_question(parsed_intent)
            preference_snapshot = build_preference_snapshot(
                parsed_intent,
                query=normalized_query,
                research_mode=payload.research_context.research_mode,
                applied_fields=memory_applied_fields,
            )
            output_summary = "信息不足，已生成补充问题。"
            confidence = 0.58
            artifact_keys = ["parsed_intent", "follow_up_question", "preference_snapshot"]
        else:
            output_summary = "已完成意图解析，任务可以继续执行。"
            confidence = 0.88 if parsed_intent.agent_control.is_intent_clear else 0.72
            artifact_keys = ["parsed_intent"]
            if memory_summary["used"]:
                artifact_keys.extend(["memory_summary", "memory_applied_fields"])

        return IntakeResult(
            normalized_query=normalized_query,
            parsed_intent=parsed_intent,
            memory_summary=memory_summary,
            memory_applied_fields=memory_applied_fields,
            follow_up_question=follow_up_question,
            preference_snapshot=preference_snapshot,
            trace=AgentTraceEntry(
                agent_name=self.name,
                input_summary=f"用户问题长度 {len(normalized_query)}，研究模式 {payload.research_context.research_mode}。",
                output_summary=output_summary,
                confidence=confidence,
                warnings=warnings,
                artifact_keys=artifact_keys,
            ),
        )


class PlannerAgent:
    """负责把意图转换成稳定、可复查的研究计划。"""

    name = "PlannerAgent"

    def run(self, *, query: str, intent: ParsedIntent, payload: AgentRunRequest) -> PlannerResult:
        """生成固定数据需求和预期输出，避免后续 agent 自由扩张范围。"""
        tickers = list(intent.explicit_targets.tickers)
        sectors = list(intent.investment_strategy.preferred_sectors)
        tool_policy = {
            "DataAgent": ["market.research_package"],
            "EvidenceAgent": ["report.build_package", "rag.attach_evidence"],
            "BullAnalystAgent": [],
            "BearAnalystAgent": [],
            "ArbiterAgent": [],
            "ReportAgent": ["report.render"],
            "ValidatorAgent": ["report.validate"],
        }
        handoff_order = [
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
        plan = {
            "agent_architecture": "limited_autonomous_multi_agent",
            "objective": self._build_objective(query, intent),
            "research_mode": payload.research_context.research_mode,
            "as_of_date": payload.research_context.as_of_date.isoformat() if payload.research_context.as_of_date else None,
            "tickers": tickers,
            "preferred_sectors": sectors,
            "data_requirements": ["market_data", "fundamentals", "news", "sec_filings", "macro", "rag_evidence"],
            "tool_candidates": [
                "market.research_package",
                "report.build_package",
                "rag.attach_evidence",
                "report.render",
                "report.validate",
            ],
            "agent_task_graph": [
                {
                    "agent_name": name,
                    "depends_on": handoff_order[index - 1 : index] if index else [],
                    "allowed_tools": tool_policy.get(name, []),
                }
                for index, name in enumerate(handoff_order)
            ],
            "autonomy_budget": {
                "max_tool_calls": 8,
                "max_debate_rounds": 1,
                "max_retries_per_tool": 1,
                "max_downstream_reruns": 1,
            },
            "tool_policy": tool_policy,
            "debate_policy": {
                "rounds": 1,
                "agents": ["BullAnalystAgent", "BearAnalystAgent", "ArbiterAgent"],
                "arbiter_rule": "summarize_supported_points_and_reject_unsupported_claims",
            },
            "recovery_policy": {
                "checkpoint_after_each_agent": True,
                "resume_scope": "rerun_requested_agent_and_downstream",
                "reuse_upstream_artifacts": True,
            },
            "fallback_policy": {
                "market_data": "use_backup_sources_and_cache",
                "rag_evidence": "continue_with_validation_warning",
                "llm_report": "fallback_to_rule_based_report",
                "backtest": "drop_unpriced_tickers_and_disclose",
            },
            "expected_outputs": [
                "candidate_scoreboard",
                "evidence_summary",
                "debate_rounds",
                "formal_report",
                "validation_checks",
                "agent_checkpoints",
            ],
            "handoff_order": handoff_order,
        }
        warnings = list(intent.agent_control.assumptions)
        return PlannerResult(
            plan=plan,
            trace=AgentTraceEntry(
                agent_name=self.name,
                input_summary="接收标准化意图和运行参数。",
                output_summary=f"已生成研究计划，数据需求 {len(plan['data_requirements'])} 类。",
                confidence=0.86,
                warnings=warnings,
                artifact_keys=["research_plan"],
            ),
        )

    @staticmethod
    def _build_objective(query: str, intent: ParsedIntent) -> str:
        """用简短文字描述本次研究目标。"""
        style = intent.investment_strategy.style or "General"
        risk = intent.risk_profile.tolerance_level or "Unspecified"
        horizon = intent.investment_strategy.horizon or "Unspecified"
        return f"{query} | style={style}; risk={risk}; horizon={horizon}"


class DataAgent:
    """负责调用现有结构化分析和行情聚合能力。"""

    name = "DataAgent"

    def __init__(self, analysis_service: Any):
        self.analysis_service = analysis_service

    async def run(
        self,
        *,
        intent: ParsedIntent,
        payload: AgentRunRequest,
        tool_runner: ToolRunner | None = None,
        allowed_tools: list[str] | None = None,
    ) -> DataResult:
        """执行筛选和多源数据聚合。"""
        tool_calls: list[dict[str, Any]] = []
        if tool_runner is not None:
            result = await tool_runner.run(
                ToolInvocationRequest(
                    tool_name="market.research_package",
                    arguments={"intent": intent, "payload": payload},
                    agent_name=self.name,
                    allowed_tools=allowed_tools or [],
                    allowed_scopes=["market_data"],
                )
            )
            tool_calls.append(result.to_dict())
            if result.status != "success":
                raise RuntimeError(result.error_message or "market.research_package failed")
            analysis = result.output
        else:
            analysis = await self.analysis_service.run_structured_analysis(build_debug_request(intent, payload))
        selected_count = int((analysis.get("debug_summary") or {}).get("selected_ticker_count") or 0)
        warnings = []
        if selected_count == 0:
            warnings.append("未筛选出候选股票。")
        return DataResult(
            analysis=analysis,
            trace=AgentTraceEntry(
                agent_name=self.name,
                input_summary="接收研究计划和结构化意图。",
                output_summary=f"已完成筛选和数据聚合，候选 {selected_count} 只。",
                confidence=0.82 if selected_count else 0.52,
                warnings=warnings,
                artifact_keys=["structured_analysis"],
                decision="调用 Planner 授权的 market.research_package 工具完成数据聚合。",
                tool_calls=tool_calls,
            ),
        )


class EvidenceAgent:
    """负责把结构化研究转成报告输入，并接入 RAG 证据和引用。"""

    name = "EvidenceAgent"

    def __init__(self, report_service: Any):
        self.report_service = report_service

    async def run(
        self,
        *,
        query: str,
        intent: ParsedIntent,
        analysis: dict[str, Any],
        payload: AgentRunRequest,
        tool_runner: ToolRunner | None = None,
        allowed_tools: list[str] | None = None,
    ) -> EvidenceResult:
        """构建报告包并附加检索证据。"""
        tool_calls: list[dict[str, Any]] = []
        if tool_runner is not None:
            package_result = self._require_tool_success(
                await tool_runner.run(
                    ToolInvocationRequest(
                        tool_name="report.build_package",
                        arguments={
                            "query": query,
                            "intent": intent,
                            "analysis": analysis,
                            "research_context": payload.research_context.model_dump(),
                            "model": payload.llm.model,
                            "base_url": payload.llm.base_url,
                        },
                        agent_name=self.name,
                        allowed_tools=allowed_tools or [],
                        allowed_scopes=["reporting"],
                    )
                )
            )
            tool_calls.append(package_result.to_dict())
            report_package = package_result.output
            evidence_result = self._require_tool_success(
                await tool_runner.run(
                    ToolInvocationRequest(
                        tool_name="rag.attach_evidence",
                        arguments={
                            "query": query,
                            "report_briefing": report_package["report_briefing"],
                            "report_input": report_package["report_input"],
                            "research_context": payload.research_context.model_dump(),
                        },
                        agent_name=self.name,
                        allowed_tools=allowed_tools or [],
                        allowed_scopes=["rag"],
                    )
                )
            )
            tool_calls.append(evidence_result.to_dict())
            evidence_payload = evidence_result.output
        else:
            report_package = self.report_service.build_report_package(
                query=query,
                intent=intent,
                analysis=analysis,
                research_context=payload.research_context.model_dump(),
                model=payload.llm.model,
                base_url=payload.llm.base_url,
            )
            evidence_payload = self.report_service.attach_evidence(
                query=query,
                report_briefing=report_package["report_briefing"],
                report_input=report_package["report_input"],
                research_context=payload.research_context.model_dump(),
            )
        evidence_count = len(evidence_payload.get("retrieved_evidence") or [])
        warnings = []
        rag_error = (report_package["report_briefing"].get("meta") or {}).get("rag_error")
        if rag_error:
            warnings.append(str(rag_error))
        if evidence_count == 0:
            warnings.append("没有检索到可引用证据。")
        return EvidenceResult(
            report_package=report_package,
            evidence_payload=evidence_payload,
            trace=AgentTraceEntry(
                agent_name=self.name,
                input_summary="接收结构化分析结果。",
                output_summary=f"已完成证据检索，引用证据 {evidence_count} 条。",
                confidence=0.78 if evidence_count else 0.56,
                warnings=warnings,
                artifact_keys=["report_input", "report_briefing", "retrieved_evidence", "citation_map"],
                evidence_count=evidence_count,
                decision="在报告包生成后，只检索 Planner 授权范围内的 RAG 证据。",
                tool_calls=tool_calls,
            ),
        )

    @staticmethod
    def _require_tool_success(result: Any) -> Any:
        """工具失败时立刻把错误交给 coordinator 记录。"""
        if result.status != "success":
            raise RuntimeError(result.error_message or f"{result.tool_name} failed")
        return result


class BullAnalystAgent:
    """负责提出有证据支撑的正面观点，不额外调用工具。"""

    name = "BullAnalystAgent"

    def run(self, *, report_briefing: dict[str, Any], evidence_payload: dict[str, Any]) -> DebateResult:
        """基于评分、优先标的和证据数量形成正方观点。"""
        executive = self._as_dict(report_briefing.get("executive"))
        top_pick = self._text(executive.get("top_pick"), "N/A")
        score = self._text(executive.get("mandate_fit_score"), "N/A")
        evidence_count = len(evidence_payload.get("retrieved_evidence") or [])
        thesis = f"{top_pick} 是当前最强候选，匹配度 {score}，并有 {evidence_count} 条证据支持。"
        payload = {
            "round_id": "debate-1",
            "stance": "bull",
            "agent_name": self.name,
            "top_pick": top_pick,
            "claims": [thesis],
            "evidence_count": evidence_count,
        }
        return DebateResult(
            payload=payload,
            trace=AgentTraceEntry(
                agent_name=self.name,
                input_summary="接收评分表、执行摘要和证据包。",
                output_summary=f"已提出正方观点：{thesis}",
                confidence=0.74 if evidence_count else 0.52,
                artifact_keys=["debate_rounds"],
                evidence_count=evidence_count,
                decision="只使用已检索证据和评分表提出正面论点。",
                debate_refs=["debate-1"],
            ),
        )

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        """安全读取字典。"""
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _text(value: Any, fallback: str = "") -> str:
        """安全读取文本。"""
        text = str(value).strip() if value is not None else ""
        return text or fallback


class BearAnalystAgent:
    """负责提出反方风险和证据缺口，不额外调用工具。"""

    name = "BearAnalystAgent"

    def run(self, *, report_briefing: dict[str, Any], evidence_payload: dict[str, Any]) -> DebateResult:
        """基于风险登记、校验提示和证据缺口形成反方观点。"""
        meta = self._as_dict(report_briefing.get("meta"))
        gaps = self._as_list(meta.get("historical_archive_gaps"))
        risks = self._risk_items(report_briefing)
        evidence = evidence_payload.get("retrieved_evidence") or []
        claims = risks[:2] or ["主要风险需要结合估值、数据覆盖和市场波动保守解读。"]
        if gaps:
            claims.append(f"历史资料存在 {len(gaps)} 个回放缺口，不能把历史研究视为完整复盘。")
        payload = {
            "round_id": "debate-1",
            "stance": "bear",
            "agent_name": self.name,
            "claims": claims,
            "evidence_count": len(evidence),
            "gap_count": len(gaps),
        }
        return DebateResult(
            payload=payload,
            trace=AgentTraceEntry(
                agent_name=self.name,
                input_summary="接收风险登记、校验摘要和证据包。",
                output_summary=f"已提出反方风险 {len(claims)} 条。",
                confidence=0.7,
                warnings=[claim for claim in claims if gaps or "风险" in claim or "risk" in claim.lower()],
                artifact_keys=["debate_rounds"],
                evidence_count=len(evidence),
                decision="专门寻找风险、缺口和不应过度解读的地方。",
                debate_refs=["debate-1"],
            ),
        )

    def _risk_items(self, report_briefing: dict[str, Any]) -> list[str]:
        """从风险登记和逐票卡中提取风险描述。"""
        risks: list[str] = []
        for item in self._as_list(report_briefing.get("risk_register")):
            text = self._text(item.get("summary") or item.get("risk") or item.get("title"))
            if text:
                risks.append(text)
        for card in self._as_list(report_briefing.get("ticker_cards")):
            for risk in card.get("risks") or []:
                text = self._text(risk)
                if text:
                    risks.append(text)
        return self._dedupe(risks)

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        """安全读取字典。"""
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _as_list(value: Any) -> list[dict[str, Any]]:
        """安全读取字典列表。"""
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    @staticmethod
    def _text(value: Any, fallback: str = "") -> str:
        """安全读取文本。"""
        text = str(value).strip() if value is not None else ""
        return text or fallback

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        """按原顺序去重。"""
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value not in seen:
                result.append(value)
                seen.add(value)
        return result


class ArbiterAgent:
    """负责裁决正反观点，把可支持内容送入报告输入。"""

    name = "ArbiterAgent"

    def run(self, *, bull: dict[str, Any], bear: dict[str, Any], report_briefing: dict[str, Any]) -> DebateResult:
        """汇总正反观点，并明确哪些内容应谨慎处理。"""
        executive = report_briefing.setdefault("executive", {})
        top_pick = str(executive.get("top_pick") or bull.get("top_pick") or "N/A")
        bear_claims = [str(item) for item in bear.get("claims") or [] if str(item).strip()]
        decision = "accept_with_cautions" if bear_claims else "accept"
        synthesis = f"保留 {top_pick} 作为优先结论，但报告必须同时呈现主要风险和资料缺口。"
        payload = {
            "round_id": "debate-1",
            "arbiter": {
                "agent_name": self.name,
                "decision": decision,
                "synthesis": synthesis,
                "accepted_bull_claims": bull.get("claims") or [],
                "accepted_bear_claims": bear_claims,
            },
            "bull": bull,
            "bear": bear,
        }
        report_briefing.setdefault("meta", {})["debate_rounds"] = [payload]
        return DebateResult(
            payload=payload,
            trace=AgentTraceEntry(
                agent_name=self.name,
                input_summary="接收正方观点、反方观点和报告摘要。",
                output_summary=f"已完成裁决：{decision}。",
                confidence=0.76,
                warnings=bear_claims,
                artifact_keys=["debate_rounds"],
                decision=synthesis,
                debate_refs=["debate-1"],
            ),
        )


class ReportAgent:
    """负责生成用户可读的正式研究报告。"""

    name = "ReportAgent"

    def __init__(self, report_service: Any):
        self.report_service = report_service

    async def run(
        self,
        *,
        query: str,
        intent: ParsedIntent,
        report_package: dict[str, Any],
        payload: AgentRunRequest,
        tool_runner: ToolRunner | None = None,
        allowed_tools: list[str] | None = None,
    ) -> ReportResult:
        """调用报告服务生成正式报告或结构化兜底报告。"""
        tool_calls: list[dict[str, Any]] = []
        if tool_runner is not None:
            result = await tool_runner.run(
                ToolInvocationRequest(
                    tool_name="report.render",
                    arguments={
                        "query": query,
                        "intent": intent,
                        "merged_data_package": report_package["merged_data_package"],
                        "report_input": report_package["report_input"],
                        "report_briefing": report_package["report_briefing"],
                        "model": payload.llm.model,
                        "base_url": payload.llm.base_url,
                    },
                    agent_name=self.name,
                    allowed_tools=allowed_tools or [],
                    allowed_scopes=["reporting"],
                )
            )
            tool_calls.append(result.to_dict())
            if result.status != "success":
                raise RuntimeError(result.error_message or "report.render failed")
            bundle = result.output
        else:
            bundle = await self.report_service.render_report(
                query=query,
                intent=intent,
                merged_data_package=report_package["merged_data_package"],
                report_input=report_package["report_input"],
                report_briefing=report_package["report_briefing"],
                model=payload.llm.model,
                base_url=payload.llm.base_url,
            )
        warnings = [str(bundle["report_error"])] if bundle.get("report_error") else []
        return ReportResult(
            bundle=bundle,
            trace=AgentTraceEntry(
                agent_name=self.name,
                input_summary="接收报告输入、证据和引用映射。",
                output_summary=f"已生成报告，模式为 {bundle.get('report_mode') or 'unknown'}。",
                confidence=0.84 if bundle.get("report_mode") == "llm" else 0.62,
                warnings=warnings,
                artifact_keys=["final_report", "report_mode", "llm_raw"],
                decision="根据证据包和 Arbiter 裁决生成用户可读报告。",
                tool_calls=tool_calls,
            ),
        )


class ValidatorAgent:
    """负责检查报告和结构化证据是否一致，并统一可信度。"""

    name = "ValidatorAgent"

    def __init__(self, report_service: Any):
        self.report_service = report_service

    async def run(
        self,
        *,
        bundle: dict[str, Any],
        language_code: str,
        tool_runner: ToolRunner | None = None,
        allowed_tools: list[str] | None = None,
    ) -> ValidationResult:
        """执行报告一致性校验并返回校验摘要。"""
        tool_calls: list[dict[str, Any]] = []
        if tool_runner is not None:
            result = await tool_runner.run(
                ToolInvocationRequest(
                    tool_name="report.validate",
                    arguments={"bundle": bundle, "language_code": language_code},
                    agent_name=self.name,
                    allowed_tools=allowed_tools or [],
                    allowed_scopes=["validation"],
                ),
            )
            tool_calls.append(result.to_dict())
            if result.status != "success":
                raise RuntimeError(result.error_message or "report.validate failed")
            validation_meta = result.output
        else:
            validation_meta = self.report_service.validate_report_bundle(bundle, language_code=language_code)
        checks = validation_meta.get("validation_checks") or []
        confidence_level = validation_meta.get("confidence_level") or "medium"
        confidence = {"high": 0.9, "medium": 0.72, "low": 0.48}.get(str(confidence_level).lower(), 0.65)
        warnings = [
            str(item.get("message") or item.get("name"))
            for item in checks
            if isinstance(item, dict) and item.get("status") not in {None, "pass"}
        ]
        return ValidationResult(
            bundle=bundle,
            validation_meta=validation_meta,
            trace=AgentTraceEntry(
                agent_name=self.name,
                input_summary="接收正式报告和结构化摘要。",
                output_summary=f"已完成一致性校验，可信度 {confidence_level}。",
                confidence=confidence,
                warnings=warnings,
                artifact_keys=["validation_checks", "confidence_level"],
                decision="统一执行结论、评分、风险、证据和时间范围校验。",
                tool_calls=tool_calls,
            ),
        )
