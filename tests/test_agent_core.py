from __future__ import annotations

import asyncio
from typing import Any

from src.agent.core import AgentRequest, AgentSource, run_agent


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
        return [{"id": "meeting-1", "title": "StVV", "meeting_date": "2026-01-01"}]

    async def get_meeting(self, meeting_id: str) -> dict[str, Any]:
        self.calls.append(("get_meeting", {"meeting_id": meeting_id}))
        return {"meeting": {"id": meeting_id, "title": "StVV"}, "agenda_items": []}


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


def test_research_mode_returns_sources_and_actions() -> None:
    tools = FakeTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="Verkehr", mode="research", limit=3),
            tools=tools,
        )
    )

    assert response.provider == "none"
    assert response.mode == "research"
    assert response.sources[0].title == "Antrag Verkehrswende"
    assert response.actions_taken[0].name == "search_text"
    assert tools.calls == [("search_text", {"query": "Verkehr", "limit": 12, "document_type": None})]


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

    assert [action.name for action in response.actions_taken] == ["list_meetings", "search_text", "search_text"]
    assert "Briefing" in response.answer
    assert tools.calls[0] == ("list_meetings", {"limit": 10})
    assert tools.calls[1] == ("search_text", {"query": "Haushalt", "limit": 16, "document_type": None})
    assert tools.calls[2] == ("search_text", {"query": "naechste Sitzung", "limit": 16, "document_type": None})


def test_briefing_for_next_meeting_uses_agenda_search_terms() -> None:
    tools = FakeTools()
    asyncio.run(
        run_agent(
            AgentRequest(task="Was steht in der nächsten Stadtverordnetenversammlung an?", mode="briefing"),
            tools=tools,
        )
    )

    assert tools.calls[1] == (
        "search_text",
        {"query": "Tagesordnung Sitzung Unterlagen", "limit": 16, "document_type": None},
    )
    assert tools.calls[2] == (
        "search_text",
        {"query": "steht nächsten Stadtverordnetenversammlung", "limit": 16, "document_type": None},
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
    assert response.actions_taken[0].arguments["document_type"] == "motion"
    assert tools.calls == [
        ("search_text", {"query": "Hortbetreuung sichern", "limit": 12, "document_type": "motion"})
    ]


def test_briefing_with_meeting_id_loads_meeting() -> None:
    tools = FakeTools()
    response = asyncio.run(
        run_agent(
            AgentRequest(task="TOP 7", mode="briefing", meeting_id="meeting-1"),
            tools=tools,
        )
    )

    assert [action.name for action in response.actions_taken] == ["get_meeting", "search_text", "search_text"]
    assert tools.calls[0] == ("get_meeting", {"meeting_id": "meeting-1"})
    assert tools.calls[1] == ("search_text", {"query": "TOP 7", "limit": 16, "document_type": None})
    assert tools.calls[2] == ("search_text", {"query": "TOP", "limit": 16, "document_type": None})
