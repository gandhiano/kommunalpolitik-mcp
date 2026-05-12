# Deployment

This document describes how to run the HTTP MCP service for one municipality. For the MVP, treat this service as a private backend: expose it only on localhost, a private network, a VPN, or an internal reverse-proxy route. Do not publish the MCP endpoint directly to the public internet without adding an explicit authentication and authorization layer.

## Runtime Model

- Run one MCP service per municipality.
- Keep the SQLite database and downloaded documents outside the container image.
- Mount the data directory read-only into the MCP runtime.
- Refresh data separately from the hosted MCP runtime.
- Keep the MCP HTTP endpoint private; authentication is deferred until the frontend or hosted-user model needs it.

## HTTP Service

Start the Streamable HTTP MCP server:

```bash
kommunalpolitik http --host 0.0.0.0 --port 8000
```

The service exposes:

- `/mcp` - Streamable HTTP MCP endpoint
- `/health` - basic health check
- `/agent` - server-side web agent endpoint
- `/feedback` - opt-in answer feedback endpoint

Expose those endpoints only through private infrastructure for the MVP. Power users can connect MCP clients such as OpenCode while they are on the private network. Non-technical users should use a later frontend web app instead of connecting to MCP directly.

For a public pilot web app, expose only the web frontend and `/agent` behind application authentication. Keep `/mcp` private or disable it in that public runtime with:

```bash
KOMMUNALPOLITIK_MCP_ENABLED=false
```

## Pilot Web App Settings

The HTTP runtime can serve a built frontend when `web/frontend/dist` exists, or when `KOMMUNALPOLITIK_WEB_DIST` points at another build directory.

Recommended public pilot settings use placeholders only:

```env
KOMMUNALPOLITIK_WEB_DIST=/APP/PATH/web/frontend/dist
KOMMUNALPOLITIK_MCP_ENABLED=false
KOMMUNALPOLITIK_AUTH_PASSWORD=REPLACE_WITH_PILOT_PASSWORD
KOMMUNALPOLITIK_SESSION_SECRET=REPLACE_WITH_RANDOM_SECRET
KOMMUNALPOLITIK_SECURE_COOKIES=true
KOMMUNALPOLITIK_FEEDBACK_PATH=/PRIVATE/WRITABLE/PATH/feedback.sqlite
```

For local HTTP development without TLS, set `KOMMUNALPOLITIK_SECURE_COOKIES=false` so browsers keep the login cookie.

The feedback endpoint stores only deliberate user ratings. The frontend notice tells users that submitting feedback shares the question, answer, source metadata, and optional comment for improvement analysis.

## Model Routing

The backend supports a single default model and optional task-specific model choices. Usually one provider API key can call multiple models if the provider account has access.

```env
KOMMUNALPOLITIK_LLM_PROVIDER=openai
KOMMUNALPOLITIK_LLM_MODEL=DEFAULT_OR_BALANCED_MODEL
KOMMUNALPOLITIK_MODEL_QUICK=CHEAPER_FAST_MODEL
KOMMUNALPOLITIK_MODEL_BALANCED=BALANCED_MODEL
KOMMUNALPOLITIK_MODEL_STRONG=STRONGER_MODEL
```

`quick` research uses the quick model. `deep`, motion drafts, and follow-up tasks use the strong model. Other requests use the balanced model or the default fallback.

## Server-Side Agent Runtime

Runtime steering, current findings, and OpenCode limitations are tracked in [Agent Runtime Steering](agent-runtime.md).

With a configured LLM provider, the public web `/agent` endpoint uses a server-side tool-loop agent by default. The browser sends the task, while the backend LLM chooses allowed local tool calls (`search_text`, `list_meetings`, `get_meeting`) step by step and then returns the final answer.

```env
KOMMUNALPOLITIK_AGENT_RUNTIME=tool-loop
```

The Python HTTP layer remains the web/auth/cost/feedback boundary and executes only allowed local tools. It does not expose MCP directly to public users. For deterministic local debugging without LLM tool-loop behavior, set:

```env
KOMMUNALPOLITIK_AGENT_RUNTIME=deterministic
```

When `KOMMUNALPOLITIK_LLM_PROVIDER=none`, deterministic retrieval is always used.

