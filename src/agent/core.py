"""Server-side agent orchestration for the web MVP."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import json
import os
import re
from typing import Any, Literal, Protocol

from mcp.types import TextContent

from src.tools import witzenhausen


AgentMode = Literal["research", "briefing", "motion_draft", "follow_up"]
ResearchDepth = Literal["quick", "auto", "deep"]


@dataclass(frozen=True)
class AgentRequest:
    task: str
    mode: AgentMode = "research"
    agent: str = "general"
    topic: str | None = None
    actor: str | None = None
    meeting_id: str | None = None
    research_depth: ResearchDepth = "auto"
    messages: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class RetrievalPlan:
    depth: ResearchDepth
    search_limit: int
    answer_source_limit: int
    target_sources: int
    max_searches: int
    complexity: int


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
    related_sources: list[AgentSource] = field(default_factory=list)
    draft: dict[str, Any] | None = None
    provider: str = "none"
    model_metadata: dict[str, Any] = field(default_factory=dict)

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

    if _agent_runtime() == "opencode":
        from .opencode_runtime import run_opencode_agent

        return await run_opencode_agent(request)

    tools = tools or WitzenhausenAgentTools()
    provider = provider or provider_from_env(request)
    actions: list[AgentAction] = []
    context: dict[str, Any] = {"actions_taken": actions}

    if _uses_tool_loop(provider):
        return await _run_tool_loop(request, tools, provider, actions, context)

    if request.mode == "briefing" and request.meeting_id:
        actions.append(AgentAction("get_meeting", {"meeting_id": request.meeting_id}))
        context["meeting"] = await tools.get_meeting(request.meeting_id)
        sources, related_sources = await _collect_sources(request, tools, actions)
    elif request.mode == "briefing" and _should_select_meeting_for_briefing(request):
        meeting_limit = 80
        actions.append(AgentAction("list_meetings", {"limit": meeting_limit}))
        context["meetings"] = await tools.list_meetings(limit=meeting_limit)
        selected_meeting = _select_meeting_for_briefing(request, context["meetings"])
        if selected_meeting:
            meeting_id = str(selected_meeting.get("id"))
            actions.append(
                AgentAction(
                    "select_meeting",
                    {
                        "meeting_id": meeting_id,
                        "body_name": selected_meeting.get("body_name"),
                        "meeting_date": selected_meeting.get("meeting_date"),
                        "selection": selected_meeting.get("selection"),
                    },
                )
            )
            actions.append(AgentAction("get_meeting", {"meeting_id": meeting_id}))
            context["meeting"] = await tools.get_meeting(meeting_id)
        sources, related_sources = await _collect_sources(request, tools, actions)
        if meeting_source := _source_from_meeting_context(context.get("meeting")):
            related_sources = _dedupe_sources([*sources, *related_sources])
            sources = [meeting_source]
    elif request.mode == "motion_draft":
        sources, related_sources = await _collect_sources(request, tools, actions, document_type="motion")
    else:
        sources, related_sources = await _collect_sources(request, tools, actions)

    context["related_sources"] = related_sources
    return await provider.generate(request, sources, context)


def _uses_tool_loop(provider: Any) -> bool:
    runtime = _agent_runtime()
    return runtime in {"tool-loop", "agent", "agentic"} and getattr(provider, "name", "none") != "none" and hasattr(provider, "next_agent_step")


def _agent_runtime() -> str:
    return os.environ.get("KOMMUNALPOLITIK_AGENT_RUNTIME", "tool-loop").strip().lower()


async def _run_tool_loop(
    request: AgentRequest,
    tools: AgentTools,
    provider: Any,
    actions: list[AgentAction],
    context: dict[str, Any],
) -> AgentResponse:
    transcript: list[dict[str, Any]] = []
    sources: list[AgentSource] = []
    related_sources: list[AgentSource] = []
    step_limit = _tool_loop_step_limit(request)
    actions.append(AgentAction("agent_start", {"runtime": "tool-loop", "max_steps": step_limit}))

    for step in range(1, step_limit + 1):
        decision = _validate_agent_decision(await provider.next_agent_step(request, transcript, sources, context), request)
        if thought := decision.get("thought"):
            actions.append(AgentAction("agent_thought", {"step": step, "thought": thought}))

        if final_answer := decision.get("final_answer"):
            context["related_sources"] = related_sources
            return AgentResponse(
                mode=request.mode,
                answer=str(final_answer).strip(),
                sources=sources[: _answer_source_limit(request)],
                actions_taken=actions,
                related_sources=related_sources,
                draft=_motion_template(request, sources) if request.mode == "motion_draft" else None,
                provider=getattr(provider, "name", "unknown"),
                model_metadata=_provider_metadata(provider),
            )

        tool_name = str(decision.get("tool") or "").strip()
        tool_args = decision.get("arguments") if isinstance(decision.get("arguments"), dict) else {}
        observation = await _execute_agent_tool(tool_name, tool_args, request, tools, actions, context)
        new_sources = observation.pop("_sources", [])
        if new_sources:
            sources = _dedupe_sources([*sources, *new_sources])
            ranked_sources = _prioritize_sources(request, _apply_date_filter(request, sources, actions), actions)
            sources = ranked_sources[: _answer_source_limit(request)]
            related_sources = ranked_sources[_answer_source_limit(request) :]
        transcript.append({"decision": decision, "observation": observation})

    context["related_sources"] = related_sources
    actions.append(AgentAction("agent_fallback", {"reason": "step_limit_reached"}))
    return await provider.generate(request, sources[: _answer_source_limit(request)], context)


def _tool_loop_step_limit(request: AgentRequest) -> int:
    if request.research_depth == "quick":
        return 3
    if request.research_depth == "deep":
        return 8
    return 5


def _answer_source_limit(request: AgentRequest) -> int:
    return _retrieval_plan(request).answer_source_limit


def _provider_metadata(provider: Any) -> dict[str, Any]:
    metadata = {"provider": getattr(provider, "name", "unknown")}
    if model := getattr(provider, "model", None):
        metadata["model"] = model
    return metadata


def _validate_agent_decision(decision: Any, request: AgentRequest) -> dict[str, Any]:
    if not isinstance(decision, dict):
        return {"tool": "search_text", "arguments": {"query": request.task}}
    if decision.get("final_answer"):
        return {"thought": str(decision.get("thought") or "")[:500], "final_answer": str(decision["final_answer"])}
    tool = str(decision.get("tool") or "search_text").strip()
    if tool not in {"search_text", "list_meetings", "get_meeting"}:
        tool = "search_text"
    arguments = decision.get("arguments") if isinstance(decision.get("arguments"), dict) else {}
    return {"thought": str(decision.get("thought") or "")[:500], "tool": tool, "arguments": arguments}


async def _execute_agent_tool(
    tool_name: str,
    arguments: dict[str, Any],
    request: AgentRequest,
    tools: AgentTools,
    actions: list[AgentAction],
    context: dict[str, Any],
) -> dict[str, Any]:
    if tool_name == "list_meetings":
        limit = _bounded_int(arguments.get("limit"), default=20, minimum=1, maximum=80)
        actions.append(AgentAction("list_meetings", {"limit": limit}))
        meetings = await tools.list_meetings(limit=limit)
        context["meetings"] = meetings
        return {"meetings": meetings[:10], "count": len(meetings)}

    if tool_name == "get_meeting":
        meeting_id = str(arguments.get("meeting_id") or request.meeting_id or "").strip()
        if not meeting_id:
            return {"error": "meeting_id is required"}
        actions.append(AgentAction("get_meeting", {"meeting_id": meeting_id}))
        meeting = await tools.get_meeting(meeting_id)
        context["meeting"] = meeting
        meeting_source = _source_from_meeting_context(meeting)
        return {"meeting": meeting, "_sources": [meeting_source] if meeting_source else []}

    query = str(arguments.get("query") or request.task).strip()[:500]
    limit = _bounded_int(arguments.get("limit"), default=12, minimum=1, maximum=40)
    document_type = _allowed_document_type(arguments.get("document_type"))
    results = await _search_text(tools, actions, query, limit, document_type)
    return {"results": _source_payloads(results[:10]), "count": len(results), "_sources": results}


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _allowed_document_type(value: Any) -> str | None:
    document_type = str(value or "").strip().lower()
    if document_type in {"motion", "minutes", "notice", "meeting", "other"}:
        return document_type
    return None


def _source_payloads(sources: list[AgentSource]) -> list[dict[str, Any]]:
    return [asdict(source) for source in sources]


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


def _source_from_meeting_context(meeting_context: Any) -> AgentSource | None:
    if not isinstance(meeting_context, dict):
        return None
    meeting = meeting_context.get("meeting")
    if not isinstance(meeting, dict):
        return None
    agenda_items = meeting_context.get("agenda_items", [])
    agenda_lines = []
    for item in agenda_items[:20]:
        if isinstance(item, dict):
            number = item.get("number") or "TOP"
            title = str(item.get("title") or "").replace("|", " ")
            agenda_lines.append(f"{number}: {title}")
    snippet = "\n".join(agenda_lines) if agenda_lines else "Keine Tagesordnungspunkte in den lokalen Daten gefunden."
    return AgentSource(
        title=f"Tagesordnung {meeting.get('body_name') or meeting.get('title') or 'Sitzung'}",
        url=meeting.get("detail_url"),
        snippet=snippet,
        document_id=f"meeting-{meeting.get('id')}",
        body_name=meeting.get("body_name"),
        meeting_date=meeting.get("meeting_date"),
        document_type="meeting",
    )


def _search_query(request: AgentRequest) -> str:
    if request.topic:
        return request.topic
    if request.mode == "briefing" and "nächste" in request.task.lower():
        return "Tagesordnung Sitzung Unterlagen"
    return request.task


def _select_meeting_for_briefing(request: AgentRequest, meetings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not meetings:
        return None

    body_hint = _body_hint(request.task)
    candidates = [meeting for meeting in meetings if not body_hint or body_hint in str(meeting.get("body_name") or "").lower()]
    if not candidates:
        return None

    today = date.today().isoformat()
    future = [meeting for meeting in candidates if str(meeting.get("meeting_date") or "") >= today]
    if future:
        selected = min(future, key=lambda meeting: str(meeting.get("meeting_date") or "9999-99-99"))
        return {**selected, "selection": "next_upcoming"}

    selected = max(candidates, key=lambda meeting: str(meeting.get("meeting_date") or "0000-00-00"))
    return {**selected, "selection": "latest_available_no_upcoming_found"}


def _should_select_meeting_for_briefing(request: AgentRequest) -> bool:
    task = request.task.lower()
    return any(term in task for term in ("nächste", "naechste", "sitzung", "tagesordnung", "top ", " stvv", "stadtverordnetenversammlung"))


def _body_hint(task: str) -> str | None:
    lowered = task.lower()
    if "stadtverordnetenversammlung" in lowered or "stvv" in lowered:
        return "stadtverordnetenversammlung"
    if "haupt" in lowered and "finanz" in lowered:
        return "haupt-, finanz- und rechtsausschuss"
    return None


async def _collect_sources(
    request: AgentRequest,
    tools: AgentTools,
    actions: list[AgentAction],
    document_type: str | None = None,
) -> tuple[list[AgentSource], list[AgentSource]]:
    primary_query = _search_query(request)
    plan = _retrieval_plan(request)
    actions.append(
        AgentAction(
            "plan_retrieval",
            {
                "depth": plan.depth,
                "complexity": plan.complexity,
                "search_limit": plan.search_limit,
                "answer_source_limit": plan.answer_source_limit,
                "target_sources": plan.target_sources,
                "max_searches": plan.max_searches,
            },
        )
    )

    sources: list[AgentSource] = []
    for query in _search_queries(request, primary_query)[: plan.max_searches]:
        more_sources = await _search_text(tools, actions, query, plan.search_limit, document_type)
        sources = _dedupe_sources([*sources, *more_sources])
        filtered_sources = _filter_sources_by_date(request, sources)
        if plan.depth != "deep" and len(filtered_sources) >= plan.target_sources:
            break

    sources = _prioritize_sources(request, _apply_date_filter(request, sources, actions), actions)
    answer_sources = sources[: plan.answer_source_limit]
    related_sources = sources[plan.answer_source_limit :]
    if related_sources:
        actions.append(AgentAction("rank_sources", {"used": len(answer_sources), "related": len(related_sources)}))
    return answer_sources, related_sources


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


def _retrieval_plan(request: AgentRequest) -> RetrievalPlan:
    complexity = _task_complexity(request)
    depth = request.research_depth

    if depth == "quick":
        return RetrievalPlan(depth=depth, search_limit=10, answer_source_limit=5, target_sources=4, max_searches=1, complexity=complexity)

    if depth == "deep":
        search_limit = 40 if request.mode == "briefing" else 36
        return RetrievalPlan(depth=depth, search_limit=search_limit, answer_source_limit=10, target_sources=12, max_searches=3, complexity=complexity)

    if complexity >= 4:
        search_limit = 32 if request.mode == "briefing" else 28
        return RetrievalPlan(depth=depth, search_limit=search_limit, answer_source_limit=10, target_sources=10, max_searches=3, complexity=complexity)

    if complexity >= 2:
        search_limit = 24 if request.mode == "briefing" else 20
        return RetrievalPlan(depth=depth, search_limit=search_limit, answer_source_limit=8, target_sources=8, max_searches=2, complexity=complexity)

    search_limit = 16 if request.mode == "briefing" else 12
    return RetrievalPlan(depth=depth, search_limit=search_limit, answer_source_limit=6, target_sources=5, max_searches=1, complexity=complexity)


def _task_complexity(request: AgentRequest) -> int:
    task = request.task.lower()
    terms = [term for term in re.findall(r"[\wÄÖÜäöüß]+", request.task) if _useful_query_term(term)]
    score = 0
    if len(terms) >= 5:
        score += 1
    if len(terms) >= 9:
        score += 1
    if re.search(r"\b(?:seit|ab|nach|zwischen|vor|bis)\s+(?:19|20)\d{2}\b", task):
        score += 1
    if any(word in task for word in (" oder ", " und ", "gegenargument", "risiko", "vergleich", "beschlüsse", "diskussionen")):
        score += 1
    if request.mode in {"briefing", "motion_draft"}:
        score += 2
    return score


def _search_queries(request: AgentRequest, primary_query: str) -> list[str]:
    queries = [primary_query]

    if follow_up_query := _follow_up_query(request, primary_query):
        queries.append(follow_up_query)

    if expansion := _domain_expansion_query(request):
        queries.append(expansion)

    unique_queries: list[str] = []
    for query in queries:
        if query and query not in unique_queries:
            unique_queries.append(query)
    return unique_queries


def _follow_up_query(request: AgentRequest, primary_query: str) -> str | None:
    if request.topic:
        return request.task if request.task != request.topic else None

    terms = [term for term in re.findall(r"[\wÄÖÜäöüß]+", request.task) if _useful_query_term(term)]
    if not terms:
        return None

    query = " ".join(terms[:8])
    return query if query and query != primary_query else None


def _domain_expansion_query(request: AgentRequest) -> str | None:
    task = request.task.lower()
    expansions: list[str] = []
    if any(term in task for term in ("haushalt", "haushaltsplan", "nachtrag", "investitionsprogramm")):
        expansions.extend(["Haushalt", "Haushaltsplan", "Nachtrag", "Jahresabschluss", "Investitionsprogramm"])
    if any(term in task for term in ("beschluss", "beschlüsse", "diskussion", "beratung")):
        expansions.extend(["Beschlussfassung", "Beratung", "Niederschrift", "Vorlage"])
    if any(term in task for term in ("nächste", "naechste", "sitzung", "tagesordnung")):
        expansions.extend(["Tagesordnung", "Einladung", "Vorlage", "Unterlagen"])
    if not expansions:
        return None
    return " ".join(dict.fromkeys(expansions))


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

    filtered = _filter_sources_by_date(request, sources)
    removed = len(sources) - len(filtered)
    if removed:
        actions.append(AgentAction("filter_sources", {"meeting_date_from": f"{start_year}-01-01", "removed": removed}))
    return filtered


def _prioritize_sources(
    request: AgentRequest,
    sources: list[AgentSource],
    actions: list[AgentAction],
) -> list[AgentSource]:
    if not _prefers_citywide_sources(request.task):
        return sources
    ranked = sorted(enumerate(sources), key=lambda item: (_citywide_rank(item[1]), item[0]))
    prioritized = [source for _, source in ranked]
    if prioritized != sources:
        actions.append(AgentAction("prioritize_sources", {"preference": "citywide", "count": len(sources)}))
    return prioritized


def _prefers_citywide_sources(task: str) -> bool:
    lowered = task.lower()
    return (
        any(term in lowered for term in ("fraktion", "grünen", "gruenen", "bündnis", "buendnis", "antrag", "anträge", "antraege"))
        and "ortsbeirat" not in lowered
    )


def _citywide_rank(source: AgentSource) -> int:
    body = (source.body_name or "").lower()
    if "stadtverordnetenversammlung" in body:
        return 0
    if body and "ortsbeirat" not in body:
        return 1
    if not body:
        return 2
    return 3


def _filter_sources_by_date(request: AgentRequest, sources: list[AgentSource]) -> list[AgentSource]:
    start_year = _start_year(request.task)
    if not start_year:
        return sources
    return [source for source in sources if not _source_year(source) or _source_year(source) >= start_year]


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
