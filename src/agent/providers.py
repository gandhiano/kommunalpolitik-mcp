"""LLM providers for the server-side kommunalpolitik agent."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import os
import time
from typing import Any, Protocol

import requests

from .core import AgentRequest, AgentResponse, AgentSource, _motion_template


class ProviderError(Exception):
    """Safe-to-return error raised by an upstream LLM provider."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class AgentProvider(Protocol):
    name: str

    async def generate(
        self,
        request: AgentRequest,
        sources: list[AgentSource],
        context: dict[str, Any],
    ) -> AgentResponse: ...

    async def next_agent_step(
        self,
        request: AgentRequest,
        transcript: list[dict[str, Any]],
        sources: list[AgentSource],
        context: dict[str, Any],
    ) -> dict[str, Any]: ...


class NoneProvider:
    name = "none"

    async def generate(
        self,
        request: AgentRequest,
        sources: list[AgentSource],
        context: dict[str, Any],
    ) -> AgentResponse:
        from .core import _deterministic_answer

        draft = _motion_template(request, sources) if request.mode == "motion_draft" else None
        return AgentResponse(
            mode=request.mode,
            answer=_deterministic_answer(request, sources, context),
            sources=sources,
            actions_taken=list(context.get("actions_taken", [])),
            related_sources=list(context.get("related_sources", [])),
            draft=draft,
            provider=self.name,
            model_metadata={"provider": self.name, "model": None},
        )


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def generate(
        self,
        request: AgentRequest,
        sources: list[AgentSource],
        context: dict[str, Any],
    ) -> AgentResponse:
        prompt = build_agent_prompt(request, sources, context)
        started_at = time.monotonic()
        answer = await asyncio.to_thread(self._complete, prompt)
        return _response_from_llm(
            self.name,
            request,
            sources,
            context,
            answer,
            {"provider": self.name, "model": self.model, "latency_ms": round((time.monotonic() - started_at) * 1000)},
        )

    async def next_agent_step(
        self,
        request: AgentRequest,
        transcript: list[dict[str, Any]],
        sources: list[AgentSource],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = build_agent_step_prompt(request, transcript, sources, context)
        answer = await asyncio.to_thread(self._complete, prompt)
        return _json_object(answer)

    def _complete(self, prompt: str) -> str:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 1800,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=90,
        )
        _raise_provider_error(response, self.name)
        payload = response.json()
        blocks = payload.get("content", [])
        return "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text").strip()


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def generate(
        self,
        request: AgentRequest,
        sources: list[AgentSource],
        context: dict[str, Any],
    ) -> AgentResponse:
        prompt = build_agent_prompt(request, sources, context)
        started_at = time.monotonic()
        answer = await asyncio.to_thread(self._complete, prompt)
        return _response_from_llm(
            self.name,
            request,
            sources,
            context,
            answer,
            {"provider": self.name, "model": self.model, "latency_ms": round((time.monotonic() - started_at) * 1000)},
        )

    async def next_agent_step(
        self,
        request: AgentRequest,
        transcript: list[dict[str, Any]],
        sources: list[AgentSource],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = build_agent_step_prompt(request, transcript, sources, context)
        answer = await asyncio.to_thread(self._complete, prompt)
        return _json_object(answer)

    def _complete(self, prompt: str) -> str:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=90,
        )
        _raise_provider_error(response, self.name)
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()


def provider_from_env(request: AgentRequest | None = None) -> AgentProvider:
    provider = os.environ.get("KOMMUNALPOLITIK_LLM_PROVIDER", "none").strip().lower()

    if provider == "none":
        return NoneProvider()
    if provider == "anthropic":
        api_key = _required_env("ANTHROPIC_API_KEY")
        return AnthropicProvider(api_key=api_key, model=_model_from_env(request, "claude-3-5-sonnet-latest"))
    if provider == "openai":
        api_key = _required_env("OPENAI_API_KEY")
        return OpenAIProvider(api_key=api_key, model=_model_from_env(request, "gpt-4o-mini"))
    if provider == "openai-compatible":
        api_key = _required_env("KOMMUNALPOLITIK_LLM_API_KEY")
        base_url = _required_env("KOMMUNALPOLITIK_LLM_BASE_URL")
        return OpenAIProvider(
            api_key=api_key,
            model=_model_from_env(request, _required_env("KOMMUNALPOLITIK_LLM_MODEL")),
            base_url=base_url,
        )
    raise ValueError(f"Unsupported KOMMUNALPOLITIK_LLM_PROVIDER: {provider}")


def _model_from_env(request: AgentRequest | None, fallback: str) -> str:
    default = os.environ.get("KOMMUNALPOLITIK_LLM_MODEL") or fallback
    if request is None:
        return default
    if request.research_depth == "quick":
        return os.environ.get("KOMMUNALPOLITIK_MODEL_QUICK") or default
    if request.research_depth == "deep" or request.mode in {"motion_draft", "follow_up"}:
        return os.environ.get("KOMMUNALPOLITIK_MODEL_STRONG") or default
    return os.environ.get("KOMMUNALPOLITIK_MODEL_BALANCED") or default


