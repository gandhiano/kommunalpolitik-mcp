import { useEffect, useState, type ReactNode } from 'react'
import './App.css'

type Role = 'user' | 'assistant'
type AgentKind = 'general' | 'research' | 'briefing' | 'drafting' | 'scrutiny'
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
  mode: string
  answer: string
  sources: AgentSource[]
  related_sources: AgentSource[]
  actions_taken: AgentAction[]
  draft: null | Record<string, unknown>
  provider: string
  model_metadata: Record<string, unknown>
}

interface ChatMessage {
  id: string
  role: Role
  content: string
  response?: AgentResponse
  requestTask?: string
}

interface AuthStatus {
  authenticated: boolean
  auth_enabled: boolean
}

const starters = [
  'Finde frühere Anträge der Grünen zum Thema Verkehr und bewerte die Argumentationslinie.',
  'Was steht in der nächsten Stadtverordnetenversammlung an?',
  'Welche Beschlüsse oder Diskussionen gab es zum Haushalt seit 2021?',
  'Hilf mir, einen Antrag zur sicheren Hortbetreuung vorzubereiten.',
]

const agents: Array<{ id: AgentKind; label: string; description: string }> = [
  { id: 'general', label: 'Allround-Agent', description: 'Entscheidet selbst, welche Werkzeuge passen.' },
  { id: 'research', label: 'Recherche-Agent', description: 'Sucht Belege, Chronologien und Quellen.' },
  { id: 'briefing', label: 'Briefing-Agent', description: 'Bereitet Sitzungen und TOPs vor.' },
  { id: 'drafting', label: 'Antrags-Agent', description: 'Hilft bei Anträgen und Änderungsanträgen.' },
  { id: 'scrutiny', label: 'Prüf-Agent', description: 'Sucht Schwächen, Risiken und Gegenargumente.' },
]

function App() {
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null)
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [agent, setAgent] = useState<AgentKind>('general')
  const [researchDepth, setResearchDepth] = useState<ResearchDepth>('auto')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    async function loadAuthStatus() {
      try {
        const res = await fetch('/auth/status')
        setAuthStatus((await res.json()) as AuthStatus)
      } catch {
        setAuthStatus({ authenticated: true, auth_enabled: false })
      }
    }

    void loadAuthStatus()
  }, [])

  async function login() {
    setAuthError(null)
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (!res.ok) {
      setAuthError(await responseError(res))
      return
    }
    setPassword('')
    setAuthStatus((await res.json()) as AuthStatus)
  }

  async function sendMessage(text = input) {
    const content = text.trim()
    if (content.length < 3 || loading) return

    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content }
    const nextMessages = [...messages, userMessage]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    setError(null)
    const startedAt = performance.now()
    console.info('[agent] request start', {
      agent,
      researchDepth,
      messages: nextMessages.length,
      taskChars: content.length,
    })

    try {
      const res = await fetch('/agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent,
          messages: nextMessages.map((message) => ({ role: message.role, content: message.content })),
          research_depth: researchDepth,
        }),
      })
      console.info('[agent] response received', {
        status: res.status,
        ok: res.ok,
        elapsedMs: Math.round(performance.now() - startedAt),
      })
      if (!res.ok) {
        if (res.status === 401) setAuthStatus({ authenticated: false, auth_enabled: true })
        throw new Error(await responseError(res))
      }
      const response = (await res.json()) as AgentResponse
      console.info('[agent] response parsed', {
        provider: response.provider,
        answerChars: response.answer.length,
        sources: response.sources.length,
        actions: response.actions_taken.length,
      })
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', content: response.answer, requestTask: content, response },
      ])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unbekannter Fehler'
      console.error('[agent] request failed', { message, elapsedMs: Math.round(performance.now() - startedAt) })
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  if (!authStatus) return <LoadingScreen />
  if (authStatus.auth_enabled && !authStatus.authenticated) {
    return <LoginScreen authError={authError} login={login} password={password} setPassword={setPassword} />
  }

  return (
    <main className="chat-shell">
      <header className="chat-header">
        <div className="brandline">
          <span className="brandmark">KP</span>
          <span>Kommunalpolitik Workbench</span>
        </div>
        <div className="chat-controls">
          <label className="depth-control compact-depth">
            Agent
            <select value={agent} onChange={(event) => setAgent(event.target.value as AgentKind)}>
              {agents.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </select>
          </label>
          <label className="depth-control compact-depth">
            Tiefe
            <select value={researchDepth} onChange={(event) => setResearchDepth(event.target.value as ResearchDepth)}>
              <option value="quick">Schnell</option>
              <option value="auto">Auto</option>
              <option value="deep">Gründlich</option>
            </select>
          </label>
        </div>
      </header>

      <section className="chat-panel">
        {messages.length === 0 && <Welcome agent={agent} sendMessage={sendMessage} />}
        {messages.map((message) => <ChatBubble key={message.id} message={message} researchDepth={researchDepth} />)}
        {loading && <div className="assistant-thinking">Der Agent recherchiert mit seinen Werkzeugen ...</div>}
        {error && <div className="error-box">{error}</div>}
      </section>

      <form
        className="chat-composer"
        onSubmit={(event) => {
          event.preventDefault()
          void sendMessage()
        }}
      >
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              void sendMessage()
            }
          }}
          placeholder="Frag den kommunalpolitischen Agenten ..."
          rows={2}
        />
        <button disabled={loading || input.trim().length < 3} type="submit">Senden</button>
      </form>
    </main>
  )
}

