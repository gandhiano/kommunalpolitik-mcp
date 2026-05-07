from __future__ import annotations

import asyncio
from typing import Any

from src.agent.core import AgentRequest, AgentResponse, AgentSource, run_agent


class FakeTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def search_text(
        self,
        query: str,
        limit: int,
        document_type: str | None = None,
    ) -> list[AgentSource]:
        self.calls.append(
            (
                "search_text",
                {"query": query, "limit": limit, "document_type": document_type},
            )
        )
        return [
            AgentSource(
                title="Antrag Verkehrswende",
                url="https://example.invalid/doc",
                snippet="Die Fraktion beantragt sichere Radwege.",
                document_id="doc-1",
                body_name="Stadtverordnetenversammlung",
                meeting_date="2025-05-01",
                document_type=document_type or "motion",
            )
        ]

    async def list_meetings(self, limit: int) -> list[dict[str, Any]]:
        self.calls.append(("list_meetings", {"limit": limit}))
        return [
            {"id": "meeting-ob", "title": "Ortsbeirat", "body_name": "Ortsbeirat", "meeting_date": "2026-01-01"},
            {"id": "meeting-1", "title": "StVV", "body_name": "Stadtverordnetenversammlung", "meeting_date": "2026-01-02"},
        ]

    async def get_meeting(self, meeting_id: str) -> dict[str, Any]:
        self.calls.append(("get_meeting", {"meeting_id": meeting_id}))
        return {
            "meeting": {
                "id": meeting_id,
                "title": "StVV",
                "body_name": "Stadtverordnetenversammlung",
                "meeting_date": "2026-01-02",
                "detail_url": "https://example.invalid/meeting",
            },
            "agenda_items": [{"number": "Ö 1", "title": "Wahl der Stadtverordnetenvorsteherin"}],
        }


class DateFilterTools(FakeTools):
    async def search_text(
        self,
        query: str,
        limit: int,
        document_type: str | None = None,
    ) -> list[AgentSource]:
        self.calls.append(("search_text", {"query": query, "limit": limit, "document_type": document_type}))
        return [
            AgentSource(title="Alter Haushalt", url="https://example.invalid/old", meeting_date="2020-09-29"),
            AgentSource(title="Protokoll SVV 29 09 20", url="https://example.invalid/old-title"),
            AgentSource(title="Neuer Haushalt", url="https://example.invalid/new", meeting_date="2022-11-08"),
            AgentSource(title="Haushaltsplan ohne Sitzungsdatum", url="https://example.invalid/plan"),
        ]


class ManySourcesTools(FakeTools):
    async def search_text(
        self,
        query: str,
        limit: int,
        document_type: str | None = None,
    ) -> list[AgentSource]:
        self.calls.append(("search_text", {"query": query, "limit": limit, "document_type": document_type}))
        return [
            AgentSource(title=f"Quelle {index}", url=f"https://example.invalid/{index}", document_id=f"doc-{index}")
            for index in range(limit)
        ]


class MixedBodiesTools(FakeTools):
    async def search_text(
        self,
        query: str,
        limit: int,
        document_type: str | None = None,
    ) -> list[AgentSource]:
        self.calls.append(("search_text", {"query": query, "limit": limit, "document_type": document_type}))
        return [
            AgentSource(title="Ortsbeirat Verkehr", url="https://example.invalid/ob", body_name="Ortsbeirat Wendershausen"),
            AgentSource(title="StVV Verkehr", url="https://example.invalid/stvv", body_name="Stadtverordnetenversammlung"),
            AgentSource(title="Ausschuss Verkehr", url="https://example.invalid/ausschuss", body_name="Stadtentwicklungs-, Umwelt- und Energieausschuss"),
        ]


class ToolLoopProvider:
    name = "tool-loop-test"

    def __init__(self, steps: list[dict[str, Any]]) -> None:
        self.steps = steps
        self.model = "test-model"

    async def next_agent_step(
        self,
        _request: AgentRequest,
        _transcript: list[dict[str, Any]],
        _sources: list[AgentSource],
        _context: dict[str, Any],
    ) -> dict[str, Any]:
        return self.steps.pop(0)

    async def generate(
        self,
        request: AgentRequest,
        sources: list[AgentSource],
        context: dict[str, Any],
    ) -> AgentResponse:
        return AgentResponse(
            mode=request.mode,
            answer="fallback answer",
            sources=sources,
            actions_taken=list(context.get("actions_taken", [])),
            provider=self.name,
        )


