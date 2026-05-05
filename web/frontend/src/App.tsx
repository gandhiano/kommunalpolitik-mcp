import { useState } from 'react'
import './App.css'

type AgentMode = 'research' | 'briefing' | 'motion_draft' | 'follow_up'

interface AgentSource {
  title: string | null
  url: string | null
  snippet: string | null
  document_id: string | null
  body_name: string | null
  meeting_date: string | null
  document_type: string | null
}

interface AgentAction {
  name: string
  arguments: Record<string, unknown>
}

interface AgentResponse {
  mode: AgentMode
  answer: string
  sources: AgentSource[]
  actions_taken: AgentAction[]
  draft: null | {
    title?: string
    resolution?: string[]
    rationale?: string[]
    precedent_count?: number
  }
  provider: string
}

const modes: Array<{
  id: AgentMode
  title: string
  eyebrow: string
  description: string
  prompt: string
}> = [
  {
    id: 'research',
    title: 'Recherche',
    eyebrow: 'Quellen finden',
    description: 'Durchsucht Protokolle, Vorlagen und Anträge mit belegbaren Fundstellen.',
    prompt: 'Welche Beschlüsse oder Diskussionen gab es zum Haushalt seit 2021?',
  },
  {
    id: 'briefing',
    title: 'Briefing',
    eyebrow: 'Sitzung vorbereiten',
    description: 'Sammelt relevante Unterlagen und macht daraus eine arbeitsfähige Grundlage.',
    prompt: 'Erstelle mir ein Briefing zur nächsten Stadtverordnetenversammlung.',
  },
  {
    id: 'motion_draft',
    title: 'Antrag',
    eyebrow: 'Entwurf starten',
    description: 'Findet Präzedenzfälle und baut eine editierbare Antragsstruktur auf.',
    prompt: 'Hilf mir, einen Antrag zur sicheren Hortbetreuung zu formulieren.',
  },
  {
    id: 'follow_up',
    title: 'Nachfrage',
    eyebrow: 'Weiterdenken',
    description: 'Vertieft ein Thema, sucht Gegenargumente oder ergänzt weitere Quellen.',
    prompt: 'Welche Gegenargumente oder früheren Beschlüsse muss ich beachten?',
  },
]

const examples = [
  'Finde frühere Anträge der Grünen zum Thema Verkehr.',
  'Was steht in der nächsten Stadtverordnetenversammlung an?',
  'Welche Dokumente sind zum Thema Kinderbetreuung relevant?',
]

function App() {
  const [mode, setMode] = useState<AgentMode>('research')
  const [task, setTask] = useState(modes[0].prompt)
  const [limit, setLimit] = useState(5)
  const [response, setResponse] = useState<AgentResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function runAgent() {
    if (task.trim().length < 3) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: task.trim(), mode, limit }),
      })
      if (!res.ok) {
        throw new Error(await res.text())
      }
      setResponse((await res.json()) as AgentResponse)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unbekannter Fehler')
    } finally {
      setLoading(false)
    }
  }

  const activeMode = modes.find((candidate) => candidate.id === mode) ?? modes[0]

  return (
    <main className="shell">
      <section className="hero-panel">
        <div className="brandline">
          <span className="brandmark">KP</span>
          <span>Kommunalpolitik Workbench</span>
        </div>
        <div className="hero-grid">
          <div>
            <p className="kicker">Pilot für die grüne Fraktionsarbeit</p>
            <h1>Agentische Recherche mit belastbaren Fundstellen.</h1>
            <p className="lead">
              Frage nach Sitzungen, früheren Beschlüssen oder Antragsideen. Der Prototyp
              arbeitet zuerst retrieval-only: Er zeigt Quellen und bereitet Ergebnisse vor,
              ohne externe LLM-Kosten auszulösen.
            </p>
          </div>
          <aside className="status-card" aria-label="Systemstatus">
            <span className="pulse" />
            <strong>Provider: none</strong>
            <p>MCP und Datenbank bleiben privat. Die Web-App spricht nur den lokalen Agent-Endpunkt an.</p>
          </aside>
        </div>
      </section>

      <section className="workspace">
        <div className="mode-rail" aria-label="Arbeitsmodus wählen">
          {modes.map((item) => (
            <button
              key={item.id}
              className={item.id === mode ? 'mode-card active' : 'mode-card'}
              type="button"
              onClick={() => {
                setMode(item.id)
                setTask(item.prompt)
              }}
            >
              <span>{item.eyebrow}</span>
              <strong>{item.title}</strong>
              <small>{item.description}</small>
            </button>
          ))}
        </div>

        <div className="agent-panel">
          <div className="panel-heading">
            <div>
              <p className="kicker">{activeMode.eyebrow}</p>
              <h2>{activeMode.title}</h2>
            </div>
            <label className="limit-control">
              Quellen
              <select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={8}>8</option>
              </select>
            </label>
          </div>

          <textarea
            value={task}
            onChange={(event) => setTask(event.target.value)}
            rows={5}
            placeholder="Was möchtest Du kommunalpolitisch klären oder vorbereiten?"
          />

          <div className="examples">
            {examples.map((example) => (
              <button key={example} type="button" onClick={() => setTask(example)}>
                {example}
              </button>
            ))}
          </div>

          <button className="run-button" type="button" disabled={loading} onClick={() => void runAgent()}>
            {loading ? 'Arbeite mit Quellen ...' : 'Agent starten'}
          </button>

          {error && <div className="error-box">{error}</div>}
          {response && <InlineResult response={response} />}
        </div>
      </section>

      {response && <Results response={response} />}
    </main>
  )
}

