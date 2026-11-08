import { demoFactDisagreements, demoFactTotals, type DemoFact } from './demo-factcheck'
import { demoDetail, demoOverview, type DemoStage } from './demo-papers'
import { demoReport } from './demo-report'
import { ApiError, TERMINAL_EVENTS, type CreateInput, type EventName, type Report, type RunStatus, type Session, type StageId, type StageState, type TraceApi, type WorkflowEvent } from './trace-types'

// DEMO MODE ONLY. A browser-side simulator of the TRACE API so the whole journey can be exercised without the backend
// (a real run takes 15-25 minutes). Everything it returns is fictional. A question containing the word "fail" makes the
// simulated run fail in the summarizer, to exercise the failure states. A question containing "factcheck" runs Stage 4 (fact check across sources);
// one containing "factfail" makes Stage 4 fail while the run still completes. Without either word Stage 4 is switched off (stage state 'not_run').

const STORE_KEY = 'trace.demo.sessions.v1'
const DEMO_PREFIX = 'demo-'

type Beat = { at: number; event: EventName; stage: StageId | null; status: string | null; message: string; data: Record<string, unknown> }

type Stored = { id: string; question: string; createdAt: string; fails: boolean; seed?: 'completed' | 'failed'; fact?: DemoFact }

const REL = { candidates: 24, shortlisted: 12, judged: 12, passed: 5, backend: 'server' }

function branch(at: number, lane: 'papers' | 'web'): Beat {
  return { at, event: 'branch_started', stage: 'retrieval', status: 'running', message: lane === 'papers' ? 'Paper retrieval started' : 'Web search started', data: { branch: lane } }
}
function step(at: number, lane: 'papers' | 'web' | 'summarizer', stepId: string, state: 'running' | 'completed', message: string, data: Record<string, unknown> = {}): Beat {
  return { at, event: 'step', stage: lane === 'summarizer' ? 'summarizer' : 'retrieval', status: state, message, data: { lane, step: stepId, state, ...data } }
}

/** Stage 4 runs after the summarizer, one sub-question after the other (about 3 minutes each on the real server). 5 sub-questions: the third has no Stage 3 result. */
function factcheckBeats(fact: Exclude<DemoFact, 'off'>): Beat[] {
  const fstep = (at: number, stepId: string, state: 'running' | 'completed' | 'failed', message: string, data: Record<string, unknown> = {}): Beat => ({ at, event: 'step', stage: 'factcheck', status: state, message, data: { lane: 'factcheck', step: stepId, state, ...data } })
  const out: Beat[] = [
    { at: 13050, event: 'stage_started', stage: 'factcheck', status: 'running', message: 'Checking claims across sources', data: {} },
    fstep(13060, 'branch', 'running', 'Checking claims across sources'),                    // a step the page does not know: it must be ignored
  ]
  const N = 5
  const last = fact === 'failed' ? 2 : N                       // a failing stage stops in the second sub-question
  for (let i = 1; i <= last; i++) {
    const at = 13100 + (i - 1) * 600
    const c = { subQuestion: i, subQuestions: N }
    out.push(fstep(at, 'claims', 'running', `Reading the claims of ${i + 1} sources`, { ...c, sources: i + 1 }),
      fstep(at + 150, 'clusters', 'running', 'Grouping the claims that say the same thing', { ...c, claims: 4 + i }),
      fstep(at + 300, 'support', 'running', 'Checking that the quotes support the grouped claims', { ...c, clusters: 3 + i }),
      fstep(at + 450, 'conflicts', 'running', 'Looking for sources that disagree', c))
  }
  if (fact === 'failed') {
    out.push(fstep(14400, 'store', 'failed', 'Fact checking failed: ConnectionError'),
      { at: 14500, event: 'stage_completed', stage: 'factcheck', status: 'failed', message: 'Fact checking failed: ConnectionError', data: { error: 'ConnectionError: the database stayed unreachable (simulated)' } })
    return out
  }
  const t = demoFactTotals()
  const claims = t.supported + t.partially_supported + t.unverified + t.contradicted
  out.push(fstep(16050, 'store', 'running', 'Saving the fact-check results', { claims, disagreements: demoFactDisagreements() }),
    fstep(16150, 'store', 'completed', `${claims} claims checked`, { claims, supported: t.supported, partially_supported: t.partially_supported, contradicted: t.contradicted, unverified: t.unverified }),
    { at: 16300, event: 'stage_completed', stage: 'factcheck', status: 'completed', message: `Checked ${claims} claims: ${t.supported} supported, ${t.partially_supported} partially supported, ${t.unverified} unverified, ${t.contradicted} contradicted`,
      data: { claims, subQuestions: N, failedSubQuestions: 1, supported: t.supported, partially_supported: t.partially_supported, unverified: t.unverified, contradicted: t.contradicted, contested: t.contested, disagreements: demoFactDisagreements(), judgeFailures: 3 } })
  return out
}

