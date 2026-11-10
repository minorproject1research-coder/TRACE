import type { WorkflowEvent } from './trace-types'

// The event reducer. Pure functions, no React: the run page re-reads the whole event list on every change, so everything here is a function of
// "the events so far" and nothing else. That is what makes a burst of replayed events render its final state at once (nothing is animated per
// event) and what lets two sub-questions be in the same step at the same time.
//
// The rules (docs/API_HANDOFF.md, "Work that now runs at the same time"):
//  - events are merged by `seq`, whatever order they arrive in; a duplicate seq counts once
//  - the real time of an event is data.occurredAt when it has one, otherwise its timestamp (the judge, Loop 2 and Stage 4 events are held and replayed)
//  - state is keyed by (lane, step, sub-question index), never by "the sub-question that is current"; the index comes from the numeric fields
//    subQuestionIndex (judge, Loop 2) and subQuestion (Stage 4), never from the message text
//  - counters never go backwards; an unknown step, an unknown field and an unknown token purpose are ignored or shown as they are

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
/** A 1-based sub-question index. Anything else (a string, 0, 2.5, null) is not an index. */
export const posInt = (v: unknown): number | null => (isNum(v) && Number.isInteger(v) && v >= 1 ? v : null)
const str = (v: unknown): string | null => (typeof v === 'string' && v ? v : null)
const hasOwn = (o: object, k: string) => Object.prototype.hasOwnProperty.call(o, k)

// ------------------------------------------------------------------------------------------------------------------------ time and order
export function toMs(v: unknown): number | null {
  if (typeof v !== 'string' || !v) return null
  const t = Date.parse(v)
  return Number.isNaN(t) ? null : t
}

/** When the event really happened: data.occurredAt if it is a readable time, else the emit timestamp. */
export const eventMs = (e: Pick<WorkflowEvent, 'data' | 'timestamp'>): number | null => toMs(e.data?.occurredAt) ?? toMs(e.timestamp)

/** The same as an ISO string. Without occurredAt this is the event's own timestamp, untouched. */
export function eventIso(e: Pick<WorkflowEvent, 'data' | 'timestamp'>): string | null {
  const o = toMs(e.data?.occurredAt)
  return o != null ? new Date(o).toISOString() : (e.timestamp ?? null)
}

/** The earliest and the latest real time among some events. */
export function spanOf(evs: Pick<WorkflowEvent, 'data' | 'timestamp'>[]): { from: string | null; to: string | null } {
  let a: number | null = null, b: number | null = null
  for (const e of evs) {
    const t = eventMs(e)
    if (t == null) continue
    if (a == null || t < a) a = t
    if (b == null || t > b) b = t
  }
  return { from: a == null ? null : new Date(a).toISOString(), to: b == null ? null : new Date(b).toISOString() }
}

/** Events in seq order, each seq once (the last copy that arrived wins). Returns the same array when it already is in order. */
export function mergeBySeq(events: WorkflowEvent[]): WorkflowEvent[] {
  let ordered = true
  for (let i = 1; i < events.length; i++) if (!(events[i - 1].seq < events[i].seq)) { ordered = false; break }
  if (ordered) return events
  const by = new Map<number, WorkflowEvent>()
  const loose: WorkflowEvent[] = []
  for (const e of events) {
    if (!e) continue
    if (isNum(e.seq)) by.set(e.seq, e)
    else loose.push(e)
  }
  return [...[...by.entries()].sort((x, y) => x[0] - y[0]).map(x => x[1]), ...loose]
}

/** Counters of a step that must never go back. Per-sub-question numbers (claims, sources, searched, covered) are not in this list on purpose. */
const MONOTONIC = ['done', 'total', 'failures', 'usable', 'attempted', 'sufficientSoFar', 'sufficientSubQuestions', 'found', 'judged', 'passed', 'shortlisted', 'candidates', 'scored', 'kept', 'stored']

/** The data of the latest event of a step, with every cumulative counter raised to the largest value any event of the step reported. Two judges that finish
 *  at nearly the same moment can reach the stream as done=3 and then done=2: the page must keep 3. */
export function mergedData(evs: WorkflowEvent[]): Record<string, unknown> {
  const out: Record<string, unknown> = { ...(evs[evs.length - 1]?.data ?? {}) }
  for (const k of MONOTONIC) {
    let m: number | null = null
    for (const e of evs) { const v = e.data?.[k]; if (isNum(v) && (m == null || v > m)) m = v }
    if (m != null) out[k] = m
  }
  return out
}

