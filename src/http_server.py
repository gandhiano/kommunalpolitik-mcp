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

from .mcp_server import server


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
        await session_manager.handle_request(scope, receive, send)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "transport": "streamable-http"})

    return Starlette(
        debug=False,
        lifespan=lifespan,
        routes=[
            Route("/health", endpoint=health, methods=["GET"]),
            Mount("/mcp", app=handle_mcp),
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