function LoadingScreen() {
  return (
    <main className="shell auth-shell">
      <section className="login-card">
        <div className="brandline"><span className="brandmark">KP</span><span>Kommunalpolitik Workbench</span></div>
        <p className="lead">Zugang wird geprüft ...</p>
      </section>
    </main>
  )
}

function LoginScreen({ authError, login, password, setPassword }: { authError: string | null; login: () => Promise<void>; password: string; setPassword: (value: string) => void }) {
  return (
    <main className="shell auth-shell">
      <section className="login-card">
        <div className="brandline"><span className="brandmark">KP</span><span>Kommunalpolitik Workbench</span></div>
        <p className="kicker">Pilot-Zugang</p>
        <h1>Geschützter Agentenchat für kommunalpolitische Arbeit.</h1>
        <p className="lead">Melde dich mit dem Pilot-Passwort an. Der Agent läuft serverseitig und nutzt dort seine Werkzeuge.</p>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void login()
          }}
        >
          <label>Passwort<input autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} type="password" /></label>
          <button className="run-button" type="submit">Einloggen</button>
        </form>
        {authError && <div className="error-box">{authError}</div>}
      </section>
    </main>
  )
}

function Welcome({ agent, sendMessage }: { agent: AgentKind; sendMessage: (text: string) => Promise<void> }) {
  const activeAgent = agents.find((item) => item.id === agent) ?? agents[0]
  return (
    <div className="welcome-card">
      <p className="kicker">Agentenchat</p>
      <h1>Frag wie in einem MCP-fähigen Agentenclient.</h1>
      <p>{activeAgent.label}: {activeAgent.description} Der Backend-Agent entscheidet selbst, welche lokalen kommunalpolitischen Werkzeuge er nutzt.</p>
      <div className="starter-grid">
        {starters.map((starter) => <button key={starter} onClick={() => void sendMessage(starter)} type="button">{starter}</button>)}
      </div>
    </div>
  )
}

function ChatBubble({ message, researchDepth }: { message: ChatMessage; researchDepth: ResearchDepth }) {
  const response = message.response
  const display = response ? displayAnswer(response) : { text: message.content, sources: [] }
  const sourceBaseId = `sources-${message.id}`
  return (
    <article className={`chat-bubble ${message.role}`}>
      {message.role === 'user' ? <p>{message.content}</p> : <MarkdownText sourceBaseId={sourceBaseId} sources={display.sources} text={display.text} />}
      {response && <AnswerDetails displaySources={display.sources} researchDepth={researchDepth} requestTask={message.requestTask ?? message.content} response={response} sourceBaseId={sourceBaseId} />}
    </article>
  )
}