OpenCode can also be used as a private backend runtime while keeping the same public `/agent` API. In this mode the HTTP app still owns auth, feedback, and response normalization; OpenCode runs server-side and is not exposed directly to browsers.

```env
KOMMUNALPOLITIK_AGENT_RUNTIME=opencode
KOMMUNALPOLITIK_OPENCODE_COMMAND=opencode
KOMMUNALPOLITIK_OPENCODE_MODEL=PROVIDER/MODEL
```

For lower latency, run a private OpenCode server on loopback and attach requests to it instead of letting every request initialize OpenCode from scratch:

```env
KOMMUNALPOLITIK_OPENCODE_ATTACH=http://127.0.0.1:PORT
```

Optional task-specific OpenCode settings:

```env
KOMMUNALPOLITIK_OPENCODE_AGENT_RESEARCH=research
KOMMUNALPOLITIK_OPENCODE_AGENT_BRIEFING=briefing
KOMMUNALPOLITIK_OPENCODE_AGENT_DRAFTING=drafting
KOMMUNALPOLITIK_OPENCODE_AGENT_SCRUTINY=scrutiny
KOMMUNALPOLITIK_OPENCODE_MODEL_QUICK=PROVIDER/FAST_MODEL
KOMMUNALPOLITIK_OPENCODE_MODEL_BALANCED=PROVIDER/BALANCED_MODEL
KOMMUNALPOLITIK_OPENCODE_MODEL_STRONG=PROVIDER/STRONG_MODEL
KOMMUNALPOLITIK_OPENCODE_TIMEOUT_SECONDS=120
```

If no `KOMMUNALPOLITIK_OPENCODE_AGENT*` value is set, OpenCode uses its default primary agent. Configure these variables only with OpenCode primary agents available in that runtime.

Configure OpenCode MCP access only inside the private runtime environment. Do not expose the OpenCode server or the MCP endpoint directly to public users.

Example remote MCP client configuration:

```json
{
  "mcp": {
    "kommunalpolitik": {
      "type": "remote",
      "url": "http://PRIVATE-HOST:8000/mcp",
      "enabled": true
    }
  }
}
```

## Data And Config

A deployed instance needs the same data layout as local ingestion:

```text
data/
└── witzenhausen/
    ├── witzenhausen.sqlite
    ├── raw/
    │   ├── html/
    │   └── pdf/
    └── text/
```

The default config is `configs/municipalities/witzenhausen.json`. Point the service to it with:

```bash
KOMMUNALPOLITIK_CONFIG=configs/municipalities/witzenhausen.json
```

## Docker

Build and run the included image:

```bash
docker build -t kommunalpolitik-mcp .
docker run --rm \
  -p 127.0.0.1:8000:8000 \
  -e KOMMUNALPOLITIK_CONFIG=configs/municipalities/witzenhausen.json \
  -v ./data:/app/data:ro \
  kommunalpolitik-mcp
```

`deploy/docker-compose.example.yml` provides a minimal private-network Compose starting point bound to localhost:

```bash
docker compose -f deploy/docker-compose.example.yml up --build -d
```

If you put it behind a reverse proxy, keep the route internal or add authentication before public exposure.

### End-To-End Local Docker Test

Run the containerized service locally, smoke-test the MCP endpoint, then stop the service:

```bash
docker compose -f deploy/docker-compose.example.yml up --build -d
kommunalpolitik smoke-http --url http://127.0.0.1:8000/mcp --call-tool
docker compose -f deploy/docker-compose.example.yml down
```

The smoke test verifies `/health`, MCP initialization, MCP tool listing, and read access to the configured SQLite database through the container mount.

## Data Refresh

Keep data refresh separate from the read-only MCP runtime. For example:

```bash
kommunalpolitik ingest witzenhausen --allow-public-crawl --delay 0.5 sync --from-year 2025 --to-year 2026
```

Use conservative delays and only crawl public pages.

## Verification

Run the HTTP/MCP smoke test against the private endpoint:

```bash
kommunalpolitik smoke-http --url http://127.0.0.1:8000/mcp
```

That verifies `/health`, initializes an MCP streamable HTTP session, and checks that the expected MCP tools are listed.

To also verify that the service can read the configured SQLite database, add `--call-tool`:

```bash
kommunalpolitik smoke-http --url http://127.0.0.1:8000/mcp --call-tool
```

For a running container, the same check can be run from the host as long as the port is bound locally.
