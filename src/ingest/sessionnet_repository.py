"""SQLite persistence for public SessionNet data."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


class SessionNetRepository:
    """Small SQLite repository for scraped public SessionNet metadata."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def init_schema(self) -> None:
        self.connection.executescript(
            """
            PRAGMA journal_mode = WAL;

            CREATE TABLE IF NOT EXISTS bodies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                detail_url TEXT,
                meeting_list_url TEXT,
                first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY,
                body_id TEXT,
                body_name TEXT,
                title TEXT NOT NULL,
                meeting_date TEXT,
                meeting_time TEXT,
                location TEXT,
                detail_url TEXT NOT NULL,
                first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agenda_items (
                id TEXT PRIMARY KEY,
                meeting_id TEXT NOT NULL,
                number TEXT,
                title TEXT NOT NULL,
                paper_reference TEXT,
                paper_url TEXT,
                public BOOLEAN,
                sort_order INTEGER,
                first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY,
                reference TEXT,
                title TEXT,
                detail_url TEXT NOT NULL,
                first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                source_type TEXT,
                source_id TEXT,
                document_type TEXT,
                label TEXT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                file_path TEXT,
                sha256 TEXT,
                size_bytes INTEGER,
                downloaded_at TEXT,
                first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS document_text (
                document_id TEXT PRIMARY KEY,
                text_path TEXT,
                text TEXT,
                extracted_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS crawl_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                source_type TEXT,
                source_id TEXT,
                document_type TEXT,
                document_name TEXT,
                body_name TEXT,
                meeting_date TEXT,
                page_number INTEGER,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
                text,
                document_id UNINDEXED,
                chunk_id UNINDEXED
            );

            CREATE TABLE IF NOT EXISTS actor_mentions (
                id TEXT PRIMARY KEY,
                actor_name TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                verb TEXT,
                confidence TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                source_type TEXT,
                source_id TEXT,
                document_type TEXT,
                document_name TEXT,
                body_name TEXT,
                meeting_date TEXT,
                snippet TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_document_chunks_meeting_date ON document_chunks(meeting_date);
            CREATE INDEX IF NOT EXISTS idx_actor_mentions_actor ON actor_mentions(actor_name, actor_type);
            CREATE INDEX IF NOT EXISTS idx_actor_mentions_date ON actor_mentions(meeting_date);
            """
        )
        self.connection.commit()

    def upsert_bodies(self, bodies: Iterable[dict[str, Any]]) -> int:
        rows = list(bodies)
        self.connection.executemany(
            """
            INSERT INTO bodies (id, name, detail_url, meeting_list_url)
            VALUES (:id, :name, :detail_url, :meeting_list_url)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                detail_url = excluded.detail_url,
                meeting_list_url = excluded.meeting_list_url,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            rows,
        )
        self.connection.commit()
        return len(rows)

    def upsert_meetings(self, meetings: Iterable[dict[str, Any]]) -> int:
        rows = list(meetings)
        self.connection.executemany(
            """
            INSERT INTO meetings (id, body_id, body_name, title, meeting_date, meeting_time, location, detail_url)
            VALUES (:id, :body_id, :body_name, :title, :meeting_date, :meeting_time, :location, :detail_url)
            ON CONFLICT(id) DO UPDATE SET
                body_id = excluded.body_id,
                body_name = excluded.body_name,
                title = excluded.title,
                meeting_date = excluded.meeting_date,
                meeting_time = excluded.meeting_time,
                location = excluded.location,
                detail_url = excluded.detail_url,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            rows,
        )
        self.connection.commit()
        return len(rows)

    def upsert_agenda_items(self, items: Iterable[dict[str, Any]]) -> int:
        rows = list(items)
        self.connection.executemany(
            """
            INSERT INTO agenda_items (id, meeting_id, number, title, paper_reference, paper_url, public, sort_order)
            VALUES (:id, :meeting_id, :number, :title, :paper_reference, :paper_url, :public, :sort_order)
            ON CONFLICT(id) DO UPDATE SET
                number = excluded.number,
                title = excluded.title,
                paper_reference = excluded.paper_reference,
                paper_url = excluded.paper_url,
                public = excluded.public,
                sort_order = excluded.sort_order,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            rows,
        )
        self.connection.commit()
        return len(rows)

    def upsert_papers(self, papers: Iterable[dict[str, Any]]) -> int:
        rows = list(papers)
        self.connection.executemany(
            """
            INSERT INTO papers (id, reference, title, detail_url)
            VALUES (:id, :reference, :title, :detail_url)
            ON CONFLICT(id) DO UPDATE SET
                reference = excluded.reference,
                title = excluded.title,
                detail_url = excluded.detail_url,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            rows,
        )
        self.connection.commit()
        return len(rows)

    def upsert_documents(self, documents: Iterable[dict[str, Any]]) -> int:
        rows = list(documents)
        self.connection.executemany(
            """
            INSERT INTO documents (id, source_type, source_id, document_type, label, name, url)
            VALUES (:id, :source_type, :source_id, :document_type, :label, :name, :url)
            ON CONFLICT(id) DO UPDATE SET
                source_type = excluded.source_type,
                source_id = excluded.source_id,
                document_type = excluded.document_type,
                label = excluded.label,
                name = excluded.name,
                url = excluded.url,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            rows,
        )
        self.connection.commit()
        return len(rows)

    def documents_pending_download(self, limit: int | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM documents WHERE file_path IS NULL ORDER BY first_seen_at"
        params: tuple[Any, ...] = ()
        if limit:
            sql += " LIMIT ?"
            params = (limit,)
        return list(self.connection.execute(sql, params))

    def documents_pending_text(self, limit: int | None = None) -> list[sqlite3.Row]:
        sql = """
            SELECT d.* FROM documents d
            LEFT JOIN document_text t ON t.document_id = d.id
            WHERE d.file_path IS NOT NULL AND t.document_id IS NULL
            ORDER BY d.downloaded_at
        """
        params: tuple[Any, ...] = ()
        if limit:
            sql += " LIMIT ?"
            params = (limit,)
        return list(self.connection.execute(sql, params))

    def mark_document_downloaded(self, document_id: str, file_path: Path, sha256: str, size_bytes: int) -> None:
        self.connection.execute(
            """
            UPDATE documents
            SET file_path = ?, sha256 = ?, size_bytes = ?, downloaded_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (str(file_path), sha256, size_bytes, document_id),
        )
        self.connection.commit()

    def save_document_text(self, document_id: str, text_path: Path, text: str) -> None:
        self.connection.execute(
            """
            INSERT INTO document_text (document_id, text_path, text)
            VALUES (?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                text_path = excluded.text_path,
                text = excluded.text,
                extracted_at = CURRENT_TIMESTAMP
            """,
            (document_id, str(text_path), text),
        )
        self.connection.commit()

    def bodies(self) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM bodies ORDER BY name"))

    def meetings_without_details(self, limit: int | None = None) -> list[sqlite3.Row]:
        sql = """
            SELECT m.* FROM meetings m
            LEFT JOIN agenda_items a ON a.meeting_id = m.id
            LEFT JOIN documents d ON d.source_type = 'meeting' AND d.source_id = m.id
            WHERE a.id IS NULL AND d.id IS NULL
            ORDER BY m.meeting_date DESC
        """
        params: tuple[Any, ...] = ()
        if limit:
            sql += " LIMIT ?"
            params = (limit,)
        return list(self.connection.execute(sql, params))

    def counts(self) -> dict[str, int]:
        tables = [
            "bodies",
            "meetings",
            "agenda_items",
            "papers",
            "documents",
            "document_text",
            "document_chunks",
            "actor_mentions",
        ]
        return {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }

    def documents_pending_chunks(self, limit: int | None = None) -> list[sqlite3.Row]:
        sql = """
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
            LEFT JOIN document_chunks c ON c.document_id = d.id
            WHERE c.id IS NULL AND t.text IS NOT NULL AND length(t.text) > 0
            ORDER BY d.id
        """
        params: tuple[Any, ...] = ()
        if limit:
            sql += " LIMIT ?"
            params = (limit,)
        return list(self.connection.execute(sql, params))

    def save_document_chunks(self, document_id: str, chunks: Iterable[dict[str, Any]], rebuild: bool = False) -> int:
        rows = list(chunks)
        if rebuild:
            existing = self.connection.execute(
                "SELECT id FROM document_chunks WHERE document_id = ?",
                (document_id,),
            ).fetchall()
            for row in existing:
                self.connection.execute("DELETE FROM document_chunks_fts WHERE chunk_id = ?", (row["id"],))
            self.connection.execute("DELETE FROM actor_mentions WHERE document_id = ?", (document_id,))
            self.connection.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))

        self.connection.executemany(
            """
            INSERT INTO document_chunks (
                id, document_id, source_type, source_id, document_type, document_name,
                body_name, meeting_date, page_number, chunk_index, text
            ) VALUES (
                :id, :document_id, :source_type, :source_id, :document_type, :document_name,
                :body_name, :meeting_date, :page_number, :chunk_index, :text
            )
            ON CONFLICT(id) DO UPDATE SET
                text = excluded.text,
                page_number = excluded.page_number,
                chunk_index = excluded.chunk_index
            """,
            rows,
        )
        self.connection.executemany(
            """
            INSERT INTO document_chunks_fts (text, document_id, chunk_id)
            VALUES (:text, :document_id, :id)
            """,
            rows,
        )
        self.connection.commit()
        return len(rows)

    def chunks_pending_actor_mentions(self, limit: int | None = None) -> list[sqlite3.Row]:
        sql = """
            SELECT c.* FROM document_chunks c
            LEFT JOIN actor_mentions a ON a.chunk_id = c.id
            WHERE a.id IS NULL
            ORDER BY c.document_id, c.chunk_index
        """
        params: tuple[Any, ...] = ()
        if limit:
            sql += " LIMIT ?"
            params = (limit,)
        return list(self.connection.execute(sql, params))

    def save_actor_mentions(self, mentions: Iterable[dict[str, Any]]) -> int:
        rows = list(mentions)
        self.connection.executemany(
            """
            INSERT OR IGNORE INTO actor_mentions (
                id, actor_name, actor_type, verb, confidence, document_id, chunk_id,
                source_type, source_id, document_type, document_name, body_name, meeting_date, snippet
            ) VALUES (
                :id, :actor_name, :actor_type, :verb, :confidence, :document_id, :chunk_id,
                :source_type, :source_id, :document_type, :document_name, :body_name, :meeting_date, :snippet
            )
            """,
            rows,
        )
        self.connection.commit()
        return len(rows)
