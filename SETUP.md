# Setup Instructions

## 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. MCP Inspector Setup

1. Copy the example config:
```bash
cp mcp_config.example.json mcp_config.json
```

2. Update `mcp_config.json` with your absolute path:
```json
{
  "mcpServers": {
    "kommunalpolitik-mcp": {
      "command": "/YOUR_ABSOLUTE_PATH/kommunalpolitik-mcp/.venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/YOUR_ABSOLUTE_PATH/kommunalpolitik-mcp"
    }
  }
}
```

3. Run MCP Inspector:
```bash
npx @modelcontextprotocol/inspector mcp_config.json
```

## 3. MCP lokal verwenden

Der MCP Server läuft über `stdio`. Clients wie OpenCode, Claude Desktop oder der MCP Inspector starten ihn über eine Config:

```json
{
  "mcpServers": {
    "kommunalpolitik-mcp": {
      "command": "/ABSOLUTE/PATH/kommunalpolitik-mcp/.venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/ABSOLUTE/PATH/kommunalpolitik-mcp",
      "env": {
        "KOMMUNALPOLITIK_DB_PATH": "/ABSOLUTE/PATH/kommunalpolitik-mcp/data/witzenhausen/witzenhausen.sqlite",
        "KOMMUNALPOLITIK_MUNICIPALITY_ID": "witzenhausen",
        "KOMMUNALPOLITIK_MUNICIPALITY_NAME": "Witzenhausen"
      }
    }
  }
}
```

Zum Testen mit dem MCP Inspector:

```bash
npx @modelcontextprotocol/inspector mcp_config.json
```

MCP Tools:

- `list_bodies`
- `list_meetings`
- `get_meeting`
- `search_documents`
- `get_document_text`
- `search_text`
- `find_actor_topics`
- `get_evidence_pack`

ChatGPT Custom Connectors benötigen einen öffentlich erreichbaren HTTP/SSE bzw. Streamable-HTTP MCP Server. Diese lokale `stdio`-Config reicht für OpenCode/Claude Desktop/Inspector, aber nicht direkt für ChatGPT. Dafür braucht es später einen kleinen HTTP-Transport oder Deployment.

## 4. Witzenhausen-Daten lokal laden

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m src.ingest.witzenhausen init-db
python -m src.ingest.witzenhausen --allow-public-crawl bodies
python -m src.ingest.witzenhausen --allow-public-crawl meetings --from-year 2026 --to-year 2026
python -m src.ingest.witzenhausen --allow-public-crawl details --limit 25
python -m src.ingest.witzenhausen --allow-public-crawl documents --limit 25
python -m src.ingest.witzenhausen extract-text --limit 25
python -m src.ingest.witzenhausen index-chunks
python -m src.ingest.witzenhausen extract-actors
python -m src.ingest.witzenhausen status
```

Die Daten liegen danach lokal unter `data/witzenhausen/`. PDFs und extrahierte Texte werden ebenfalls dort gespeichert.

Für eine vollständige lokale Datenbank inklusive Volltext- und Actor-Index:

```bash
python -m src.ingest.witzenhausen --allow-public-crawl --delay 0.5 sync --from-year 2000 --to-year 2026
```

Die Analyse-Tools basieren auf heuristischen Treffern. `strong` bedeutet, dass ein Handlungsverb wie `beantragt`, `fragt`, `bittet`, `kritisiert` oder `berichtet` nahe an der Person/Fraktion erkannt wurde. `weak` bedeutet nur eine Erwähnung in der Nähe des Snippets.
