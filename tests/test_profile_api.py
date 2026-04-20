"""
测试 profile API 与 run 链路联动。
"""

import time

from fastapi.testclient import TestClient


EMPTY_PROFILE = {
    "capital_amount": None,
    "currency": None,
    "risk_tolerance": None,
    "investment_horizon": None,
    "investment_style": None,
    "preferred_sectors": [],
    "preferred_industries": [],
}


def _wait_for_terminal_status(client: TestClient, run_id: str, headers: dict[str, str]) -> dict:
    deadline = time.time() + 5
    while time.time() < deadline:
        response = client.get(f"/api/runs/{run_id}", headers=headers)
        detail = response.json()
        if detail["run"]["status"] in {"completed", "failed", "needs_clarification", "cancelled"}:
            return detail
        time.sleep(0.1)
    raise AssertionError("run did not reach a terminal state in time")


def test_profile_api_and_run_memory_integration(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCIAL_AGENT_DB_PATH", str(tmp_path / "runs.sqlite3"))
    monkeypatch.setenv("FINANCIAL_AGENT_MARKET_DB_PATH", str(tmp_path / "market.sqlite3"))

    from app.main import create_app

    headers = {"X-Client-Id": "browser-api"}
    with TestClient(create_app()) as client:
        profile_response = client.get("/api/v1/profile", headers=headers)
        assert profile_response.status_code == 200
        assert profile_response.json()["profile"] == EMPTY_PROFILE

        run_response = client.post(
            "/api/runs",
            headers=headers,
            json={
                "mode": "agent",
                "agent": {
                    "query": "我偏低风险，想长期持有",
                    "options": {"fetch_live_data": True, "max_results": 5},
                    "llm": {},
                },
            },
        )
        assert run_response.status_code == 200

        run_id = run_response.json()["run"]["id"]
        detail = _wait_for_terminal_status(client, run_id, headers)
        assert detail["run"]["status"] == "needs_clarification"
        assert "risk_tolerance" in detail["result"]["memory"]["updated_fields"]
        assert "investment_horizon" in detail["result"]["memory"]["updated_fields"]

        stored_profile = client.get("/api/v1/profile", headers=headers).json()
        assert stored_profile["profile"]["risk_tolerance"] == "Low"
        assert stored_profile["profile"]["investment_horizon"] == "Long-term"

        updated_profile = client.put(
            "/api/v1/profile",
            headers=headers,
            json={
                "capital_amount": None,
                "currency": None,
                "risk_tolerance": "Medium",
                "investment_horizon": "Long-term",
                "investment_style": None,
                "preferred_sectors": [],
                "preferred_industries": [],
            },
        )
        assert updated_profile.status_code == 200
        assert updated_profile.json()["profile"]["risk_tolerance"] == "Medium"

        cleared_profile = client.delete("/api/v1/profile", headers=headers)
        assert cleared_profile.status_code == 200
        assert cleared_profile.json()["profile"] == EMPTY_PROFILE
