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

Planned server/cloud usage:

- HTTP/Streamable MCP transport in addition to stdio.
- Bearer-token authentication for early hosted deployments.
- Separate ingestion/sync job from the read-only MCP server.
- Deployment docs for a hosted endpoint, e.g. `https://<domain>/<municipality>/mcp`.

## Non-Technical Users

Early target: Green fraction users who should not need local developer tooling.

Preferred first hosted model:

- Host MCP + database + sync centrally.
- Let users consume it from existing LLM interfaces where possible, especially ChatGPT Custom Connectors if available.
- Avoid operating LLM billing in the first iteration if users can use their own LLM product accounts.

Possible later model:

- A simple web app with user login.
- Either BYOK (users bring API keys) or centrally managed LLM billing.
- Add tenant/user roles only when the hosted use case requires them.

## Near-Term Implementation Plan

1. Add `pyproject.toml` and a `kommunalpolitik` CLI.
2. Add Dockerfile and Docker Compose examples.
3. Add HTTP MCP transport and hosted connector docs.
4. Extract a clearer adapter interface once a second municipality is implemented.

## Caveats

- The current parser and ingestion implementation is still Witzenhausen/SessionNet-specific.
- Actor extraction is heuristic. Evidence snippets should be cited and interpreted cautiously.
- Public documents may contain personal data. Do not publish local data dumps without a separate legal/privacy review.
