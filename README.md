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
- **SessionNet Scraping**: Für weitere Städte ohne OParl-API
- **Bestehende Infrastruktur**: Python Scraper bereits vorhanden

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
