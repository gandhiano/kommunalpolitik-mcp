# Entwicklungsplan: kommunalpolitik-mcp (default branch)

*Erstellt am 2025-11-14 durch Vibe Feature MCP*
*Workflow: [epcc](https://mrsimpson.github.io/responsible-vibe-mcp/workflows/epcc)*

## Ziel
MCP Server für Kommunalpolitik entwickeln, der strukturierten Zugang zu kommunalpolitischen Daten (Sitzungen, Protokolle, Termine) über die OParl API bereitstellt. Der Server agiert als **Datenquelle und Kontext-Provider** für Client-LLMs, die dann die eigentliche Analyse durchführen.

## Erkunden
### Aufgaben
- [x] OParl API Spezifikation analysieren
- [x] Bestehende Scraper-Infrastruktur analysieren
- [x] MCP Architektur verstehen (Server = Datenquelle, Client = Analyse)
- [x] MCP Tools für Use Cases definieren
- [x] Technologie-Stack festlegen (Python + JSON)

### Abgeschlossen
- [x] Entwicklungsplan-Datei erstellt
- [x] Bestehende Python Scraper analysiert (23 OParl Kommunen verfügbar)
- [x] Datenquellen identifiziert: OParl API + SessionNet Scraping
- [x] MCP Architektur-Missverständnis geklärt
- [x] Use-Case-basierte MCP Tools definiert
- [x] Implementierungssprache gewählt: Python (bestehende Infrastruktur nutzen)

## Planen

### Aufgaben
- [x] MCP Server Architektur definieren
- [x] Iterative Entwicklungsstrategie planen
- [x] OParl API Spezifikation validieren (https://dev.oparl.org/spezifikation)
- [x] JSON-Schemas basierend auf OParl Spec anpassen
- [x] User Journeys für 3 Zielgruppen analysieren
- [x] MCP Tools für User Journeys erweitern
- [x] Error-Handling und Edge Cases definieren
- [x] Package-Struktur und Dependencies festlegen

### Implementierungsstrategie

#### 1. MCP Server Architektur
```
kommunalpolitik-mcp/
├── src/
│   ├── mcp_server.py           # Haupt-MCP Server
│   ├── tools/                  # MCP Tool Implementierungen
│   │   ├── __init__.py
│   │   ├── municipalities.py   # list_municipalities
│   │   ├── meetings.py         # get_meetings, get_meeting_protocol
│   │   ├── agenda.py           # get_agenda_items, get_upcoming_meetings
│   │   ├── documents.py        # get_meeting_documents
│   │   └── voting.py           # get_voting_results, get_participants
│   ├── providers/              # Datenquellen-Adapter
│   │   ├── __init__.py
│   │   ├── oparl_provider.py   # OParl API Client
│   │   └── base_provider.py    # Interface für Provider
│   └── schemas/                # JSON-Schemas
│       ├── __init__.py
│       ├── municipality.py     # Datenstrukturen
│       ├── meeting.py
│       └── document.py
├── requirements.txt            # MCP + bestehende Dependencies
└── README.md
```

#### 2. MCP Tools Spezifikation

**Basis-Tools:**
- `list_municipalities()` → `List[Municipality]`
- `get_meetings(municipality: str, start_date?: str, end_date?: str)` → `List[Meeting]`
- `get_meeting_protocol(meeting_id: str)` → `MeetingProtocol`

**Erweiterte Tools:**
- `get_agenda_items(meeting_id: str)` → `List[AgendaItem]`
- `get_meeting_documents(meeting_id: str)` → `List[Document]`
- `get_upcoming_meetings(municipality: str, days_ahead: int = 30)` → `List[Meeting]`

#### 3. JSON-Schema Design
```python
Municipality = {
    "id": str,
    "name": str,
    "oparl_endpoint": str,
    "data_source": "oparl" | "sessionnet",
    "available_data": List[str]  # ["meetings", "protocols", "documents"]
}

Meeting = {
    "id": str,
    "municipality": str,
    "name": str,
    "date": str,  # ISO format
    "status": "scheduled" | "completed" | "cancelled",
    "agenda_url": str,
    "protocol_url": str | None
}
```

#### 5. Iterative Entwicklungsstrategie

**MVP (Minimum Viable Product):**
- `list_municipalities()` - Basis-Funktionalität
- `get_meetings()` - Kernfunktion für alle Use Cases
- `get_meeting_protocol()` - Für Protokoll-Zusammenfassungen

**Iteration 1: Themensuche**
- `get_agenda_items()` - Strukturierte Tagesordnung
- `search_meetings_by_date()` - Zeitraum-basierte Suche

**Iteration 2: Abstimmungsanalyse**
- `get_voting_results()` - Falls in OParl verfügbar
- `get_participants()` - Teilnehmer und Fraktionen

**Iteration 3: Benachrichtigungen**
- `get_upcoming_meetings()` - Kommende Termine
- `monitor_meeting_changes()` - Änderungserkennung

#### 6. Erweiterbarkeit (MCP Best Practices)

**Plugin-Architektur:**
```python
# Neue Tools einfach hinzufügen
@mcp_tool("new_analysis_tool")
async def analyze_something(param: str) -> Dict:
    return provider.get_analysis_data(param)
```

**Provider-System:**
```python
# Neue Datenquellen integrieren
class SessionNetProvider(BaseProvider):
    async def get_meetings(self, municipality: str) -> List[Meeting]:
        # Scraping-Logik
```

#### 7. MVP JSON-Schemas

```python
# Municipality Schema
Municipality = {
    "id": str,
    "name": str,
    "oparl_endpoint": str,
    "data_source": "oparl",
    "last_updated": str  # ISO timestamp
}

# Meeting Schema
Meeting = {
    "id": str,
    "municipality_id": str,
    "name": str,
    "date": str,  # ISO format
    "status": "scheduled" | "completed",
    "agenda_url": str | None,
    "protocol_available": bool
}

# Protocol Schema
MeetingProtocol = {
    "meeting_id": str,
    "content": str,  # Volltext für LLM
    "format": "text" | "html",
    "source_url": str,
    "extracted_at": str  # ISO timestamp
}
```

#### 8. Error-Handling & Edge Cases

**API Fehler:**
- OParl Endpoint nicht erreichbar → Cached Data + Warning
- Malformed JSON → Skip + Log Error
- Rate Limiting → Exponential Backoff

**Daten-Qualität:**
- Fehlende Protokolle → `protocol_available: false`
- Leere Meetings → Filter aus Ergebnissen
- Encoding-Probleme → UTF-8 Fallback

#### 9. Dependencies

```txt
# requirements.txt
mcp>=1.0.0
aiohttp>=3.8.0
pydantic>=2.0.0
python-dateutil>=2.8.0
# Bestehende Dependencies beibehalten
requests>=2.28.0
```

### Abgeschlossen
*Noch keine*

## Programmieren

### Phasen-Eintrittskriterien:
- [x] Detaillierte Implementierungsstrategie ist erstellt
- [x] Architektur und Design sind dokumentiert
- [x] Aufgaben sind in spezifische, umsetzbare Schritte unterteilt
- [x] Abhängigkeiten und potenzielle Herausforderungen sind identifiziert

### Aufgaben
- [x] MCP Server Grundgerüst implementieren
- [x] OParl Provider Integration
- [x] Basis-Tools implementieren (municipalities, meetings, protocols)
- [x] JSON-Schemas implementieren
- [ ] Error-Handling und Logging
- [ ] Integration Tests mit bestehenden Daten
- [ ] Erweiterte Tools implementieren (agenda, documents, voting)
- [ ] Dokumentation und README

### Abgeschlossen
- [x] Project structure erstellt (src/, tools/, providers/, schemas/)
- [x] Requirements.txt mit MCP Dependencies
- [x] OParl-konforme Pydantic Schemas (Municipality, Meeting, AgendaItem, File)
- [x] BaseProvider Interface definiert
- [x] OParlProvider implementiert mit HTTP Client
- [x] MVP MCP Tools implementiert (list_municipalities, get_meetings, get_meeting_details, get_protocol_text)
- [x] MCP Server Hauptdatei mit Tool-Routing
- [x] Test-Script für Provider-Validierung

## Finalisieren

### Phasen-Eintrittskriterien:
- [ ] Kern-Implementierung ist vollständig
- [ ] Code funktioniert wie geplant
- [ ] Grundlegende Tests sind erfolgreich
- [ ] Dokumentation entspricht der Implementierung

### Aufgaben
- [ ] *Wird hinzugefügt, wenn diese Phase aktiv wird*

### Abgeschlossen
*Noch keine*

## Wichtige Entscheidungen
- **MCP Architektur**: Server stellt Daten bereit, Client-LLMs führen Analyse durch
- **Datenquellen**: OParl API (23 Kommunen) + SessionNet Scraping für weitere Städte
- **Hauptendpunkte**: Protokolle und Termine (weitere nach Bedarf)
- **Fokus**: Strukturierte Datenbereitstellung, nicht GenAI-Implementation
- **Technologie**: Python (bestehende Infrastruktur erweitern)
- **Datenformat**: JSON (MCP Standard)
- **Entwicklungsansatz**: Iterativ - MVP → Use Case Vertiefung → Neue Use Cases
- **OParl-Konformität**: JSON-Schemas folgen OParl 1.1 Spezifikation exakt

## Notizen
### MCP Server Rolle
- **Datenquelle**: Zugriff auf kommunalpolitische Daten
- **Kontext-Provider**: Strukturierte Informationen für Client-LLMs
- **Keine AI-Logik**: Client macht Zusammenfassungen, Analysen, etc.

### Bestehende Infrastruktur
- Python Scraper vorhanden unter `/Users/gualterbaptista/git/politik/kommunal-mcp`
- 23 Kommunen über OParl verfügbar (Rees, Gernsheim, Dortmund, etc.)
- 56 weitere über politik-bei-uns.de
- Witzenhausen nicht in OParl verfügbar (SessionNet ohne API)

### User Journey Erkenntnisse

**Zielgruppe 1: Stadtverordnete/Fraktion**
- Benötigt: Fraktionszuordnung, kommende Sitzungen, Themenanalyse
- Beispiel: "Fraktion Die PARTEI, Stadt Witzenhausen"
- Use Case: Antragsunterstützung, Positionsfindung

**Zielgruppe 2: Bürger**
- Benötigt: Parteienpositionen, historische Entwicklung
- Beispiel: "LKW-Verkehr Innenstadt über Legislaturperioden"
- Use Case: Politische Transparenz, Wahlentscheidung

**Zielgruppe 3: Stadtverwaltung**
- Benötigt: Umsetzungsaufgaben aus Beschlüssen
- Beispiel: "Monatsplanung basierend auf Gremienbeschlüssen"
- Use Case: Verwaltungsplanung, Aufgabenmanagement

### Erweiterte MCP Tools
**Politik-Tools**: Fraktionen, Abstimmungsverhalten, Themensuche
**Verwaltungs-Tools**: Beschlüsse mit Handlungsbedarf, Umsetzungsplanung
**Bürger-Tools**: Parteienpositionen, historische Entwicklung

---
*Dieser Plan wird vom LLM gepflegt. Tool-Antworten geben Anleitung, auf welchen Abschnitt man sich konzentrieren und welche Aufgaben man bearbeiten soll.*