function InlineResult({ response }: { response: AgentResponse }) {
  const firstSource = response.sources[0]

  return (
    <section className="inline-result" aria-live="polite">
      <div>
        <p className="kicker">Ergebnis</p>
        <h3>{labelForMode(response.mode)}</h3>
      </div>
      <p>{firstSentence(response.answer)}</p>
      <div className="result-metrics">
        <span>{response.sources.length} Quellen</span>
        <span>{response.actions_taken.length} Schritte</span>
        <span>Provider: {response.provider}</span>
      </div>
      {firstSource && (
        <a className="inline-source" href={firstSource.url ?? '#'} rel="noreferrer" target="_blank">
          <span>Erste Fundstelle</span>
          <strong>{firstSource.title ?? 'Unbenannte Quelle'}</strong>
          {firstSource.meeting_date && <small>{firstSource.meeting_date}</small>}
        </a>
      )}
    </section>
  )
}

function Results({ response }: { response: AgentResponse }) {
  return (
    <section className="results-grid">
      <article className="answer-card">
        <div className="panel-heading">
          <div>
            <p className="kicker">Antwort</p>
            <h2>{labelForMode(response.mode)}</h2>
          </div>
          <span className="provider-pill">{response.provider}</span>
        </div>
        <pre>{response.answer}</pre>
        {response.draft && <DraftPreview draft={response.draft} />}
      </article>

      <aside className="side-stack">
        <section className="trace-card">
          <p className="kicker">Rechercheweg</p>
          <ol>
            {response.actions_taken.map((action, index) => (
              <li key={`${action.name}-${index}`}>
                <strong>{action.name}</strong>
                <span>{JSON.stringify(action.arguments)}</span>
              </li>
            ))}
          </ol>
        </section>

        <section className="source-card">
          <p className="kicker">Quellen</p>
          <div className="sources">
            {response.sources.map((source, index) => (
              <a
                className="source-item"
                href={source.url ?? '#'}
                key={`${source.document_id}-${index}`}
                rel="noreferrer"
                target="_blank"
              >
                <span>{source.meeting_date ?? source.document_type ?? 'Quelle'}</span>
                <strong>{source.title ?? 'Unbenannte Quelle'}</strong>
                <small>{source.body_name}</small>
                {source.snippet && <p>{source.snippet}</p>}
              </a>
            ))}
            {response.sources.length === 0 && <p className="empty">Keine Quellen gefunden.</p>}
          </div>
        </section>
      </aside>
    </section>
  )
}

function DraftPreview({ draft }: { draft: NonNullable<AgentResponse['draft']> }) {
  return (
    <div className="draft-card">
      <p className="kicker">Editierbare Vorlage</p>
      <h3>{draft.title}</h3>
      <h4>Beschlussvorschlag</h4>
      <ol>
        {draft.resolution?.map((item) => <li key={item}>{item}</li>)}
      </ol>
      <h4>Begründung</h4>
      {draft.rationale?.map((item) => <p key={item}>{item}</p>)}
      <span>{draft.precedent_count ?? 0} Präzedenzfälle gefunden</span>
    </div>
  )
}

function labelForMode(mode: AgentMode) {
  if (mode === 'briefing') return 'Briefing-Grundlage'
  if (mode === 'motion_draft') return 'Antragsvorbereitung'
  if (mode === 'follow_up') return 'Nachfrage'
  return 'Rechercheergebnis'
}

function firstSentence(text: string) {
  const line = text.split('\n')[0]?.trim()
  return line || text
}

export default App