/** The step events of one lane and step, in seq order. */
export const stepEvents = (events: WorkflowEvent[], lane: string, step: string): WorkflowEvent[] =>
  events.filter(e => e.event === 'step' && e.data?.lane === lane && e.data?.step === step)

// ------------------------------------------------------------------------------------------------------------------------ judge (Stage 3)
export type SqPhase = 'waiting' | 'active' | 'done'

export type JudgeSq = {
  index: number
  phase: SqPhase
  /** Only for a finished sub-question: did it end up with enough evidence? null when the event did not say. */
  sufficient: boolean | null
  judgeUsed: boolean | null
  startedAt: string | null
  endedAt: string | null
}

export type JudgeModel = {
  /** true when the events carry subQuestionIndex. Old events do not: then only the counters are known and `sqs` is empty. */
  indexed: boolean
  total: number | null
  /** Sub-questions FINISHED (completion order, not an index). Never decreases. */
  done: number
  sufficient: number | null
  /** The digest step has reported completed. The judge events are held until then, so no chip can change before it. */
  digestDone: boolean
  completed: boolean
  judging: number
  sqs: JudgeSq[]
}

const SUMMARIZER = 'summarizer'

export function judgeModel(input: WorkflowEvent[]): JudgeModel {
  const events = mergeBySeq(input)
  const digest = stepEvents(events, SUMMARIZER, 'digest')
  const mine = stepEvents(events, SUMMARIZER, 'judge')
  const by = new Map<number, JudgeSq>()
  let total: number | null = null, done = 0, sufficient: number | null = null, completed = false, indexed = false
  const bump = (v: unknown, cur: number | null) => (isNum(v) && (cur == null || v > cur) ? v : cur)
  for (const e of mine) {
    const d = e.data
    total = bump(d.total, total); total = bump(d.subQuestions, total)
    if (isNum(d.done) && d.done > done) done = d.done
    sufficient = bump(d.sufficientSoFar, sufficient); sufficient = bump(d.sufficientSubQuestions, sufficient)
    if (d.state === 'completed') completed = true
    const idx = posInt(d.subQuestionIndex)
    if (idx == null) continue
    indexed = true
    const sq = by.get(idx) ?? { index: idx, phase: 'waiting' as SqPhase, sufficient: null, judgeUsed: null, startedAt: null, endedAt: null }
    by.set(idx, sq)
    const t = eventIso(e)
    const finished = typeof d.sufficient === 'boolean'
    if (finished) {
      sq.phase = 'done'; sq.sufficient = d.sufficient as boolean
      sq.judgeUsed = typeof d.judgeUsed === 'boolean' ? d.judgeUsed : sq.judgeUsed
      sq.endedAt = t
    } else if (sq.phase !== 'done') sq.phase = 'active'                           // a late "started" never takes a finished chip back
    const tm = toMs(t), cur = toMs(sq.startedAt)
    if (t != null && (cur == null || (tm != null && tm < cur))) sq.startedAt = t
  }
  const finishedCount = [...by.values()].filter(s => s.phase === 'done').length
  done = Math.max(done, finishedCount)
  if (completed && total != null) done = Math.max(done, total)
  const n = Math.max(total ?? 0, ...by.keys())
  const sqs: JudgeSq[] = indexed
    ? Array.from({ length: n }, (_, i) => by.get(i + 1) ?? { index: i + 1, phase: 'waiting' as SqPhase, sufficient: null, judgeUsed: null, startedAt: null, endedAt: null })
    : []
  return {
    indexed, total: total ?? (indexed ? n : null), done, sufficient, completed,
    digestDone: digest.some(e => e.data.state === 'completed'),
    judging: sqs.filter(s => s.phase === 'active').length, sqs,
  }
}

// ------------------------------------------------------------------------------------------------------------------------ Loop 2 (second search)
export type Loop2Sq = {
  index: number
  /** The rung it is on now (reselect | pool | queries, or any word the server invents) and the ones it already went through. */
  rung: string | null
  rungs: string[]
  aspects: number | null
  searched: number | null
  covered: number | null
  /** The sub-question reported its totals: its second search is over. */
  done: boolean
}

