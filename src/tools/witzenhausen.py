"""MCP tools for locally ingested municipal politics data."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from mcp import Tool
from mcp.types import TextContent


DEFAULT_DB_PATH = Path("data/witzenhausen/witzenhausen.sqlite")


def _db_path() -> Path:
    return Path(os.environ.get("KOMMUNALPOLITIK_DB_PATH", DEFAULT_DB_PATH))


def _municipality() -> dict[str, str]:
    return {
        "id": os.environ.get("KOMMUNALPOLITIK_MUNICIPALITY_ID", "witzenhausen"),
        "name": os.environ.get("KOMMUNALPOLITIK_MUNICIPALITY_NAME", "Witzenhausen"),
    }


def _connect() -> sqlite3.Connection:
    db_path = _db_path()
    if not db_path.exists():
        raise FileNotFoundError(
            f"Municipal politics database not found at {db_path}. Run the ingestion command for your municipality first."
        )
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _content(payload: dict[str, Any]) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


async def list_bodies(limit: int = 100) -> list[TextContent]:
    """List locally ingested bodies/gremia."""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, name, detail_url, meeting_list_url FROM bodies ORDER BY name LIMIT ?",
            (limit,),
        ).fetchall()
    return _content({"municipality": _municipality(), "bodies": [_row_to_dict(row) for row in rows], "total": len(rows)})


async def list_meetings(
    body_id: str | None = None,
    year: int | None = None,
    limit: int = 20,
) -> list[TextContent]:
    """List locally ingested meetings."""
    clauses: list[str] = []
    params: list[Any] = []
    if body_id:
        clauses.append("body_id = ?")
        params.append(body_id)
    if year:
        clauses.append("meeting_date LIKE ?")
        params.append(f"{year}-%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, body_id, body_name, title, meeting_date, meeting_time, location, detail_url
            FROM meetings
            {where}
            ORDER BY meeting_date DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return _content({"municipality": _municipality(), "meetings": [_row_to_dict(row) for row in rows], "total": len(rows)})


async def get_meeting(meeting_id: str) -> list[TextContent]:
    """Get one meeting with agenda items and documents."""
    with _connect() as connection:
        meeting = connection.execute(
            "SELECT * FROM meetings WHERE id = ?",
            (meeting_id,),
        ).fetchone()
        if not meeting:
            return _content({"error": "Meeting not found", "meeting_id": meeting_id})

        agenda_items = connection.execute(
            """
            SELECT number, title, paper_reference, paper_url, public, sort_order
            FROM agenda_items
            WHERE meeting_id = ?
            ORDER BY sort_order
            """,
            (meeting_id,),
        ).fetchall()
        documents = connection.execute(
            """
            SELECT id, document_type, label, name, url, file_path, sha256, size_bytes
            FROM documents
            WHERE source_type = 'meeting' AND source_id = ?
            ORDER BY document_type, name
            """,
            (meeting_id,),
        ).fetchall()

    return _content(
        {
            "meeting": _row_to_dict(meeting),
            "agenda_items": [_row_to_dict(row) for row in agenda_items],
            "documents": [_row_to_dict(row) for row in documents],
        }
    )


async def search_documents(
    query: str,
    document_type: str | None = None,
    limit: int = 10,
) -> list[TextContent]:
    """Search locally extracted document text and document names."""
    like = f"%{query}%"
    clauses = ["(d.name LIKE ? OR t.text LIKE ?)"]
    params: list[Any] = [like, like]
    if document_type:
        clauses.append("d.document_type = ?")
        params.append(document_type)
    params.append(limit)

    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT
                d.id,
                d.document_type,
                d.label,
                d.name,
                d.url,
                d.file_path,
                d.source_type,
                d.source_id,
                substr(t.text, 1, 800) AS text_preview
            FROM documents d
            LEFT JOIN document_text t ON t.document_id = d.id
            WHERE {' AND '.join(clauses)}
            ORDER BY d.downloaded_at DESC, d.first_seen_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    return _content({"municipality": _municipality(), "query": query, "results": [_row_to_dict(row) for row in rows], "total": len(rows)})


async def get_document_text(document_id: str) -> list[TextContent]:
    """Return extracted full text for a downloaded document."""
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT d.id, d.document_type, d.name, d.url, d.file_path, t.text, t.text_path
            FROM documents d
            LEFT JOIN document_text t ON t.document_id = d.id
            WHERE d.id = ?
            """,
            (document_id,),
        ).fetchone()

    if not row:
        return _content({"error": "Document not found", "document_id": document_id})
    if not row["text"]:
        return _content(
            {
                "error": "Document text not extracted yet",
                "document_id": document_id,
                "hint": "Run text extraction for your municipality first.",
            }
        )
    return _content({"document": _row_to_dict(row)})


