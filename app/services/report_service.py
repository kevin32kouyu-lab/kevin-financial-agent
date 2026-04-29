from __future__ import annotations

import asyncio
from typing import Any

from app.integrations.llm_client import DeepSeekChatClient, DeepSeekChatConfig

from app.domain.contracts import ParsedIntent
from app.services.investment_memo import (
    build_merged_data_package,
    build_report_briefing,
    build_report_input,
    build_report_system_prompt,
    build_report_user_prompt,
    build_rule_based_report,
    validate_report_output,
)
from app.services.rag_service import KnowledgeRagService
from app.services.report_outputs import attach_dual_report_outputs


class ReportService:
    def __init__(self, rag_service: KnowledgeRagService | None = None):
        self.rag_service = rag_service

    def _attach_rag_payload(
        self,
        *,
        query: str,
        report_briefing: dict[str, Any],
        report_input: dict[str, Any],
        research_context: dict[str, Any] | None,
    ) -> None:
        """把 RAG 证据写入报告摘要和模型输入，失败时不阻断主报告。"""
        if self.rag_service is None:
            return
        meta = report_briefing.setdefault("meta", {})
        try:
            ingested_count = self.rag_service.ingest_run_evidence(
                query=query,
                report_briefing=report_briefing,
                research_context=research_context,
            )
            evidence_payload = self.rag_service.attach_retrieved_evidence(
                query=query,
                report_briefing=report_briefing,
                research_context=research_context,
            )
            meta["rag_ingested_documents"] = ingested_count
            report_input["Retrieved_Evidence"] = evidence_payload["retrieved_evidence"]
            report_input["Citation_Map"] = evidence_payload["citation_map"]
        except Exception as exc:
            meta["rag_error"] = str(exc)
            meta.setdefault("retrieved_evidence", [])
            meta.setdefault("citation_map", {})
            report_input["Retrieved_Evidence"] = []
            report_input["Citation_Map"] = {}

    def _attach_report_mode_notes(self, bundle: dict[str, Any], *, language_code: str) -> None:
        """把报告模式与校验结果同步到用户可读摘要里。"""
        meta = bundle.get("report_briefing", {}).get("meta", {}) or {}
        validation_summary = meta.get("validation_summary", {}) or {}
        safety_summary = meta.get("safety_summary", {}) or {}
        validation_items = validation_summary.get("items", []) or []
        degraded_modules = safety_summary.get("degraded_modules", []) or []

        if bundle.get("report_mode") == "fallback":
            note = (
                "本次正式长文未直接采用模型输出，系统已回落到结构化报告。"
                if language_code == "zh"
                else "The long-form memo fell back to the structured report instead of using raw model output."
            )
            if note not in validation_items:
                validation_items.append(note)
            if note not in degraded_modules:
                degraded_modules.append(note)
            if validation_summary.get("level") in {None, "", "pass"}:
                validation_summary["level"] = "warning"

        validation_summary["items"] = validation_items
        safety_summary["degraded_modules"] = degraded_modules
        meta["validation_summary"] = validation_summary
        meta["safety_summary"] = safety_summary
        meta["validation_flags"] = list(validation_items)
        meta["coverage_flags"] = list(degraded_modules)
        if not meta.get("confidence_level"):
            meta["confidence_level"] = (
                "high"
                if validation_summary.get("level") == "pass"
                else "medium"
                if validation_summary.get("level") == "caution"
                else "low"
            )
        bundle["report_briefing"]["meta"] = meta

    def get_runtime_config(self, *, model: str | None = None, base_url: str | None = None) -> dict[str, Any]:
        return DeepSeekChatConfig.from_overrides(model=model, base_url=base_url).public_view()

    def _build_chat_client(self, runtime_config: DeepSeekChatConfig) -> DeepSeekChatClient:
        """构建统一的 DeepSeek 模型客户端。"""
        return DeepSeekChatClient(runtime_config)

    def build_report_package(
        self,
        *,
        query: str,
        intent: ParsedIntent,
        analysis: dict[str, Any],
        research_context: dict[str, Any] | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """构造报告基础包，供 EvidenceAgent 接管 RAG 证据。"""
        runtime_config = DeepSeekChatConfig.from_overrides(model=model, base_url=base_url)
        merged_data_package = build_merged_data_package(query, intent, analysis)
        report_briefing = build_report_briefing(query, intent, merged_data_package)
        report_input = build_report_input(query, intent, merged_data_package)
        return {
            "runtime": runtime_config.public_view(),
            "merged_data_package": merged_data_package,
            "report_input": report_input,
            "report_briefing": report_briefing,
            "research_context": research_context or {},
        }

    def attach_evidence(
        self,
        *,
        query: str,
        report_briefing: dict[str, Any],
        report_input: dict[str, Any],
        research_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """把 RAG 证据接入报告包，供 EvidenceAgent 记录交接结果。"""
        self._attach_rag_payload(
            query=query,
            report_briefing=report_briefing,
            report_input=report_input,
            research_context=research_context,
        )
        meta = report_briefing.setdefault("meta", {})
        return {
            "retrieved_evidence": meta.get("retrieved_evidence", []),
            "citation_map": meta.get("citation_map", {}),
        }

    async def render_report(
        self,
        *,
        query: str,
        intent: ParsedIntent,
        merged_data_package: dict[str, Any],
        report_input: dict[str, Any],
        report_briefing: dict[str, Any],
        model: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """生成正式报告或结构化兜底报告，不在这里执行 RAG 一致性校验。"""
        runtime_config = DeepSeekChatConfig.from_overrides(model=model, base_url=base_url)
        bundle: dict[str, Any] = {
            "runtime": runtime_config.public_view(),
            "report_input": report_input,
            "report_briefing": report_briefing,
            "report_mode": None,
            "report_error": None,
            "final_report": "",
            "llm_raw": {},
        }

        client = self._build_chat_client(runtime_config)
        try:
            report_result = await asyncio.wait_for(
                asyncio.to_thread(
                    client.chat,
                    system_prompt=build_report_system_prompt(intent.system_context.language),
                    user_prompt=build_report_user_prompt(query, intent, merged_data_package, report_input=report_input),
                    temperature=0.2,
                    max_tokens=1400,
                ),
                timeout=18.0,
            )
            bundle["llm_raw"]["report_response"] = report_result["content"]
            bundle["llm_raw"]["report_provider"] = report_result.get("provider")
            validation_error = validate_report_output(report_result["content"], intent, report_briefing)
            if validation_error:
                bundle["final_report"] = build_rule_based_report(intent, report_briefing)
                bundle["report_mode"] = "fallback"
                bundle["report_error"] = validation_error
                bundle["report_briefing"]["meta"]["report_mode"] = "fallback"
            else:
                bundle["final_report"] = report_result["content"]
                bundle["report_mode"] = "llm"
                bundle["report_briefing"]["meta"]["report_mode"] = "llm"
        except Exception as exc:
            bundle["final_report"] = build_rule_based_report(intent, report_briefing)
            bundle["report_mode"] = "fallback"
            bundle["report_error"] = str(exc)
            bundle["report_briefing"]["meta"]["report_mode"] = "fallback"

        self._attach_report_mode_notes(bundle, language_code=intent.system_context.language)
        return bundle

    def validate_report_bundle(self, bundle: dict[str, Any], *, language_code: str) -> dict[str, Any]:
        """由 ValidatorAgent 调用，统一写入最终校验和可信度。"""
        if self.rag_service is not None:
            return self.rag_service.apply_validation(
                final_report=bundle["final_report"],
                report_briefing=bundle["report_briefing"],
                language_code=language_code,
            )
        return bundle.get("report_briefing", {}).setdefault("meta", {})

    async def generate_report(
        self,
        *,
        query: str,
        intent: ParsedIntent,
        analysis: dict[str, Any],
        research_context: dict[str, Any] | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        report_package = self.build_report_package(
            query=query,
            intent=intent,
            analysis=analysis,
            research_context=research_context,
            model=model,
            base_url=base_url,
        )
        self.attach_evidence(
            query=query,
            report_briefing=report_package["report_briefing"],
            report_input=report_package["report_input"],
            research_context=research_context,
        )
        bundle = await self.render_report(
            query=query,
            intent=intent,
            merged_data_package=report_package["merged_data_package"],
            report_input=report_package["report_input"],
            report_briefing=report_package["report_briefing"],
            model=model,
            base_url=base_url,
        )
        self.validate_report_bundle(bundle, language_code=intent.system_context.language)
        attach_dual_report_outputs(
            bundle=bundle,
            query=query,
            language_code=intent.system_context.language,
        )
        return bundle