export type Loop2Model = {
  /** Some loop2 event carried subQuestionIndex. Without it there can only be one "current step" for the whole run, as before. */
  indexed: boolean
  sqs: Loop2Sq[]
}

export function loop2Model(input: WorkflowEvent[]): Loop2Model {
  const events = mergeBySeq(input)
  const by = new Map<number, Loop2Sq>()
  for (const e of stepEvents(events, SUMMARIZER, 'loop2')) {
    const idx = posInt(e.data.subQuestionIndex)
    if (idx == null) continue
    const sq = by.get(idx) ?? { index: idx, rung: null, rungs: [], aspects: null, searched: null, covered: null, done: false }
    by.set(idx, sq)
    const rung = str(e.data.loop2Step)
    if (rung && !sq.done) {
      sq.rung = rung; if (!sq.rungs.includes(rung)) sq.rungs.push(rung)
      sq.aspects = isNum(e.data.aspects) ? e.data.aspects : sq.aspects
    }
    if (isNum(e.data.searched) && isNum(e.data.covered)) {
      sq.searched = Math.max(sq.searched ?? 0, e.data.searched); sq.covered = Math.max(sq.covered ?? 0, e.data.covered); sq.done = true
    }
  }
  return { indexed: by.size > 0, sqs: [...by.values()].sort((a, b) => a.index - b.index) }
}

// ------------------------------------------------------------------------------------------------------------------------ Stage 4 (fact check)
/** The steps of one sub-question, in the order they start. near and conflicts have the same rank: they run side by side. store is not per
 *  sub-question: the node saves everything once at the end. */
export const FACT_RANK = { claims: 0, clusters: 1, support: 2, near: 3, conflicts: 3, store: 4 } as const
export type FactStepId = keyof typeof FACT_RANK
export const FACT_STEPS: FactStepId[] = ['claims', 'clusters', 'support', 'near', 'conflicts', 'store']
const isFactStep = (s: unknown): s is FactStepId => typeof s === 'string' && hasOwn(FACT_RANK, s)

export type FactSqStatus = 'waiting' | 'running' | 'done' | 'failed' | 'not_reported'

export type FactSq = {
  /** 1-based. 0 collects the events that carried no usable index. */
  index: number
  status: FactSqStatus
  /** The steps it reported, in pipeline order (without store). */
  reported: FactStepId[]
  /** The steps running now. After `support` the next two (near, conflicts) are both active until the sub-question is finished. */
  active: FactStepId[]
  sources: number | null
  claims: number | null
  clusters: number | null
  firstAt: string | null
  lastAt: string | null
  /** Its work began before the evidence stage (Stage 3) ended: Stage 4 overlapped with Stage 3. */
  early: boolean
  lastSeq: number
  totalSeen: number | null
}

export type FactStore = { state: string | null; claims: number | null; disagreements: number | null; at: string | null }

export type FactModel = {
  /** Any stage_started / stage_completed / run_failed event of the fact-check stage. */
  hasStage: boolean
  stage: 'running' | 'completed' | 'failed' | null
  total: number | null
  sqs: FactSq[]
  /** Did any sub-question report the near step? Old servers never do: then the near column is left out, as before. */
  hasNear: boolean
  store: FactStore | null
  /** The real start: the earliest of stage_started and of every step (a replayed step carries occurredAt). NOT just stage_started. */
  startedAt: string | null
  stageStartedAt: string | null
  endedAt: string | null
  /** How many sub-questions began before the evidence stage ended. */
  overlapped: number
  newest: FactSq | null
  /** The step id of the last known step event in seq order. */
  lastStep: FactStepId | null
}

