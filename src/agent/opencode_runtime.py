"""OpenCode-backed runtime for the public web agent boundary."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any

from .core import AgentAction, AgentRequest, AgentResponse


LOGGER = logging.getLogger("kommunalpolitik.opencode")


async def run_opencode_agent(request: AgentRequest) -> AgentResponse:
    started_at = time.monotonic()
    prompt = _build_prompt(request)
    LOGGER.info(
        "opencode_runtime start agent=%s opencode_agent=%s mode=%s depth=%s model=%s prompt_chars=%s timeout=%s",
        request.agent,
        _opencode_agent(request) or "default",
        request.mode,
        request.research_depth,
        _opencode_model(request) or "default",
        len(prompt),
        _timeout_seconds(request),
    )
    output = await asyncio.to_thread(_run_opencode_process, prompt, request)
    answer = _answer_from_output(output)
    if not answer:
        LOGGER.warning("opencode_runtime no_answer output_chars=%s output_preview=%r", len(output), output[:500])
        raise ValueError("OpenCode returned no answer")

    LOGGER.info(
        "opencode_runtime finish answer_chars=%s output_chars=%s elapsed_ms=%s",
        len(answer),
        len(output),
        round((time.monotonic() - started_at) * 1000),
    )

    return AgentResponse(
        mode=request.mode,
        answer=answer,
        sources=[],
        actions_taken=[
            AgentAction(
                "agent_start",
                {
                    "runtime": "opencode",
                    "command": _command_name(),
                    "agent": _opencode_agent(request) or "default",
                },
            )
        ],
        provider="opencode",
        model_metadata={
            "provider": "opencode",
            "model": _opencode_model(request),
            "latency_ms": round((time.monotonic() - started_at) * 1000),
        },
    )


def _run_opencode_process(prompt: str, request: AgentRequest) -> str:
    command = [_command_name(), "run", prompt, "--format", "json"]
    if agent := _opencode_agent(request):
        command.extend(["--agent", agent])
    if model := _opencode_model(request):
        command.extend(["--model", model])
    if attach_url := os.environ.get("KOMMUNALPOLITIK_OPENCODE_ATTACH"):
        command.extend(["--attach", attach_url])
    command.extend(["--dir", _opencode_dir()])

    timeout = _timeout_seconds(request)
    LOGGER.info(
        "opencode_process start command=%s has_agent=%s has_model=%s has_attach=%s has_dir=%s timeout=%s",
        _safe_command_for_log(command),
        bool(_opencode_agent(request)),
        bool(_opencode_model(request)),
        bool(os.environ.get("KOMMUNALPOLITIK_OPENCODE_ATTACH")),
        True,
        timeout,
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        LOGGER.exception("opencode_process command_not_found command=%s", _command_name())
        raise ValueError("OpenCode runtime is configured but the opencode command was not found") from exc
    except subprocess.TimeoutExpired as exc:
        LOGGER.warning("opencode_process timeout timeout=%s", timeout)
        raise ValueError(f"OpenCode runtime timed out after {timeout} seconds") from exc

    LOGGER.info(
        "opencode_process finish returncode=%s stdout_chars=%s stderr_chars=%s",
        result.returncode,
        len(result.stdout or ""),
        len(result.stderr or ""),
    )
    if result.stderr:
        LOGGER.info("opencode_process stderr_preview=%r", result.stderr[:500])
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "OpenCode runtime failed").strip()
        LOGGER.warning("opencode_process failed returncode=%s message_preview=%r", result.returncode, message[:500])
        raise ValueError(message[:1000])
    return result.stdout


def _build_prompt(request: AgentRequest) -> str:
    return f"""Du bist ein spezialisierter kommunalpolitischer Agent fuer Witzenhausen.

Aufgabe: {request.task}
Agent: {request.agent}
Legacy-Modus: {request.mode}
Recherche-Tiefe: {request.research_depth}

Gespräch bisher:
{_conversation(request.messages)}

