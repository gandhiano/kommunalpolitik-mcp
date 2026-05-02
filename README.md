# Kommunalpolitik MCP Server

Ein lokaler Model Context Protocol (MCP) Server und Ingestion-Toolkit für kommunalpolitische Dokumente. Viele deutsche Ratsinformationssysteme bieten keine OParl-Schnittstelle an, liefern über OParl nur unvollständige Metadaten oder lassen wichtige Dokumente wie Niederschriften, Einladungen, Anträge und Anlagen aus. Dieses Projekt verfolgt deshalb einen pragmatischen Adapter-Ansatz: öffentliche RIS-/SessionNet-Daten werden direkt eingelesen, lokal normalisiert und über MCP-Tools für LLM-gestützte Recherche nutzbar gemacht.

Der aktuelle Stand ist **Witzenhausen-first**. Das öffentliche SessionNet-Bürgerinfoportal der Stadt Witzenhausen ist unterstützt und getestet. Die Architektur soll generisch genug werden, um weitere Kommunen und Ratsinformationssysteme über Adapter/Konfigurationen anzubinden.

Dieses Projekt ist in aktiver Entwicklung. Nutzung auf eigene Verantwortung.

## Warum nicht einfach OParl?

OParl bleibt sinnvoll, wenn eine Kommune eine offene und vollständige Schnittstelle bereitstellt. In der Praxis fehlen aber oft genau die Dokumente, die für politische Recherche wichtig sind: Sitzungsniederschriften, Tagesordnungs-PDFs, Vorlagen, Anlagen, Änderungsanträge und Bekanntmachungen. Dieses Projekt behandelt OParl daher als eine mögliche Quelle, aber nicht als einzige Ingestion-Strategie.

Der Witzenhausen-Adapter zeigt, wie sich die öffentlich verfügbaren SessionNet-Daten konsistent und effizient lokal sammeln, indexieren und über MCP abfragen lassen.

## Unterstützte Kommunen

| Kommune | Quelle | Status |
| --- | --- | --- |
| Witzenhausen | Öffentliches SessionNet-Bürgerinfoportal | Unterstützt und lokal getestet |

Weitere Kommunen sind willkommen. Neue Kommunen sollten als Adapter/Konfiguration ergänzt werden, nicht durch Vermischung mit Witzenhausen-spezifischer Logik.

## Betriebsmodell

Empfohlen ist zunächst **eine lokale Datenbank und ein MCP-Runtime pro Kommune**.

Das hält Suchergebnisse sauber auf eine Kommune begrenzt, reduziert versehentliche Vermischung, erleichtert Updates und macht Quell-spezifische Rate-Limits und Datenqualitätsprüfungen einfacher. Ein Multi-Kommunen-Betrieb kann später auf einer gemeinsamen Basis entstehen, sollte aber explizit mit `municipality_id`/Mandantenfähigkeit modelliert werden.

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

## Architektur-Richtung

Geplante Richtung:

- Gemeinsame Ingestion-Grundbausteine für HTTP, Caching, Parsing, Persistenz und Textindexierung
- Adapter für SessionNet, OParl und perspektivisch weitere Ratsinformationssysteme
- Konfiguration pro Kommune mit eigener Quelle, eigenem Datenverzeichnis und eigener SQLite-Datenbank
- MCP-Runtime pro Kommune als Standardmodell
- Optionaler Multi-Kommunen-Betrieb erst später mit expliziter Mandantenfähigkeit

Aktuell sind einige Module noch Witzenhausen-spezifisch benannt. Das ist bewusst akzeptiert, solange nur Witzenhausen unterstützt wird. Die Generalisierung sollte erfolgen, sobald eine zweite Kommune angebunden wird.

## Verantwortliche Nutzung

Dieses Projekt zielt ausschließlich auf öffentliche Informationen. Verwende es nicht, um Login-Bereiche abzufragen, Zugriffskontrollen zu umgehen oder nicht-öffentliche/private Daten zu sammeln. Betreiberinnen und Betreiber sind selbst dafür verantwortlich, geltendes Recht, lokale Nutzungsbedingungen, `robots.txt`-Hinweise, Rate-Limits und Datenschutzanforderungen einzuhalten.

Die extrahierten Daten können personenbezogene Informationen enthalten, die bereits in öffentlichen Sitzungsunterlagen veröffentlicht wurden. Gehe damit sorgsam um, speichere nur was du brauchst und veröffentliche keine lokalen Datenbank-/PDF-Dumps ohne eigene Prüfung der rechtlichen und datenschutzbezogenen Rahmenbedingungen.

## Support und Integration

Wenn du dieses Projekt für deine Kommune adaptieren, in einen lokalen Workflow integrieren oder als gehostete/verwaltete Lösung betreiben möchtest, kontaktiere den Autor. Unterstützung bei neuen Adaptern, Datenqualität, OCR, MCP-Deployment und Integration in bestehende Rechercheprozesse ist möglich.

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
1. **MVP**: Witzenhausen SessionNet-Ingestion, lokale SQLite/PDF/Text-Ablage, MCP-Tools
2. **Iteration 1**: Volltext-Snippet-Suche, Evidenz-Packs, Personen-/Fraktions-Heuristiken
3. **Iteration 2**: Adapter-Abstraktion für weitere Kommunen und Ratsinformationssysteme
4. **Iteration 3**: OCR-Fallback, bessere Datenqualität, HTTP/Streamable-MCP-Deployment

## 📋 Status

- ✅ Witzenhausen-Ingestion funktionsfähig
- ✅ Lokale Dokument- und Volltextsuche funktionsfähig
- ✅ MCP-Tools für Evidenzsuche verfügbar
- 🔄 Adapter-Abstraktion und weitere Kommunen in Entwicklung

## Lizenz

Dieses Projekt steht unter der Apache License 2.0. Siehe [LICENSE](LICENSE).

## Beitragen

Beiträge sind willkommen. Siehe [CONTRIBUTING.md](CONTRIBUTING.md).

## 🛠️ Technologie

- **Python** (bestehende Infrastruktur nutzen)
- **MCP Protocol** für Client-LLM Integration
- **OParl 1.1** konforme JSON-Schemas
- **Pydantic** für Datenvalidierung
