"""Command line entry point for kommunalpolitik-mcp."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import http_server, mcp_server, smoke_http
from .agent import evaluate
from .ingest import witzenhausen


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kommunalpolitik")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("mcp", help="Start the MCP stdio server")
    subparsers.add_parser("http", help="Start the MCP streamable HTTP server")
    subparsers.add_parser("smoke-http", help="Smoke test an MCP streamable HTTP server")
    subparsers.add_parser("eval-agent", help="Run local agent quality evals")

    ingest = subparsers.add_parser("ingest", help="Run ingestion commands")
    ingest_subparsers = ingest.add_subparsers(dest="municipality", required=True)
    ingest_subparsers.add_parser("witzenhausen", help="Run Witzenhausen SessionNet ingestion")

    args, remaining = parser.parse_known_args(argv)
    if args.command == "mcp":
        mcp_server.run()
    elif args.command == "http":
        http_server.main(remaining)
    elif args.command == "smoke-http":
        smoke_http.main(remaining)
    elif args.command == "eval-agent":
        evaluate.main(remaining)
    elif args.command == "ingest" and args.municipality == "witzenhausen":
        witzenhausen.main(remaining)
