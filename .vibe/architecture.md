# Architekturentscheidung & Spezifikation: MCP-basiertes Ratsinformationssystem

## 1. Ziel

Dieses System ermöglicht die KI-gestützte Analyse kommunaler Ratsdaten (z. B. aus SessionNet oder OParl), um Fragen wie:

> „Was waren die Positionen der Fraktionen zu Thema X?“

zu beantworten.

Das System wird **pro Kommune als eigenständige Instanz** betrieben (Single-Tenancy), mit Option auf SaaS-Betrieb für Kommunen und Fraktionen.

---

## 2. High-Level-Architektur

Das Projekt wird als Mono-Repo realisiert, mit mehreren modularen Komponenten:

- Scraper / Ingestion
- Persistenz (Datenbank)
- Retrieval-Layer
- MCP-Server (API für LLMs)
- (Optional später) RAG-/Vektorindex

---

## 3. Komponenten im Detail

### 3.1 Scraper / Ingestion

- Läuft periodisch (Cron, Worker).
- Unterstützt z. B. SessionNet (HTML) und/oder OParl (JSON).
- Extrahiert und normalisiert Daten:
  - `Stadt`, `Meeting`, `AgendaItem`, `Document` (PDF/Protokoll), `Person`, `Faction`
- Nutzt PDF → Text und optional OCR.
- Persistiert in internes Datenmodell.

### 3.2 Persistenz (DB)

- PostgreSQL, eine DB oder Schema pro Instanz.
- Kern-Tabellen:
  - `municipality`
  - `body`
  - `meeting`
  - `agenda_item`
  - `document` (inkl. Volltext)
  - `person`
  - `faction`
  - `membership`
  - `decision` (optional)

### 3.3 Retrieval Layer

Abstraktes Interface zur Dokument- und Sitzungssuche:

```ts
interface DocumentRepository {
  searchDocuments(query: string, filters): DocumentRef[];
  getDocumentText(id: string): string;
}

interface MeetingRepository {
  findMeetingsByTopic(topic: string, filters): MeetingRef[];
  getMeetingDetails(id: string): MeetingDetails;
}