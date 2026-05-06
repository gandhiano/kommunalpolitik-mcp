"""Small local eval runner for agent quality regression checks."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Sequence

from .core import AgentRequest, run_agent


DEFAULT_EVALS = Path("evals/agent_quality.json")


async def run_evals(path: Path) -> dict[str, Any]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        response = await run_agent(
            AgentRequest(
                task=case["task"],
                mode=case.get("mode", "research"),
                research_depth=case.get("research_depth", "auto"),
            )
        )
        failures = _check_case(case, response.to_dict())
        results.append(
            {
                "id": case["id"],
                "passed": not failures,
                "failures": failures,
                "provider": response.provider,
                "actions_taken": [asdict(action) for action in response.actions_taken],
                "source_titles": [source.title for source in response.sources],
            }
        )
    return {"passed": all(result["passed"] for result in results), "results": results}


def _check_case(case: dict[str, Any], response: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    checks = case.get("checks", {})
    answer = response.get("answer", "")
    sources = response.get("sources", [])
    actions = response.get("actions_taken", [])

    if body := checks.get("selected_body_contains"):
        selected_body = " ".join(
            str(action.get("arguments", {}).get("body_name", ""))
            for action in actions
            if action.get("name") == "select_meeting"
        )
        if body not in selected_body:
            failures.append(f"Expected selected body to contain {body!r}, got {selected_body!r}")

    if title := checks.get("first_source_title_contains"):
        first_title = str(sources[0].get("title", "")) if sources else ""
        if title not in first_title:
            failures.append(f"Expected first source title to contain {title!r}, got {first_title!r}")

    if source_type := checks.get("first_source_type"):
        first_type = str(sources[0].get("document_type", "")) if sources else ""
        if source_type != first_type:
            failures.append(f"Expected first source type {source_type!r}, got {first_type!r}")

    first_snippet = str(sources[0].get("snippet", "")) if sources else ""
    for required in checks.get("first_source_snippet_contains", []):
        if required not in first_snippet:
            failures.append(f"Expected first source snippet to contain {required!r}")

    for required in checks.get("answer_must_contain", []):
        if required not in answer:
            failures.append(f"Expected answer to contain {required!r}")

    for forbidden in checks.get("answer_must_not_contain", []):
        if forbidden in answer:
            failures.append(f"Expected answer not to contain {forbidden!r}")

    return failures


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run kommunalpolitik agent eval cases")
    parser.add_argument("--cases", type=Path, default=DEFAULT_EVALS)
    args = parser.parse_args(argv)

    result = asyncio.run(run_evals(args.cases))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
