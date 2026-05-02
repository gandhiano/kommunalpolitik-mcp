# Kommunalpolitik MCP Server

Ein lokaler Model Context Protocol (MCP) Server und Ingestion-Toolkit für kommunalpolitische Dokumente. Viele deutsche Ratsinformationssysteme bieten keine OParl-Schnittstelle an, liefern über OParl nur unvollständige Metadaten oder lassen wichtige Dokumente wie Niederschriften, Einladungen, Anträge und Anlagen aus. Dieses Projekt verfolgt deshalb einen pragmatischen Adapter-Ansatz: öffentliche RIS-/SessionNet-Daten werden direkt eingelesen, lokal normalisiert und über MCP-Tools für LLM-gestützte Recherche nutzbar gemacht.

Der aktuelle Stand ist **Witzenhausen-first**. Das öffentliche SessionNet-Bürgerinfoportal der Stadt Witzenhausen ist unterstützt und getestet. Die Architektur soll generisch genug werden, um weitere Kommunen und Ratsinformationssysteme über Adapter/Konfigurationen anzubinden.

Dieses Projekt ist in aktiver Entwicklung. Nutzung auf eigene Verantwortung.

## Was kann ich damit fragen?

Praktische Recherchehilfe für kommunalpolitische Arbeit: schnell herausfinden, was ansteht, was früher dokumentiert wurde und wo die belastbaren Fundstellen sind.

Beispiele für Fragen an einen MCP-fähigen Agenten:

```text
Was steht in der nächsten Stadtverordnetenversammlung an? Gibt es schon eine Tagesordnung und Unterlagen?
```

```text
Erstelle mir eine kurze Briefing-Notiz für die nächste Sitzung: wichtigste TOPs, relevante Dokumente und mögliche Rückfragen.
```

```text
Welche Beschlüsse oder Diskussionen gab es seit 2021 zum Haushalt? Bitte mit Sitzungsdatum und Quellenstellen.
```

```text
Welche Anträge oder Wortbeiträge der Grünen zum Thema Verkehr finde ich in den Niederschriften?
```

```text
Gibt es Hinweise, dass dieses Thema schon einmal behandelt wurde, bevor wir einen neuen Antrag formulieren?
```

## Nutzung

Wenn eine gehostete Instanz betrieben wird, kann OpenCode direkt den Remote-MCP-Endpunkt nutzen:

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

Für lokale Entwicklung oder Tests kann OpenCode stattdessen einen lokalen stdio-MCP Server starten:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "kommunalpolitik": {
      "type": "local",
      "command": [
        "/bin/zsh",
        "-lc",
        "cd /ABSOLUTE/PATH/kommunalpolitik-mcp && exec .venv/bin/kommunalpolitik-mcp"
      ],
      "enabled": true,
      "environment": {
        "KOMMUNALPOLITIK_CONFIG": "configs/municipalities/witzenhausen.json"
      }
    }
  }
}
```

## Warum nicht einfach OParl?

OParl bleibt sinnvoll, wenn eine Kommune eine offene und vollständige Schnittstelle bereitstellt. In der Praxis fehlen aber oft genau die Dokumente, die für politische Recherche wichtig sind: Niederschriften, Tagesordnungs-PDFs, Vorlagen, Anlagen und Anträge. Dieses Projekt behandelt OParl daher als eine mögliche Quelle, aber nicht als einzige Ingestion-Strategie.

## Unterstützte Kommunen

| Kommune | Quelle | Status |
| --- | --- | --- |
| Witzenhausen | Öffentliches SessionNet-Bürgerinfoportal | Unterstützt und lokal getestet |

Weitere Kommunen sind willkommen. Hinweise dazu stehen in [CONTRIBUTING.md](CONTRIBUTING.md).

## Betriebsmodell

Empfohlen ist zunächst **eine Datenbank und eine MCP-Runtime pro Kommune**. Das hält Suchergebnisse sauber begrenzt und erleichtert Updates.

## Lokaler Schnellstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
kommunalpolitik ingest witzenhausen init-db
kommunalpolitik ingest witzenhausen --allow-public-crawl --delay 0.5 sync --from-year 2024 --to-year 2026
kommunalpolitik ingest witzenhausen status
```

Die Witzenhausen-Defaults liegen in `configs/municipalities/witzenhausen.json`. Andere Pfade oder spätere Kommunen können über `--config` ausgewählt werden.

Danach den MCP Server lokal testen:

```bash
cp mcp_config.example.json mcp_config.json
# mcp_config.json: absolute Pfade anpassen
npx @modelcontextprotocol/inspector mcp_config.json
```

Für HTTP-/Server-Deployments steht zusätzlich ein Streamable-HTTP-Transport bereit:

```bash
kommunalpolitik http --host 0.0.0.0 --port 8000
```

Der MCP-Endpunkt liegt dann unter `/mcp`, ein einfacher Healthcheck unter `/health`.

## Repository-Struktur