export function factModel(input: WorkflowEvent[]): FactModel {
  const events = mergeBySeq(input)
  const started = events.find(e => e.event === 'stage_started' && e.stage === 'factcheck')
  const closed = events.find(e => e.event === 'stage_completed' && e.stage === 'factcheck')
  const runFailed = events.find(e => e.event === 'run_failed' && e.stage === 'factcheck')
  const failed = !!runFailed || (!!closed && (closed.status === 'failed' || str(closed.data?.error) != null))
  const hasStage = !!started || !!closed || !!runFailed
  const stage: FactModel['stage'] = !hasStage ? null : failed ? 'failed' : closed ? 'completed' : 'running'

  const sumDone = events.find(e => e.event === 'stage_completed' && e.stage === 'summarizer')
  const boundary = toMs(sumDone?.timestamp) ?? toMs(started?.timestamp)

  type Acc = { sq: FactSq; maxRank: number; firstMs: number | null; lastMs: number | null }
  const by = new Map<number, Acc>()
  let store = null as FactStore | null
  let lastStep = null as FactStepId | null
  let total: number | null = null
  const times: number[] = []
  const stepEvs = events.filter(e => e.event === 'step' && e.data?.lane === 'factcheck' && isFactStep(e.data.step))
  for (const e of stepEvs) {
    const step = e.data.step as FactStepId
    const t = eventMs(e)
    if (t != null) times.push(t)
    lastStep = step
    const tot = posInt(e.data.subQuestions)
    if (tot != null && (total == null || tot > total)) total = tot
    if (step === 'store') {
      store = { state: str(e.data.state) ?? store?.state ?? null, claims: isNum(e.data.claims) ? e.data.claims : store?.claims ?? null, disagreements: isNum(e.data.disagreements) ? e.data.disagreements : store?.disagreements ?? null, at: eventIso(e) }
      continue
    }
    const idx = posInt(e.data.subQuestion) ?? 0
    let a = by.get(idx)
    if (!a) { a = { sq: { index: idx, status: 'running', reported: [], active: [], sources: null, claims: null, clusters: null, firstAt: null, lastAt: null, early: false, lastSeq: -Infinity, totalSeen: null }, maxRank: -1, firstMs: null, lastMs: null }; by.set(idx, a) }
    const sq = a.sq
    if (!sq.reported.includes(step)) sq.reported.push(step)
    a.maxRank = Math.max(a.maxRank, FACT_RANK[step])
    sq.lastSeq = Math.max(sq.lastSeq, e.seq)
    sq.totalSeen = tot ?? sq.totalSeen
    if (isNum(e.data.sources)) sq.sources = e.data.sources
    if (isNum(e.data.claims)) sq.claims = e.data.claims
    if (isNum(e.data.clusters)) sq.clusters = e.data.clusters
    if (t != null) { a.firstMs = a.firstMs == null ? t : Math.min(a.firstMs, t); a.lastMs = a.lastMs == null ? t : Math.max(a.lastMs, t) }
  }
  const closedTotal = posInt(closed?.data?.subQuestions)
  if (closedTotal != null && (total == null || closedTotal > total)) total = closedTotal

  const accs = [...by.values()].sort((x, y) => x.sq.index - y.sq.index)
  const ended = !!closed || !!runFailed
  const storeAll = store != null && store.state !== 'failed'            // everything was checked once the node is saving
  for (const a of accs) {
    const sq = a.sq
    sq.reported.sort((x, y) => FACT_RANK[x] - FACT_RANK[y])
    sq.firstAt = a.firstMs == null ? null : new Date(a.firstMs).toISOString()
    sq.lastAt = a.lastMs == null ? null : new Date(a.lastMs).toISOString()
    sq.early = boundary != null && a.firstMs != null && a.firstMs < boundary
    // A step reports only when it starts, so "finished" is inferred: the stage is saving or over, or the sub-question reached the last group of
    // steps and another sub-question has reported after it. A sub-question that has not reached the last group keeps its step running.
    const later = accs.some(o => o !== a && o.sq.lastSeq > sq.lastSeq)
    const finished = storeAll || (stage === 'completed') || (a.maxRank >= FACT_RANK.near && later)
    sq.status = finished ? 'done' : stage === 'failed' || store?.state === 'failed' ? 'failed' : 'running'
    sq.active = sq.status === 'done' ? [] : sq.reported.filter(s => FACT_RANK[s] === a.maxRank)
  }

  const maxIdx = accs.reduce((m, a) => Math.max(m, a.sq.index), 0)
  const n = Math.max(total ?? 0, maxIdx)
  const sqs: FactSq[] = []
  if (by.has(0)) sqs.push(by.get(0)!.sq)
  for (let i = 1; i <= n; i++) {
    sqs.push(by.get(i)?.sq ?? {
      index: i, status: ended ? 'not_reported' : 'waiting', reported: [], active: [], sources: null, claims: null, clusters: null,
      firstAt: null, lastAt: null, early: false, lastSeq: -Infinity, totalSeen: null,
    })
  }
  const real = [toMs(started?.timestamp), ...times].filter((x): x is number => x != null)
  const newest = accs.reduce<FactSq | null>((best, a) => (best == null || a.sq.lastSeq > best.lastSeq ? a.sq : best), null)
  return {
    hasStage, stage, total: total ?? (n > 0 ? n : null), sqs, hasNear: stepEvs.some(e => e.data.step === 'near'), store,
    startedAt: real.length ? new Date(Math.min(...real)).toISOString() : null,
    stageStartedAt: started?.timestamp ?? null,
    endedAt: (closed ?? runFailed)?.timestamp ?? null,
    overlapped: accs.filter(a => a.sq.early).length, newest, lastStep,
  }
}