function AnswerDetails({ displaySources, researchDepth, requestTask, response, sourceBaseId }: { displaySources: AgentSource[]; researchDepth: ResearchDepth; requestTask: string; response: AgentResponse; sourceBaseId: string }) {
  const latency = typeof response.model_metadata.latency_ms === 'number' ? `${response.model_metadata.latency_ms} ms` : null
  return (
    <div className="answer-details">
      <div className="answer-meta"><span>{response.provider}</span><span>{displaySources.length} Quellen</span>{latency && <span>{latency}</span>}</div>
      {displaySources.length > 0 && <SourceList baseId={sourceBaseId} sources={displaySources} />}
      <details className="trace-card inline-trace">
        <summary>Rechercheweg</summary>
        <ol>{response.actions_taken.map((action, index) => <li key={`${action.name}-${index}`}><strong>{action.name}</strong><span>{JSON.stringify(action.arguments)}</span></li>)}</ol>
      </details>
      <FeedbackBox requestTask={requestTask || response.answer.slice(0, 200)} researchDepth={researchDepth} response={response} />
    </div>
  )
}

function SourceList({ baseId, sources }: { baseId: string; sources: AgentSource[] }) {
  return (
    <div className="sources used-sources chat-sources">
      {sources.map((source, index) => {
        const href = source.url ?? documentDownloadUrl(source.document_id)
        return (
          <a className="source-item" href={href ?? `#${baseId}-${index + 1}`} id={`${baseId}-${index + 1}`} key={`${source.document_id}-${index}`} rel="noreferrer" target={href ? '_blank' : undefined}>
            <span className="source-meta"><span className="source-number">[{index + 1}]</span>{source.meeting_date ?? sourceTypeLabel(source.document_type)}</span>
            <strong><InlineMarkdown text={source.title ?? 'Unbenannte Quelle'} /></strong>
            <small>{source.body_name}</small>
            {source.snippet && <p><InlineMarkdown text={source.snippet} /></p>}
            {href && <span className="source-download">Original öffnen</span>}
          </a>
        )
      })}
    </div>
  )
}

function InlineMarkdown({ text }: { text: string }) {
  return <>{renderInline(text, '', 0, new Map())}</>
}

function documentDownloadUrl(documentId: string | null) {
  const id = documentId?.match(/^\d{5,6}$/)?.[0]
  return id ? `https://sessionnet.owl-it.de/witzenhausen/BI/getfile.asp?id=${id}&type=do` : null
}

function FeedbackBox({ requestTask, researchDepth, response }: { requestTask: string; researchDepth: ResearchDepth; response: AgentResponse }) {
  const [rating, setRating] = useState<'up' | 'down' | null>(null)
  const [comment, setComment] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submitFeedback(nextRating: 'up' | 'down') {
    setRating(nextRating)
    setSubmitting(true)
    setStatus(null)
    try {
      const res = await fetch('/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rating: nextRating,
          comment,
          task: requestTask,
          answer: response.answer,
          mode: response.mode,
          research_depth: researchDepth,
          provider: response.provider,
          model_metadata: response.model_metadata,
          actions_taken: response.actions_taken,
          sources: response.sources,
          related_sources: response.related_sources,
        }),
      })
      if (!res.ok) throw new Error(await responseError(res))
      setStatus(nextRating === rating ? 'Kommentar aktualisiert. Danke.' : 'Danke. Optional kannst du noch ergänzen, was gut war oder fehlt.')
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Feedback konnte nicht gespeichert werden.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="feedback-box compact-feedback" aria-label="Antwort bewerten">
      <p className="feedback-privacy">Klick sendet anonym Frage, Antwort, Quellen-Metadaten und Bewertung zur Verbesserung.</p>
      <div className="feedback-actions">
        <button aria-label="Antwort hilfreich bewerten" className={rating === 'up' ? 'selected' : ''} disabled={submitting} onClick={() => void submitFeedback('up')} type="button"><span aria-hidden="true" className="thumb-icon">👍</span><span>Hilfreich</span></button>
        <button aria-label="Antwort nicht hilfreich bewerten" className={rating === 'down' ? 'selected' : ''} disabled={submitting} onClick={() => void submitFeedback('down')} type="button"><span aria-hidden="true" className="thumb-icon">👎</span><span>Nicht hilfreich</span></button>
      </div>
      {rating && <div className="feedback-comment"><textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Optional: Was war gut, falsch oder fehlt?" rows={2} /><button disabled={submitting || comment.trim().length === 0} onClick={() => void submitFeedback(rating)} type="button">Kommentar senden</button></div>}
      {status && <p className="feedback-status">{status}</p>}
    </section>
  )
}