/** The retrieval branches run AT THE SAME TIME (like the real graph); each reports its steps. */
function timeline(fails: boolean, fact: DemoFact = 'off'): Beat[] {
  const beats: Beat[] = [
    { at: 0, event: 'run_queued', stage: null, status: 'pending', message: 'Run queued', data: {} },
    { at: 700, event: 'run_started', stage: null, status: 'running', message: 'Run started', data: {} },
    { at: 900, event: 'stage_started', stage: 'planner', status: 'running', message: 'Planner started', data: {} },
    { at: 3200, event: 'stage_completed', stage: 'planner', status: 'completed', message: 'Planned 3 sub-questions and 9 search queries', data: { subQuestions: 3, queries: 9, domainAnchor: 'sample research field', topics: ['What is the sample method and how does it work?', 'How does the sample method scale to long inputs?', 'What are the open problems of the sample method?'] } },
    { at: 3500, event: 'stage_started', stage: 'retrieval', status: 'running', message: 'Retrieval started', data: {} },

    // ---- paper lane
    branch(3600, 'papers'),
    step(3650, 'papers', 'search', 'running', 'Searching OpenAlex, Scopus and arXiv', { subQuestions: 3, queries: 9 }),
    step(4600, 'papers', 'search', 'completed', 'Found 24 candidate papers', { candidates: 24 }),
    step(4650, 'papers', 'relevance_filter', 'running', 'Judging relevance (embedding shortlist, then the LLM judge)', { candidates: 24, done: 0, total: 3 }),
    step(5100, 'papers', 'relevance_filter', 'running', 'Judged sub-question 1 of 3', { done: 1, total: 3, candidates: 8, shortlisted: 4, judged: 4, passed: 2, backend: 'server' }),
    step(5600, 'papers', 'relevance_filter', 'running', 'Judged sub-question 2 of 3', { done: 2, total: 3, candidates: 16, shortlisted: 8, judged: 8, passed: 3, backend: 'server' }),
    step(6100, 'papers', 'relevance_filter', 'running', 'Judged sub-question 3 of 3', { done: 3, total: 3, ...REL }),
    step(6150, 'papers', 'relevance_filter', 'completed', '5 of 24 candidates passed (12 judge calls)', REL),
    step(6200, 'papers', 'citations', 'running', 'Fetching citation counts for the papers that passed', { papers: 5 }),
    step(6350, 'papers', 'citations', 'completed', '5 papers kept', { kept: 5 }),
    step(6400, 'papers', 'scoring', 'running', 'Scoring reliability and ranking', { papers: 5 }),
    step(6500, 'papers', 'scoring', 'completed', 'Scored 5 papers', { scored: 5 }),
    step(6550, 'papers', 'store', 'running', 'Saving the papers', { papers: 5 }),
    step(6650, 'papers', 'store', 'completed', 'Saved 5 papers', { stored: 5 }),
    step(6700, 'papers', 'parsing', 'running', 'Parsing the best 3 papers (PDF to text)', { target: 3, attempted: 0, usable: 0, papers: 5 }),
    step(7300, 'papers', 'parsing', 'running', 'Parsed 1 of 3 papers', { target: 3, attempted: 1, usable: 1 }),
    step(8000, 'papers', 'parsing', 'running', 'Parsed 2 of 3 papers', { target: 3, attempted: 2, usable: 2 }),
    step(8700, 'papers', 'parsing', 'running', 'Parsed 2 of 3 papers', { target: 3, attempted: 3, usable: 2 }),
    step(9000, 'papers', 'parsing', 'completed', '2 of 3 papers parsed', { target: 3, attempted: 3, usable: 2 }),
    { at: 9100, event: 'branch_completed', stage: 'retrieval', status: 'completed', message: 'Kept 5 papers', data: { branch: 'papers', papers: 5 } },

    // ---- web lane (same time as the paper lane)
    branch(3600, 'web'),
    step(3650, 'web', 'search', 'running', 'Searching the web', { subQuestions: 3, queries: 9, done: 0, total: 3 }),
    step(4200, 'web', 'search', 'running', 'Searched sub-question 1 of 3', { done: 1, total: 3, found: 1 }),
    step(4800, 'web', 'search', 'running', 'Searched sub-question 2 of 3', { done: 2, total: 3, found: 2 }),
    step(5400, 'web', 'search', 'running', 'Searched sub-question 3 of 3', { done: 3, total: 3, found: 3 }),
    step(5500, 'web', 'search', 'completed', 'Found 3 web sources', { found: 3 }),
    step(5550, 'web', 'scoring', 'running', 'Scoring source reliability', { sources: 3 }),
    step(5650, 'web', 'scoring', 'completed', 'Scored 3 sources', { scored: 3 }),
    step(5700, 'web', 'store', 'running', 'Saving the web sources', { sources: 3 }),
    step(5800, 'web', 'store', 'completed', 'Saved 3 web sources', { stored: 3 }),
    { at: 5900, event: 'branch_completed', stage: 'retrieval', status: 'completed', message: 'Found 3 web sources', data: { branch: 'web', webSources: 3 } },

    { at: 9200, event: 'stage_completed', stage: 'retrieval', status: 'completed', message: 'Retrieval finished', data: {} },
    { at: 9400, event: 'stage_started', stage: 'summarizer', status: 'running', message: 'Reading sources and checking evidence', data: {} },
    step(9450, 'summarizer', 'prepare', 'running', 'Selecting the passages to read (chunking, embeddings)', { subQuestions: 3 }),
    step(9700, 'summarizer', 'prepare', 'completed', '3 sources to read', { jobs: 3, papers: 2, web: 1 }),
    step(9800, 'summarizer', 'digest', 'running', 'Reading 3 sources with the LLM', { done: 0, total: 3, failures: 0 }),
    step(10500, 'summarizer', 'digest', 'running', 'Read 1 of 3 sources', { done: 1, total: 3, failures: 0 }),
    step(11200, 'summarizer', 'digest', 'running', 'Read 2 of 3 sources', { done: 2, total: 3, failures: 0 }),
    step(11900, 'summarizer', 'digest', 'running', 'Read 3 of 3 sources', { done: 3, total: 3, failures: 0 }),
    step(11950, 'summarizer', 'digest', 'completed', 'Read 3 sources', { done: 3, total: 3, failures: 0 }),
    step(12000, 'summarizer', 'judge', 'running', 'Judging the evidence for sub-question 1 of 3', { done: 0, total: 3 }),
    step(12250, 'summarizer', 'judge', 'running', 'Judged sub-question 1 of 3', { done: 1, total: 3, sufficient: true, judgeUsed: true, sufficientSoFar: 1 }),
    // Loop 2 (the optional second search) runs between the judge events: judge, loop2, judge, loop2, judge
    step(12300, 'summarizer', 'loop2', 'running', "Loop 2 (reselect): 2 aspect(s) of 'How does the sample method scale to long inputs?'", { loop2Step: 'reselect', aspects: 2 }),
    step(12400, 'summarizer', 'loop2', 'running', "Loop 2 searched again: 'How does the sample method scale to long inputs?'", { subQuestion: 'How does the sample method scale to long inputs?', searched: 2, covered: 1 }),
    step(12500, 'summarizer', 'judge', 'running', 'Judged sub-question 2 of 3', { done: 2, total: 3, sufficient: false, judgeUsed: true, sufficientSoFar: 1 }),
    step(12550, 'summarizer', 'loop2', 'running', "Loop 2 (pool): 1 aspect(s) of 'What are the open problems of the sample method?'", { loop2Step: 'pool', aspects: 1 }),
    step(12620, 'summarizer', 'loop2', 'running', "Loop 2 searched again: 'What are the open problems of the sample method?'", { subQuestion: 'What are the open problems of the sample method?', searched: 1, covered: 0 }),
    step(12700, 'summarizer', 'judge', 'running', 'Judged sub-question 3 of 3', { done: 3, total: 3, sufficient: false, judgeUsed: null, sufficientSoFar: 1 }),
    step(12730, 'summarizer', 'loop2', 'completed', 'Loop 2 finished: 3 aspect(s) searched again, 1 covered', { searched: 3, covered: 1 }),
    step(12750, 'summarizer', 'judge', 'completed', '1 of 3 sub-questions have enough evidence', { done: 3, total: 3, sufficientSubQuestions: 1 }),
    step(12800, 'summarizer', 'store', 'running', 'Saving the digests and coverage', { digests: 3 }),
    step(12900, 'summarizer', 'store', 'completed', 'Saved 3 digests', { stored: 3 }),
  ]
  if (fails) {
    // the summarizer stops while it is reading sources
    const failure: Beat = { at: 12500, event: 'run_failed', stage: 'summarizer', status: 'failed', message: 'DemoError: simulated failure in the summarizer', data: {} }
    return [...beats.filter(b => b.at < 11000), failure].sort((x, y) => x.at - y.at)
  }
  beats.push({ at: 13000, event: 'stage_completed', stage: 'summarizer', status: 'completed', message: 'Digested 3 sources; 1 of 3 sub-questions have sufficient evidence', data: { digests: 3, subQuestions: 3, sufficientSubQuestions: 1 } })
  if (fact === 'off') beats.push({ at: 13500, event: 'run_completed', stage: null, status: 'completed', message: 'Run finished', data: { reportUrl: '', stagesNotRun: ['factcheck', 'report'] } })
  else beats.push(...factcheckBeats(fact), { at: fact === 'on' ? 16500 : 14800, event: 'run_completed', stage: null, status: 'completed', message: 'Run finished', data: { reportUrl: '', stagesNotRun: ['report'] } })
  return beats.sort((x, y) => x.at - y.at)
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
    { id: 'demo-factcheck', question: 'How does the sample method compare with the baseline? (demo, with the cross-check)', createdAt: ago(130), fails: false, seed: 'completed', fact: 'on' },
    { id: 'demo-factcheck-failed', question: 'How does the sample method scale? (demo, the cross-check failed)', createdAt: ago(160), fails: false, seed: 'completed', fact: 'failed' },
  ]
}
function all(): Stored[] {
  const mine = load()
  return [...mine, ...seeded().filter(s => !mine.some(m => m.id === s.id))].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
}

