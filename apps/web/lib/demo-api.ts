import { demoDetail, demoOverview, type DemoStage } from './demo-papers'
import { demoReport } from './demo-report'
import { ApiError, TERMINAL_EVENTS, type CreateInput, type EventName, type Report, type RunStatus, type Session, type StageId, type StageState, type TraceApi, type WorkflowEvent } from './trace-types'

// DEMO MODE ONLY. A browser-side simulator of the TRACE API so the whole journey can be exercised without the backend
// (a real run takes 15-25 minutes). Everything it returns is fictional. A question containing the word "fail" makes the
// simulated run fail in the summarizer, to exercise the failure states.

const STORE_KEY = 'trace.demo.sessions.v1'
const DEMO_PREFIX = 'demo-'

type Beat = { at: number; event: EventName; stage: StageId | null; status: string | null; message: string; data: Record<string, unknown> }

type Stored = { id: string; question: string; createdAt: string; fails: boolean; seed?: 'completed' | 'failed' }

function timeline(fails: boolean): Beat[] {
  const beats: Beat[] = [
    { at: 0, event: 'run_queued', stage: null, status: 'pending', message: 'Run queued', data: {} },
    { at: 700, event: 'run_started', stage: null, status: 'running', message: 'Run started', data: {} },
    { at: 900, event: 'stage_started', stage: 'planner', status: 'running', message: 'Planner started', data: {} },
    { at: 3200, event: 'stage_completed', stage: 'planner', status: 'completed', message: 'Planned 3 sub-questions and 9 search queries', data: { subQuestions: 3, queries: 9, domainAnchor: 'sample research field', topics: ['What is the sample method and how does it work?', 'How does the sample method scale to long inputs?', 'What are the open problems of the sample method?'] } },
    { at: 3500, event: 'stage_started', stage: 'retrieval', status: 'running', message: 'Retrieval started', data: {} },
    { at: 6500, event: 'branch_completed', stage: 'retrieval', status: 'completed', message: 'Kept 3 papers', data: { branch: 'papers', papers: 3 } },
    { at: 7800, event: 'branch_completed', stage: 'retrieval', status: 'completed', message: 'Found 2 web sources', data: { branch: 'web', webSources: 2 } },
    { at: 8200, event: 'stage_completed', stage: 'retrieval', status: 'completed', message: 'Retrieval finished', data: {} },
    { at: 8500, event: 'stage_started', stage: 'summarizer', status: 'running', message: 'Summarizer started', data: {} },
  ]
  if (fails) beats.push({ at: 12500, event: 'run_failed', stage: 'summarizer', status: 'failed', message: 'DemoError: simulated failure in the summarizer', data: {} })
  else beats.push(
    { at: 12500, event: 'stage_completed', stage: 'summarizer', status: 'completed', message: 'Digested 8 sources; 1 of 3 sub-questions have sufficient evidence', data: { digests: 8, subQuestions: 3, sufficientSubQuestions: 1 } },
    { at: 13000, event: 'run_completed', stage: null, status: 'completed', message: 'Run finished', data: { reportUrl: '', stagesNotRun: ['factcheck', 'report'] } },
  )
  return beats
}

function load(): Stored[] {
  if (typeof window === 'undefined') return []
  try { return JSON.parse(localStorage.getItem(STORE_KEY) ?? '[]') as Stored[] } catch { return [] }
}
function save(items: Stored[]) { try { localStorage.setItem(STORE_KEY, JSON.stringify(items.slice(0, 50))) } catch { /* storage full or blocked: the demo just forgets */ } }

function seeded(): Stored[] {
  const ago = (min: number) => new Date(Date.now() - min * 60_000).toISOString()
  return [
    { id: 'demo-completed', question: 'How does the sample method compare with the baseline? (demo)', createdAt: ago(95), fails: false, seed: 'completed' },
    { id: 'demo-interrupted', question: 'What happened to this interrupted demo run?', createdAt: ago(300), fails: true, seed: 'failed' },
  ]
}
function all(): Stored[] {
  const mine = load()
  return [...mine, ...seeded().filter(s => !mine.some(m => m.id === s.id))].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
}

function elapsed(s: Stored) { return s.seed ? Infinity : Date.now() - new Date(s.createdAt).getTime() }

function view(s: Stored): Session {
  const beats = timeline(s.fails)
  const t = elapsed(s)
  const stages: Record<StageId, StageState> = { planner: 'pending', retrieval: 'pending', summarizer: 'pending', factcheck: 'not_built', report: 'not_built' }
  let status: RunStatus = 'pending'
  let error: string | null = null
  for (const b of beats) {
    if (b.at > t) break
    if (b.event === 'run_started') status = 'running'
    if (b.stage && (b.event === 'stage_started' || b.event === 'stage_completed')) stages[b.stage] = b.event === 'stage_started' ? 'running' : 'completed'
    if (b.event === 'run_completed') status = 'completed'
    if (b.event === 'run_failed') { status = 'failed'; error = b.message; if (b.stage) stages[b.stage] = 'failed' }
  }
  if (s.seed === 'failed') error = 'The run did not finish (the server restarted or the run was stopped)'
  return {
    id: s.id, question: s.question, status, createdAt: s.createdAt,
    // like the real API, a run that only exists in storage has no start/finish times
    startedAt: s.seed || status === 'pending' ? null : new Date(new Date(s.createdAt).getTime() + 700).toISOString(),
    finishedAt: !s.seed && (status === 'completed' || status === 'failed') ? new Date(new Date(s.createdAt).getTime() + 13000).toISOString() : null,
    error, stages,
  }
}

