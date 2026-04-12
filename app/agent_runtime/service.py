from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from app.analysis_runtime import DebugAnalysisRequest, PipelineOptions, run_analysis_pipeline
from app.integrations.llm_client import VolcengineChatClient, VolcengineChatConfig

from .intent import _build_follow_up_question, _normalize_query, parse_intent
from .models import AgentRunRequest, ParsedIntent
from .reporting import (
    _build_merged_data_package,
    _build_report_briefing,
    _build_report_input,
    _build_report_system_prompt,
    _build_report_user_prompt,
    _build_rule_based_report,
    _validate_report_output,
)

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


def get_runtime_config(model: str | None = None, base_url: str | None = None) -> dict[str, Any]:
    config = VolcengineChatConfig.from_overrides(model=model, base_url=base_url)
    return config.public_view()


def _build_stage(key: str, label: str, elapsed_ms: float, status: str, summary: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 2),
        "summary": summary,
    }


def _build_debug_request(intent: ParsedIntent, options: PipelineOptions) -> DebugAnalysisRequest:
    return DebugAnalysisRequest(
        risk_profile=intent.risk_profile,
        investment_strategy=intent.investment_strategy,
        fundamental_filters=intent.fundamental_filters,
        explicit_targets=intent.explicit_targets,
        portfolio_sizing=intent.portfolio_sizing.model_dump(),
        options=options,
    )


async def _publish_snapshot(hooks: AgentRunHooks | None, response: dict[str, Any]) -> None:
    if hooks is None:
        return
    await _maybe_call(hooks.snapshot_callback, copy.deepcopy(response))


async def _publish_artifact(hooks: AgentRunHooks | None, kind: str, name: str, value: Any) -> None:
    if hooks is None:
        return
    await _maybe_call(hooks.artifact_callback, kind, name, copy.deepcopy(value))


async def _append_stage(
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
    await _publish_snapshot(hooks, response)


async def run_financial_agent(payload: AgentRunRequest, hooks: AgentRunHooks | None = None) -> dict[str, Any]:
    normalized_query = _normalize_query(payload.query)
    runtime_config = VolcengineChatConfig.from_overrides(model=payload.llm.model, base_url=payload.llm.base_url)
    client = VolcengineChatClient(runtime_config)

    response: dict[str, Any] = {
        "mode": "natural_language",
        "query": normalized_query,
        "status": "running",
        "runtime": runtime_config.public_view(),
        "stages": [],
        "llm_raw": {},
    }
    await _publish_artifact(hooks, "runtime", "config", response["runtime"])
    await _publish_snapshot(hooks, response)

    intent_started = perf_counter()
    parsed_intent = parse_intent(normalized_query)
    intent_elapsed = (perf_counter() - intent_started) * 1000
    response["parsed_intent"] = parsed_intent.model_dump()
    await _publish_artifact(hooks, "derived", "parsed_intent", response["parsed_intent"])
    await _append_stage(
        hooks,
        response,
        key="intent_analysis",
        label="意图解析",
        elapsed_ms=intent_elapsed,
        status="completed",
        summary="已用本地规则完成投资意图解析。",
    )

    if not parsed_intent.agent_control.is_intent_clear:
        follow_up_started = perf_counter()
        follow_up_question = _build_follow_up_question(parsed_intent)
        follow_up_elapsed = (perf_counter() - follow_up_started) * 1000
        response["follow_up_question"] = follow_up_question
        response["status"] = "needs_clarification"
        await _publish_artifact(hooks, "derived", "follow_up_question", follow_up_question)
        await _append_stage(
            hooks,
            response,
            key="follow_up",
            label="补充追问",
            elapsed_ms=follow_up_elapsed,
            status="completed",
            summary="当前信息不足，已生成补充问题。",
        )
        return response

    analysis_started = perf_counter()
    analysis = await run_analysis_pipeline(_build_debug_request(parsed_intent, payload.options))
    analysis_elapsed = (perf_counter() - analysis_started) * 1000
    response["analysis"] = analysis
    await _publish_artifact(hooks, "analysis", "structured_analysis", analysis)
    await _append_stage(
        hooks,
        response,
        key="structured_analysis",
        label="结构化分析",
        elapsed_ms=analysis_elapsed,
        status="completed",
        summary=f"已完成筛选与多源聚合，共 {analysis.get('debug_summary', {}).get('selected_ticker_count', 0)} 只股票。",
    )

    merged_data_package = _build_merged_data_package(normalized_query, parsed_intent, analysis)
    report_briefing = _build_report_briefing(normalized_query, parsed_intent, merged_data_package)
    response["report_input"] = _build_report_input(normalized_query, parsed_intent, merged_data_package)
    response["report_briefing"] = report_briefing
    await _publish_artifact(hooks, "report", "input", response["report_input"])
    await _publish_artifact(hooks, "report", "briefing", report_briefing)
    await _publish_snapshot(hooks, response)

    report_started = perf_counter()
    try:
        report_result = await asyncio.wait_for(
            asyncio.to_thread(
                client.chat,
                system_prompt=_build_report_system_prompt(parsed_intent.system_context.language),
                user_prompt=_build_report_user_prompt(normalized_query, parsed_intent, merged_data_package),
                temperature=0.2,
                max_tokens=1400,
            ),
            timeout=18.0,
        )
        report_elapsed = (perf_counter() - report_started) * 1000
        response["llm_raw"]["report_response"] = report_result["content"]
        await _publish_artifact(hooks, "llm", "report_response", report_result["content"])
        validation_error = _validate_report_output(report_result["content"], parsed_intent, report_briefing)
        if validation_error:
            response["final_report"] = _build_rule_based_report(parsed_intent, report_briefing)
            response["report_mode"] = "fallback"
            response["report_error"] = validation_error
            response["report_briefing"]["meta"]["report_mode"] = "fallback"
            await _publish_artifact(hooks, "report", "final_report", response["final_report"])
            await _publish_artifact(hooks, "report", "error", validation_error)
            await _append_stage(
                hooks,
                response,
                key="final_report",
                label="最终报告",
                elapsed_ms=report_elapsed,
                status="fallback",
                summary="LLM 输出未通过报告校验，已切换到本地结构化报告。",
            )
        else:
            response["final_report"] = report_result["content"]
            response["report_mode"] = "llm"
            response["report_briefing"]["meta"]["report_mode"] = "llm"
            await _publish_artifact(hooks, "report", "final_report", response["final_report"])
            await _append_stage(
                hooks,
                response,
                key="final_report",
                label="最终报告",
                elapsed_ms=report_elapsed,
                status="completed",
                summary="已基于统一 merged package 生成最终报告。",
            )
    except Exception as exc:
        report_elapsed = (perf_counter() - report_started) * 1000
        response["final_report"] = _build_rule_based_report(parsed_intent, report_briefing)
        response["report_mode"] = "fallback"
        response["report_error"] = str(exc)
        response["report_briefing"]["meta"]["report_mode"] = "fallback"
        await _publish_artifact(hooks, "report", "final_report", response["final_report"])
        await _publish_artifact(hooks, "report", "error", str(exc))
        await _append_stage(
            hooks,
            response,
            key="final_report",
            label="最终报告",
            elapsed_ms=report_elapsed,
            status="fallback",
            summary="LLM 报告阶段失败，已切换到同结构的本地备选报告。",
        )

    response["status"] = "completed"
    await _publish_snapshot(hooks, response)
    return response
