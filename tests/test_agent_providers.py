from __future__ import annotations

from src.agent.core import AgentAction, AgentRequest, AgentSource
from src.agent.providers import NoneProvider, _response_from_llm, build_agent_prompt, provider_from_env


def test_provider_from_env_defaults_to_none(monkeypatch) -> None:
    monkeypatch.delenv("KOMMUNALPOLITIK_LLM_PROVIDER", raising=False)

    provider = provider_from_env()

    assert isinstance(provider, NoneProvider)


def test_provider_from_env_builds_anthropic(monkeypatch) -> None:
    monkeypatch.setenv("KOMMUNALPOLITIK_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("KOMMUNALPOLITIK_LLM_MODEL", "test-model")

    provider = provider_from_env()

    assert provider.name == "anthropic"
    assert provider.model == "test-model"


def test_provider_from_env_builds_openai_compatible(monkeypatch) -> None:
    monkeypatch.setenv("KOMMUNALPOLITIK_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("KOMMUNALPOLITIK_LLM_API_KEY", "test-key")
    monkeypatch.setenv("KOMMUNALPOLITIK_LLM_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("KOMMUNALPOLITIK_LLM_MODEL", "local-model")

    provider = provider_from_env()

    assert provider.name == "openai"
    assert provider.base_url == "http://localhost:1234/v1"
    assert provider.model == "local-model"


def test_provider_from_env_selects_model_by_request(monkeypatch) -> None:
    monkeypatch.setenv("KOMMUNALPOLITIK_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("KOMMUNALPOLITIK_LLM_MODEL", "default-model")
    monkeypatch.setenv("KOMMUNALPOLITIK_MODEL_QUICK", "quick-model")
    monkeypatch.setenv("KOMMUNALPOLITIK_MODEL_BALANCED", "balanced-model")
    monkeypatch.setenv("KOMMUNALPOLITIK_MODEL_STRONG", "strong-model")

    quick = provider_from_env(AgentRequest(task="Kurz", research_depth="quick"))
    balanced = provider_from_env(AgentRequest(task="Normal"))
    strong = provider_from_env(AgentRequest(task="Entwurf", mode="motion_draft"))

    assert quick.model == "quick-model"
    assert balanced.model == "balanced-model"
    assert strong.model == "strong-model"


def test_build_agent_prompt_includes_sources_and_mode_instruction() -> None:
    prompt = build_agent_prompt(
        AgentRequest(task="Haushalt", mode="research"),
        [
            AgentSource(
                title="Niederschrift",
                url="https://example.invalid/doc",
                snippet="Debatte zum Haushalt",
                meeting_date="2025-01-01",
                body_name="StVV",
            )
        ],
        {"actions_taken": [AgentAction("search_text", {"query": "Haushalt"})]},
    )

    assert "Aufgabe: Haushalt" in prompt
    assert "[1] Niederschrift" in prompt
    assert "Debatte zum Haushalt" in prompt
    assert "Quellenverweisen" in prompt


def test_briefing_prompt_demands_structured_markdown() -> None:
    prompt = build_agent_prompt(
        AgentRequest(task="Briefing", mode="briefing"),
        [],
        {"actions_taken": []},
    )

    assert "## Kurzbriefing" in prompt
    assert "## Rueckfragen fuer die Sitzung" in prompt
    assert "## Unsicherheiten" in prompt


def test_empty_llm_answer_falls_back_to_retrieval_summary() -> None:
    response = _response_from_llm(
        "openai",
        AgentRequest(task="Haushalt", mode="research"),
        [AgentSource(title="Haushaltsplan", url="https://example.invalid/doc")],
        {"actions_taken": []},
        "",
    )

    assert "Haushaltsplan" in response.answer
    assert "leere Antwort" in response.answer
    assert response.model_metadata == {"provider": "openai"}
