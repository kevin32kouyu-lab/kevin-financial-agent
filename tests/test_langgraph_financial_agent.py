"""测试 LangGraph 版金融研究 workflow 的兼容输出和质量门阻断。"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent_runtime.models import AgentRunRequest
from app.core.config import AppSettings
from app.core.runtime import build_runtime
from app.repositories.sqlite_run_repository import SqliteRunRepository
from app.services.run_service import RunService
from app.workflows.base import WorkflowContext
from app.workflows.langgraph_financial_agent import LangGraphFinancialAgentWorkflow


class FakeAnalysisService:
    """提供稳定的结构化分析结果，避免测试依赖真实外部数据。"""

    def __init__(self, *, selected_count: int = 1):
        """记录调用次数并允许测试注入候选数量。"""
        self.selected_count = selected_count
        self.call_count = 0

    async def run_structured_analysis(self, payload: Any) -> dict[str, Any]:
        """返回最小可用或空候选研究包。"""
        self.call_count += 1
        if self.selected_count == 0:
            return {
                "debug_summary": {"selected_ticker_count": 0},
                "comparison_matrix": [],
                "ticker_snapshots": [],
                "macro_data": {},
                "market_data_status": {"source": "test"},
            }
        return {
            "debug_summary": {"selected_ticker_count": 1},
            "comparison_matrix": [{"Ticker": "AAPL", "Total_Quant_Score": 82}],
            "ticker_snapshots": [
                {
                    "ticker": "AAPL",
                    "thesis": "Quality compounder",
                    "news": [{"title": "AAPL expands services"}],
                }
            ],
            "macro_data": {"Global_Regime": "Normal"},
            "market_data_status": {"source": "test"},
        }


class FakeReportService:
    """模拟报告服务，验证 LangGraph workflow 的编排和输出兼容性。"""

    def __init__(self, *, evidence_count: int = 2):
        """允许测试控制证据数量。"""
        self.evidence_count = evidence_count

    def get_runtime_config(self, *, model: str | None = None, base_url: str | None = None) -> dict[str, Any]:
        """返回公开运行时信息。"""
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
        """构造报告输入。"""
        report_briefing = {
            "executive": {"top_pick": "AAPL", "mandate_fit_score": 82},
            "scoreboard": [{"ticker": "AAPL", "composite_score": 82}],
            "risk_register": [{"summary": "估值波动风险"}],
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
        """按测试参数返回证据列表。"""
        evidence = [
            {"citation_key": f"E{index}", "ticker": "AAPL", "title": f"Evidence {index}"}
            for index in range(1, self.evidence_count + 1)
        ]
        citation_map = {item["citation_key"]: item for item in evidence}
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
        """返回固定正式报告。"""
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
        """写入一致性校验结果。"""
        meta = bundle["report_briefing"].setdefault("meta", {})
        meta["validation_checks"] = [{"name": "top_pick", "status": "pass"}]
        meta["confidence_level"] = "high"
        return meta


@pytest.fixture
def workflow_context(tmp_path):
    """创建带 SQLite 仓储的 workflow context。"""
    repository = SqliteRunRepository(tmp_path / "runs.sqlite3")
    repository.init_schema()
    run_id = "run-1"
    repository.create_run(
        run_id=run_id,
        mode="agent",
        workflow_key="agent_v2",
        title="LangGraph run",
        metadata={"source": "test"},
    )
    return WorkflowContext(run_id=run_id, mode="agent", repository=repository)


@pytest.mark.asyncio
async def test_langgraph_workflow_returns_legacy_compatible_completed_response(workflow_context):
    """完整 agent_v2 图应输出旧前端可读取的核心字段。"""
    workflow = LangGraphFinancialAgentWorkflow(
        FakeAnalysisService(),
        FakeReportService(evidence_count=2),
        profile_service=None,
    )

    result = await workflow.execute(
        AgentRunRequest(query="Find low risk quality tech stocks for 10000 USD"),
        workflow_context,
    )

    response = result.response
    assert result.status == "completed"
    assert response["status"] == "completed"
    assert response["research_plan"]["agent_architecture"] == "langgraph_limited_autonomous_multi_agent"
    assert response["quality_gates"][-1]["name"] == "report_quality_gate"
    assert response["final_report"].startswith("# Report")
    assert "report_outputs" in response
    assert response["agent_trace"]
    assert response["agent_checkpoints"]
    assert response["tool_invocations"]
    assert [item["agent_name"] for item in response["agent_trace"]][:3] == [
        "IntakeNode",
        "PlannerNode",
        "MarketDataNode",
    ]
    briefing_artifact = workflow_context.repository.get_artifact_content("run-1", kind="report", name="briefing")
    assert briefing_artifact["meta"]["validation_checks"][0]["status"] == "pass"


@pytest.mark.asyncio
async def test_langgraph_workflow_blocks_when_data_quality_fails(workflow_context):
    """候选股票为空时，agent_v2 应停止在数据质量门，不生成正式报告。"""
    workflow = LangGraphFinancialAgentWorkflow(
        FakeAnalysisService(selected_count=0),
        FakeReportService(evidence_count=2),
        profile_service=None,
    )

    result = await workflow.execute(
        AgentRunRequest(query="Find low risk quality tech stocks for 10000 USD"),
        workflow_context,
    )

    response = result.response
    assert result.status == "failed"
    assert response["status"] == "failed"
    assert response["blocking_reason"]
    assert "final_report" not in response
    assert response["quality_gates"][-1]["name"] == "data_quality_gate"
    assert response["quality_gates"][-1]["status"] == "block"


@pytest.mark.asyncio
async def test_langgraph_workflow_blocks_when_evidence_quality_fails(workflow_context):
    """没有可引用证据时，agent_v2 不应继续生成正式报告。"""
    workflow = LangGraphFinancialAgentWorkflow(
        FakeAnalysisService(),
        FakeReportService(evidence_count=0),
        profile_service=None,
    )

    result = await workflow.execute(
        AgentRunRequest(query="Find low risk quality tech stocks for 10000 USD"),
        workflow_context,
    )

    response = result.response
    assert result.status == "failed"
    assert response["status"] == "failed"
    assert response["blocking_reason"]
    assert "final_report" not in response
    assert response["quality_gates"][-1]["name"] == "evidence_quality_gate"
    assert response["quality_gates"][-1]["status"] == "block"


def test_runtime_registers_agent_v2_and_uses_it_by_default(tmp_path):
    """运行时应同时注册旧版 agent 和新版 agent_v2，且默认使用 v2。"""
    runtime = build_runtime(
        AppSettings(
            db_path=tmp_path / "runs.sqlite3",
            market_db_path=tmp_path / "market.sqlite3",
            knowledge_db_path=tmp_path / "knowledge.sqlite3",
        )
    )

    assert "agent" in runtime.workflow_runner.workflows
    assert "agent_v2" in runtime.workflow_runner.workflows
    assert runtime.run_service.agent_workflow_key == "agent_v2"


def test_runtime_can_fall_back_to_agent_v1_when_settings_request_it(tmp_path):
    """配置为 v1 时，新建自然语言 run 应回退旧版 agent。"""
    runtime = build_runtime(
        AppSettings(
            db_path=tmp_path / "runs.sqlite3",
            market_db_path=tmp_path / "market.sqlite3",
            knowledge_db_path=tmp_path / "knowledge.sqlite3",
            agent_workflow_version="v1",
        )
    )

    assert runtime.run_service.agent_workflow_key == "agent"


def test_run_service_maps_agent_mode_to_configured_workflow_key(tmp_path):
    """RunService 应只在 agent 模式下改用配置的 workflow。"""
    repository = SqliteRunRepository(tmp_path / "runs.sqlite3")
    repository.init_schema()
    runner = type("Runner", (), {"schedule": lambda self, run_id: None})()
    service = RunService(
        repository=repository,
        runner=runner,  # type: ignore[arg-type]
        profile_service=type("Profile", (), {"get_preferences": lambda self, profile_id, user_id=None: type("Prefs", (), {"values": type("Values", (), {})()})()})(),
        run_audit_service=object(),  # type: ignore[arg-type]
        agent_workflow_key="agent_v2",
    )

    assert service._workflow_key_for_mode("agent") == "agent_v2"
    assert service._workflow_key_for_mode("structured") == "structured"
