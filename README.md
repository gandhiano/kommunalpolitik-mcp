# Kommunalpolitik MCP Server

Ein lokaler Model Context Protocol (MCP) Server für deutsche Kommunalpolitik. Der aktuelle Fokus liegt auf Witzenhausen: öffentliche SessionNet-Daten werden lokal in SQLite/PDF/Text gespeichert und über MCP-Tools für LLMs wie OpenCode, Claude Desktop oder den MCP Inspector nutzbar gemacht.

## Schnellstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.ingest.witzenhausen init-db
python -m src.ingest.witzenhausen --allow-public-crawl --delay 0.5 sync --from-year 2024 --to-year 2026
python -m src.ingest.witzenhausen status
```

Danach den MCP Server lokal testen:

```bash
cp mcp_config.example.json mcp_config.json
# mcp_config.json: absolute Pfade anpassen
npx @modelcontextprotocol/inspector mcp_config.json
```

Für OpenCode als globalen lokalen MCP Server:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "kommunalpolitik": {
      "type": "local",
      "command": [
        "/bin/zsh",
        "-lc",
        "cd /ABSOLUTE/PATH/kommunalpolitik-mcp && exec .venv/bin/python -m src.mcp_server"
      ],
      "enabled": true,
      "environment": {
        "WITZENHAUSEN_DB_PATH": "/ABSOLUTE/PATH/kommunalpolitik-mcp/data/witzenhausen/witzenhausen.sqlite"
      }
    }
  }
}
```

Beispielfragen in OpenCode:

```text
Use kommunalpolitik to search Witzenhausen text for Haushalt from 2021 to 2026, limited to minutes.
```

```text
Use kommunalpolitik to get an evidence pack for Grüne and Haushalt from 2021 to 2026, then summarize by topic with citations.
```

## 🎯 Ziel

Dieser MCP Server agiert als **Datenquelle und Kontext-Provider** für Client-LLMs und ermöglicht:
- Automatische Zusammenfassungen von Sitzungsprotokollen
- Suche nach Themen über mehrere Sitzungen hinweg
- Analyse von Abstimmungsverhalten
- Benachrichtigungen über relevante Tagesordnungspunkte

## 👥 Zielgruppen

### 1. Stadtverordnete/Fraktionen
- Kommende Sitzungen und Themen
- Fraktionsargumente und Positionsfindung
- Antragsunterstützung

### 2. Bürger
- Parteienpositionen zu Themen
- Historische Entwicklung über Legislaturperioden
- Politische Transparenz

### 3. Stadtverwaltung
- Umsetzungsaufgaben aus Beschlüssen
- Monatsplanung basierend auf Gremienbeschlüssen
- Verwaltungsplanung

## 🏗️ Architektur

```
kommunalpolitik-mcp/
├── src/
│   ├── mcp_server.py           # Haupt-MCP Server
│   ├── tools/                  # MCP Tool Implementierungen
│   ├── providers/              # Datenquellen-Adapter
│   └── schemas/                # JSON-Schemas
├── specs/                      # OParl Spezifikation
├── .vibe/                      # Entwicklungsplan
└── requirements.txt
```

## 📊 Datenquellen

- **OParl API**: 23+ Kommunen verfügbar (Rees, Gernsheim, Dortmund, etc.)
- **SessionNet Scraping**: Für Witzenhausen und weitere Städte ohne nutzbare OParl-API
- **Bestehende Infrastruktur**: Python Scraper bereits vorhanden

## Witzenhausen SessionNet Ingestion

Witzenhausen nutzt ein öffentliches SessionNet-Bürgerinfoportal statt einer offenen OParl-API. Die neue lokale Ingestion liest ausschließlich öffentliche BI-Seiten, speichert Metadaten in SQLite und PDFs/Texte im lokalen Dateisystem.

Für eine vollständige lokale Datenbank kann `sync` über alle Jahre laufen. Das dauert länger und benötigt mehrere GB Speicherplatz:

```bash
python -m src.ingest.witzenhausen --allow-public-crawl --delay 0.5 sync --from-year 2000 --to-year 2026
```

Für regelmäßige Aktualisierungen reicht normalerweise ein kleiner aktueller Zeitraum:

```bash
python -m src.ingest.witzenhausen --allow-public-crawl --delay 0.5 sync --from-year 2025 --to-year 2026
```

Die Einzelbefehle darunter sind nützlich für Entwicklung und Debugging:

