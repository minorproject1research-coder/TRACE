import { ApiError, TERMINAL_EVENTS, type CreateInput, type Health, type PaperDetail, type PapersOverview, type Report, type RunSummary, type Session, type StreamHandlers, type TraceApi, type WorkflowEvent, type WrittenReportResponse, type WrittenReportResult } from './trace-types'

/**
 * Public URL of the FastAPI service. Only a URL: no secret ever belongs in a NEXT_PUBLIC_ variable (it ships to every browser).
 * In development it defaults to localhost. In production there is no default: if it is unset the app calls its own origin, so a reverse proxy
 * must route /api and /health to the backend. A production build must never point visitors' browsers at their own localhost.
 */
export const API_BASE_URL = (process.env.NEXT_PUBLIC_TRACE_API_URL ?? (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000')).replace(/\/$/, '')
export const API_LABEL = API_BASE_URL || 'this site (same origin)'

const DEFAULT_TIMEOUT = 20_000
const REPORT_TIMEOUT = 60_000

/** FastAPI sends {"detail": "text"} or, for 422, {"detail": [{loc, msg}, ...]}. */
function detailMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string; loc?: unknown[] }
    const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : ''
    return `${field ? field + ': ' : ''}${first.msg ?? 'Invalid request'}`
  }
  if (status === 404) return 'Not found'
  if (status === 429) return 'TRACE is busy. The run queue is full, try again in a few minutes.'
  if (status >= 500) return 'The TRACE server hit an error. Try again.'
  return `Request failed (${status})`
}

const wait = (ms: number) => new Promise(r => setTimeout(r, ms))

/** GETs are idempotent, so one transient failure (dropped connection, 5xx) is retried once before the user sees an error. */
async function request<T>(path: string, init?: RequestInit, timeout = DEFAULT_TIMEOUT): Promise<T> {
  const isGet = !init?.method || init.method === 'GET'
  try {
    return await attempt<T>(path, init, timeout)
  } catch (e) {
    const transient = e instanceof ApiError && (e.status === undefined ? !e.message.includes('too long') : e.status >= 500)
    if (!isGet || !transient) throw e
    await wait(500)
    return attempt<T>(path, init, timeout)
  }
}

async function attempt<T>(path: string, init?: RequestInit, timeout = DEFAULT_TIMEOUT): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers },
      signal: controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('The TRACE backend took too long to respond. Try again.')
    throw new ApiError(`Cannot reach the TRACE backend at ${API_BASE_URL}. Is it running?`)
  } finally {
    clearTimeout(timer)
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(detailMessage(body, response.status), response.status)
  return body as T
}

const enc = encodeURIComponent

/** The written-report GET answers 200 (ready), 202 (being written) and 404 (none stored); 202 and 404 are results here, not errors. 503 and the rest throw. */
async function writtenReport(id: string): Promise<WrittenReportResult> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REPORT_TIMEOUT)
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/api/research/${enc(id)}/written-report`, { headers: { Accept: 'application/json' }, signal: controller.signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('The TRACE backend took too long to respond. Try again.')
    throw new ApiError(`Cannot reach the TRACE backend at ${API_BASE_URL}. Is it running?`)
  } finally {
    clearTimeout(timer)
  }
  const body = await response.json().catch(() => null)
  if (response.status === 202) return { state: 'running' }
  if (response.status === 404) return { state: 'none', detail: detailMessage(body, 404) }
  if (!response.ok) throw new ApiError(detailMessage(body, response.status), response.status)
  return { state: 'ready', data: body as WrittenReportResponse }
}

export const liveApi: TraceApi = {
  mode: 'live',
  health: () => request<Health>('/health', undefined, 8_000),
  async list(limit = 20) {
    const body = await request<{ items: RunSummary[] }>(`/api/research?limit=${limit}`)
    return body.items
  },
  create: (input: CreateInput) => request<Session>('/api/research', { method: 'POST', body: JSON.stringify(input) }),
  get: (id) => request<Session>(`/api/research/${enc(id)}`),
  report: (id) => request<Report>(`/api/research/${enc(id)}/report`, undefined, REPORT_TIMEOUT),
  papers: (id) => request<PapersOverview>(`/api/research/${enc(id)}/papers`, undefined, REPORT_TIMEOUT),
  paper: (id, paperId) => request<PaperDetail>(`/api/research/${enc(id)}/papers/${enc(paperId)}`, undefined, REPORT_TIMEOUT),
  writtenReport,
  writeWrittenReport: (id) => request<{ state: string }>(`/api/research/${enc(id)}/written-report`, { method: 'POST', body: JSON.stringify({}) }),

  subscribe(id, { onEvent, onStatus }: StreamHandlers) {
    let source: EventSource | null = null
    let lastSeq = -1
    let done = false
    onStatus('connecting')
    // The server replays every event on (re)connect; `after` keeps us from re-delivering what we already have.
    const open = () => {
      source = new EventSource(`${API_BASE_URL}/api/research/${enc(id)}/events${lastSeq >= 0 ? `?after=${lastSeq}` : ''}`)
      source.onopen = () => onStatus('open')
      source.onmessage = (message) => {
        let event: WorkflowEvent
        try { event = JSON.parse(message.data) as WorkflowEvent } catch { return }
        if (event.seq <= lastSeq) return
        lastSeq = event.seq
        onEvent(event)
        if (TERMINAL_EVENTS.includes(event.event)) {   // the server ends the stream here; close or the browser reconnects forever
          done = true
          source?.close()
          onStatus('closed')
        }
      }
      source.onerror = () => {
        if (done) return
        if (source?.readyState === EventSource.CLOSED) {   // the server refused (404) or the connection is gone for good
          source.close()
          onStatus('error', 'The live event stream is unavailable.')
        } else {
          onStatus('reconnecting')                        // the browser retries by itself
        }
      }
    }
    open()
    return () => { done = true; source?.close() }
  },
}
