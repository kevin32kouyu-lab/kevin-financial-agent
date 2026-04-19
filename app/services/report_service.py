from __future__ import annotations

import asyncio
from typing import Any

from app.integrations.llm_client import VolcengineChatClient, VolcengineChatConfig

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


class ReportService:
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
        return VolcengineChatConfig.from_overrides(model=model, base_url=base_url).public_view()

    async def generate_report(
        self,
        *,
        query: str,
        intent: ParsedIntent,
        analysis: dict[str, Any],
        model: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        runtime_config = VolcengineChatConfig.from_overrides(model=model, base_url=base_url)
        merged_data_package = build_merged_data_package(query, intent, analysis)
        report_input = build_report_input(query, intent, merged_data_package)
        report_briefing = build_report_briefing(query, intent, merged_data_package)

        bundle: dict[str, Any] = {
            "runtime": runtime_config.public_view(),
            "report_input": report_input,
            "report_briefing": report_briefing,
            "report_mode": None,
            "report_error": None,
            "final_report": "",
            "llm_raw": {},
        }

        client = VolcengineChatClient(runtime_config)
        try:
            report_result = await asyncio.wait_for(
                asyncio.to_thread(
                    client.chat,
                    system_prompt=build_report_system_prompt(intent.system_context.language),
                    user_prompt=build_report_user_prompt(query, intent, merged_data_package),
                    temperature=0.2,
                    max_tokens=1400,
                ),
                timeout=18.0,
            )
            bundle["llm_raw"]["report_response"] = report_result["content"]
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