def test_research_mode_returns_sources_and_actions() -> None:
    tools = FakeTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="Verkehr", mode="research"),
            tools=tools,
        )
    )

    assert response.provider == "none"
    assert response.mode == "research"
    assert response.sources[0].title == "Antrag Verkehrswende"
    assert response.actions_taken[0].name == "plan_retrieval"
    assert response.actions_taken[0].arguments == {
        "depth": "auto",
        "complexity": 0,
        "search_limit": 12,
        "answer_source_limit": 6,
        "target_sources": 5,
        "max_searches": 1,
    }
    assert tools.calls == [("search_text", {"query": "Verkehr", "limit": 12, "document_type": None})]


def test_agent_splits_used_and_related_sources() -> None:
    tools = ManySourcesTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="Verkehr", mode="research"),
            tools=tools,
        )
    )

    assert len(response.sources) == 6
    assert len(response.related_sources) == 6
    assert response.actions_taken[-1].name == "rank_sources"
    assert response.actions_taken[-1].arguments == {"used": 6, "related": 6}


def test_complex_research_uses_larger_limit_and_iterates() -> None:
    tools = FakeTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="Welche Beschlüsse oder Diskussionen gab es zum Haushalt seit 2021?", mode="research"),
            tools=tools,
        )
    )

    assert response.actions_taken[0].arguments == {
        "depth": "auto",
        "complexity": 2,
        "search_limit": 20,
        "answer_source_limit": 8,
        "target_sources": 8,
        "max_searches": 2,
    }
    assert tools.calls == [
        (
            "search_text",
            {"query": "Welche Beschlüsse oder Diskussionen gab es zum Haushalt seit 2021?", "limit": 20, "document_type": None},
        ),
        (
            "search_text",
            {"query": "Beschlüsse Diskussionen Haushalt 2021", "limit": 20, "document_type": None},
        ),
    ]


def test_deep_research_runs_available_search_iterations() -> None:
    tools = FakeTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="Haushalt Beschlüsse", mode="research", research_depth="deep"),
            tools=tools,
        )
    )

    assert response.actions_taken[0].arguments["depth"] == "deep"
    assert response.actions_taken[0].arguments["max_searches"] == 3
    assert [call[1]["limit"] for call in tools.calls] == [36, 36]


def test_research_since_year_filters_older_meeting_sources() -> None:
    tools = DateFilterTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="Welche Diskussionen gab es zum Haushalt seit 2021?", mode="research"),
            tools=tools,
        )
    )

    assert [source.title for source in response.sources] == ["Neuer Haushalt", "Haushaltsplan ohne Sitzungsdatum"]
    assert response.actions_taken[-1].name == "filter_sources"
    assert response.actions_taken[-1].arguments == {"meeting_date_from": "2021-01-01", "removed": 2}


def test_briefing_mode_lists_meetings_before_searching() -> None:
    tools = FakeTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="naechste Sitzung", mode="briefing", topic="Haushalt"),
            tools=tools,
        )
    )

    assert [action.name for action in response.actions_taken] == ["list_meetings", "select_meeting", "get_meeting", "plan_retrieval", "search_text", "search_text"]
    assert "Briefing" in response.answer
    assert tools.calls[0] == ("list_meetings", {"limit": 80})
    assert tools.calls[1] == ("get_meeting", {"meeting_id": "meeting-1"})
    assert tools.calls[2] == ("search_text", {"query": "Haushalt", "limit": 24, "document_type": None})
    assert tools.calls[3] == ("search_text", {"query": "naechste Sitzung", "limit": 24, "document_type": None})
    assert response.sources[0].title == "Tagesordnung Stadtverordnetenversammlung"
    assert "Wahl der Stadtverordnetenvorsteherin" in (response.sources[0].snippet or "")


def test_briefing_for_next_meeting_uses_agenda_search_terms() -> None:
    tools = FakeTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="Was steht in der nächsten Stadtverordnetenversammlung an?", mode="briefing"),
            tools=tools,
        )
    )

    assert response.actions_taken[1].arguments["body_name"] == "Stadtverordnetenversammlung"
    assert tools.calls[2] == (
        "search_text",
        {"query": "Tagesordnung Sitzung Unterlagen", "limit": 24, "document_type": None},
    )
    assert tools.calls[3] == (
        "search_text",
        {"query": "steht nächsten Stadtverordnetenversammlung", "limit": 24, "document_type": None},
    )


