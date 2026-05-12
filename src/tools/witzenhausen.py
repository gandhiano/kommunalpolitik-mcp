"""MCP tools for locally ingested municipal politics data."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from mcp import Tool
from mcp.types import TextContent

from src.config import load_municipality_config
from src.ingest.pdf_text import extract_pdf_text
from src.ingest.sessionnet_client import SessionNetClient
from src.ingest.sessionnet_repository import SessionNetRepository
from src.ingest.text_index import chunk_document


DEFAULT_DB_PATH = Path("data/witzenhausen/witzenhausen.sqlite")


def _db_path() -> Path:
    if db_path := os.environ.get("KOMMUNALPOLITIK_DB_PATH"):
        return Path(db_path)
    try:
        return load_municipality_config().database_path
    except FileNotFoundError:
        return DEFAULT_DB_PATH


def _municipality() -> dict[str, str]:
    try:
        config = load_municipality_config()
        municipality_id = config.id
        municipality_name = config.name
    except FileNotFoundError:
        municipality_id = "witzenhausen"
        municipality_name = "Witzenhausen"

    return {
        "id": os.environ.get("KOMMUNALPOLITIK_MUNICIPALITY_ID", municipality_id),
        "name": os.environ.get("KOMMUNALPOLITIK_MUNICIPALITY_NAME", municipality_name),
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
    row = _document_text_row(document_id)

    if not row:
        return _content({"error": "Document not found", "document_id": document_id})
    if not row["text"]:
        extraction = _extract_document_on_demand(document_id)
        if extraction.get("error"):
            return _content(extraction)
        row = _document_text_row(document_id)
    return _content({"document": _row_to_dict(row), "on_demand_extraction": bool(row and row["text_path"])})


def _document_text_row(document_id: str) -> sqlite3.Row | None:
    with _connect() as connection:
        return connection.execute(
            """
            SELECT d.id, d.document_type, d.name, d.url, d.file_path, t.text, t.text_path
            FROM documents d
            LEFT JOIN document_text t ON t.document_id = d.id
            WHERE d.id = ?
            """,
            (document_id,),
        ).fetchone()


def _extract_document_on_demand(document_id: str) -> dict[str, Any]:
    config = load_municipality_config()
    repo = SessionNetRepository(config.database_path)
    try:
        repo.init_schema()
        row = repo.connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            return {"error": "Document not found", "document_id": document_id}

        file_path = Path(row["file_path"]) if row["file_path"] else None
        if not file_path or not file_path.exists():
            client = SessionNetClient(config.base_url, config.data_dir / "raw" / "html", delay_seconds=0)
            file_path = config.data_dir / "raw" / "pdf" / f"{document_id}{_extension_from_url(row['url'])}"
            sha256, size = client.download(row["url"], file_path)
            repo.mark_document_downloaded(document_id, file_path, sha256, size)

        try:
            text = _sanitize_text(extract_pdf_text(file_path))
        except Exception as exc:
            return {
                "error": "Document text extraction failed",
                "document_id": document_id,
                "document_name": row["name"],
                "url": row["url"],
                "reason": str(exc)[:500],
            }
        text_path = config.data_dir / "text" / f"{document_id}.txt"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(text, encoding="utf-8")
        repo.save_document_text(document_id, text_path, text)

        chunk_row = repo.connection.execute(
            """
            SELECT
                d.id,
                d.source_type,
                d.source_id,
                d.document_type,
                d.name AS document_name,
                m.body_name,
                m.meeting_date,
                t.text
            FROM documents d
            JOIN document_text t ON t.document_id = d.id
            LEFT JOIN meetings m ON d.source_type = 'meeting' AND d.source_id = m.id
            WHERE d.id = ?
            """,
            (document_id,),
        ).fetchone()
        chunks = chunk_document(chunk_row)
        repo.save_document_chunks(document_id, chunks, rebuild=True)
        return {"status": "extracted", "document_id": document_id, "chunks": len(chunks)}
    finally:
        repo.close()


def _extension_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.path.endswith("getfile.asp") and parse_qs(parsed.query).get("type") == ["do"]:
        return ".pdf"
    if match := re.search(r"\.([a-zA-Z0-9]{2,5})$", parsed.path):
        return f".{match.group(1).lower()}"
    return ".pdf"


def _sanitize_text(text: str) -> str:
    return text.encode("utf-8", errors="replace").decode("utf-8")


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
    terms = [term for term in re.findall(r"[\wÄÖÜäöüß]+", query) if _useful_fts_term(term)]
    if not terms:
        fallback = query.replace(chr(34), "").strip()
        return f'"{fallback}"' if fallback else '""'
    return " OR ".join(f"{term}*" for term in terms)


def _useful_fts_term(term: str) -> bool:
    return len(term) > 2 and term.lower() not in _GERMAN_STOPWORDS


_GERMAN_STOPWORDS = {
    "aber", "alle", "als", "an", "auch", "auf", "aus", "bei", "bis", "das", "dass",
    "dem", "den", "der", "des", "die", "dies", "diese", "diesem", "diesen", "dieser",
    "dieses", "doch", "ein", "eine", "einem", "einen", "einer", "eines", "er", "es",
    "gab", "gibt", "haben", "hat", "hatte", "im", "in", "ist", "mit", "nach", "nicht",
    "noch", "oder", "seit", "sind", "um", "und", "vom", "von", "vor", "war", "waren",
    "was", "welche", "welcher", "welches", "wenn", "wer", "werden", "wie", "wird", "wo",
    "zu", "zum", "zur", "über", "ueber",
}