function MarkdownText({ sourceBaseId, sources, text }: { sourceBaseId: string; sources: AgentSource[]; text: string }) {
  const blocks = text.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean)
  const sourceIndex = sourceIndexByDocument(sources)
  return <div className="markdown-answer">{blocks.map((block, index) => <MarkdownBlock block={block} key={index} sourceBaseId={sourceBaseId} sourceCount={sources.length} sourceIndex={sourceIndex} />)}</div>
}

function MarkdownBlock({ block, sourceBaseId, sourceCount, sourceIndex }: { block: string; sourceBaseId: string; sourceCount: number; sourceIndex: Map<string, number> }) {
  const lines = block.split('\n').map((line) => line.trim()).filter(Boolean)
  const firstLine = lines[0] ?? ''
  if (isMarkdownTable(lines)) return <MarkdownTable lines={lines} sourceBaseId={sourceBaseId} sourceCount={sourceCount} sourceIndex={sourceIndex} />
  if (/^#{1,3}\s+/.test(firstLine)) return <><h3>{renderInline(firstLine.replace(/^#{1,3}\s+/, ''), sourceBaseId, sourceCount, sourceIndex)}</h3>{renderLines(lines.slice(1), sourceBaseId, sourceCount, sourceIndex)}</>
  if (lines.every((line) => /^[-*]\s+/.test(line))) return <ul>{lines.map((line) => <li key={line}>{renderInline(line.replace(/^[-*]\s+/, ''), sourceBaseId, sourceCount, sourceIndex)}</li>)}</ul>
  if (lines.every((line) => /^\d+[.)]\s+/.test(line))) return <ol>{lines.map((line) => <li key={line}>{renderInline(line.replace(/^\d+[.)]\s+/, ''), sourceBaseId, sourceCount, sourceIndex)}</li>)}</ol>
  return <>{renderLines(lines, sourceBaseId, sourceCount, sourceIndex)}</>
}

function MarkdownTable({ lines, sourceBaseId, sourceCount, sourceIndex }: { lines: string[]; sourceBaseId: string; sourceCount: number; sourceIndex: Map<string, number> }) {
  const rows = lines.filter((line) => !/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line)).map(tableCells)
  const [header, ...body] = rows
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{header.map((cell) => <th key={cell}>{renderInline(cell, sourceBaseId, sourceCount, sourceIndex)}</th>)}</tr></thead>
        <tbody>{body.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{renderInline(cell, sourceBaseId, sourceCount, sourceIndex)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

function isMarkdownTable(lines: string[]) {
  return lines.length >= 2 && lines[0].includes('|') && /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(lines[1])
}

function tableCells(line: string) {
  return line.replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim())
}

function renderLines(lines: string[], sourceBaseId: string, sourceCount: number, sourceIndex: Map<string, number>) {
  if (lines.length === 0) return null
  const rendered: ReactNode[] = []
  let index = 0
  while (index < lines.length) {
    const line = lines[index]
    if (/^[-*]\s+/.test(line)) {
      const items: string[] = []
      while (index < lines.length && /^[-*]\s+/.test(lines[index])) items.push(lines[index++].replace(/^[-*]\s+/, ''))
      rendered.push(<ul key={`ul-${index}`}>{items.map((item) => <li key={item}>{renderInline(item, sourceBaseId, sourceCount, sourceIndex)}</li>)}</ul>)
      continue
    }
    if (/^\d+[.)]\s+/.test(line)) {
      const items: string[] = []
      while (index < lines.length && /^\d+[.)]\s+/.test(lines[index])) items.push(lines[index++].replace(/^\d+[.)]\s+/, ''))
      rendered.push(<ol key={`ol-${index}`}>{items.map((item) => <li key={item}>{renderInline(item, sourceBaseId, sourceCount, sourceIndex)}</li>)}</ol>)
      continue
    }
    rendered.push(<p key={`p-${index}`}>{renderInline(line, sourceBaseId, sourceCount, sourceIndex)}</p>)
    index += 1
  }
  return rendered
}