function elapsed(s: Stored) { return s.seed ? Infinity : Date.now() - new Date(s.createdAt).getTime() }

function view(s: Stored): Session {
  const beats = timeline(s.fails, s.fact)
  const t = elapsed(s)
  const stages: Record<StageId, StageState> = { planner: 'pending', retrieval: 'pending', summarizer: 'pending', factcheck: s.fact ? 'pending' : 'not_run', report: 'not_built' }
  let status: RunStatus = 'pending'
  let error: string | null = null
  for (const b of beats) {
    if (b.at > t) break
    if (b.event === 'run_started') status = 'running'
    if (b.stage && (b.event === 'stage_started' || b.event === 'stage_completed')) stages[b.stage] = b.event === 'stage_started' ? 'running' : b.status === 'failed' ? 'failed' : 'completed'
    if (b.event === 'run_completed') status = 'completed'
    if (b.event === 'run_failed') { status = 'failed'; error = b.message; if (b.stage) stages[b.stage] = 'failed' }
  }
  if (s.seed === 'failed') error = 'The run did not finish (the server restarted or the run was stopped)'
  return {
    id: s.id, question: s.question, status, createdAt: s.createdAt,
    // like the real API, a run that only exists in storage has no start/finish times
    startedAt: s.seed || status === 'pending' ? null : new Date(new Date(s.createdAt).getTime() + 700).toISOString(),
    finishedAt: !s.seed && (status === 'completed' || status === 'failed') ? new Date(new Date(s.createdAt).getTime() + (s.fact === 'on' ? 16500 : s.fact === 'failed' ? 14800 : 13000)).toISOString() : null,
    error, stages,
  }
}