```bash
source .venv/bin/activate
pip install -r requirements.txt

# Lokale Datenbank anlegen
python -m src.ingest.witzenhausen init-db

# Öffentliche Gremien laden
python -m src.ingest.witzenhausen --allow-public-crawl bodies

# Sitzungen laden, z.B. ab 2026
python -m src.ingest.witzenhausen --allow-public-crawl meetings --from-year 2026 --to-year 2026

# Details, Tagesordnung, Vorlagen- und Dokumentlinks laden
python -m src.ingest.witzenhausen --allow-public-crawl details --limit 25

# PDFs herunterladen und eingebetteten Text extrahieren
python -m src.ingest.witzenhausen --allow-public-crawl documents --limit 25
python -m src.ingest.witzenhausen extract-text --limit 25

# Volltext in Such-Snippets aufteilen und Personen/Fraktionen heuristisch erkennen
python -m src.ingest.witzenhausen index-chunks
python -m src.ingest.witzenhausen extract-actors

# Status anzeigen
python -m src.ingest.witzenhausen status
```

Lokale Ausgabe:

```text
data/witzenhausen/
├── witzenhausen.sqlite
├── raw/
│   ├── html/
│   └── pdf/
└── text/
```

Hinweise:
- Es werden keine Login-Seiten und kein Gremieninfoportal (`/gi/`) verwendet.
- Live-Requests sind bewusst opt-in über `--allow-public-crawl`.
- HTML wird lokal gecacht, PDFs werden nur einmal heruntergeladen.
- Dokumente mit `NS`, `Niederschrift` oder `Protokoll` werden als `minutes` klassifiziert.
- Für Analysefragen gibt es zusätzlich einen lokalen FTS-Index über Text-Chunks und heuristische Actor-Mentions für Personen, Parteien und Fraktionen.
- Die lokalen Daten unter `data/` werden nicht versioniert.
- Die Heuristiken liefern Evidenzstellen, keine rechtlich/verbindliche politische Bewertung. Zusammenfassungen sollten mit Quellen/Snippets arbeiten.

## 🔧 MCP Tools

### Basis-Tools (MVP)
- `list_municipalities()` - Verfügbare Städte
- `get_meetings()` - Sitzungen mit Metadaten
- `get_meeting_details()` - Vollständige Meeting-Daten
- `get_protocol_text()` - Protokoll-Volltext

### Witzenhausen-Tools

- `list_witzenhausen_bodies()` - Gremien/Fraktionen auflisten
- `list_witzenhausen_meetings()` - Sitzungen nach Gremium/Jahr listen
- `get_witzenhausen_meeting()` - Sitzung mit Tagesordnung und Dokumenten abrufen
- `search_witzenhausen_text()` - Volltext-Snippet-Suche mit Datum/Gremium/Dokumenttyp-Filtern
- `find_witzenhausen_actor_topics()` - Evidenzstellen für Person, Partei oder Fraktion suchen
- `get_witzenhausen_evidence_pack()` - Evidenzstellen gruppiert für Zusammenfassungen abrufen

Beispiele für Agent/LLM-Fragen:

```text
Use kommunalpolitik to find evidence for SPD topics about Haushalt from 2021 to 2026 in Witzenhausen minutes.
```

```text
Use kommunalpolitik to get an evidence pack for Grüne and Haushalt from 2021 to 2026, then summarize by topic with citations.
```

### Politik-Tools
- `get_organizations()` - Fraktionen/Parteien
- `search_topics_by_keyword()` - Themensuche
- `get_voting_history()` - Abstimmungsverhalten

### Verwaltungs-Tools
- `get_decisions_requiring_action()` - Umsetzungsaufgaben
- `get_meeting_outcomes()` - Beschlüsse für Planung

## 🚀 Usage

### With Amazon Q

1. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Start Q with kommunalpolitik agent:**
   ```bash
   q chat --agent kommunalpolitik
   ```

3. **Test the MCP tools:**
   ```
   List available German municipalities
   Show me recent meetings from Dortmund
   ```

## 🚀 Entwicklungsansatz

**Iterative Entwicklung:**
1. **MVP**: Basis-Funktionalität (Kommunen, Sitzungen, Protokolle)
2. **Iteration 1**: Themensuche und Agenda-Tools
3. **Iteration 2**: Abstimmungsanalyse und Fraktions-Tools
4. **Iteration 3**: Verwaltungs-Tools und Benachrichtigungen

## 📋 Status

- ✅ Exploration abgeschlossen
- ✅ Planung finalisiert
- 🔄 Implementierung startet

## Lizenz

Dieses Projekt steht unter der Apache License 2.0. Siehe [LICENSE](LICENSE).

## Beitragen

Beiträge sind willkommen. Siehe [CONTRIBUTING.md](CONTRIBUTING.md).

## 🛠️ Technologie

- **Python** (bestehende Infrastruktur nutzen)
- **MCP Protocol** für Client-LLM Integration
- **OParl 1.1** konforme JSON-Schemas
- **Pydantic** für Datenvalidierung