function renderInline(text: string, sourceBaseId: string, sourceCount: number, sourceIndex: Map<string, number>) {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[\d+\]|Dok(?:ument)?\.?\s*\d{5,6}|\b\d{5,6}\b)/g).map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`')) return <code key={index}>{part.slice(1, -1)}</code>
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>
    if (/^\[\d+\]$/.test(part)) {
      const sourceIndex = Number(part.slice(1, -1))
      if (sourceIndex >= 1 && sourceIndex <= sourceCount) return <CitationLink key={index} label={part} sourceBaseId={sourceBaseId} sourceNumber={sourceIndex} />
      if (sourceIndex >= 1) return <span className="citation-link" key={index}>{part}</span>
    }
    const documentMatch = part.match(/^(?:Dok(?:ument)?\.?\s*)?(\d{5,6})$/)
    if (documentMatch) {
      const sourceNumber = sourceIndex.get(documentMatch[1])
      if (sourceNumber) return <CitationLink key={index} label={`[${sourceNumber}]`} sourceBaseId={sourceBaseId} sourceNumber={sourceNumber} />
    }
    return <span key={index}>{part}</span>
  })
}

function CitationLink({ label, sourceBaseId, sourceNumber }: { label: string; sourceBaseId: string; sourceNumber: number }) {
  const targetId = `${sourceBaseId}-${sourceNumber}`
  return (
    <a
      className="citation-link"
      href={`#${targetId}`}
      onClick={(event) => {
        const target = document.getElementById(targetId)
        if (!target) return
        event.preventDefault()
        target.scrollIntoView({ behavior: 'smooth', block: 'center' })
        window.history.replaceState(null, '', `#${targetId}`)
      }}
    >
      {label}
    </a>
  )
}

function displayAnswer(response: AgentResponse) {
  const answer = stripSystemReminders(response.answer)
  if (response.sources.length > 0) return { text: answer, sources: response.sources }
  const extracted = extractReferenceSection(answer)
  if (extracted.sources.length > 0) return { text: extracted.text, sources: extracted.sources }
  const sources = extractInlineDocumentSources(answer)
  return { text: normalizeInlineDocumentReferences(answer, sources), sources }
}

function stripSystemReminders(text: string) {
  return text.replace(/<system-reminder>[\s\S]*?<\/system-reminder>/g, '').trim()
}

function extractReferenceSection(answer: string): { text: string; sources: AgentSource[] } {
  const lines = answer.split('\n')
  const headingIndex = lines.findIndex((line) => isReferenceHeading(line))
  if (headingIndex < 0) return { text: answer, sources: [] }

  const headingReference = parseReferenceLine(stripReferenceHeading(lines[headingIndex]))
  const sources = [headingReference, ...lines.slice(headingIndex + 1).map(parseReferenceLine)].filter((source): source is AgentSource => source !== null)
  if (sources.length === 0) return { text: answer, sources: [] }
  return { text: lines.slice(0, headingIndex).join('\n').trim(), sources }
}

function isReferenceHeading(line: string) {
  return /^#{0,3}\s*(?:\*\*)?\s*(quellen|sources|referenzen|references)\s*(?:\*\*)?\s*:?/i.test(line.trim())
}

function stripReferenceHeading(line: string) {
  return line.trim().replace(/^#{0,3}\s*(?:\*\*)?\s*(quellen|sources|referenzen|references)\s*(?:\*\*)?\s*:?\s*/i, '')
}

function parseReferenceLine(line: string): AgentSource | null {
  const match = line.trim().match(/^(?:[-*]\s*)?(?:\d+[.)]\s*)?\[(\d+)\]\s*:?[\s-]*(.+)$/)
  if (!match) return null
  const raw = match[2].trim()
  const url = raw.match(/https?:\/\/\S+/)?.[0].replace(/[).,;]+$/, '') ?? null
  const title = raw.replace(/https?:\/\/\S+/, '').replace(/^[-:–—\s]+|[-:–—\s]+$/g, '').trim()
  return {
    title: title || url || `Quelle ${match[1]}`,
    url,
    snippet: null,
    document_id: `extracted-${match[1]}`,
    body_name: null,
    meeting_date: null,
    document_type: 'extracted',
  }
}

function extractInlineDocumentSources(answer: string): AgentSource[] {
  const sources = new Map<string, AgentSource>()
  const lines = answer.split('\n').map((line) => line.trim()).filter(Boolean)
  for (const line of lines) {
    for (const documentId of documentIds(line)) {
      if (!sources.has(documentId)) sources.set(documentId, sourceFromInlineReference(documentId, line))
    }
  }
  return [...sources.values()]
}

