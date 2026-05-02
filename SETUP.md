# Setup Instructions

## 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
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
      "command": "/YOUR_ABSOLUTE_PATH/kommunalpolitik-mcp/.venv/bin/kommunalpolitik-mcp",
      "args": [],
      "cwd": "/YOUR_ABSOLUTE_PATH/kommunalpolitik-mcp"
    }
  }
}
```

3. Run MCP Inspector:
```bash
npx @modelcontextprotocol/inspector mcp_config.json
```

## 3. MCP verwenden

Für eine gehostete MCP-Instanz kann OpenCode direkt den Remote-Endpunkt nutzen:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "kommunalpolitik": {
      "type": "remote",
      "url": "https://YOUR-HOST/kommunalpolitik/mcp",
      "enabled": true
    }
  }
}
```

Beispiele für Fragen:

```text
Was steht in der nächsten Stadtverordnetenversammlung an? Gibt es schon eine Tagesordnung und Unterlagen?
```

```text
Welche Beschlüsse oder Diskussionen gab es seit 2021 zum Haushalt? Bitte mit Sitzungsdatum und Quellenstellen.
```

Für lokale Entwicklung oder Tests läuft der MCP Server über `stdio`. Clients wie OpenCode, Claude Desktop oder der MCP Inspector starten ihn über eine Config:

Lokale stdio-Config:

```json
{
  "mcpServers": {
    "kommunalpolitik-mcp": {
      "command": "/ABSOLUTE/PATH/kommunalpolitik-mcp/.venv/bin/kommunalpolitik-mcp",
      "args": [],
      "cwd": "/ABSOLUTE/PATH/kommunalpolitik-mcp",
      "env": {
        "KOMMUNALPOLITIK_CONFIG": "configs/municipalities/witzenhausen.json"
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

ChatGPT Custom Connectors benötigen einen öffentlich erreichbaren Streamable-HTTP MCP Server. Eine lokale `stdio`-Config reicht für OpenCode/Claude Desktop/Inspector, aber nicht direkt für ChatGPT.

Für Server-Deployments kann der Streamable-HTTP-Transport gestartet werden:

```bash
kommunalpolitik http --host 0.0.0.0 --port 8000
```

Der MCP-Endpunkt ist `/mcp`, der Healthcheck ist `/health`.

## 4. Witzenhausen-Daten lokal laden

Die Standardkonfiguration liegt in `configs/municipalities/witzenhausen.json`. Der CLI-Default verwendet diese Datei automatisch; mit `--config PFAD` kann eine andere Kommune/Konfiguration ausgewählt werden.

```bash
source .venv/bin/activate
pip install -e .
kommunalpolitik ingest witzenhausen init-db
kommunalpolitik ingest witzenhausen --allow-public-crawl bodies
kommunalpolitik ingest witzenhausen --allow-public-crawl meetings --from-year 2026 --to-year 2026
kommunalpolitik ingest witzenhausen --allow-public-crawl details --limit 25
kommunalpolitik ingest witzenhausen --allow-public-crawl documents --limit 25
kommunalpolitik ingest witzenhausen extract-text --limit 25
kommunalpolitik ingest witzenhausen index-chunks
kommunalpolitik ingest witzenhausen extract-actors
kommunalpolitik ingest witzenhausen status
```

Die bisherigen Modulaufrufe wie `python -m src.ingest.witzenhausen status` bleiben weiterhin nutzbar.

Die Daten liegen danach lokal unter `data/witzenhausen/`. PDFs und extrahierte Texte werden ebenfalls dort gespeichert.

Für eine vollständige lokale Datenbank inklusive Volltext- und Actor-Index:

```bash
kommunalpolitik ingest witzenhausen --allow-public-crawl --delay 0.5 sync --from-year 2000 --to-year 2026
```

Die Analyse-Tools basieren auf heuristischen Treffern. `strong` bedeutet, dass ein Handlungsverb wie `beantragt`, `fragt`, `bittet`, `kritisiert` oder `berichtet` nahe an der Person/Fraktion erkannt wurde. `weak` bedeutet nur eine Erwähnung in der Nähe des Snippets.
