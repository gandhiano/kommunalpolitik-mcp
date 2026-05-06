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

Expose those endpoints only through private infrastructure for the MVP. Power users can connect MCP clients such as OpenCode while they are on the private network. Non-technical users should use a later frontend web app instead of connecting to MCP directly.

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
