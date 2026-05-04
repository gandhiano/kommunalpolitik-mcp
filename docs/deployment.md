# Deployment

This document describes how to run the HTTP MCP service for one hosted municipality. Infrastructure details such as DNS, TLS, reverse proxies, process supervision, backups, and monitoring depend on the target environment and are intentionally not specified here.

## Runtime Model

- Run one MCP service per municipality.
- Keep the SQLite database and downloaded documents outside the container image.
- Mount the data directory read-only into the MCP runtime.
- Refresh data separately from the hosted MCP runtime.

## HTTP Service

Start the Streamable HTTP MCP server:

```bash
kommunalpolitik http --host 0.0.0.0 --port 8000
```

The service exposes:

- `/mcp` - Streamable HTTP MCP endpoint
- `/health` - basic health check

Expose those endpoints through your own HTTPS frontend according to your infrastructure.

Example remote MCP client configuration:

```json
{
  "mcp": {
    "kommunalpolitik": {
      "type": "remote",
      "url": "https://YOUR-HOST/kommunalpolitik/mcp",
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
  -p 8000:8000 \
  -e KOMMUNALPOLITIK_CONFIG=configs/municipalities/witzenhausen.json \
  -v ./data:/app/data:ro \
  kommunalpolitik-mcp
```

`deploy/docker-compose.example.yml` provides a minimal Compose starting point with placeholder values.

## Data Refresh

Keep data refresh separate from the read-only MCP runtime. For example:

```bash
kommunalpolitik ingest witzenhausen --allow-public-crawl --delay 0.5 sync --from-year 2025 --to-year 2026
```

Use conservative delays and only crawl public pages.

## Verification

- `/health` returns `{"status":"ok"}`.
- The service can read the configured SQLite database.
- MCP tool listing returns the expected tools.
- A small `search_text` call returns results.
