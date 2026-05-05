from __future__ import annotations

from src.agent.core import AgentResponse
from src import http_server


def test_agent_endpoint_requires_task() -> None:
    from starlette.testclient import TestClient

    with TestClient(http_server.create_app()) as client:
        response = client.post("/agent", json={"mode": "research"})

    assert response.status_code == 400
    assert response.json()["error"] == "Field 'task' is required"


def test_agent_endpoint_rejects_unknown_mode() -> None:
    from starlette.testclient import TestClient

    with TestClient(http_server.create_app()) as client:
        response = client.post("/agent", json={"task": "Haushalt", "mode": "unknown"})

    assert response.status_code == 400
    assert response.json()["error"] == "Unsupported mode: unknown"


def test_agent_endpoint_returns_agent_response(monkeypatch) -> None:
    from starlette.testclient import TestClient

    async def fake_run_agent(request):
        return AgentResponse(
            mode=request.mode,
            answer=f"answer for {request.task}",
            sources=[],
            actions_taken=[],
        )

    monkeypatch.setattr(http_server, "run_agent", fake_run_agent)

    with TestClient(http_server.create_app()) as client:
        response = client.post("/agent", json={"task": "Haushalt", "mode": "research"})

    assert response.status_code == 200
    assert response.json()["answer"] == "answer for Haushalt"
    assert response.json()["provider"] == "none"


def test_agent_endpoint_returns_503_when_database_is_missing(monkeypatch) -> None:
    from starlette.testclient import TestClient

    async def fake_run_agent(_request):
        raise FileNotFoundError("database missing")

    monkeypatch.setattr(http_server, "run_agent", fake_run_agent)

    with TestClient(http_server.create_app()) as client:
        response = client.post("/agent", json={"task": "Haushalt", "mode": "research"})

    assert response.status_code == 503
    assert response.json()["error"] == "database missing"