def test_motion_draft_mode_uses_motion_filter_and_returns_template() -> None:
    tools = FakeTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="Hortbetreuung sichern", mode="motion_draft"),
            tools=tools,
        )
    )

    assert response.draft is not None
    assert response.draft["title"] == "Hortbetreuung sichern"
    assert response.draft["precedent_count"] == 1
    assert response.actions_taken[1].arguments["document_type"] == "motion"
    assert tools.calls == [("search_text", {"query": "Hortbetreuung sichern", "limit": 20, "document_type": "motion"})]


def test_briefing_with_meeting_id_loads_meeting() -> None:
    tools = FakeTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="TOP 7", mode="briefing", meeting_id="meeting-1"),
            tools=tools,
        )
    )

    assert [action.name for action in response.actions_taken] == ["get_meeting", "plan_retrieval", "search_text", "search_text"]
    assert tools.calls[0] == ("get_meeting", {"meeting_id": "meeting-1"})
    assert tools.calls[1] == ("search_text", {"query": "TOP 7", "limit": 24, "document_type": None})
    assert tools.calls[2] == ("search_text", {"query": "TOP", "limit": 24, "document_type": None})


def test_briefing_without_meeting_intent_does_not_select_next_meeting() -> None:
    tools = FakeTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="Finde frühere Anträge der Grünen zum Thema Verkehr", mode="briefing"),
            tools=tools,
        )
    )

    assert "list_meetings" not in [action.name for action in response.actions_taken]
    assert "select_meeting" not in [action.name for action in response.actions_taken]
    assert tools.calls[0] == ("search_text", {"query": "Finde frühere Anträge der Grünen zum Thema Verkehr", "limit": 24, "document_type": None})


def test_citywide_fraction_queries_prioritize_stvv_over_ortsbeirat() -> None:
    tools = MixedBodiesTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="Finde frühere Anträge der Grünen zum Thema Verkehr", mode="research"),
            tools=tools,
        )
    )

    assert [source.body_name for source in response.sources[:3]] == [
        "Stadtverordnetenversammlung",
        "Stadtentwicklungs-, Umwelt- und Energieausschuss",
        "Ortsbeirat Wendershausen",
    ]
    assert response.actions_taken[-1].name == "prioritize_sources"


def test_tool_loop_provider_controls_search_and_final_answer() -> None:
    tools = FakeTools()
    provider = ToolLoopProvider(
        [
            {"thought": "Search for Green traffic motions.", "tool": "search_text", "arguments": {"query": "Grüne Verkehr Antrag", "limit": 7, "document_type": "motion"}},
            {"thought": "Enough evidence.", "final_answer": "## Antwort\nDie Quelle belegt sichere Radwege [1]."},
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentRequest(task="Finde frühere Anträge der Grünen zum Thema Verkehr", mode="research"),
            tools=tools,
            provider=provider,
        )
    )

    assert response.provider == "tool-loop-test"
    assert response.answer == "## Antwort\nDie Quelle belegt sichere Radwege [1]."
    assert [action.name for action in response.actions_taken] == ["agent_start", "agent_thought", "search_text", "agent_thought"]
    assert tools.calls == [("search_text", {"query": "Grüne Verkehr Antrag", "limit": 7, "document_type": "motion"})]


def test_tool_loop_can_list_and_get_meetings() -> None:
    tools = FakeTools()
    provider = ToolLoopProvider(
        [
            {"tool": "list_meetings", "arguments": {"limit": 5}},
            {"tool": "get_meeting", "arguments": {"meeting_id": "meeting-1"}},
            {"final_answer": "## Kurzbriefing\nTOP 1 ist relevant [1]."},
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentRequest(task="Was steht in der nächsten Stadtverordnetenversammlung an?", mode="briefing"),
            tools=tools,
            provider=provider,
        )
    )

    assert tools.calls[:2] == [("list_meetings", {"limit": 5}), ("get_meeting", {"meeting_id": "meeting-1"})]
    assert response.sources[0].title == "Tagesordnung Stadtverordnetenversammlung"
