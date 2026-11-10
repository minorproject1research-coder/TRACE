import { ladderLabel } from './loop2'
import { eventMs, factModel, judgeModel, loop2Model, loop2RungResults, loop2Tip, mergeBySeq, notesOf, toMs, type FactDone, type FactSq } from './stream'
import type { WorkflowEvent } from './trace-types'

// Pure derivations for the per-sub-question views of the Timeline: the swimlane matrix (T1), the Gantt of Stages 3 and 4 (T2) and the Stage 4 worker
// view (T3). Everything comes from the events; a missing field gives an empty cell, never an error. The number of sub-questions and of workers is read
// from the data, never fixed.

export type CellState = 'none' | 'waiting' | 'active' | 'done' | 'failed'
export type CellTone = 'neutral' | 'blue' | 'mint' | 'amber'
export type Cell = { state: CellState; text: string; tone: CellTone }
export type SwimRow = { index: number; topic: string | null; judge: Cell; second: Cell; fact: Cell }

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
const cell = (state: CellState, text: string, tone: CellTone = 'neutral'): Cell => ({ state, text, tone })

/** Did the server send the parallel-pipeline fields? Without them the per-sub-question views stay hidden and the Timeline looks as before. */
export function isParallelRun(events: WorkflowEvent[]): boolean {
  const ev = mergeBySeq(events)
  return judgeModel(ev).indexed || factModel(ev).hasNear || factModel(ev).hasDone
}

/** The sub-question topics the planner announced (stage_completed data.topics), as plain strings. */
export function plannedTopics(events: WorkflowEvent[]): string[] {
  const done = events.find(e => e.event === 'stage_completed' && e.stage === 'planner')
  const t = done?.data?.topics
  return Array.isArray(t) ? t.map(x => (typeof x === 'string' ? x : '')) : []
}

/** "3 supported · 1 partly supported · 2 not yet confirmed": only the labels that are not 0. Never a word of truth. */
export function factCountsText(d: FactDone | null): string | null {
  if (!d) return null
  const parts: string[] = []
  if (d.supported) parts.push(`${d.supported} supported`)
  if (d.partially_supported) parts.push(`${d.partially_supported} partly supported`)
  if (d.unverified) parts.push(`${d.unverified} not yet confirmed`)
  if (d.contradicted) parts.push(`${d.contradicted} contradicted`)
  if (parts.length) return parts.join(' · ')
  return d.claims != null ? plural(d.claims, 'claim', 'claims') : null
}

/** The matrix: one row per sub-question, three columns. */
export function swimlanes(input: WorkflowEvent[], fallbackTopics: string[] = []): SwimRow[] {
  const events = mergeBySeq(input)
  const jm = judgeModel(events), lm = loop2Model(events), fm = factModel(events)
  const notes = notesOf(events)
  const topics = plannedTopics(events).length ? plannedTopics(events) : fallbackTopics
  const plannedN = events.find(e => e.event === 'stage_completed' && e.stage === 'planner')?.data?.subQuestions
  const n = Math.max(jm.total ?? 0, fm.total ?? 0, topics.length, typeof plannedN === 'number' ? plannedN : 0, ...lm.sqs.map(s => s.index), ...fm.sqs.map(s => s.index))
  const rows: SwimRow[] = []
  for (let i = 1; i <= n; i++) {
    const j = jm.sqs.find(s => s.index === i)
    const judge = !j || j.phase === 'waiting' ? cell('waiting', 'waiting')
      : j.phase === 'active' ? cell('active', 'judging', 'blue')
        : j.sufficient === true ? cell('done', 'done · enough evidence', 'mint') : j.sufficient === false ? cell('done', 'done · not enough evidence', 'amber') : cell('done', 'done')
    const l = lm.sqs.find(s => s.index === i)
    const gaps = notes.find(x => x.code === 'loop2_gaps' && x.subQuestionIndex === i)?.data.gaps
    const second = l
      ? (l.done ? cell('done', `done · searched ${plural(l.searched ?? 0, 'aspect', 'aspects')}, ${l.covered ?? 0} covered${typeof gaps === 'number' && gaps > 0 ? ` · ${gaps} still without evidence` : ''}`, 'neutral')
        : cell('active', l.rung ? `now: ${ladderLabel(l.rung)}` : 'second search started', 'blue'))
      : judge.state === 'done' ? cell('none', 'not needed') : cell('waiting', 'waiting')
    const f = fm.sqs.find(s => s.index === i)
    const fact = !f || f.status === 'waiting' ? cell('waiting', 'waiting')
      : f.status === 'running' ? cell('active', `checking${f.worker != null ? ` · worker ${f.worker}` : ''}`, 'blue')
        : f.status === 'done' ? cell('done', ['checked', factCountsText(f.done)].filter(Boolean).join(' · '), 'neutral')
          : f.status === 'failed' ? cell('failed', 'stopped', 'amber') : cell('none', 'no result')
    rows.push({ index: i, topic: topics[i - 1] || null, judge, second, fact })
  }
  return rows
}