SYSTEM_PROMPT = """Du bist ein spezialisierter kommunalpolitischer Arbeitsassistent fuer Witzenhausen.
Du arbeitest fuer Fraktionsmitglieder und musst praktisch nutzbare, quellengebundene Ergebnisse liefern.

Harte Regeln:
- Nutze ausschliesslich die gelieferten Quellen als Tatsachengrundlage.
- Zitiere konkrete Quellen mit [1], [2] usw. bei jeder faktischen Aussage.
- Unterscheide klar zwischen belegten Fakten, politischer Einordnung und offenen Fragen.
- Wenn die Quellenlage nicht reicht, sage das deutlich und nenne die fehlende Recherche.
- Erfinde keine Beschluesse, Namen, Termine, Rechtsfolgen oder Mehrheiten.
- Schreibe auf Deutsch, sachlich, knapp und arbeitspraktisch.
- Gib keine generische Datenbank-Zusammenfassung aus; beantworte die Aufgabe.
"""


def build_agent_step_prompt(
    request: AgentRequest,
    transcript: list[dict[str, Any]],
    sources: list[AgentSource],
    context: dict[str, Any],
) -> str:
    return f"""Du bist ein tool-nutzender kommunalpolitischer Agent.

Aufgabe: {request.task}
Modus: {request.mode}
Recherche-Tiefe: {request.research_depth}

Du darfst genau eine Aktion als JSON-Objekt ausgeben, ohne Markdown.

Erlaubte Tool-Aktionen:
{{"thought":"kurze Begruendung","tool":"search_text","arguments":{{"query":"Suchanfrage","limit":12,"document_type":null}}}}
{{"thought":"kurze Begruendung","tool":"list_meetings","arguments":{{"limit":20}}}}
{{"thought":"kurze Begruendung","tool":"get_meeting","arguments":{{"meeting_id":"..."}}}}

Wenn Du genug Evidenz hast, antworte final:
{{"thought":"kurze Begruendung","final_answer":"Markdown-Antwort mit Quellenverweisen [1], [2] ..."}}

Werkzeugregeln:
- Nutze search_text fuer inhaltliche Recherche ueber Protokolle, Vorlagen, Antraege, Bekanntmachungen und Textauszuege.
- Nutze list_meetings/get_meeting nur fuer konkrete Sitzung, Tagesordnung, TOP oder naechste Sitzung.
- Bei Fraktionslinien, frueheren Antraegen, Strategie oder Schwachstellen ueber Zeit suche breit im Korpus, nicht nur in der naechsten Sitzung.
- Fuer Antraege/Fraktionen bevorzuge Suchanfragen mit Stadtverordnetenversammlung, Ausschuss, Antrag, Fraktion, Gruene/Buendnis 90.
- final_answer darf nur Fakten aus den Quellen/Beobachtungen verwenden und muss Quellen mit [n] zitieren.

Bisherige Quellen:
{_sources_for_agent_prompt(sources)}

Ausgewaehlte Sitzung, falls vorhanden:
{_short_json(context.get("meeting"))}

Bisheriger Verlauf:
{_short_json(transcript)}
"""


def _sources_for_agent_prompt(sources: list[AgentSource]) -> str:
    if not sources:
        return "Noch keine Quellen."
    lines = []
    for index, source in enumerate(sources[:12], start=1):
        lines.append(f"[{index}] {source.title or 'Unbenannte Quelle'}")
        if source.meeting_date or source.body_name:
            lines.append(f"    Kontext: {source.meeting_date or '?'} / {source.body_name or '?'}")
        if source.snippet:
            lines.append(f"    Auszug: {source.snippet[:1000]}")
    return "\n".join(lines)


def _short_json(value: Any) -> str:
    if value is None:
        return "-"
    return json.dumps(value, ensure_ascii=False, default=str)[:6000]


def build_agent_prompt(
    request: AgentRequest,
    sources: list[AgentSource],
    context: dict[str, Any],
) -> str:
    lines = [
        f"Modus: {request.mode}",
        f"Aufgabe: {request.task}",
        "",
        "Rechercheweg:",
    ]
    for action in context.get("actions_taken", []):
        lines.append(f"- {action.name}: {action.arguments}")

    if meetings := context.get("meetings"):
        lines.extend(["", "Geladene Sitzungen:"])
        for meeting in meetings[:5]:
            lines.append(f"- {meeting.get('meeting_date')}: {meeting.get('title')} ({meeting.get('body_name')})")

    if meeting := context.get("meeting"):
        meeting_meta = meeting.get("meeting") if isinstance(meeting, dict) else None
        agenda_items = meeting.get("agenda_items", []) if isinstance(meeting, dict) else []
        lines.extend(["", "Ausgewaehlte Sitzung:", str(meeting_meta or meeting)[:1200]])
        if agenda_items:
            lines.append("Tagesordnung der ausgewaehlten Sitzung:")
            for item in agenda_items[:30]:
                number = item.get("number") or "TOP"
                title = str(item.get("title") or "").replace("|", " ")
                reference = f" ({item.get('paper_reference')})" if item.get("paper_reference") else ""
                lines.append(f"- {number}: {title[:500]}{reference}")
        elif meeting_meta:
            lines.append("Keine Tagesordnungspunkte in den lokalen Daten fuer diese Sitzung gefunden.")

    lines.extend(["", "Quellen:"])
    if not sources:
        lines.append("Keine passenden Quellen gefunden.")
    for index, source in enumerate(sources, start=1):
        lines.append(f"[{index}] {source.title or 'Unbenannte Quelle'}")
        if source.meeting_date or source.body_name:
            lines.append(f"    Kontext: {source.meeting_date or '?'} / {source.body_name or '?'}")
        if source.url:
            lines.append(f"    URL: {source.url}")
        if source.snippet:
            lines.append(f"    Auszug: {source.snippet[:1600]}")

    lines.extend(["", _mode_instruction(request.mode)])
    return "\n".join(lines)


