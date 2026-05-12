# Roadmap

This project is currently Witzenhausen-first, but should become a generic local-first MCP server and ingestion toolkit for municipal political documents.

## Current Position

- Supported adapter: Witzenhausen public SessionNet Bürgerinfoportal.
- Runtime model: one local SQLite database and one MCP runtime per municipality.
- Current data path: local ingestion into `data/<municipality>/`, then read-only MCP tools over the local DB.
- Current clients: local stdio MCP clients such as OpenCode, Claude Desktop, and MCP Inspector.

## Direction

- Keep the repository generic: `kommunalpolitik-mcp`.
- Keep Witzenhausen as the first supported municipality and reference adapter.
- Generalize tool names and runtime configuration so the MCP API is not Witzenhausen-specific.
- Add municipality configs before adding more towns.
- Add source adapters over time, e.g. SessionNet, OParl where complete, and other RIS systems.
- Prefer one DB/runtime per municipality until there is an explicit multi-tenant model.

## Packaging

Planned local usage:

- Python CLI for developers.
- Docker Compose for less technical local installs.
- Persistent local volume for SQLite, cached HTML, PDFs, and extracted text.

Planned MVP server usage:

- HTTP/Streamable MCP transport in addition to stdio.
- Private-network backend access first; do not expose the MCP endpoint directly to the public internet.
- Defer application authentication until there is a frontend web app or a concrete hosted-user model.
- Separate ingestion/sync job from the read-only MCP server.
- Deployment docs for a private endpoint, e.g. `http://<private-host>:8000/mcp` or an internal HTTPS route.

## Non-Technical Users

Early target: Green fraction users who should not need local developer tooling.

Preferred first hosted model:

- Host MCP + database + sync centrally.
- Keep MCP as a backend service reachable only from a private network.
- Let power users consume it from existing MCP clients such as OpenCode when they are on that private network.
- Provide a simple frontend web app later for non-technical users.
- Avoid operating LLM billing in the first iteration if users can use their own LLM product accounts.

Possible later model:

- A simple web app with user login.
- Either BYOK (users bring API keys) or centrally managed LLM billing.
- Add tenant/user roles only when the hosted use case requires them.

## Near-Term Implementation Plan

1. Verify Dockerfile, Docker Compose example, and HTTP MCP runtime for private-network MVP usage.
2. Keep the HTTP/MCP smoke-test workflow current as deployment behavior changes.
3. Extract a clearer adapter interface once a second municipality is implemented.
4. Continue the server-side agent runtime refactor described in [Agent Runtime Steering](agent-runtime.md), keeping `/agent` public and `/mcp` private.

## Caveats

- The current parser and ingestion implementation is still Witzenhausen/SessionNet-specific.
- Actor extraction is heuristic. Evidence snippets should be cited and interpreted cautiously.
- Public documents may contain personal data. Do not publish local data dumps without a separate legal/privacy review.
