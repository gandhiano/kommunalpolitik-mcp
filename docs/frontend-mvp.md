# Frontend MVP Plan

## Goal

Build an AI-assisted kommunalpolitik workbench for Witzenhausen-first municipal political work.

The MVP must provide an agentic user experience for non-technical political users while keeping the MCP/data backend private and reusable for power users.

## Personas

### Standard User: Web App User

Typical users are Green fraction members who do not want to configure developer tools or MCP clients.

They access a browser-based web app, authenticate through the pilot access gate, and use guided AI workflows for:

- researching municipal documents
- preparing meeting briefings
- finding precedents and source evidence
- drafting motions or amendments
- editing and exporting results

They should not need to understand MCP, SQLite, ingestion, model providers, or API keys.

### Power User: MCP Client User

Power users use agentic clients such as OpenCode, Claude Desktop, or MCP Inspector.

They connect directly to the private MCP endpoint while on the private network or VPN.

They use their own agent/client and model configuration. The MCP server exposes municipal tools such as search, meetings, evidence packs, and document retrieval.

This path is separate from the web app and remains private.

## Product Experience

The web app should feel like a specialized kommunalpolitik agent, not a generic chatbot.

Example tasks:

- "Was steht in der nächsten Stadtverordnetenversammlung an?"
- "Erstelle ein Briefing zur nächsten Sitzung."
- "Finde frühere Anträge der Grünen zum Thema Verkehr."
- "Welche Beschlüsse oder Diskussionen gab es zum Haushalt seit 2021?"
- "Hilf mir, einen Antrag zur Hortbetreuung zu formulieren, mit Quellen."
- "Welche Gegenargumente oder früheren Beschlüsse muss ich beachten?"

The agent must show sources, distinguish evidence from interpretation, and make outputs editable.

## Architecture

```text
Standard user browser
-> web frontend
-> web API / server-side agent
-> municipal data/tool layer
-> optional LLM provider
-> SQLite/document corpus
```

```text
Power user agent client
-> private MCP endpoint
-> kommunalpolitik-mcp tools
-> SQLite/document corpus
```

The frontend does not contain LLM keys and does not run the agent. The agent runs server-side.

## MVP Agent Modes

### Research

Source-backed Q&A over the municipal corpus.

Uses:

- full-text search
- document search
- evidence packs
- actor/topic search

Returns:

- answer
- evidence snippets
- source links
- uncertainty notes

### Briefing

Meeting or topic briefing.

Uses:

- list meetings
- get meeting
- agenda items
- relevant documents
- text search

Returns:

- concise briefing
- important TOPs/documents
- possible questions
- source links

### Motion Draft

Drafting assistant for motions and amendments.

Uses:

- user-provided concern
- faction/profile fields
- retrieved precedents
- motion schema/template
- source evidence

Returns:

- structured editable draft
- cited precedents
- caveats
- Markdown export first

### Follow-Up

Allows refinements such as:

- "kürzer"
- "mehr juristisch"
- "als Änderungsantrag"
- "zeige mehr Quellen"
- "formuliere neutraler"

## LLM Provider Strategy

The backend supports multiple provider modes through one internal abstraction.

Provider modes:

- `none`
- `anthropic`
- `openai`
- `openai-compatible`

### None

Used for tests, development, demos, and retrieval-only mode.

No external LLM call.

The agent can still return evidence packs, structured summaries, and motion templates.

### Anthropic

Server-side Anthropic integration.

Environment:

```env
ANTHROPIC_API_KEY=
KOMMUNALPOLITIK_LLM_MODEL=
```

Likely first fully tested provider.

### OpenAI

Server-side OpenAI integration.

Environment:

```env
OPENAI_API_KEY=
KOMMUNALPOLITIK_LLM_MODEL=
```

### OpenAI-Compatible

Generic OpenAI-compatible API endpoint for local gateways or alternative hosted providers.

Environment:

```env
KOMMUNALPOLITIK_LLM_BASE_URL=
KOMMUNALPOLITIK_LLM_API_KEY=
KOMMUNALPOLITIK_LLM_MODEL=
```

This is the cleanest way to support local/provider-gateway options if available.

OpenCode itself remains a power-user MCP client path, not a backend LLM provider unless it exposes a compatible API.

## Configuration

Suggested environment:

```env
KOMMUNALPOLITIK_AGENT_ENABLED=true
KOMMUNALPOLITIK_LLM_PROVIDER=none
KOMMUNALPOLITIK_LLM_MODEL=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
KOMMUNALPOLITIK_LLM_BASE_URL=
KOMMUNALPOLITIK_LLM_API_KEY=
```

Allowed `KOMMUNALPOLITIK_LLM_PROVIDER` values:

```text
none
anthropic
openai
openai-compatible
```

## Authentication And Access

MVP pilot:

- Web app can be exposed over HTTPS for pilot users.
- Basic Auth is acceptable as a temporary pilot gate.
- MCP endpoint remains private and must not be publicly exposed.
- LLM endpoints require authentication.
- API keys remain server-side only.
- No keys are pasted into or stored by the frontend.

Later:

- Replace Basic Auth with proper user accounts or OAuth/OIDC.
- Add per-user rate limits and auditing.
- Add role/tenant model only when needed.

## Safety Rules

The agent must:

- cite source snippets for factual claims
- distinguish evidence from interpretation
- say when corpus coverage is incomplete
- avoid legal certainty
- never auto-submit motions
- make drafts editable
- keep original source links visible
- avoid exposing local data dumps
- keep public/private deployment boundaries explicit

## Implementation Phases

### Phase 1: Spec And Skeleton

- Add this frontend MVP plan.
- Define API contracts for agent requests/responses.
- Decide direct Python tool calls vs MCP HTTP calls for the web API.
- Add provider abstraction with `none` mode first.

### Phase 2: Backend Agent

- Add server-side agent endpoint.
- Add `none` provider for deterministic tests.
- Add Anthropic provider.
- Add OpenAI provider.
- Add OpenAI-compatible provider if simple.
- Add mocked tests; no real API calls in tests.
- Add prompt templates for research, briefing, and motion drafting.

### Phase 3: Frontend

- Add `web/frontend`.
- Build task-oriented UI:
- agent task box
- mode selector
- source/evidence cards
- briefing view
- motion editor
- Markdown export

### Phase 4: Deployment

- Extend Docker/Compose for web app and agent API.
- Keep MCP private.
- Expose only frontend/API through pilot auth.
- Add smoke test for web/agent endpoint.