Arbeite quellengebunden mit den lokal konfigurierten kommunalpolitischen Werkzeugen. Antworte auf Deutsch, sachlich und arbeitspraktisch. Zitiere Quellen konkret, wenn Du kommunale Fakten nennst. Wenn die Quellenlage nicht reicht, sage das klar.
"""


def _answer_from_output(output: str) -> str:
    events = [_json_line(line) for line in output.splitlines()]
    events = [event for event in events if isinstance(event, dict)]
    if not events:
        LOGGER.info("opencode_parse plain_text output_chars=%s", len(output))
        return _strip_system_reminders(output).strip()

    candidates: list[str] = []
    for event in events:
        candidates.extend(_text_candidates(event))
    answer = _strip_system_reminders("\n".join(_dedupe_lines(candidates))).strip()
    LOGGER.info("opencode_parse events=%s candidates=%s answer_chars=%s", len(events), len(candidates), len(answer))
    return answer


def _json_line(line: str) -> Any:
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _text_candidates(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if _looks_like_answer(value) else []
    if isinstance(value, list):
        candidates: list[str] = []
        for item in value:
            candidates.extend(_text_candidates(item))
        return candidates
    if not isinstance(value, dict):
        return []

    if value.get("type") in {"debug", "info", "warn", "error", "step_start", "step_finish"}:
        return []

    if value.get("type") == "text" and isinstance(value.get("part"), dict):
        text = value["part"].get("text")
        if isinstance(text, str) and text.strip():
            return [text.strip()]

    candidates: list[str] = []
    for key in ("part", "message", "content", "text", "answer", "output"):
        item = value.get(key)
        if isinstance(item, str) and _looks_like_answer(item):
            candidates.append(item.strip())
        elif isinstance(item, (dict, list)):
            candidates.extend(_text_candidates(item))
    return candidates


def _looks_like_answer(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 2:
        return False
    lowered = stripped.lower()
    noisy_prefixes = ("debug", "info", "warn", "error", "tool", "session", "event")
    return not lowered.startswith(noisy_prefixes)


def _dedupe_lines(lines: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for line in lines:
        normalized = line.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _strip_system_reminders(text: str) -> str:
    return re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL).strip()


def _conversation(messages: list[dict[str, str]]) -> str:
    if not messages:
        return "Keine vorherigen Nachrichten."
    lines = []
    for message in messages[-10:]:
        role = message.get("role", "user")
        content = message.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "Keine vorherigen Nachrichten."


def _command_name() -> str:
    return os.environ.get("KOMMUNALPOLITIK_OPENCODE_COMMAND", "opencode").strip() or "opencode"


def _opencode_dir() -> str:
    return os.environ.get("KOMMUNALPOLITIK_OPENCODE_DIR") or str(Path.cwd())


def _opencode_agent(request: AgentRequest) -> str | None:
    specific = os.environ.get(f"KOMMUNALPOLITIK_OPENCODE_AGENT_{request.agent.upper()}")
    configured = specific or os.environ.get("KOMMUNALPOLITIK_OPENCODE_AGENT")
    if not configured:
        return None
    agent = configured.strip()
    return agent if agent and agent != "general" else None


def _opencode_model(request: AgentRequest) -> str | None:
    if request.research_depth == "quick":
        return os.environ.get("KOMMUNALPOLITIK_OPENCODE_MODEL_QUICK") or os.environ.get(
            "KOMMUNALPOLITIK_OPENCODE_MODEL"
        )
    if request.research_depth == "deep" or request.mode in {"motion_draft", "follow_up"} or request.agent in {"drafting", "scrutiny"}:
        return os.environ.get("KOMMUNALPOLITIK_OPENCODE_MODEL_STRONG") or os.environ.get(
            "KOMMUNALPOLITIK_OPENCODE_MODEL"
        )
    return os.environ.get("KOMMUNALPOLITIK_OPENCODE_MODEL_BALANCED") or os.environ.get(
        "KOMMUNALPOLITIK_OPENCODE_MODEL"
    )


def _timeout_seconds(request: AgentRequest) -> int:
    default = 240 if request.research_depth == "deep" else 120
    value = os.environ.get("KOMMUNALPOLITIK_OPENCODE_TIMEOUT_SECONDS")
    if not value:
        return default
    try:
        return max(10, min(int(value), 600))
    except ValueError:
        return default


def _safe_command_for_log(command: list[str]) -> list[str]:
    if len(command) <= 2:
        return command
    safe = command.copy()
    safe[2] = f"<prompt:{len(command[2])} chars>"
    return safe
