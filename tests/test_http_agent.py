from __future__ import annotations

import sqlite3

from src.agent.core import AgentResponse
from src.agent.providers import ProviderError
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


def test_agent_endpoint_returns_503_when_provider_config_is_missing(monkeypatch) -> None:
    from starlette.testclient import TestClient

    async def fake_run_agent(_request):
        raise ValueError("ANTHROPIC_API_KEY is required")

    monkeypatch.setattr(http_server, "run_agent", fake_run_agent)

    with TestClient(http_server.create_app()) as client:
        response = client.post("/agent", json={"task": "Haushalt", "mode": "research"})

    assert response.status_code == 503
    assert response.json()["error"] == "ANTHROPIC_API_KEY is required"


def test_agent_endpoint_returns_provider_status(monkeypatch) -> None:
    from starlette.testclient import TestClient

    async def fake_run_agent(_request):
        raise ProviderError(429, "openai provider rate limit or quota exceeded")

    monkeypatch.setattr(http_server, "run_agent", fake_run_agent)

    with TestClient(http_server.create_app()) as client:
        response = client.post("/agent", json={"task": "Haushalt", "mode": "research"})

    assert response.status_code == 429
    assert response.json()["error"] == "openai provider rate limit or quota exceeded"


def test_agent_endpoint_requires_auth_when_password_is_configured(monkeypatch) -> None:
    from starlette.testclient import TestClient

    monkeypatch.setenv("KOMMUNALPOLITIK_AUTH_PASSWORD", "secret")
    monkeypatch.setenv("KOMMUNALPOLITIK_SESSION_SECRET", "test-session-secret")

    with TestClient(http_server.create_app()) as client:
        response = client.post("/agent", json={"task": "Haushalt", "mode": "research"})

    assert response.status_code == 401
    assert response.json()["error"] == "Authentication required"


def test_login_allows_agent_request(monkeypatch) -> None:
    from starlette.testclient import TestClient

    async def fake_run_agent(request):
        return AgentResponse(
            mode=request.mode,
            answer=f"answer for {request.task}",
            sources=[],
            actions_taken=[],
        )

    monkeypatch.setenv("KOMMUNALPOLITIK_AUTH_PASSWORD", "secret")
    monkeypatch.setenv("KOMMUNALPOLITIK_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("KOMMUNALPOLITIK_SECURE_COOKIES", "false")
    monkeypatch.setattr(http_server, "run_agent", fake_run_agent)

    with TestClient(http_server.create_app()) as client:
        login = client.post("/auth/login", json={"password": "secret"})
        response = client.post("/agent", json={"task": "Haushalt", "mode": "research"})

    assert login.status_code == 200
    assert response.status_code == 200
    assert response.json()["answer"] == "answer for Haushalt"


def test_feedback_endpoint_stores_opt_in_feedback(monkeypatch, tmp_path) -> None:
    from starlette.testclient import TestClient

    feedback_path = tmp_path / "feedback.sqlite"
    monkeypatch.setenv("KOMMUNALPOLITIK_FEEDBACK_PATH", str(feedback_path))

    with TestClient(http_server.create_app()) as client:
        response = client.post(
            "/feedback",
            json={
                "rating": "up",
                "comment": "Gute Quellen.",
                "task": "Was steht an?",
                "answer": "Antwort [1]",
                "mode": "briefing",
                "research_depth": "auto",
                "provider": "none",
                "model_metadata": {"provider": "none"},
                "actions_taken": [{"name": "search_text", "arguments": {"query": "Was steht an?"}}],
                "sources": [{"title": "Tagesordnung"}],
                "related_sources": [],
            },
        )

    assert response.status_code == 200
    assert response.json()["feedback_id"] == 1
    with sqlite3.connect(feedback_path) as connection:
        row = connection.execute("SELECT rating, comment, task, provider FROM feedback").fetchone()
    assert row == ("up", "Gute Quellen.", "Was steht an?", "none")
