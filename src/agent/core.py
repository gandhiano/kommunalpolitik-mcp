"""Server-side agent orchestration for the web MVP."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any, Literal, Protocol

from mcp.types import TextContent

from src.tools import witzenhausen


AgentMode = Literal["research", "briefing", "motion_draft", "follow_up"]


@dataclass(frozen=True)
class AgentRequest:
    task: str
    mode: AgentMode = "research"
    topic: str | None = None
    actor: str | None = None
    meeting_id: str | None = None
    limit: int = 5


@dataclass(frozen=True)
class AgentSource:
    title: str | None
    url: str | None
    snippet: str | None = None
    document_id: str | None = None
    body_name: str | None = None
    meeting_date: str | None = None
    document_type: str | None = None


@dataclass(frozen=True)
class AgentAction:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResponse:
    mode: AgentMode
    answer: str
    sources: list[AgentSource]
    actions_taken: list[AgentAction]
    draft: dict[str, Any] | None = None
    provider: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentTools(Protocol):
    async def search_text(
        self,
        query: str,
        limit: int,
        document_type: str | None = None,
    ) -> list[AgentSource]: ...

    async def list_meetings(self, limit: int) -> list[dict[str, Any]]: ...

    async def get_meeting(self, meeting_id: str) -> dict[str, Any]: ...


class WitzenhausenAgentTools:
    async def search_text(
        self,
        query: str,
        limit: int,
        document_type: str | None = None,
    ) -> list[AgentSource]:
        payload = _payload(
            await witzenhausen.search_text(
                query=query,
                document_type=document_type,
                limit=limit,
            )
        )
        return [_source_from_search_result(row) for row in payload.get("results", [])]

    async def list_meetings(self, limit: int) -> list[dict[str, Any]]:
        payload = _payload(await witzenhausen.list_meetings(limit=limit))
        return list(payload.get("meetings", []))

    async def get_meeting(self, meeting_id: str) -> dict[str, Any]:
        return _payload(await witzenhausen.get_meeting(meeting_id=meeting_id))


async def run_agent(
    request: AgentRequest,
    tools: AgentTools | None = None,
    provider: Any | None = None,
) -> AgentResponse:
    from .providers import provider_from_env

    tools = tools or WitzenhausenAgentTools()
    provider = provider or provider_from_env()
    actions: list[AgentAction] = []
    context: dict[str, Any] = {"actions_taken": actions}

    if request.mode == "briefing" and request.meeting_id:
        actions.append(AgentAction("get_meeting", {"meeting_id": request.meeting_id}))
        context["meeting"] = await tools.get_meeting(request.meeting_id)
        query = _search_query(request)
        actions.append(AgentAction("search_text", {"query": query, "limit": request.limit}))
        sources = await tools.search_text(query=query, limit=request.limit)
    elif request.mode == "briefing":
        actions.append(AgentAction("list_meetings", {"limit": min(request.limit, 10)}))
        context["meetings"] = await tools.list_meetings(limit=min(request.limit, 10))
        query = _search_query(request)
        actions.append(AgentAction("search_text", {"query": query, "limit": request.limit}))
        sources = await tools.search_text(query=query, limit=request.limit)
    elif request.mode == "motion_draft":
        query = _search_query(request)
        actions.append(
            AgentAction(
                "search_text",
                {"query": query, "document_type": "motion", "limit": request.limit},
            )
        )
        sources = await tools.search_text(query=query, document_type="motion", limit=request.limit)
    else:
        query = _search_query(request)
        actions.append(AgentAction("search_text", {"query": query, "limit": request.limit}))
        sources = await tools.search_text(query=query, limit=request.limit)

    return await provider.generate(request, sources, context)


def _payload(contents: list[TextContent]) -> dict[str, Any]:
    if not contents:
        return {}
    return json.loads(contents[0].text)


def _source_from_search_result(row: dict[str, Any]) -> AgentSource:
    return AgentSource(
        title=row.get("document_name") or row.get("name"),
        url=row.get("url"),
        snippet=row.get("snippet") or row.get("text_preview"),
        document_id=row.get("document_id") or row.get("id"),
        body_name=row.get("body_name"),
        meeting_date=row.get("meeting_date"),
        document_type=row.get("document_type"),
    )


def _search_query(request: AgentRequest) -> str:
    if request.topic:
        return request.topic
    if request.mode == "briefing" and "nächste" in request.task.lower():
        return "Tagesordnung Sitzung Unterlagen"
    return request.task


def _deterministic_answer(
    request: AgentRequest,
    sources: list[AgentSource],
    context: dict[str, Any],
) -> str:
    if request.mode == "briefing":
        meeting_count = len(context.get("meetings", []))
        if request.meeting_id:
            return _answer_with_sources("Briefing-Grundlage fuer die ausgewaehlte Sitzung", sources)
        if meeting_count:
            return _answer_with_sources(f"Briefing-Grundlage mit {meeting_count} geladenen Sitzungen", sources)
        return _answer_with_sources("Briefing-Grundlage", sources)
    if request.mode == "motion_draft":
        return _answer_with_sources("Antragsentwurf-Vorbereitung mit gefundenen Praezedenzfaellen", sources)
    if request.mode == "follow_up":
        return _answer_with_sources("Folgefrage anhand der kommunalen Quellen vorbereitet", sources)
    return _answer_with_sources("Recherche anhand der kommunalen Quellen vorbereitet", sources)


def _answer_with_sources(prefix: str, sources: list[AgentSource]) -> str:
    if not sources:
        return f"{prefix}. Es wurden keine passenden Quellen im lokalen Korpus gefunden."
    lines = [f"{prefix}. Gefundene Quellen:"]
    for index, source in enumerate(sources, start=1):
        title = source.title or "unbenannte Quelle"
        date = f" ({source.meeting_date})" if source.meeting_date else ""
        lines.append(f"{index}. {title}{date}")
    return "\n".join(lines)


def _motion_template(request: AgentRequest, sources: list[AgentSource]) -> dict[str, Any]:
    return {
        "title": request.topic or request.task,
        "resolution": ["Die Stadtverordnetenversammlung wird gebeten, den Sachverhalt zu beraten."],
        "rationale": [
            "Dieser Entwurf ist eine strukturierte Vorlage aus dem retrieval-only Modus.",
            "Die Begruendung muss politisch und fachlich durch die Nutzerin oder den Nutzer geprueft werden.",
        ],
        "precedent_count": len(sources),
    }
