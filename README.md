# Kommunalpolitik MCP Server

Ein Model Context Protocol (MCP) Server für deutsche Kommunalpolitik, der strukturierten Zugang zu Sitzungen, Protokollen und politischen Daten über die OParl API bereitstellt.

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

## 🔧 MCP Tools

### Basis-Tools (MVP)
- `list_municipalities()` - Verfügbare Städte
- `get_meetings()` - Sitzungen mit Metadaten
- `get_meeting_details()` - Vollständige Meeting-Daten
- `get_protocol_text()` - Protokoll-Volltext

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

## 🛠️ Technologie

- **Python** (bestehende Infrastruktur nutzen)
- **MCP Protocol** für Client-LLM Integration
- **OParl 1.1** konforme JSON-Schemas
- **Pydantic** für Datenvalidierung