def _json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Agent step must be a JSON object")
    return payload


def _mode_instruction(mode: str) -> str:
    if mode == "briefing":
        return """Antworte exakt in dieser Markdown-Struktur:
## Kurzbriefing
3-5 Bulletpoints mit den wichtigsten belegten Punkten.

## Relevante Quellen
Liste die wichtigsten Quellen mit [n], Datum/Gremium und kurzer Relevanz.

## Politische Einordnung
Was bedeutet das fuer die Fraktionsarbeit? Nur vorsichtige Einordnung, keine erfundenen Fakten.

## Rueckfragen fuer die Sitzung
Konkrete Fragen, die ein Fraktionsmitglied stellen koennte.

## Unsicherheiten
Was ist aus den Quellen nicht klar?"""
    if mode == "motion_draft":
        return """Antworte exakt in dieser Markdown-Struktur:
## Arbeitstitel
Ein praeziser Antragstitel.

## Beschlussvorschlag
Konkreter, editierbarer Beschlussvorschlag als nummerierte Liste.

## Begruendung
Sachliche Begruendung mit Quellenverweisen [n].

## Praezedenzfaelle
Welche frueheren Antraege/Dokumente wurden als Stil- oder Inhaltsvorlage genutzt?

## Offene Pruefpunkte
Was muss politisch, rechtlich oder fachlich noch geprueft werden?"""
    if mode == "follow_up":
        return """Antworte exakt in dieser Markdown-Struktur:
## Antwort
Direkte Antwort auf die Nachfrage mit Quellenverweisen.

## Belege
Die wichtigsten Quellen und was sie belegen.

## Naechste Recherche
Welche Anschlussfrage sollte als naechstes geklaert werden?"""
    return """Antworte exakt in dieser Markdown-Struktur:
## Antwort
Direkte, knappe Antwort auf die Recherchefrage mit Quellenverweisen [n].

## Belege
Bulletpoints mit Quelle, Datum/Gremium und relevanter Aussage.

## Einordnung
Vorsichtige politische oder sachliche Einordnung, klar getrennt von Fakten.

## Unsicherheiten
Was bleibt offen oder braucht weitere Recherche?"""


def _response_from_llm(
    provider: str,
    request: AgentRequest,
    sources: list[AgentSource],
    context: dict[str, Any],
    answer: str,
    model_metadata: dict[str, Any] | None = None,
) -> AgentResponse:
    if not answer.strip():
        from .core import _deterministic_answer

        answer = (
            f"{_deterministic_answer(request, sources, context)}\n\n"
            "Hinweis: Der konfigurierte LLM-Provider hat eine leere Antwort geliefert."
        )
    return AgentResponse(
        mode=request.mode,
        answer=answer,
        sources=sources,
        actions_taken=list(context.get("actions_taken", [])),
        related_sources=list(context.get("related_sources", [])),
        draft=_motion_template(request, sources) if request.mode == "motion_draft" else None,
        provider=provider,
        model_metadata=model_metadata or {"provider": provider},
    )


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required for the configured LLM provider")
    return value


def _raise_provider_error(response: requests.Response, provider: str) -> None:
    if response.ok:
        return

    message = _provider_error_message(response, provider)
    status_code = response.status_code if response.status_code in {400, 401, 403, 408, 409, 429} else 502
    raise ProviderError(status_code=status_code, message=message)


def _provider_error_message(response: requests.Response, provider: str) -> str:
    fallback = f"{provider} provider request failed with HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        return fallback

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        detail = error.get("message") or error.get("type") or fallback
    elif isinstance(error, str):
        detail = error
    else:
        detail = fallback

    if response.status_code == 429:
        return f"{provider} provider rate limit or quota exceeded: {detail}"
    if response.status_code in {401, 403}:
        return f"{provider} provider authentication failed: {detail}"
    return f"{provider} provider error: {detail}"


def source_payloads(sources: list[AgentSource]) -> list[dict[str, Any]]:
    return [asdict(source) for source in sources]
