import { useEffect, useState } from 'react'
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
      if (!res.ok) {
        if (res.status === 401) setAuthStatus({ authenticated: false, auth_enabled: true })
        throw new Error(await responseError(res))
      }
      const response = (await res.json()) as AgentResponse
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', content: response.answer, requestTask: content, response },
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unbekannter Fehler')
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
  return (
    <article className={`chat-bubble ${message.role}`}>
      {message.role === 'user' ? <p>{message.content}</p> : <MarkdownText sourceCount={response?.sources.length ?? 0} text={message.content} />}
      {response && <AnswerDetails researchDepth={researchDepth} requestTask={message.requestTask ?? message.content} response={response} />}
    </article>
  )
}

function AnswerDetails({ researchDepth, requestTask, response }: { researchDepth: ResearchDepth; requestTask: string; response: AgentResponse }) {
  return (
    <div className="answer-details">
      <div className="answer-meta"><span>{response.provider}</span><span>{response.sources.length} Quellen</span></div>
      {response.sources.length > 0 && <SourceList sources={response.sources} />}
      <details className="trace-card inline-trace">
        <summary>Rechercheweg</summary>
        <ol>{response.actions_taken.map((action, index) => <li key={`${action.name}-${index}`}><strong>{action.name}</strong><span>{JSON.stringify(action.arguments)}</span></li>)}</ol>
      </details>
      <FeedbackBox requestTask={requestTask || response.answer.slice(0, 200)} researchDepth={researchDepth} response={response} />
    </div>
  )
}

function SourceList({ sources }: { sources: AgentSource[] }) {
  return (
    <div className="sources used-sources chat-sources">
      {sources.map((source, index) => (
        <a className="source-item" href={source.url ?? '#'} key={`${source.document_id}-${index}`} rel="noreferrer" target="_blank">
          <span className="source-meta"><span className="source-number">[{index + 1}]</span>{source.meeting_date ?? source.document_type ?? 'Quelle'}</span>
          <strong>{source.title ?? 'Unbenannte Quelle'}</strong>
          <small>{source.body_name}</small>
          {source.snippet && <p>{source.snippet}</p>}
        </a>
      ))}
    </div>
  )
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

function MarkdownText({ sourceCount, text }: { sourceCount: number; text: string }) {
  const blocks = text.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean)
  return <div className="markdown-answer">{blocks.map((block, index) => <MarkdownBlock block={block} key={index} sourceCount={sourceCount} />)}</div>
}

function MarkdownBlock({ block, sourceCount }: { block: string; sourceCount: number }) {
  const lines = block.split('\n').map((line) => line.trim()).filter(Boolean)
  const firstLine = lines[0] ?? ''
  if (firstLine.startsWith('## ')) return <><h3>{renderInline(firstLine.slice(3), sourceCount)}</h3>{lines.slice(1).map((line) => <p key={line}>{renderInline(line.replace(/^[-*]\s+/, ''), sourceCount)}</p>)}</>
  if (lines.every((line) => /^[-*]\s+/.test(line))) return <ul>{lines.map((line) => <li key={line}>{renderInline(line.replace(/^[-*]\s+/, ''), sourceCount)}</li>)}</ul>
  return <p>{renderInline(lines.join(' '), sourceCount)}</p>
}

function renderInline(text: string, sourceCount: number) {
  return text.split(/(\*\*[^*]+\*\*|\[\d+\])/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>
    if (/^\[\d+\]$/.test(part)) {
      const sourceIndex = Number(part.slice(1, -1))
      if (sourceIndex >= 1 && sourceIndex <= sourceCount) return <span className="citation-link" key={index}>{part}</span>
    }
    return <span key={index}>{part}</span>
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
