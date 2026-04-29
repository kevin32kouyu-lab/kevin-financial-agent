"""测试可控多智能体流程的计划、交接记录和主流程串联。"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent_runtime.controlled_agents import PlannerAgent
from app.agent_runtime.models import AgentRunRequest
from app.services.agent_coordinator import AgentCoordinator, AgentRunHooks


class FakeAnalysisService:
    """提供稳定的结构化分析结果，避免测试依赖外部行情。"""

    async def run_structured_analysis(self, payload: Any) -> dict[str, Any]:
        """返回一个最小可用的股票研究包。"""
        return {
            "debug_summary": {"selected_ticker_count": 1},
            "comparison_matrix": [{"Ticker": "AAPL", "Total_Quant_Score": 82}],
            "ticker_snapshots": [{"ticker": "AAPL", "thesis": "Quality compounder"}],
            "macro_data": {"Global_Regime": "Normal"},
            "market_data_status": {"source": "test"},
        }


class FakeReportService:
    """模拟报告服务的拆分式能力，验证 coordinator 是否按 agent 顺序调用。"""

    def get_runtime_config(self, *, model: str | None = None, base_url: str | None = None) -> dict[str, Any]:
        """返回可公开展示的运行时信息。"""
        return {"provider": "fake", "model": model, "base_url": base_url}

    def build_report_package(
        self,
        *,
        query: str,
        intent: Any,
        analysis: dict[str, Any],
        research_context: dict[str, Any] | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """构造报告输入，不访问真实 LLM。"""
        report_briefing = {
            "executive": {"top_pick": "AAPL"},
            "scoreboard": [{"ticker": "AAPL", "composite_score": 82}],
            "meta": {},
        }
        return {
            "runtime": {"provider": "fake"},
            "merged_data_package": {"Query": query, "Analysis": analysis},
            "report_input": {"User Financial Query": query},
            "report_briefing": report_briefing,
        }

    def attach_evidence(
        self,
        *,
        query: str,
        report_briefing: dict[str, Any],
        report_input: dict[str, Any],
        research_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """写入一条可追踪证据。"""
        evidence = [{"citation_key": "E1", "ticker": "AAPL", "title": "AAPL score snapshot"}]
        citation_map = {"E1": {"ticker": "AAPL", "title": "AAPL score snapshot"}}
        report_briefing["meta"]["retrieved_evidence"] = evidence
        report_briefing["meta"]["citation_map"] = citation_map
        report_input["Retrieved_Evidence"] = evidence
        report_input["Citation_Map"] = citation_map
        return {"retrieved_evidence": evidence, "citation_map": citation_map}

    async def render_report(
        self,
        *,
        query: str,
        intent: Any,
        merged_data_package: dict[str, Any],
        report_input: dict[str, Any],
        report_briefing: dict[str, Any],
        model: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """返回固定报告，避免真实模型调用。"""
        return {
            "runtime": {"provider": "fake"},
            "report_input": report_input,
            "report_briefing": report_briefing,
            "report_mode": "llm",
            "report_error": None,
            "final_report": "# Report\nAAPL is the top pick. [E1]",
            "llm_raw": {"report_provider": "fake"},
        }

    def validate_report_bundle(self, bundle: dict[str, Any], *, language_code: str) -> dict[str, Any]:
        """写入校验结果和统一可信度。"""
        meta = bundle["report_briefing"].setdefault("meta", {})
        meta["validation_checks"] = [{"name": "top_pick", "status": "pass"}]
        meta["confidence_level"] = "high"
        return meta


def test_planner_agent_builds_research_plan_from_intent():
    """PlannerAgent 应生成后续 agent 可读的研究计划。"""
    payload = AgentRunRequest(query="Find low risk quality tech stocks for 10000 USD")
    result = PlannerAgent().run(
        query=payload.query,
        intent=__import__("app.agent_runtime.intent", fromlist=["parse_intent"]).parse_intent(payload.query),
        payload=payload,
    )

    assert result.plan["objective"]
    assert result.plan["data_requirements"] == ["market_data", "fundamentals", "news", "sec_filings", "macro", "rag_evidence"]
    assert result.plan["tool_candidates"] == ["screener", "market_toolkit", "knowledge_rag", "report_builder", "rag_validator"]
    assert result.plan["fallback_policy"]["market_data"] == "use_backup_sources_and_cache"
    assert "formal_report" in result.plan["expected_outputs"]
    assert result.trace.agent_name == "PlannerAgent"
    assert result.trace.artifact_keys == ["research_plan"]


@pytest.mark.asyncio
async def test_agent_coordinator_emits_research_plan_and_agent_trace():
    """完整自然语言研究应留下研究计划和六个 agent 的交接记录。"""
    artifacts: list[tuple[str, str, Any]] = []

    async def on_artifact(kind: str, name: str, value: Any) -> None:
        """收集流程发布的 artifact。"""
        artifacts.append((kind, name, value))

    coordinator = AgentCoordinator(FakeAnalysisService(), FakeReportService())
    payload = AgentRunRequest(query="Find low risk quality tech stocks for 10000 USD")
    response = await coordinator.run(payload, hooks=AgentRunHooks(artifact_callback=on_artifact))

    assert response["status"] == "completed"
    assert response["research_plan"]["agent_architecture"] == "controlled_multi_agent"
    assert response["report_briefing"]["meta"]["retrieved_evidence"][0]["citation_key"] == "E1"
    assert response["report_briefing"]["meta"]["validation_checks"][0]["status"] == "pass"
    assert "report_outputs" in response
    assert response["report_outputs"]["simple_investment"]["markdown"] == response["final_report"]
    assert response["report_outputs"]["investment"] == response["report_outputs"]["simple_investment"]
    assert "Professional Investment Report" in response["report_outputs"]["professional_investment"]["markdown"]
    assert "Agent Workflow" in response["report_outputs"]["development"]["markdown"]

    agent_names = [item["agent_name"] for item in response["agent_trace"]]
    assert agent_names == [
        "IntakeAgent",
        "PlannerAgent",
        "DataAgent",
        "EvidenceAgent",
        "ReportAgent",
        "ValidatorAgent",
    ]
    for item in response["agent_trace"]:
        assert set(item) == {
            "agent_name",
            "status",
            "started_at",
            "finished_at",
            "elapsed_ms",
            "input_summary",
            "output_summary",
            "confidence",
            "warnings",
            "artifact_keys",
            "evidence_count",
            "error_message",
        }
        assert item["status"] == "completed"
        assert isinstance(item["elapsed_ms"], float)
        assert item["started_at"]
        assert item["finished_at"]
    evidence_trace = next(item for item in response["agent_trace"] if item["agent_name"] == "EvidenceAgent")
    assert evidence_trace["evidence_count"] == 1

    artifact_names = {(kind, name) for kind, name, _ in artifacts}
    assert ("derived", "research_plan") in artifact_names
    assert ("derived", "agent_trace") in artifact_names
    assert ("derived", "memory_resolution") in artifact_names
    assert ("report", "outputs") in artifact_names


@pytest.mark.asyncio
async def test_agent_coordinator_stops_before_data_agent_when_clarification_needed():
    """信息不足时流程应停在 IntakeAgent，不调用数据和报告 agent。"""
    coordinator = AgentCoordinator(FakeAnalysisService(), FakeReportService())
    payload = AgentRunRequest(query="推荐一些股票")
    response = await coordinator.run(payload)

    assert response["status"] == "needs_clarification"
    assert "follow_up_question" in response
    assert [item["agent_name"] for item in response["agent_trace"]] == ["IntakeAgent"]