// ------------------------------------------------------------------------------------------------------------------------ duration of a stage
/** When a stage's work started. For the fact check this is the earliest real time of its steps, not stage_started (its first sub-questions were
 *  checked during Stage 3 and are replayed when the stage starts). */
export function stageStartedAt(events: WorkflowEvent[], stage: string): string | null {
  if (stage === 'factcheck') {
    const m = factModel(events)
    if (m.startedAt) return m.startedAt
  }
  return events.find(e => e.event === 'stage_started' && e.stage === stage)?.timestamp ?? null
}

// ------------------------------------------------------------------------------------------------------------------------ PDF parsing
/** The parsing step reports {target, attempted, usable} only when it starts and again when a long round ends, so for minutes the parsed count is 0 although
 *  the parser is busy. While it runs and nothing has been attempted yet this says what it is doing instead; otherwise null (the real counts are shown). */
export function parsingNote(input: WorkflowEvent[]): string | null {
  const events = mergeBySeq(input)
  const evs = stepEvents(events, 'papers', 'parsing')
  if (evs.length === 0 || events.some(e => e.event === 'run_failed')) return null
  const last = evs[evs.length - 1]
  if (last.data.state !== 'running') return null
  const d = mergedData(evs)
  if (isNum(d.attempted) && d.attempted > 0) return null
  if (isNum(d.usable) && d.usable > 0) return null
  const target = isNum(d.target) && d.target > 0 ? Math.floor(d.target) : null
  return target != null ? `parsing up to ${target} paper${target === 1 ? '' : 's'}…` : 'parsing papers…'
}

// ------------------------------------------------------------------------------------------------------------------------ token usage
/** What each Groq purpose is called on screen. The keys are open strings: an unknown one is shown as it is. stage4_judge is the single purpose of older runs. */
export const PURPOSE_LABEL: Record<string, string> = {
  digest: 'Reading the sources (digests)',
  digest_loop2: 'Reading the sources of the second search',
  aspect_split: 'Splitting the questions into aspects',
  query_expansion: 'Writing search queries',
  stage4_merge: 'Fact check: grouping the claims',
  stage4_support: 'Fact check: checking the quotes',
  stage4_near: 'Fact check: looking for close variants',
  stage4_conflict: 'Fact check: looking for disagreements',
  stage4_judge: 'Fact check: judge (older runs)',
}

export const purposeLabel = (key: string): string => (hasOwn(PURPOSE_LABEL, key) ? PURPOSE_LABEL[key] : key)

export type TokenRow = { key: string; label: string; tokens: number; share: number }
export type TokenUsage = { total: number | null; calls: number | null; rows: TokenRow[] }

/** The Groq tokens the finished run used, by purpose, largest first. null when the run did not report them (every run before this was added). */
export function tokenUsage(events: WorkflowEvent[]): TokenUsage | null {
  const done = [...events].reverse().find(e => e.event === 'run_completed')
  if (!done) return null
  const total = isNum(done.data?.groqTokens) ? done.data.groqTokens : null
  const calls = isNum(done.data?.groqCalls) ? done.data.groqCalls : null
  const raw = done.data?.groqTokensByPurpose
  const entries = raw && typeof raw === 'object' && !Array.isArray(raw) ? Object.entries(raw as Record<string, unknown>).filter((x): x is [string, number] => isNum(x[1]) && x[1] >= 0) : []
  if (total == null && entries.length === 0) return null
  const sum = entries.reduce((s, [, v]) => s + v, 0)
  const rows = entries.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([key, tokens]) => ({ key, label: purposeLabel(key), tokens, share: sum > 0 ? tokens / sum : 0 }))
  return { total: total ?? (entries.length ? sum : null), calls, rows }
}

export const tokensLabel = (n: number): string => (n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 10_000 ? `${Math.round(n / 1000)}k` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n))
