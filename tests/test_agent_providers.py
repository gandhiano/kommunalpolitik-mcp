from __future__ import annotations

from src.agent.core import AgentAction, AgentRequest, AgentSource
from src.agent.providers import NoneProvider, build_agent_prompt, provider_from_env


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