async def search_text(
    query: str,
    from_date: str | None = None,
    to_date: str | None = None,
    body: str | None = None,
    document_type: str | None = None,
    limit: int = 20,
) -> list[TextContent]:
    """Search chunked full text with date/body/type filters and compact snippets."""
    clauses = ["document_chunks_fts MATCH ?"]
    params: list[Any] = [_fts_query(query)]
    if from_date:
        clauses.append("c.meeting_date >= ?")
        params.append(from_date)
    if to_date:
        clauses.append("c.meeting_date <= ?")
        params.append(to_date)
    if body:
        clauses.append("c.body_name LIKE ?")
        params.append(f"%{body}%")
    if document_type:
        clauses.append("c.document_type = ?")
        params.append(document_type)
    params.append(limit)

    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT
                c.id AS chunk_id,
                c.document_id,
                c.document_type,
                c.document_name,
                c.source_type,
                c.source_id,
                c.body_name,
                c.meeting_date,
                c.page_number,
                d.url,
                substr(c.text, 1, 1200) AS snippet,
                bm25(document_chunks_fts) AS rank
            FROM document_chunks_fts
            JOIN document_chunks c ON c.id = document_chunks_fts.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE {' AND '.join(clauses)}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ).fetchall()
    return _content({"municipality": _municipality(), "query": query, "results": [_row_to_dict(row) for row in rows], "total": len(rows)})


