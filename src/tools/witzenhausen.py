"""MCP tools for locally ingested Witzenhausen SessionNet data."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from mcp import Tool
from mcp.types import TextContent


DEFAULT_DB_PATH = Path("data/witzenhausen/witzenhausen.sqlite")


def _db_path() -> Path:
    return Path(os.environ.get("WITZENHAUSEN_DB_PATH", DEFAULT_DB_PATH))


def _connect() -> sqlite3.Connection:
    db_path = _db_path()
    if not db_path.exists():
        raise FileNotFoundError(
            f"Witzenhausen database not found at {db_path}. Run: python -m src.ingest.witzenhausen init-db"
        )
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _content(payload: dict[str, Any]) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


async def list_witzenhausen_bodies(limit: int = 100) -> list[TextContent]:
    """List locally ingested Witzenhausen bodies/gremia."""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, name, detail_url, meeting_list_url FROM bodies ORDER BY name LIMIT ?",
            (limit,),
        ).fetchall()
    return _content({"bodies": [_row_to_dict(row) for row in rows], "total": len(rows)})


async def list_witzenhausen_meetings(
    body_id: str | None = None,
    year: int | None = None,
    limit: int = 20,
) -> list[TextContent]:
    """List locally ingested Witzenhausen meetings."""
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
    return _content({"meetings": [_row_to_dict(row) for row in rows], "total": len(rows)})


async def get_witzenhausen_meeting(meeting_id: str) -> list[TextContent]:
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


async def search_witzenhausen_documents(
    query: str,
    document_type: str | None = None,
    limit: int = 10,
) -> list[TextContent]:
    """Search locally extracted Witzenhausen document text and document names."""
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

    return _content({"query": query, "results": [_row_to_dict(row) for row in rows], "total": len(rows)})


async def get_witzenhausen_document_text(document_id: str) -> list[TextContent]:
    """Return extracted full text for a downloaded Witzenhausen document."""
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
                "hint": "Run: python -m src.ingest.witzenhausen extract-text --limit 25",
            }
        )
    return _content({"document": _row_to_dict(row)})


list_witzenhausen_bodies_tool = Tool(
    name="list_witzenhausen_bodies",
    description="List locally ingested Witzenhausen committees/bodies from SessionNet",
    inputSchema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "description": "Maximum number of bodies"}},
        "required": [],
    },
)

list_witzenhausen_meetings_tool = Tool(
    name="list_witzenhausen_meetings",
    description="List locally ingested Witzenhausen meetings, optionally filtered by body and year",
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

get_witzenhausen_meeting_tool = Tool(
    name="get_witzenhausen_meeting",
    description="Get one Witzenhausen meeting with agenda items and meeting-level documents",
    inputSchema={
        "type": "object",
        "properties": {"meeting_id": {"type": "string", "description": "SessionNet meeting id"}},
        "required": ["meeting_id"],
    },
)

search_witzenhausen_documents_tool = Tool(
    name="search_witzenhausen_documents",
    description="Search locally extracted Witzenhausen document text and document names",
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

get_witzenhausen_document_text_tool = Tool(
    name="get_witzenhausen_document_text",
    description="Get extracted full text for a Witzenhausen document by SessionNet file id",
    inputSchema={
        "type": "object",
        "properties": {"document_id": {"type": "string", "description": "SessionNet getfile id"}},
        "required": ["document_id"],
    },
)