// ------------------------------------------------------------------------------------------------------------------------ T2: the Gantt of Stages 3 and 4
export type BarKind = 'judge' | 'second' | 'fact'
export type GanttBar = { kind: BarKind; fromMs: number; toMs: number; open: boolean; worker?: number | null; /** A tooltip: for the second search, the queries asked and the result of each finished rung. */ tip?: string }
export type GanttLane = { index: number; topic: string | null; bars: GanttBar[]; wait: { fromMs: number; toMs: number } | null }
export type StageGantt = {
  fromMs: number
  toMs: number
  lanes: GanttLane[]
  /** Where the evidence stage ended (its stage_completed), for the vertical marker. */
  stage3EndMs: number | null
  /** The sub-question whose judge ended last, and the one whose fact check ended last. */
  critical: { evidence: number | null; run: number | null }
  running: boolean
}

/** The bars of every sub-question on one time axis. null unless the stream carries the per-sub-question fields and at least one bar exists. */
export function stageGantt(input: WorkflowEvent[], nowMs: number, fallbackTopics: string[] = []): StageGantt | null {
  const events = mergeBySeq(input)
  if (!isParallelRun(events)) return null
  const jm = judgeModel(events), lm = loop2Model(events), fm = factModel(events)
  const rungResults = loop2RungResults(events)
  const topics = plannedTopics(events).length ? plannedTopics(events) : fallbackTopics
  const runEnd = events.find(e => e.event === 'run_completed' || e.event === 'run_failed')
  const running = !runEnd
  const lastMs = Math.max(0, ...events.map(e => eventMs(e) ?? 0))
  const edge = running ? Math.max(nowMs, lastMs) : (eventMs(runEnd!) ?? lastMs)
  const sumStart = toMs(events.find(e => e.event === 'stage_started' && e.stage === 'summarizer')?.timestamp)
  const sumEnd = toMs(events.find(e => e.event === 'stage_completed' && e.stage === 'summarizer')?.timestamp)
  const lanes: GanttLane[] = []
  let evidence: { i: number; t: number } | null = null, run: { i: number; t: number } | null = null
  const n = Math.max(jm.total ?? 0, fm.total ?? 0, topics.length, ...fm.sqs.map(s => s.index), ...lm.sqs.map(s => s.index))
  for (let i = 1; i <= n; i++) {
    const bars: GanttBar[] = []
    const j = jm.sqs.find(s => s.index === i), l = lm.sqs.find(s => s.index === i), f = fm.sqs.find(s => s.index === i)
    const ms = (iso: string | null) => toMs(iso)
    let judgeEnd: number | null = null, factStart: number | null = null
    if (j && ms(j.startedAt) != null) {
      const open = j.phase !== 'done'
      judgeEnd = j.phase === 'done' ? ms(j.endedAt) : null
      bars.push({ kind: 'judge', fromMs: ms(j.startedAt)!, toMs: judgeEnd ?? edge, open: open && running })
      if (judgeEnd != null && (!evidence || judgeEnd > evidence.t) && (sumEnd == null || judgeEnd <= sumEnd + 1)) evidence = { i, t: judgeEnd }
    }
    if (l && ms(l.startedAt) != null) bars.push({ kind: 'second', fromMs: ms(l.startedAt)!, toMs: l.done ? (ms(l.endedAt) ?? edge) : edge, open: !l.done && running, ...(loop2Tip(rungResults, i) ? { tip: loop2Tip(rungResults, i)! } : {}) })
    if (f && ms(f.firstAt) != null) {
      factStart = ms(f.firstAt)
      const end = ms(f.doneAt) ?? (f.status === 'done' ? ms(f.lastAt) : null)
      bars.push({ kind: 'fact', fromMs: factStart!, toMs: end ?? edge, open: end == null && running, worker: f.worker })
      if (end != null && (!run || end > run.t)) run = { i, t: end }
    }
    const wait = judgeEnd != null && factStart != null && factStart > judgeEnd ? { fromMs: judgeEnd, toMs: factStart } : null
    if (bars.length) lanes.push({ index: i, topic: topics[i - 1] || null, bars, wait })
  }
  if (lanes.length === 0) return null
  const all = lanes.flatMap(l => l.bars)
  const fromMs = Math.min(sumStart ?? Infinity, ...all.map(b => b.fromMs))
  const axisEnd = Math.max(...all.map(b => b.toMs), runEnd ? edge : 0)
  return {
    fromMs, toMs: Math.max(axisEnd, fromMs + 1000), lanes, stage3EndMs: sumEnd, running,
    // the evidence stage ends with its last judge only once it has ended; "the run ended when ..." only once the fact check is over
    critical: { evidence: sumEnd != null ? (evidence?.i ?? null) : null, run: events.some(e => e.event === 'stage_completed' && e.stage === 'factcheck') ? (run?.i ?? null) : null },
  }
}

