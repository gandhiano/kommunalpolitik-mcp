"""HTTP transport for the kommunalpolitik MCP server."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import uvicorn
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

from .agent import AgentRequest, run_agent
from .agent.providers import ProviderError
from .mcp_server import server


AGENT_MODES = {"research", "briefing", "motion_draft", "follow_up"}
AGENT_TYPES = {"general", "research", "briefing", "drafting", "scrutiny"}
RESEARCH_DEPTHS = {"quick", "auto", "deep"}
SESSION_COOKIE = "kommunalpolitik_session"
SESSION_TTL_SECONDS = 60 * 60 * 12


def create_app(stateless: bool = True, json_response: bool = False) -> Starlette:
    session_manager = StreamableHTTPSessionManager(
        app=server,
        stateless=stateless,
        json_response=json_response,
    )

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        if not _mcp_enabled():
            response = JSONResponse({"error": "Not found"}, status_code=404)
            await response(scope, receive, send)
            return
        if scope["type"] == "http" and scope.get("path") in {"/mcp", "/mcp/"}:
            await session_manager.handle_request(scope, receive, send)
            return
        response = JSONResponse({"error": "Not found"}, status_code=404)
        await response(scope, receive, send)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "transport": "streamable-http"})

    async def auth_status(request: Request) -> JSONResponse:
        return JSONResponse({"authenticated": _is_authenticated(request), "auth_enabled": _auth_enabled()})

    async def login(request: Request) -> JSONResponse:
        if not _auth_enabled():
            return JSONResponse({"authenticated": True, "auth_enabled": False})
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "Request body must be JSON"}, status_code=400)

        password = str(payload.get("password") or "")
        if not hmac.compare_digest(password, os.environ.get("KOMMUNALPOLITIK_AUTH_PASSWORD", "")):
            return JSONResponse({"error": "Invalid password"}, status_code=401)

        response = JSONResponse({"authenticated": True, "auth_enabled": True})
        response.set_cookie(
            SESSION_COOKIE,
            _sign_session(int(time.time())),
            httponly=True,
            secure=_secure_cookies(),
            samesite="lax",
            max_age=SESSION_TTL_SECONDS,
            path="/",
        )
        return response

    async def logout(_: Request) -> JSONResponse:
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    async def agent(request: Request) -> JSONResponse:
        if not _is_authenticated(request):
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "Request body must be JSON"}, status_code=400)

        messages = _chat_messages(payload.get("messages"))
        task = str(payload.get("task") or "").strip() or _latest_user_message(messages)
        agent = str(payload.get("agent") or "general").strip().lower()
        if agent not in AGENT_TYPES:
            return JSONResponse({"error": f"Unsupported agent: {agent}"}, status_code=400)
        mode = str(payload.get("mode") or _mode_for_agent(agent))
        if not task:
            return JSONResponse({"error": "Field 'task' is required"}, status_code=400)
        if mode not in AGENT_MODES:
            return JSONResponse({"error": f"Unsupported mode: {mode}"}, status_code=400)
        research_depth = str(payload.get("research_depth") or "auto")
        if research_depth not in RESEARCH_DEPTHS:
            return JSONResponse({"error": f"Unsupported research_depth: {research_depth}"}, status_code=400)

        try:
            response = await run_agent(
                AgentRequest(
                    task=task,
                    mode=mode,  # type: ignore[arg-type]
                    agent=agent,
                    topic=payload.get("topic"),
                    actor=payload.get("actor"),
                    meeting_id=payload.get("meeting_id"),
                    research_depth=research_depth,  # type: ignore[arg-type]
                    messages=messages,
                )
            )
        except FileNotFoundError as exc:
            return JSONResponse({"error": str(exc)}, status_code=503)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=503)
        except ProviderError as exc:
            return JSONResponse({"error": exc.message}, status_code=exc.status_code)
        return JSONResponse(response.to_dict())

    async def feedback(request: Request) -> JSONResponse:
        if not _is_authenticated(request):
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "Request body must be JSON"}, status_code=400)

        rating = str(payload.get("rating") or "").strip().lower()
        if rating not in {"up", "down"}:
            return JSONResponse({"error": "Field 'rating' must be 'up' or 'down'"}, status_code=400)
        task = str(payload.get("task") or "").strip()
        answer = str(payload.get("answer") or "").strip()
        if not task or not answer:
            return JSONResponse({"error": "Fields 'task' and 'answer' are required"}, status_code=400)

        feedback_id = _store_feedback(
            {
                "rating": rating,
                "comment": str(payload.get("comment") or "").strip()[:4000],
                "task": task[:12000],
                "answer": answer[:50000],
                "mode": str(payload.get("mode") or "")[:80],
                "research_depth": str(payload.get("research_depth") or "")[:80],
                "provider": str(payload.get("provider") or "")[:120],
                "model_metadata": payload.get("model_metadata") if isinstance(payload.get("model_metadata"), dict) else {},
                "actions_taken": payload.get("actions_taken") if isinstance(payload.get("actions_taken"), list) else [],
                "sources": payload.get("sources") if isinstance(payload.get("sources"), list) else [],
                "related_sources": payload.get("related_sources") if isinstance(payload.get("related_sources"), list) else [],
            }
        )
        return JSONResponse({"status": "ok", "feedback_id": feedback_id})

    routes = [
        Route("/health", endpoint=health, methods=["GET"]),
        Route("/auth/status", endpoint=auth_status, methods=["GET"]),
        Route("/auth/login", endpoint=login, methods=["POST"]),
        Route("/auth/logout", endpoint=logout, methods=["POST"]),
        Route("/agent", endpoint=agent, methods=["POST"]),
        Route("/feedback", endpoint=feedback, methods=["POST"]),
    ]
    routes.extend(_frontend_routes())
    routes.append(Mount("/", app=handle_mcp))

    return Starlette(
        debug=False,
        lifespan=lifespan,
        routes=routes,
    )


def _auth_enabled() -> bool:
    return bool(os.environ.get("KOMMUNALPOLITIK_AUTH_PASSWORD"))


def _chat_messages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    messages: list[dict[str, str]] = []
    for item in value[-20:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content[:12000]})
    return messages


def _mode_for_agent(agent: str) -> str:
    if agent == "briefing":
        return "briefing"
    if agent == "drafting":
        return "motion_draft"
    if agent == "scrutiny":
        return "follow_up"
    return "research"


def _latest_user_message(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message["role"] == "user":
            return message["content"]
    return ""


def _secure_cookies() -> bool:
    return os.environ.get("KOMMUNALPOLITIK_SECURE_COOKIES", "true").strip().lower() not in {"0", "false", "no"}


def _mcp_enabled() -> bool:
    return os.environ.get("KOMMUNALPOLITIK_MCP_ENABLED", "true").strip().lower() not in {"0", "false", "no"}


def _frontend_routes() -> list[Any]:
    dist = Path(os.environ.get("KOMMUNALPOLITIK_WEB_DIST", "web/frontend/dist"))
    index = dist / "index.html"
    if not index.exists():
        return []

    async def frontend(_: Request) -> FileResponse:
        return FileResponse(index)

    routes: list[Any] = [Route("/", endpoint=frontend, methods=["GET"])]
    assets = dist / "assets"
    if assets.exists():
        routes.append(Mount("/assets", app=StaticFiles(directory=assets)))
    for name in ("favicon.svg", "icons.svg"):
        static_file = dist / name
        if static_file.exists():
            async def static_endpoint(_: Request, file_path: Path = static_file) -> FileResponse:
                return FileResponse(file_path)

            routes.append(Route(f"/{name}", endpoint=static_endpoint, methods=["GET"]))
    return routes


def _is_authenticated(request: Request) -> bool:
    if not _auth_enabled():
        return True
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    return _verify_session(token)


def _session_secret() -> str:
    secret = os.environ.get("KOMMUNALPOLITIK_SESSION_SECRET")
    if secret:
        return secret
    if _auth_enabled():
        return os.environ["KOMMUNALPOLITIK_AUTH_PASSWORD"]
    return secrets.token_hex(32)


def _sign_session(created_at: int) -> str:
    payload = str(created_at)
    signature = hmac.new(_session_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _verify_session(token: str) -> bool:
    try:
        payload, signature = token.split(".", 1)
        created_at = int(payload)
    except ValueError:
        return False
    if time.time() - created_at > SESSION_TTL_SECONDS:
        return False
    expected = hmac.new(_session_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _feedback_path() -> Path:
    return Path(os.environ.get("KOMMUNALPOLITIK_FEEDBACK_PATH", "data/feedback.sqlite"))


def _store_feedback(payload: dict[str, Any]) -> int:
    path = _feedback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
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
        cursor = connection.execute(
            """
            INSERT INTO feedback (
                created_at, rating, comment, task, answer, mode, research_depth, provider,
                model_metadata, actions_taken, sources, related_sources
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                payload["rating"],
                payload["comment"],
                payload["task"],
                payload["answer"],
                payload["mode"],
                payload["research_depth"],
                payload["provider"],
                json.dumps(payload["model_metadata"], ensure_ascii=False),
                json.dumps(payload["actions_taken"], ensure_ascii=False),
                json.dumps(payload["sources"], ensure_ascii=False),
                json.dumps(payload["related_sources"], ensure_ascii=False),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run kommunalpolitik MCP over streamable HTTP")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--stateful", action="store_true", help="Track MCP sessions instead of using stateless requests")
    parser.add_argument("--json-response", action="store_true", help="Use JSON responses instead of SSE streams")
    parser.add_argument("--reload", action="store_true", help="Reload the local HTTP server when source files change")
    args = parser.parse_args(argv)

    if args.reload and (args.stateful or args.json_response):
        raise SystemExit("--reload only supports the default stateless SSE-compatible local dev server")

    if args.reload:
        uvicorn.run(
            "src.http_server:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=True,
        )
        return

    uvicorn.run(
        create_app(stateless=not args.stateful, json_response=args.json_response),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