async def find_actor_topics(
    actor: str,
    topic: str | None = None,
    actor_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    body: str | None = None,
    document_type: str | None = "minutes",
    confidence: str | None = None,
    limit: int = 30,
) -> list[TextContent]:
    """Find evidence snippets for a person, party, or faction over a period."""
    clauses = ["a.actor_name LIKE ?"]
    params: list[Any] = [f"%{actor}%"]
    if actor_type:
        clauses.append("a.actor_type = ?")
        params.append(actor_type)
    if from_date:
        clauses.append("a.meeting_date >= ?")
        params.append(from_date)
    if to_date:
        clauses.append("a.meeting_date <= ?")
        params.append(to_date)
    if body:
        clauses.append("a.body_name LIKE ?")
        params.append(f"%{body}%")
    if document_type:
        clauses.append("a.document_type = ?")
        params.append(document_type)
    if confidence:
        clauses.append("a.confidence = ?")
        params.append(confidence)
    if topic:
        clauses.append("a.snippet LIKE ?")
        params.append(f"%{topic}%")
    params.append(limit)

    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT
                a.actor_name,
                a.actor_type,
                a.verb,
                a.confidence,
                a.document_id,
                a.chunk_id,
                a.document_type,
                a.document_name,
                a.body_name,
                a.meeting_date,
                a.source_type,
                a.source_id,
                d.url,
                a.snippet
            FROM actor_mentions a
            JOIN document_chunks c ON c.id = a.chunk_id
            JOIN documents d ON d.id = a.document_id
            WHERE {' AND '.join(clauses)}
            ORDER BY
                CASE a.confidence WHEN 'strong' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                a.meeting_date DESC,
                a.document_id
            LIMIT ?
            """,
            params,
        ).fetchall()

    return _content(
        {
            "actor": actor,
            "topic": topic,
            "municipality": _municipality(),
            "note": "strong means an action verb was detected near the actor; weak means a nearby mention only.",
            "results": [_row_to_dict(row) for row in rows],
            "total": len(rows),
        }
    )


async def get_evidence_pack(
    actor: str | None = None,
    topic: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    body: str | None = None,
    limit: int = 50,
) -> list[TextContent]:
    """Return grouped evidence for summarization by meeting and document."""
    if actor:
        actor_result = await find_actor_topics(
            actor=actor,
            topic=topic,
            from_date=from_date,
            to_date=to_date,
            body=body,
            document_type="minutes",
            limit=limit,
        )
        payload = json.loads(actor_result[0].text)
        rows = payload["results"]
    elif topic:
        topic_result = await search_text(
            query=topic,
            from_date=from_date,
            to_date=to_date,
            body=body,
            document_type="minutes",
            limit=limit,
        )
        payload = json.loads(topic_result[0].text)
        rows = payload["results"]
    else:
        return _content({"error": "Provide actor or topic"})

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"{row.get('meeting_date')}|{row.get('body_name')}|{row.get('document_id')}"
        group = grouped.setdefault(
            key,
            {
                "meeting_date": row.get("meeting_date"),
                "body_name": row.get("body_name"),
                "document_id": row.get("document_id"),
                "document_name": row.get("document_name"),
                "source_url": row.get("url"),
                "snippets": [],
            },
        )
        group["snippets"].append(row.get("snippet"))

    return _content({"municipality": _municipality(), "actor": actor, "topic": topic, "groups": list(grouped.values()), "total_groups": len(grouped)})


list_bodies_tool = Tool(
    name="list_bodies",
    description="List locally ingested municipal committees/bodies",
    inputSchema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "description": "Maximum number of bodies"}},
        "required": [],
    },
)

list_meetings_tool = Tool(
    name="list_meetings",
    description="List locally ingested meetings, optionally filtered by body and year",
    inputSchema={
        "type": "object",
        "properties": {
            "body_id": {"type": "string", "description": "SessionNet body id, e.g. 1 for Stadtverordnetenversammlung"},
            "year": {"type": "integer", "description": "Meeting year"},
            "limit": {"type": "integer", "description": "Maximum number of meetings"},
        },
        "required": [],
    },
)

get_meeting_tool = Tool(
    name="get_meeting",
    description="Get one meeting with agenda items and meeting-level documents",
    inputSchema={
        "type": "object",
        "properties": {"meeting_id": {"type": "string", "description": "SessionNet meeting id"}},
        "required": ["meeting_id"],
    },
)

search_documents_tool = Tool(
    name="search_documents",
    description="Search locally extracted document text and document names",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keyword to search for"},
            "document_type": {
                "type": "string",
                "description": "Optional type: minutes, notice, paper, motion, attachment, other",
            },
            "limit": {"type": "integer", "description": "Maximum number of results"},
        },
        "required": ["query"],
    },
)

get_document_text_tool = Tool(
    name="get_document_text",
    description="Get extracted full text for a document by source file id",
    inputSchema={
        "type": "object",
        "properties": {"document_id": {"type": "string", "description": "SessionNet getfile id"}},
        "required": ["document_id"],
    },
)

search_text_tool = Tool(
    name="search_text",
    description="Search chunked municipal full text with snippets and filters",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Full-text query"},
            "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
            "body": {"type": "string", "description": "Body/committee name contains"},
            "document_type": {"type": "string", "description": "minutes, notice, paper, motion, attachment, other"},
            "limit": {"type": "integer", "description": "Maximum number of snippets"},
        },
        "required": ["query"],
    },
)

find_actor_topics_tool = Tool(
    name="find_actor_topics",
    description="Find evidence snippets for a person, party, or faction in local minutes/documents",
    inputSchema={
        "type": "object",
        "properties": {
            "actor": {"type": "string", "description": "Person, party, or faction name"},
            "topic": {"type": "string", "description": "Optional topic keyword"},
            "actor_type": {"type": "string", "description": "person, party, or faction"},
            "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
            "body": {"type": "string", "description": "Body/committee name contains"},
            "document_type": {"type": "string", "description": "Defaults to minutes"},
            "confidence": {"type": "string", "description": "strong or weak"},
            "limit": {"type": "integer", "description": "Maximum number of snippets"},
        },
        "required": ["actor"],
    },
)

get_evidence_pack_tool = Tool(
    name="get_evidence_pack",
    description="Return grouped evidence snippets for summarization by actor/topic/date range",
    inputSchema={
        "type": "object",
        "properties": {
            "actor": {"type": "string", "description": "Optional person, party, or faction"},
            "topic": {"type": "string", "description": "Optional topic keyword"},
            "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
            "body": {"type": "string", "description": "Body/committee name contains"},
            "limit": {"type": "integer", "description": "Maximum number of snippets before grouping"},
        },
        "required": [],
    },
)


def _fts_query(query: str) -> str:
    terms = re.findall(r"[\wÄÖÜäöüß-]+", query)
    if not terms:
        return f'"{query.replace(chr(34), "")}"'
    return " ".join(f'"{term}"' for term in terms)
