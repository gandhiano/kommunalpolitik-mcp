# Contributing

Danke für dein Interesse an diesem Projekt. Ziel ist ein lokaler, nachvollziehbarer MCP-Zugang zu öffentlichen kommunalpolitischen Daten. Der aktuelle unterstützte Adapter ist Witzenhausen/SessionNet; die Codebasis soll perspektivisch weitere Kommunen und Ratsinformationssysteme unterstützen.

## Grundsätze

- Nur öffentliche Datenquellen verwenden.
- Keine Login-Bereiche, keine Zugriffsumgehung, keine privaten personenbezogenen Daten anreichern.
- Live-Crawling muss explizit opt-in bleiben, z.B. über `--allow-public-crawl`.
- Scraper sollen konservativ sein: Caching, Rate-Limit, Resume-Fähigkeit.
- Lokale Daten, PDFs, SQLite-Dateien und extrahierte Texte nicht committen.
- MCP-Tools sollen kompakte, zitierbare Evidenz liefern statt riesige Dokumente zurückzugeben.
- Neue Kommunen sollen als Adapter/Konfiguration ergänzt werden, nicht durch Hardcoding in Witzenhausen-spezifische Module.
- Standardmodell ist eine Datenbank und ein MCP-Runtime pro Kommune. Multi-Kommunen-Betrieb braucht explizite Mandantenfähigkeit.

## Neue Kommunen und Adapter

Wenn du eine weitere Kommune anbinden möchtest, dokumentiere zuerst:

- öffentliches RIS/Bürgerinfoportal und Basis-URLs
- verwendetes System, z.B. SessionNet, OParl, Allris oder anderes
- welche öffentlichen Seiten Sitzungen, Gremien, Vorlagen und Dokumente enthalten
- ob Dokumente direkt öffentlich herunterladbar sind
- bekannte Einschränkungen, Rate-Limits, `robots.txt`-Hinweise oder Nutzungsbedingungen

Technisch sollte eine neue Kommune langfristig über Konfiguration und Adapter auswählbar sein. Solange die gemeinsame Adapter-Abstraktion noch nicht fertig ist, darf ein neuer Adapter pragmatisch beginnen, sollte aber Quell-spezifische Parser von generischen Repository-/MCP-Funktionen trennen.

## Datenschutz und verantwortliche Nutzung

Dieses Projekt verarbeitet öffentliche kommunalpolitische Unterlagen. Diese können personenbezogene Informationen enthalten, z.B. Namen von Mandatsträgerinnen, Bürgerinnen oder Antragstellern. Beiträge sollten keine unnötige Anreicherung, Profilbildung oder Veröffentlichung lokaler Daten-Dumps fördern.

Bitte achte besonders darauf:

- keine nicht-öffentlichen Datenquellen einzubinden
- keine Authentifizierung oder Zugriffskontrollen zu umgehen
- keine lokalen PDFs, SQLite-Datenbanken oder extrahierten Texte ins Repository aufzunehmen
- Analyse-Tools als Evidenz-/Recherchehilfe zu formulieren, nicht als verbindliche politische Bewertung

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optionaler Smoke-Test mit kleinem Datensatz:

```bash
kommunalpolitik ingest witzenhausen init-db
kommunalpolitik ingest witzenhausen --allow-public-crawl bodies
kommunalpolitik ingest witzenhausen --allow-public-crawl meetings --from-year 2026 --to-year 2026 --body-id 1
kommunalpolitik ingest witzenhausen --allow-public-crawl details --limit 1
kommunalpolitik ingest witzenhausen --allow-public-crawl documents --limit 1
kommunalpolitik ingest witzenhausen extract-text --limit 1
kommunalpolitik ingest witzenhausen index-chunks --limit 1
kommunalpolitik ingest witzenhausen extract-actors --limit 100
kommunalpolitik ingest witzenhausen status
```

## Prüfen vor einem Pull Request

```bash
python -m compileall src
kommunalpolitik ingest witzenhausen status
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