function documentIds(text: string) {
  return [...text.matchAll(/(Dok(?:ument)?\.?\s*`?)?(\d{5,6})\b/g)]
    .filter((match) => {
      const before = text.slice(Math.max(0, match.index - 32), match.index)
      const hasDocumentMarker = Boolean(match[1])
      const isSourceLine = /Quelle[n]?:/i.test(text)
      const isMeetingId = /sitzung|sitzungsdatensatz|sitzungsdatensatz\s*$/i.test(before)
      return !isMeetingId && (hasDocumentMarker || isSourceLine)
    })
    .map((match) => match[2])
}

function sourceFromInlineReference(documentId: string, context: string): AgentSource {
  const explicitUrl = context.match(/https?:\/\/\S+/)?.[0].replace(/[).,;]+$/, '') ?? null
  const sourceText = context.split(/Quelle[n]?:/i).pop() ?? context
  const label = sourceText
    .split(new RegExp(`(?:Dok(?:ument)?\\.?\\s*` + '`?' + `)?${documentId}\\b`, 'i'))[0]
    .replace(/SessionNet-Sitzung\s*`?\d+`?,?/i, '')
    .replace(/https?:\/\/\S+/, '')
    .replace(/Dok(?:ument)?\.?\s*`?$/i, '')
    .replace(/[`*_]/g, '')
    .replace(/[,;:–—\s]+$/g, '')
    .replace(/^[,;:–—\s]+/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  const title = enrichedSourceTitle(label, context, documentId)
  return {
    title: title || `Dokument ${documentId}`,
    url: explicitUrl ?? documentDownloadUrl(documentId),
    snippet: null,
    document_id: documentId,
    body_name: null,
    meeting_date: null,
    document_type: 'document',
  }
}

function enrichedSourceTitle(label: string, context: string, documentId: string) {
  const cleanedLabel = label || `Dokument ${documentId}`
  const body = context.match(/Stadtverordnetenversammlung|Haupt-, Finanz- und Rechtsausschuss|Stadtentwicklungs-, Umwelt- und Energieausschuss|Ortsbeirat [A-Za-zÄÖÜäöüß\- ]+/)?.[0]
  const date = context.match(/\b\d{2}\.\d{2}\.\d{4}\b/)?.[0]
  if (body && date) return `${cleanedLabel} zur ${body} vom ${date}`
  if (body) return `${cleanedLabel} zur ${body}`
  if (date) return `${cleanedLabel} vom ${date}`
  return cleanedLabel
}

function sourceTypeLabel(documentType: string | null) {
  if (documentType === 'document') return 'Dokument'
  if (documentType === 'extracted') return 'Quelle'
  return documentType ?? 'Quelle'
}

function sourceIndexByDocument(sources: AgentSource[]) {
  const index = new Map<string, number>()
  sources.forEach((source, sourceIndex) => {
    const documentId = source.document_id?.match(/\d{4,}/)?.[0]
    if (documentId && !index.has(documentId)) index.set(documentId, sourceIndex + 1)
  })
  return index
}

function normalizeInlineDocumentReferences(answer: string, sources: AgentSource[]) {
  if (sources.length === 0) return answer
  const index = sourceIndexByDocument(sources)
  return answer.split('\n').map((line) => normalizeReferenceLine(line, index)).join('\n')
}

function normalizeReferenceLine(line: string, sourceIndex: Map<string, number>) {
  if (/Quelle[n]?:/i.test(line)) {
    const [prefix] = line.split(/Quelle[n]?:/i)
    const refs = [...new Set(documentIds(line).map((documentId) => sourceIndex.get(documentId)).filter((value): value is number => Boolean(value)))]
    if (refs.length > 0) return `${prefix.trimEnd()} ${refs.map((ref) => `[${ref}]`).join(' ')}`.trim()
    if (/Dok(?:ument)?\.?\s*`{2}/i.test(line)) return prefix.trimEnd()
  }
  return line.replace(/(?:Dok(?:ument)?\.?\s*)?(\d{5,6})\b/g, (match, documentId: string) => {
    const ref = sourceIndex.get(documentId)
    return ref ? `[${ref}]` : match
  })
}

async function responseError(res: Response) {
  const text = await res.text()
  try {
    const payload = JSON.parse(text) as { error?: string }
    return payload.error || text
  } catch {
    return text || `HTTP ${res.status}`
  }
}

export default App
