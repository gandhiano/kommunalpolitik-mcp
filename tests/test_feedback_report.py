from __future__ import annotations

import json
import sqlite3

from src.feedback import build_report


def test_feedback_report_recommends_retrieval_fixes(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at INTEGER NOT NULL,
                rating TEXT NOT NULL,
                comment TEXT NOT NULL,
                task TEXT NOT NULL,
                answer TEXT NOT NULL,
                mode TEXT NOT NULL,
                research_depth TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_metadata TEXT NOT NULL,
                actions_taken TEXT NOT NULL,
                sources TEXT NOT NULL,
                related_sources TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO feedback (
                created_at, rating, comment, task, answer, mode, research_depth, provider,
                model_metadata, actions_taken, sources, related_sources
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "down",
                "Nur Ortsbeiräte.",
                "Finde frühere Anträge der Grünen zum Thema Verkehr",
                "Antwort",
                "briefing",
                "auto",
                "openai",
                json.dumps({"provider": "openai"}),
                json.dumps([{"name": "select_meeting", "arguments": {}}]),
                json.dumps([{"title": "Protokoll", "body_name": "Ortsbeirat Wendershausen"}]),
                json.dumps([]),
            ),
        )

    report = build_report(path)

    assert "Total feedback: 1" in report
    assert "Avoid selecting a next meeting" in report
    assert "prioritize citywide bodies" in report
    assert "Nur Ortsbeiräte" in report