```
kommunalpolitik-mcp/
├── configs/municipalities/    # Kommune-spezifische Runtime/Ingestion-Konfiguration
├── src/
│   ├── ingest/                 # Witzenhausen/SessionNet Ingestion
│   ├── tools/                  # MCP Tool Implementierungen
│   └── mcp_server.py           # Haupt-MCP Server
├── CONTRIBUTING.md
├── LICENSE
└── requirements.txt
```

## Witzenhausen SessionNet Ingestion

Witzenhausen nutzt ein öffentliches SessionNet-Bürgerinfoportal statt einer offenen OParl-API. Die neue lokale Ingestion liest ausschließlich öffentliche BI-Seiten, speichert Metadaten in SQLite und PDFs/Texte im lokalen Dateisystem.

Die Standardkonfiguration steht in `configs/municipalities/witzenhausen.json` und enthält Kommune, Adapter, SessionNet-Basis-URL, Datenverzeichnis und SQLite-Pfad. Der CLI-Default nutzt diese Datei; alternativ kann eine andere Konfiguration mit `--config PFAD` angegeben werden.

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
pip install -e .

# Lokale Datenbank anlegen
kommunalpolitik ingest witzenhausen init-db

# Öffentliche Gremien laden
kommunalpolitik ingest witzenhausen --allow-public-crawl bodies

# Sitzungen laden, z.B. ab 2026
kommunalpolitik ingest witzenhausen --allow-public-crawl meetings --from-year 2026 --to-year 2026

# Details, Tagesordnung, Vorlagen- und Dokumentlinks laden
kommunalpolitik ingest witzenhausen --allow-public-crawl details --limit 25

# PDFs herunterladen und eingebetteten Text extrahieren
kommunalpolitik ingest witzenhausen --allow-public-crawl documents --limit 25
kommunalpolitik ingest witzenhausen extract-text --limit 25

# Volltext in Such-Snippets aufteilen und Personen/Fraktionen heuristisch erkennen
kommunalpolitik ingest witzenhausen index-chunks
kommunalpolitik ingest witzenhausen extract-actors

# Status anzeigen
kommunalpolitik ingest witzenhausen status
```

Die bisherigen Modulaufrufe wie `python -m src.ingest.witzenhausen status` bleiben für Entwicklung und Debugging nutzbar.

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

## Verantwortliche Nutzung

Dieses Projekt zielt ausschließlich auf öffentliche Informationen. Verwende es nicht, um Login-Bereiche abzufragen, Zugriffskontrollen zu umgehen oder nicht-öffentliche/private Daten zu sammeln. Betreiberinnen und Betreiber sind selbst dafür verantwortlich, geltendes Recht, lokale Nutzungsbedingungen, `robots.txt`-Hinweise, Rate-Limits und Datenschutzanforderungen einzuhalten.

Die extrahierten Daten können personenbezogene Informationen enthalten, die bereits in öffentlichen Sitzungsunterlagen veröffentlicht wurden. Gehe damit sorgsam um, speichere nur was du brauchst und veröffentliche keine lokalen Datenbank-/PDF-Dumps ohne eigene Prüfung der rechtlichen und datenschutzbezogenen Rahmenbedingungen.

## Support und Integration

Wenn du dieses Projekt für deine Kommune adaptieren, in einen lokalen Workflow integrieren oder als gehostete/verwaltete Lösung betreiben möchtest, kontaktiere den Autor. Unterstützung bei neuen Adaptern, Datenqualität, OCR, MCP-Deployment und Integration in bestehende Rechercheprozesse ist möglich.

## MCP Tools

- `list_bodies()` - Gremien/Fraktionen auflisten
- `list_meetings()` - Sitzungen nach Gremium/Jahr listen
- `get_meeting()` - Sitzung mit Tagesordnung und Dokumenten abrufen
- `search_documents()` - Dokumentnamen und extrahierte Texte durchsuchen
- `get_document_text()` - extrahierten Volltext eines Dokuments abrufen
- `search_text()` - Volltext-Snippet-Suche mit Datum/Gremium/Dokumenttyp-Filtern
- `find_actor_topics()` - Evidenzstellen für Person, Partei oder Fraktion suchen
- `get_evidence_pack()` - Evidenzstellen gruppiert für Zusammenfassungen abrufen

## Status

- ✅ Witzenhausen-Ingestion funktionsfähig
- ✅ Lokale Dokument- und Volltextsuche funktionsfähig
- ✅ MCP-Tools für Evidenzsuche verfügbar
- 🔄 Adapter-Abstraktion, OCR-Fallback und weitere Kommunen sind mögliche nächste Schritte

## Lizenz

Dieses Projekt steht unter der Apache License 2.0. Siehe [LICENSE](LICENSE).

## Beitragen

Beiträge sind willkommen. Siehe [CONTRIBUTING.md](CONTRIBUTING.md).

## Technologie

- **Python** (bestehende Infrastruktur nutzen)
- **MCP Protocol** für Client-LLM Integration
- **SQLite FTS5** für lokale Volltextsuche
- **BeautifulSoup + requests** für öffentliche SessionNet-Seiten
