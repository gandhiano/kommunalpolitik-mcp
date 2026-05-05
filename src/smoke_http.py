"""Smoke test for the kommunalpolitik MCP HTTP endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _health_url(mcp_url: str) -> str:
    base_url = mcp_url.removesuffix("/")
    if base_url.endswith("/mcp"):
        return f"{base_url[:-4]}/health"
    return f"{base_url}/health"


def _check_health(url: str, timeout: float) -> dict[str, Any]:
    try:
        with urlopen(_health_url(url), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"health check failed: {exc}") from exc

    if payload.get("status") != "ok":
        raise RuntimeError(f"health check returned unexpected payload: {payload}")
    return payload


async def _check_mcp(url: str, timeout: float, call_tool: bool) -> list[str]:
    async with streamablehttp_client(url, timeout=timeout) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            if "search_text" not in tool_names:
                raise RuntimeError(f"MCP tool list is missing search_text: {tool_names}")
            if call_tool:
                await session.call_tool("list_bodies", {"limit": 1})
            return tool_names


async def run(url: str, timeout: float, call_tool: bool) -> None:
    health = _check_health(url, timeout)
    tool_names = await _check_mcp(url, timeout, call_tool)
    print(
        json.dumps(
            {
                "status": "ok",
                "health": health,
                "tools": tool_names,
                "database_checked": call_tool,
            },
            indent=2,
        )
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Smoke test a kommunalpolitik MCP HTTP endpoint")
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp", help="MCP HTTP endpoint URL")
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout in seconds")
    parser.add_argument(
        "--call-tool",
        action="store_true",
        help="Call list_bodies to verify the service can read the configured database",
    )
    args = parser.parse_args(argv)
    asyncio.run(run(args.url, args.timeout, args.call_tool))


if __name__ == "__main__":
    main()