/** What the simulated pipeline has written to its 'database' by now: papers kept (after retrieval), parsed (during), digests (after the summarizer). */
function stageOf(s: Stored): DemoStage | null {
  const t = elapsed(s)
  if (s.seed) return s.seed === 'completed' ? 'evidence' : 'parsed'
  if (t < 6650) return null                     // the papers are saved at 6.65 s (see timeline())
  if (t < 7300) return 'kept'
  if (t < 12900 || s.fails) return 'parsed'
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
    const s: Stored = { id: `${DEMO_PREFIX}${crypto.randomUUID().slice(0, 8)}`, question: input.question, createdAt: new Date().toISOString(), fails: /\bfail/i.test(input.question), fact: /\bfactfail\b/i.test(input.question) ? 'failed' : /\bfactcheck\b/i.test(input.question) ? 'on' : undefined }
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
    const report: Report = demoReport(s.id, s.question, s.createdAt, s.fact ?? 'off')
    if (v.status === 'failed') report.runError = v.error ?? undefined
    return report
  },
  async papers(id) {
    await wait(250)
    const s = find(id)
    if (!s) throw new ApiError('Research session not found', 404)
    const stage = stageOf(s)
    if (!stage) {
      const empty = demoOverview(id, 'kept', s.createdAt)
      return { ...empty, counts: Object.fromEntries(Object.keys(empty.counts).map(k => [k, 0])) as typeof empty.counts, papers: [], web: [], subQuestions: [] }
    }
    return demoOverview(id, stage, s.createdAt)
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
    const beats = timeline(s.fails, s.fact)
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
