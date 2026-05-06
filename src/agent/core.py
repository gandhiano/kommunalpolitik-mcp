"""Server-side agent orchestration for the web MVP."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re
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
    limit: int | None = None


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
        sources = await _collect_sources(request, tools, actions)
    elif request.mode == "briefing":
        meeting_limit = 10
        actions.append(AgentAction("list_meetings", {"limit": meeting_limit}))
        context["meetings"] = await tools.list_meetings(limit=meeting_limit)
        sources = await _collect_sources(request, tools, actions)
    elif request.mode == "motion_draft":
        sources = await _collect_sources(request, tools, actions, document_type="motion")
    else:
        sources = await _collect_sources(request, tools, actions)

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


async def _collect_sources(
    request: AgentRequest,
    tools: AgentTools,
    actions: list[AgentAction],
    document_type: str | None = None,
) -> list[AgentSource]:
    primary_query = _search_query(request)
    limit = _retrieval_limit(request.mode)
    sources = await _search_text(tools, actions, primary_query, limit, document_type)

    follow_up_query = _follow_up_query(request, primary_query)
    if follow_up_query and len(sources) < _target_source_count(request.mode):
        more_sources = await _search_text(tools, actions, follow_up_query, limit, document_type)
        sources = _dedupe_sources([*sources, *more_sources])

    sources = _apply_date_filter(request, sources, actions)
    return sources[:limit]


async def _search_text(
    tools: AgentTools,
    actions: list[AgentAction],
    query: str,
    limit: int,
    document_type: str | None,
) -> list[AgentSource]:
    arguments: dict[str, Any] = {"query": query, "limit": limit}
    if document_type:
        arguments["document_type"] = document_type
    actions.append(AgentAction("search_text", arguments))
    return await tools.search_text(query=query, limit=limit, document_type=document_type)


def _retrieval_limit(mode: AgentMode) -> int:
    if mode == "motion_draft":
        return 12
    if mode == "briefing":
        return 16
    return 12


def _target_source_count(mode: AgentMode) -> int:
    if mode == "briefing":
        return 8
    return 6


def _follow_up_query(request: AgentRequest, primary_query: str) -> str | None:
    if request.topic:
        return request.task if request.task != request.topic else None

    terms = [term for term in re.findall(r"[\wÄÖÜäöüß]+", request.task) if _useful_query_term(term)]
    if not terms:
        return None

    query = " ".join(terms[:8])
    return query if query and query != primary_query else None


def _useful_query_term(term: str) -> bool:
    return len(term) > 2 and term.lower() not in _QUERY_STOPWORDS


def _dedupe_sources(sources: list[AgentSource]) -> list[AgentSource]:
    seen: set[tuple[str | None, str | None, str | None]] = set()
    unique: list[AgentSource] = []
    for source in sources:
        key = (source.document_id, source.url, source.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique


def _apply_date_filter(
    request: AgentRequest,
    sources: list[AgentSource],
    actions: list[AgentAction],
) -> list[AgentSource]:
    start_year = _start_year(request.task)
    if not start_year:
        return sources

    filtered = [source for source in sources if not _source_year(source) or _source_year(source) >= start_year]
    removed = len(sources) - len(filtered)
    if removed:
        actions.append(AgentAction("filter_sources", {"meeting_date_from": f"{start_year}-01-01", "removed": removed}))
    return filtered


def _start_year(text: str) -> int | None:
    match = re.search(r"\b(?:seit|ab|nach)\s+(20\d{2}|19\d{2})\b", text.lower())
    return int(match.group(1)) if match else None


def _source_year(source: AgentSource) -> int | None:
    if not source.meeting_date:
        return _title_year(source.title)
    match = re.match(r"(\d{4})", source.meeting_date)
    return int(match.group(1)) if match else _title_year(source.title)


def _title_year(title: str | None) -> int | None:
    if not title:
        return None
    if match := re.search(r"\b(19\d{2}|20\d{2})\b", title):
        return int(match.group(1))
    if match := re.search(r"\b(19\d{2}|20\d{2})\d{4}\b", title):
        return int(match.group(1))
    if match := re.search(r"\b\d{1,2}\s+\d{1,2}\s+(\d{2})\b", title):
        year = int(match.group(1))
        return 2000 + year if year < 70 else 1900 + year
    return None


_QUERY_STOPWORDS = {
    "aber", "alle", "als", "auch", "auf", "aus", "bei", "bis", "das", "dass",
    "dem", "den", "der", "des", "die", "doch", "ein", "eine", "einem", "einen",
    "einer", "eines", "gab", "gibt", "haben", "hat", "hatte", "im", "in", "ist",
    "mit", "nach", "nicht", "noch", "oder", "seit", "sind", "und", "vom", "von",
    "vor", "war", "waren", "was", "welche", "welcher", "welches", "wenn", "wer",
    "werden", "wie", "wird", "wo", "zu", "zum", "zur", "über", "ueber",
}


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
