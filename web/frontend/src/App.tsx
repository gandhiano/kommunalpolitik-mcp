import { useState } from 'react'
import './App.css'

type AgentMode = 'research' | 'briefing' | 'motion_draft' | 'follow_up'
type ResearchDepth = 'quick' | 'auto' | 'deep'

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
  related_sources: AgentSource[]
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
  const [researchDepth, setResearchDepth] = useState<ResearchDepth>('auto')
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
        body: JSON.stringify({ task: task.trim(), mode, research_depth: researchDepth }),
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
              Frage nach Sitzungen, früheren Beschlüssen oder Antragsideen. Der Server-Agent
              recherchiert zuerst im kommunalen Korpus und formuliert dann mit dem konfigurierten
              LLM eine quellengebundene Antwort.
            </p>
          </div>
          <aside className="status-card" aria-label="Systemstatus">
            <span className="pulse" />
            <strong>Server-side Agent</strong>
            <p>LLM-Schlüssel bleiben auf dem Server. Die Antwort zeigt den tatsächlich genutzten Provider.</p>
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
            <label className="depth-control">
              Recherche-Tiefe
              <select value={researchDepth} onChange={(event) => setResearchDepth(event.target.value as ResearchDepth)}>
                <option value="auto">Auto</option>
                <option value="quick">Schnell</option>
                <option value="deep">Gründlich</option>
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
        </div>
      </section>

      {response && <Results response={response} />}
    </main>
  )
}

function Results({ response }: { response: AgentResponse }) {
  const [activeSourceIndex, setActiveSourceIndex] = useState(0)
  const activeSource = response.sources[activeSourceIndex] ?? response.sources[0] ?? null

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
        <MarkdownText
          onCitationFocus={(index) => setActiveSourceIndex(index - 1)}
          sourceCount={response.sources.length}
          text={response.answer}
        />
        {response.draft && <DraftPreview draft={response.draft} />}

        <section className="used-sources-section">
          <p className="kicker">Im Bericht verwendet</p>
          <SourceList sources={response.sources} onSourceFocus={setActiveSourceIndex} />
        </section>
      </article>

      <aside className="side-stack">
        <ContextBox response={response} source={activeSource} sourceIndex={activeSourceIndex + 1} />

        {response.related_sources.length > 0 && (
          <section className="source-card related-card">
            <details>
              <summary>Weitere relevante Treffer ({response.related_sources.length})</summary>
              <div className="sources related-sources">
                {response.related_sources.map((source, index) => (
                  <a
                    className="source-item compact"
                    href={source.url ?? '#'}
                    key={`${source.document_id}-related-${index}`}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <span className="source-meta">{source.meeting_date ?? source.document_type ?? 'Quelle'}</span>
                    <strong>{source.title ?? 'Unbenannte Quelle'}</strong>
                    <small>{source.body_name}</small>
                  </a>
                ))}
              </div>
            </details>
          </section>
        )}

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
      </aside>
    </section>
  )
}

function SourceList({ sources, onSourceFocus }: { sources: AgentSource[]; onSourceFocus: (index: number) => void }) {
  return (
    <div className="sources used-sources">
      {sources.map((source, index) => (
        <a
          className="source-item"
          href={source.url ?? '#'}
          id={`source-${index + 1}`}
          key={`${source.document_id}-${index}`}
          onFocus={() => onSourceFocus(index)}
          onMouseEnter={() => onSourceFocus(index)}
          rel="noreferrer"
          target="_blank"
        >
          <span className="source-meta">
            <span className="source-number">[{index + 1}]</span>
            {source.meeting_date ?? source.document_type ?? 'Quelle'}
          </span>
          <strong>{source.title ?? 'Unbenannte Quelle'}</strong>
          <small>{source.body_name}</small>
          {source.snippet && <p>{source.snippet}</p>}
        </a>
      ))}
      {sources.length === 0 && <p className="empty">Keine Quellen gefunden.</p>}
    </div>
  )
}

function ContextBox({ response, source, sourceIndex }: { response: AgentResponse; source: AgentSource | null; sourceIndex: number }) {
  const retrievalPlan = response.actions_taken.find((action) => action.name === 'plan_retrieval')?.arguments

  return (
    <section className="source-card context-card">
      <p className="kicker">Kontext</p>
      <h3>{contextTitle(response.mode)}</h3>
      <p>{extractTlDr(response.answer)}</p>

      <div className="context-metrics">
        <span>{response.sources.length} zitierte Quellen</span>
        <span>{response.related_sources.length} weitere Treffer</span>
        {typeof retrievalPlan?.depth === 'string' && <span>Tiefe: {depthLabel(retrievalPlan.depth)}</span>}
      </div>

      <div className="next-action">
        <strong>Nächster sinnvoller Schritt</strong>
        <p>{nextAction(response.mode)}</p>
      </div>

      {source && (
        <div className="focused-source">
          <strong>Aktuelle Quelle</strong>
          <span className="source-meta">
            <span className="source-number">[{sourceIndex}]</span>
            {source.meeting_date ?? source.document_type ?? 'Quelle'}
          </span>
          <p>{source.title ?? 'Unbenannte Quelle'}</p>
          {source.url && (
            <a className="source-open-link" href={source.url} rel="noreferrer" target="_blank">
              Original öffnen
            </a>
          )}
        </div>
      )}
    </section>
  )
}

function contextTitle(mode: AgentMode) {
  if (mode === 'briefing') return 'Kurzbriefing'
  if (mode === 'motion_draft') return 'Antragskontext'
  if (mode === 'follow_up') return 'Einordnung'
  return 'TL;DR'
}

