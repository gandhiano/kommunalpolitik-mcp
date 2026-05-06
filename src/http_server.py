"""HTTP transport for the kommunalpolitik MCP server."""

from __future__ import annotations

import argparse
import contextlib
from collections.abc import AsyncIterator, Sequence

import uvicorn
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from .agent import AgentRequest, run_agent
from .agent.providers import ProviderError
from .mcp_server import server


AGENT_MODES = {"research", "briefing", "motion_draft", "follow_up"}


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
        if scope["type"] == "http" and scope.get("path") in {"/mcp", "/mcp/"}:
            await session_manager.handle_request(scope, receive, send)
            return
        response = JSONResponse({"error": "Not found"}, status_code=404)
        await response(scope, receive, send)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "transport": "streamable-http"})

    async def agent(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "Request body must be JSON"}, status_code=400)

        task = str(payload.get("task") or "").strip()
        mode = str(payload.get("mode") or "research")
        if not task:
            return JSONResponse({"error": "Field 'task' is required"}, status_code=400)
        if mode not in AGENT_MODES:
            return JSONResponse({"error": f"Unsupported mode: {mode}"}, status_code=400)

        try:
            response = await run_agent(
                AgentRequest(
                    task=task,
                    mode=mode,  # type: ignore[arg-type]
                    topic=payload.get("topic"),
                    actor=payload.get("actor"),
                    meeting_id=payload.get("meeting_id"),
                    limit=int(payload.get("limit") or 5),
                )
            )
        except FileNotFoundError as exc:
            return JSONResponse({"error": str(exc)}, status_code=503)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=503)
        except ProviderError as exc:
            return JSONResponse({"error": exc.message}, status_code=exc.status_code)
        return JSONResponse(response.to_dict())

    return Starlette(
        debug=False,
        lifespan=lifespan,
        routes=[
            Route("/health", endpoint=health, methods=["GET"]),
            Route("/agent", endpoint=agent, methods=["POST"]),
            Mount("/", app=handle_mcp),
        ],
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run kommunalpolitik MCP over streamable HTTP")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--stateful", action="store_true", help="Track MCP sessions instead of using stateless requests")
    parser.add_argument("--json-response", action="store_true", help="Use JSON responses instead of SSE streams")
    args = parser.parse_args(argv)

    uvicorn.run(
        create_app(stateless=not args.stateful, json_response=args.json_response),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
