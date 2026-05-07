"""Local feedback review utilities for pilot improvement loops."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Sequence


DEFAULT_FEEDBACK = Path("data/feedback.sqlite")


def build_report(path: Path = DEFAULT_FEEDBACK) -> str:
    rows = _load_feedback(path)
    if not rows:
        return "# Feedback Report\n\nNo feedback rows found."

    negative = [row for row in rows if row["rating"] == "down"]
    positive = [row for row in rows if row["rating"] == "up"]
    lines = [
        "# Feedback Report",
        "",
        f"Total feedback: {len(rows)}",
        f"Positive: {len(positive)}",
        f"Negative: {len(negative)}",
        "",
    ]

    recommendations = _recommendations(rows)
    if recommendations:
        lines.extend(["## Recommended Actions", ""])
        lines.extend(f"- {item}" for item in recommendations)
        lines.append("")

    lines.extend(["## Negative Feedback", ""])
    if not negative:
        lines.append("No negative feedback yet.")
    for row in negative:
        comment = row["comment"] or "No comment provided."
        lines.extend(
            [
                f"### #{row['id']} {row['mode']} / {row['provider']}",
                "",
                f"Task: {row['task']}",
                f"Comment: {comment}",
                f"First sources: {_source_summary(row['sources'])}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _load_feedback(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, created_at, rating, comment, task, answer, mode, research_depth, provider,
                   model_metadata, actions_taken, sources, related_sources
            FROM feedback
            ORDER BY id
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for key in ("model_metadata", "actions_taken", "sources", "related_sources"):
        try:
            result[key] = json.loads(result[key])
        except (TypeError, json.JSONDecodeError):
            result[key] = [] if key != "model_metadata" else {}
    return result


def _recommendations(rows: list[dict[str, Any]]) -> list[str]:
    recommendations: list[str] = []
    for row in rows:
        if row["rating"] != "down":
            continue
        actions = [action.get("name") for action in row["actions_taken"] if isinstance(action, dict)]
        bodies = [str(source.get("body_name") or "") for source in row["sources"] if isinstance(source, dict)]
        task = row["task"].lower()
        if "select_meeting" in actions and not any(term in task for term in ("sitzung", "tagesordnung", "stvv", "stadtverordnetenversammlung")):
            recommendations.append("Avoid selecting a next meeting for broad briefing tasks that ask for prior research or motions.")
        if bodies and all("Ortsbeirat" in body for body in bodies):
            recommendations.append("For faction/motion research, prioritize citywide bodies before Ortsbeirat-only hits unless the user asks for Ortsbeirat material.")
    return list(dict.fromkeys(recommendations))


def _source_summary(sources: list[Any]) -> str:
    labels = []
    for source in sources[:3]:
        if isinstance(source, dict):
            title = source.get("title") or "Untitled"
            body = source.get("body_name") or "no body"
            labels.append(f"{title} ({body})")
    return "; ".join(labels) if labels else "No sources stored."


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Summarize local pilot feedback")
    parser.add_argument("--path", type=Path, default=DEFAULT_FEEDBACK)
    args = parser.parse_args(argv)
    print(build_report(args.path), end="")


if __name__ == "__main__":
    main()