export function criticalPathText(g: StageGantt): string[] {
  const out: string[] = []
  if (g.critical.evidence != null) out.push(`The evidence stage ended when sub-question ${g.critical.evidence} finished judging.`)
  if (g.critical.run != null) out.push(`The run ended when sub-question ${g.critical.run} finished fact checking.`)
  return out
}

// ------------------------------------------------------------------------------------------------------------------------ T3: the Stage 4 workers
export type WorkerRow = {
  index: number
  topic: string | null
  /** When it joined the queue: the end of its judge. */
  queuedAt: string | null
  startedAt: string | null
  /** The real time of its done event. Without done events (an older server) it is null: the end is not guessed. */
  finishedAt: string | null
  waitedMs: number | null
  tookMs: number | null
  worker: number | null
  status: FactSq['status']
  counts: string | null
}

export type WorkerView = {
  rows: WorkerRow[]
  /** The largest worker number in the data; 0 hides the worker column and the lanes. */
  workers: number
  /** Finished sub-questions come from done events (true) or are inferred from the next sub-question starting (false). */
  usesDone: boolean
  lanes: { worker: number; items: { index: number; fromMs: number; toMs: number; open: boolean }[] }[]
  fromMs: number | null
  toMs: number | null
}

export function workerView(input: WorkflowEvent[], nowMs: number, fallbackTopics: string[] = []): WorkerView | null {
  const events = mergeBySeq(input)
  const fm = factModel(events), jm = judgeModel(events)
  const topics = plannedTopics(events).length ? plannedTopics(events) : fallbackTopics
  const rows: WorkerRow[] = []
  for (const f of fm.sqs) {
    if (f.index < 1) continue
    const j = jm.sqs.find(s => s.index === f.index)
    const queued = j && j.phase === 'done' ? j.endedAt : null
    if (!f.firstAt && !queued) continue
    const started = f.firstAt, finished = f.doneAt
    const waited = queued && started ? Math.max(0, toMs(started)! - toMs(queued)!) : null
    const took = started && finished ? Math.max(0, toMs(finished)! - toMs(started)!) : null
    rows.push({ index: f.index, topic: topics[f.index - 1] || null, queuedAt: queued, startedAt: started, finishedAt: finished, waitedMs: waited, tookMs: took, worker: f.worker, status: f.status, counts: factCountsText(f.done) })
  }
  if (rows.length === 0) return null
  rows.sort((a, b) => (toMs(a.queuedAt ?? a.startedAt) ?? 0) - (toMs(b.queuedAt ?? b.startedAt) ?? 0) || a.index - b.index)
  const lanes: WorkerView['lanes'] = []
  for (let w = 1; w <= fm.workers; w++) {
    const items = rows.filter(r => r.worker === w && r.startedAt).map(r => {
      const open = r.finishedAt == null && r.status === 'running'
      return { index: r.index, fromMs: toMs(r.startedAt)!, toMs: r.finishedAt ? toMs(r.finishedAt)! : open ? Math.max(nowMs, toMs(r.startedAt)!) : toMs(r.startedAt)!, open }
    })
    lanes.push({ worker: w, items })
  }
  const stamps = lanes.flatMap(l => l.items.flatMap(i => [i.fromMs, i.toMs]))
  return { rows, workers: fm.workers, usesDone: fm.hasDone, lanes, fromMs: stamps.length ? Math.min(...stamps) : null, toMs: stamps.length ? Math.max(...stamps) : null }
}

/** "2 min 5 s" for a duration in ms; null stays null (nothing is invented). */
export function msLabel(ms: number | null): string | null {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return null
  const s = Math.round(ms / 1000)
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`
}
