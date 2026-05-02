# Contributing

Danke für dein Interesse an diesem Projekt. Ziel ist ein lokaler, nachvollziehbarer MCP-Zugang zu öffentlichen kommunalpolitischen Daten, aktuell mit Fokus auf Witzenhausen/SessionNet.

## Grundsätze

- Nur öffentliche Datenquellen verwenden.
- Keine Login-Bereiche, keine Zugriffsumgehung, keine privaten personenbezogenen Daten anreichern.
- Live-Crawling muss explizit opt-in bleiben, z.B. über `--allow-public-crawl`.
- Scraper sollen konservativ sein: Caching, Rate-Limit, Resume-Fähigkeit.
- Lokale Daten, PDFs, SQLite-Dateien und extrahierte Texte nicht committen.
- MCP-Tools sollen kompakte, zitierbare Evidenz liefern statt riesige Dokumente zurückzugeben.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optionaler Smoke-Test mit kleinem Datensatz:

```bash
python -m src.ingest.witzenhausen init-db
python -m src.ingest.witzenhausen --allow-public-crawl bodies
python -m src.ingest.witzenhausen --allow-public-crawl meetings --from-year 2026 --to-year 2026 --body-id 1
python -m src.ingest.witzenhausen --allow-public-crawl details --limit 1
python -m src.ingest.witzenhausen --allow-public-crawl documents --limit 1
python -m src.ingest.witzenhausen extract-text --limit 1
python -m src.ingest.witzenhausen index-chunks --limit 1
python -m src.ingest.witzenhausen extract-actors --limit 100
python -m src.ingest.witzenhausen status
```

## Prüfen vor einem Pull Request

```bash
python -m compileall src
python -m src.ingest.witzenhausen status
```

Wenn du MCP-Tools änderst, teste sie zusätzlich über den MCP Inspector oder einen stdio-Client.

```bash
npx @modelcontextprotocol/inspector mcp_config.json
```

## Code-Stil

- Kleine, fokussierte Änderungen bevorzugen.
- Keine unnötigen Frameworks einführen.
- Parser robust gegenüber leicht veränderten SessionNet-HTML-Strukturen halten.
- SQLite-Schemaänderungen rückwärtskompatibel über `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` hinzufügen.
- Fehlerhafte PDFs oder OCR-Lücken als Datenqualitätsthema behandeln, nicht als Grund für einen Abbruch der gesamten Pipeline.

## Gute erste Beiträge

- Weitere Tests mit gespeicherten HTML-Fixtures.
- Bessere Erkennung von Fraktionen, Personen und Antragstellern.
- OCR-Fallback für gescannte PDFs.
- Verbesserte Evidenz-Packs für konkrete Analysefragen.
- HTTP/Streamable-MCP-Transport für ChatGPT Custom Connectors.

## Lizenz

Mit einem Beitrag erklärst du dich damit einverstanden, dass dein Beitrag unter der Apache License 2.0 veröffentlicht wird.