/** What the simulated pipeline has written to its 'database' by now: papers kept (after retrieval), parsed (during), digests (after the summarizer). */
function stageOf(s: Stored): DemoStage | null {
  const t = elapsed(s)
  if (s.seed) return s.seed === 'completed' ? 'evidence' : 'parsed'
  if (t < 6500) return null
  if (t < 8200) return 'kept'
  if (t < 12500 || s.fails) return 'parsed'
  return 'evidence'
}

const wait = (ms: number) => new Promise(r => setTimeout(r, ms))
const find = (id: string) => all().find(s => s.id === id)

export const demoApi: TraceApi = {
  mode: 'demo',
  async health() { await wait(120); return { status: 'ok', activeRuns: all().filter(s => { const v = view(s).status; return v === 'pending' || v === 'running' }).length } },
  async list(limit = 20) { await wait(200); return all().slice(0, limit).map(s => { const v = view(s); return { id: v.id, question: v.question, status: v.status, createdAt: v.createdAt } }) },
  async create(input: CreateInput) {
    await wait(300)
    const s: Stored = { id: `${DEMO_PREFIX}${crypto.randomUUID().slice(0, 8)}`, question: input.question, createdAt: new Date().toISOString(), fails: /\bfail/i.test(input.question) }
    save([s, ...load()])
    return view(s)
  },
  async get(id) { await wait(150); const s = find(id); if (!s) throw new ApiError('Research session not found', 404); return view(s) },
  async report(id) {
    await wait(350)
    const s = find(id)
    if (!s) throw new ApiError('Research session not found', 404)
    const v = view(s)
    if (v.status === 'pending' || v.status === 'running') throw new ApiError('The run is not finished yet; follow /events and read the report after run_completed', 409)
    if (v.status === 'failed' && s.seed === 'failed') throw new ApiError('Research session not found', 404)
    const report: Report = demoReport(s.id, s.question, s.createdAt)
    if (v.status === 'failed') report.runError = v.error ?? undefined
    return report
  },
  async papers(id) {
    await wait(250)
    const s = find(id)
    if (!s) throw new ApiError('Research session not found', 404)
    const stage = stageOf(s)
    if (!stage) {
      const empty = demoOverview(id, 'kept')
      return { ...empty, counts: Object.fromEntries(Object.keys(empty.counts).map(k => [k, 0])) as typeof empty.counts, papers: [], web: [], subQuestions: [] }
    }
    return demoOverview(id, stage)
  },
  async paper(id, paperId) {
    await wait(300)
    const s = find(id)
    const stage = s ? stageOf(s) : null
    const detail = stage ? demoDetail(paperId, stage) : null
    if (!detail) throw new ApiError('Paper not found in this research session', 404)
    return detail
  },
  subscribe(id, { onEvent, onStatus }) {
    const s = find(id)
    onStatus('connecting')
    if (!s) { setTimeout(() => onStatus('error', 'Research session not found'), 200); return () => {} }
    const timers: ReturnType<typeof setTimeout>[] = []
    let cancelled = false
    const beats = timeline(s.fails)
    const base = new Date(s.createdAt).getTime()
    const deliver = (b: Beat, seq: number) => {
      if (cancelled) return
      const ev: WorkflowEvent = { seq, event: b.event, stage: b.stage, status: b.status, message: b.message, data: b.event === 'run_completed' ? { ...b.data, reportUrl: `/api/research/${id}/report` } : b.data, timestamp: new Date(base + b.at).toISOString() }
      onEvent(ev)
      if (TERMINAL_EVENTS.includes(b.event)) onStatus('closed')
    }
    timers.push(setTimeout(() => {
      if (cancelled) return
      onStatus('open')
      if (s.seed) {  // a run that only exists in storage gets one closing event, like the real API after a restart
        const last = beats[beats.length - 1]
        deliver({ ...last, at: 0, message: s.seed === 'failed' ? 'The run did not finish (the server restarted or the run was stopped)' : 'Run finished' }, 0)
        return
      }
      const t = elapsed(s)
      beats.forEach((b, seq) => {   // replay what already happened, schedule the rest
        if (b.at <= t) deliver(b, seq)
        else timers.push(setTimeout(() => deliver(b, seq), b.at - t))
      })
    }, 250))
    return () => { cancelled = true; timers.forEach(clearTimeout) }
  },
}