function nextAction(mode: AgentMode) {
  if (mode === 'briefing') return 'Offene Punkte in konkrete Sitzungsfragen übersetzen und die wichtigsten TOPs prüfen.'
  if (mode === 'motion_draft') return 'Beschlussvorschlag politisch schärfen und offene Prüfaufträge markieren.'
  if (mode === 'follow_up') return 'Die stärksten Gegenargumente und fehlenden Belege gezielt nachrecherchieren.'
  return 'Bei Bedarf auf „Gründlich“ wechseln oder eine engere Nachfrage zu einem Beleg stellen.'
}

function depthLabel(depth: string) {
  if (depth === 'quick') return 'schnell'
  if (depth === 'deep') return 'gründlich'
  return 'auto'
}

function extractTlDr(answer: string) {
  const lines = answer.split('\n').map((line) => line.trim()).filter(Boolean)
  const content = lines.find((line) => !line.startsWith('#') && !line.startsWith('- ') && !/^\d+[.)]\s+/.test(line))
  if (!content) return 'Die Antwort fasst die wichtigsten belegten Punkte aus den gefundenen Quellen zusammen.'
  return content.replace(/\*\*/g, '').slice(0, 280)
}

function MarkdownText({
  onCitationFocus,
  sourceCount,
  text,
}: {
  onCitationFocus: (index: number) => void
  sourceCount: number
  text: string
}) {
  const blocks = text.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean)

  return (
    <div className="markdown-answer">
      {blocks.map((block, index) => {
        const lines = block.split('\n').map((line) => line.trim()).filter(Boolean)
        const firstLine = lines[0] ?? ''

        if (firstLine.startsWith('### ')) {
          return <BlockWithHeading key={index} heading={firstLine.slice(4)} lines={lines.slice(1)} level="h4" onCitationFocus={onCitationFocus} sourceCount={sourceCount} />
        }
        if (firstLine.startsWith('## ')) {
          return <BlockWithHeading key={index} heading={firstLine.slice(3)} lines={lines.slice(1)} level="h3" onCitationFocus={onCitationFocus} sourceCount={sourceCount} />
        }
        if (firstLine.startsWith('# ')) {
          return <BlockWithHeading key={index} heading={firstLine.slice(2)} lines={lines.slice(1)} level="h3" onCitationFocus={onCitationFocus} sourceCount={sourceCount} />
        }
        return <MarkdownLines key={index} lines={lines} onCitationFocus={onCitationFocus} sourceCount={sourceCount} />
      })}
    </div>
  )
}

function BlockWithHeading({
  heading,
  lines,
  level,
  onCitationFocus,
  sourceCount,
}: {
  heading: string
  lines: string[]
  level: 'h3' | 'h4'
  onCitationFocus: (index: number) => void
  sourceCount: number
}) {
  const Heading = level
  return (
    <div>
      <Heading>{renderInline(heading, sourceCount, onCitationFocus)}</Heading>
      {lines.length > 0 && <MarkdownLines lines={lines} onCitationFocus={onCitationFocus} sourceCount={sourceCount} />}
    </div>
  )
}

function MarkdownLines({
  lines,
  onCitationFocus,
  sourceCount,
}: {
  lines: string[]
  onCitationFocus: (index: number) => void
  sourceCount: number
}) {
  const bulletItems = parseBulletItems(lines)
  if (bulletItems.length > 0) {
    return (
      <ul>
        {bulletItems.map((line) => <li key={line}>{renderInline(line, sourceCount, onCitationFocus)}</li>)}
      </ul>
    )
  }

  if (lines.every((line) => /^\d+[.)]\s+/.test(line))) {
    return (
      <ol>
        {lines.map((line) => <li key={line}>{renderInline(line.replace(/^\d+[.)]\s+/, ''), sourceCount, onCitationFocus)}</li>)}
      </ol>
    )
  }

  return <p>{renderInline(lines.join(' '), sourceCount, onCitationFocus)}</p>
}

function parseBulletItems(lines: string[]) {
  if (lines.every((line) => /^[-*]\s+/.test(line))) {
    return lines.map((line) => line.replace(/^[-*]\s+/, ''))
  }

  const joined = lines.join(' ').trim()
  if (!joined.startsWith('- ')) return []
  return joined.replace(/^-\s+/, '').split(/\s+-\s+(?=\[\d+\]|\*\*)/).map((item) => item.trim()).filter(Boolean)
}

function renderInline(text: string, sourceCount: number, onCitationFocus: (index: number) => void) {
  return text.split(/(\*\*[^*]+\*\*|\[\d+\])/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      const content = part.slice(2, -2)
      if (/^\[\d+\]$/.test(content)) {
        return renderCitation(content, sourceCount, onCitationFocus, index)
      }
      return <strong key={index}>{content}</strong>
    }
    if (/^\[\d+\]$/.test(part)) {
      return renderCitation(part, sourceCount, onCitationFocus, index)
    }
    return <span key={index}>{part}</span>
  })
}

function renderCitation(text: string, sourceCount: number, onCitationFocus: (index: number) => void, key: number) {
  const sourceIndex = Number(text.slice(1, -1))
  if (sourceIndex < 1 || sourceIndex > sourceCount) return <span key={key}>{text}</span>
  return (
    <a
      className="citation-link"
      href={`#source-${sourceIndex}`}
      key={key}
      onFocus={() => onCitationFocus(sourceIndex)}
      onMouseEnter={() => onCitationFocus(sourceIndex)}
      title={`Zur Quelle ${sourceIndex}`}
    >
      {text}
    </a>
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

export default App
