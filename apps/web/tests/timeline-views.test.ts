// Run with:  pnpm test. The per-sub-question views and the measurements of the Timeline: swimlanes, Gantt, workers, time shares, ETA, event filters,
// per-paper parsing, Groq per stage, cache chips and notes. Pure logic only.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { demoEvents } from '../lib/demo-api'
import { estimateTimeLeft, etaText } from '../lib/eta'
import { eventSubQuestion, filterRows, isWarning, logOptions, NO_FILTER, searchIndex, eventsJson } from '../lib/event-log'
import { cacheInfo, factModel, groqByPurpose, groqByStage, groqOf, groqTotal, notesOf, paperParseModel, tokenUsage } from '../lib/stream'
import { criticalPathText, factCountsText, isParallelRun, msLabel, stageGantt, swimlanes, workerView } from '../lib/swimlanes'
import { cacheChips, groqLine, noteView, slowerHint, stageExtras, timeShares, TYPICAL_NOTE, TYPICAL_SECONDS } from '../lib/telemetry'
import type { EventName, StageId, WorkflowEvent } from '../lib/trace-types'

const T0 = Date.parse('2026-11-10T10:00:00Z')
let seq = 0
const iso = (sec: number) => new Date(T0 + sec * 1000).toISOString()
function ev(event: EventName, stage: StageId | null, data: Record<string, unknown> = {}, sec = seq, message = '', occ?: number): WorkflowEvent {
  return { seq: seq++, event, stage, status: null, message, data: { ...data, ...(occ != null ? { occurredAt: iso(occ) } : {}) }, timestamp: iso(sec) }
}
const step = (lane: string, id: string, state: string, data: Record<string, unknown>, sec: number, occ?: number) =>
  ev('step', lane === 'papers' ? 'retrieval' : (lane as StageId), { lane, step: id, state, ...data }, sec, '', occ)
const reset = () => { seq = 0 }
const sqs = { subQuestions: 3 }

// ------------------------------------------------------------------------------------------------------------------------ T1 swimlanes
test('swimlane cells: waiting, judging, done with the verdict; second search: not needed, current rung, done; fact check: checking with its worker, done with the counts', () => {
  reset()
  const events = [
    ev('stage_completed', 'planner', { subQuestions: 3, topics: ['A?', 'B?', 'C?'] }, 1),
    step('summarizer', 'digest', 'completed', { done: 3, total: 3 }, 5),
    step('summarizer', 'judge', 'running', { subQuestionIndex: 1, ...sqs, done: 0, total: 3 }, 6, 4),
    step('summarizer', 'judge', 'running', { subQuestionIndex: 2, ...sqs, done: 0, total: 3 }, 6, 4.5),
    step('summarizer', 'judge', 'running', { subQuestionIndex: 1, ...sqs, done: 1, total: 3, sufficient: true }, 7, 5),
    step('summarizer', 'loop2', 'running', { subQuestionIndex: 2, ...sqs, loop2Step: 'pool', aspects: 2 }, 8),
    step('factcheck', 'claims', 'running', { subQuestion: 1, subQuestions: 3, worker: 2 }, 9),
  ]
  const rows = swimlanes(events)
  assert.equal(rows.length, 3); assert.deepEqual(rows.map(r => r.topic), ['A?', 'B?', 'C?'])
  assert.deepEqual([rows[0].judge.text, rows[1].judge.text, rows[2].judge.text], ['done · enough evidence', 'judging', 'waiting'])
  assert.deepEqual([rows[0].second.text, rows[1].second.text, rows[2].second.text], ['not needed', 'now: reading more papers from the search results', 'waiting'])
  assert.equal(rows[0].fact.text, 'checking · worker 2'); assert.equal(rows[1].fact.text, 'waiting')
  events.push(step('factcheck', 'done', 'running', { subQuestion: 1, subQuestions: 3, worker: 2, claims: 6, supported: 3, partially_supported: 1, unverified: 2, contradicted: 0 }, 12))
  assert.equal(swimlanes(events)[0].fact.text, 'checked · 3 supported · 1 partly supported · 2 not yet confirmed')
  assert.equal(factCountsText(null), null); assert.equal(factCountsText({ claims: 4 } as never), '4 claims')
  events.push(step('summarizer', 'loop2', 'running', { subQuestionIndex: 2, ...sqs, searched: 2, covered: 1 }, 13))
  assert.equal(swimlanes(events)[1].second.text, 'done · searched 2 aspects, 1 covered')
})

test('the per-sub-question views stay hidden for a stream without the parallel fields', () => {
  assert.equal(isParallelRun(demoEvents({ fact: 'on', old: true })), false)
  assert.equal(stageGantt(demoEvents({ fact: 'on', old: true }), T0), null)
  assert.equal(isParallelRun(demoEvents({ fact: 'on' })), true)
})

// ------------------------------------------------------------------------------------------------------------------------ T2 Gantt and critical path
test('the Gantt: a bar per stage of every sub-question, the wait for a worker, the evidence-stage marker and the critical path', () => {
  reset()
  const events = [
    ev('stage_started', 'summarizer', {}, 0),
    step('summarizer', 'digest', 'completed', { done: 2, total: 2 }, 5),
    step('summarizer', 'judge', 'running', { subQuestionIndex: 1, subQuestions: 2, done: 0, total: 2 }, 6, 1),
    step('summarizer', 'judge', 'running', { subQuestionIndex: 1, subQuestions: 2, done: 1, total: 2, sufficient: true }, 6, 4),
    step('summarizer', 'judge', 'running', { subQuestionIndex: 2, subQuestions: 2, done: 1, total: 2 }, 6, 2),
    step('summarizer', 'loop2', 'running', { subQuestionIndex: 2, subQuestions: 2, loop2Step: 'queries', aspects: 1 }, 6, 3),
    step('summarizer', 'loop2', 'running', { subQuestionIndex: 2, subQuestions: 2, searched: 1, covered: 0 }, 6, 8),
    step('summarizer', 'judge', 'running', { subQuestionIndex: 2, subQuestions: 2, done: 2, total: 2, sufficient: false }, 6, 9),
    ev('stage_completed', 'summarizer', {}, 10),
    ev('stage_started', 'factcheck', {}, 10),
    step('factcheck', 'claims', 'running', { subQuestion: 1, subQuestions: 2, worker: 1 }, 10, 6),         // waited 2 s for a free worker
    step('factcheck', 'near', 'running', { subQuestion: 1, subQuestions: 2 }, 10, 7),
    step('factcheck', 'done', 'running', { subQuestion: 1, subQuestions: 2, worker: 1, claims: 2 }, 10, 12),
    step('factcheck', 'claims', 'running', { subQuestion: 2, subQuestions: 2, worker: 2 }, 13),
    step('factcheck', 'done', 'running', { subQuestion: 2, subQuestions: 2, worker: 2, claims: 1 }, 15),
    ev('stage_completed', 'factcheck', { subQuestions: 2 }, 16),
    ev('run_completed', null, {}, 17),
  ]
  const g = stageGantt(events, T0 + 99_000)!
  const lane = (i: number) => g.lanes.find(l => l.index === i)!
  const sec = (ms: number) => (ms - T0) / 1000
  assert.deepEqual(lane(1).bars.map(b => [b.kind, sec(b.fromMs), sec(b.toMs)]), [['judge', 1, 4], ['fact', 6, 12]])
  assert.deepEqual(lane(2).bars.map(b => [b.kind, sec(b.fromMs), sec(b.toMs)]), [['judge', 2, 9], ['second', 3, 8], ['fact', 13, 15]])
  assert.deepEqual([sec(lane(1).wait!.fromMs), sec(lane(1).wait!.toMs)], [4, 6], 'hatched between the end of the judge and the start of the fact check')
  assert.equal(sec(g.stage3EndMs!), 10, 'the marker where the evidence stage ended')
  assert.deepEqual(g.critical, { evidence: 2, run: 2 })
  assert.deepEqual(criticalPathText(g), ['The evidence stage ended when sub-question 2 finished judging.', 'The run ended when sub-question 2 finished fact checking.'])
  assert.equal(g.running, false); assert.ok(g.toMs <= T0 + 17_000 + 1, 'the axis ends with the run, not with now')
})

test('the Gantt of a run in progress ends at now and has no critical path yet', () => {
  reset()
  const events = [
    ev('stage_started', 'summarizer', {}, 0), step('summarizer', 'digest', 'completed', { done: 1, total: 1 }, 3),
    step('summarizer', 'judge', 'running', { subQuestionIndex: 1, subQuestions: 1, done: 0, total: 1 }, 4, 2),
  ]
  const g = stageGantt(events, T0 + 20_000)!
  assert.equal(g.running, true); assert.equal(g.lanes[0].bars[0].open, true); assert.equal(g.toMs, T0 + 20_000)
  assert.deepEqual(g.critical, { evidence: null, run: null }); assert.deepEqual(criticalPathText(g), [])
})

// ------------------------------------------------------------------------------------------------------------------------ T3 workers
test('the worker table: queued, started, finished, waited, took and worker, from done events and the data (never a fixed number of workers)', () => {
  const all = demoEvents({ fact: 'on' })
  const v = workerView(all, T0)!
  assert.equal(v.workers, 2); assert.equal(v.usesDone, true)
  assert.equal(v.lanes.length, 2); assert.ok(v.lanes.every(l => l.items.length > 0))
  const r4 = v.rows.find(r => r.index === 4)!
  assert.ok(r4.queuedAt && r4.startedAt && r4.finishedAt && r4.tookMs! > 0 && r4.waitedMs! >= 0 && r4.worker === 2)
  assert.ok(r4.counts && /supported|not yet confirmed/.test(r4.counts))
  // three workers in the data: three lanes
  reset()
  const three = [ev('stage_started', 'factcheck', {}, 0), ...[1, 2, 3].flatMap(i => [
    step('factcheck', 'claims', 'running', { subQuestion: i, subQuestions: 3, worker: i }, i), step('factcheck', 'done', 'running', { subQuestion: i, subQuestions: 3, worker: i }, i + 5)])]
  assert.equal(workerView(three, T0)!.workers, 3); assert.equal(workerView(three, T0)!.lanes.length, 3)
})

test('without done or worker fields (an older stream) the end is not guessed and the worker column is hidden', () => {
  reset()
  const events = [ev('stage_started', 'factcheck', {}, 0), step('factcheck', 'claims', 'running', { subQuestion: 1, subQuestions: 2 }, 1), step('factcheck', 'near', 'running', { subQuestion: 1, subQuestions: 2 }, 2),
    step('factcheck', 'claims', 'running', { subQuestion: 2, subQuestions: 2 }, 3)]
  const v = workerView(events, T0)!
  assert.equal(v.workers, 0); assert.equal(v.usesDone, false); assert.deepEqual(v.lanes, [])
  assert.equal(v.rows[0].finishedAt, null); assert.equal(v.rows[0].tookMs, null)
  assert.equal(factModel(events).sqs[0].status, 'done', 'the old inference still says it moved on')
})

test('a done event finishes a sub-question even when another one started after it, and not before it', () => {
  reset()
  const events = [ev('stage_started', 'factcheck', {}, 0),
    step('factcheck', 'claims', 'running', { subQuestion: 1, subQuestions: 2, worker: 1 }, 1), step('factcheck', 'near', 'running', { subQuestion: 1, subQuestions: 2 }, 2),
    step('factcheck', 'claims', 'running', { subQuestion: 2, subQuestions: 2, worker: 2 }, 3)]
  assert.equal(factModel(events).sqs[0].status, 'done', 'a stream without done events: the old inference, sub-question 2 started so 1 moved on')
  events.push(step('factcheck', 'done', 'running', { subQuestion: 2, subQuestions: 2, worker: 2 }, 4))
  const m2 = factModel(events)
  assert.equal(m2.hasDone, true); assert.deepEqual(m2.sqs.map(s => s.status), ['running', 'done'], 'with done events, sub-question 2 starting does not finish sub-question 1: only its own done event does')
  assert.equal(msLabel(65_000), '1 min 5 s'); assert.equal(msLabel(null), null)
})

// ------------------------------------------------------------------------------------------------------------------------ T4 time shares
test('time shares: percentages of the run, the part of Stage 4 that overlapped hatched, and "slower" only above 1.3 times the typical high end', () => {
  reset()
  const events = [
    ev('run_started', null, {}, 0), ev('stage_started', 'planner', {}, 0), ev('stage_completed', 'planner', {}, 60),                      // 60 s: not slower (limit 71.5 s)
    ev('stage_started', 'retrieval', {}, 60), step('papers', 'parsing', 'running', { target: 10, attempted: 0 }, 360), ev('stage_completed', 'retrieval', {}, 660),
    ev('stage_started', 'summarizer', {}, 660), ev('stage_completed', 'summarizer', {}, 1100),
    ev('stage_started', 'factcheck', {}, 1100), step('factcheck', 'claims', 'running', { subQuestion: 1, subQuestions: 1 }, 1100, 900),
    ev('stage_completed', 'factcheck', {}, 1460), ev('run_completed', null, {}, 1460),
  ]
  const t = timeShares(events, T0 + 2000_000)!
  assert.deepEqual(t.segs.map(s => [s.id, Math.round(s.share * 100)]), [['planner', 4], ['search', 21], ['parsing', 21], ['evidence', 30], ['stage4After', 25]])
  assert.ok(Math.abs(t.segs.reduce((n, s) => n + s.share, 0) - 1) < 1e-9, 'the shares add up to the whole')
  assert.equal(t.overlap!.ms, 200_000, 'Stage 4 began at 900 s, 200 s before the evidence stage ended')
  assert.ok(Math.abs(t.overlap!.shareOfEvidence - 200 / 440) < 1e-9)
  const hint = (id: string) => t.phases.find(p => p.id === id)!
  assert.equal(hint('planner').slower, false); assert.equal(slowerHint(hint('planner')), null)
  assert.equal(hint('retrieval').slower, false, '600 s against a typical high end of 510 s x 1.3 = 663 s: not slower')
})

test('the slower hint: above 1.3 times the high end of the typical range, labelled as measured on two runs', () => {
  reset()
  const mk = (plannerSec: number) => [ev('run_started', null, {}, 0), ev('stage_started', 'planner', {}, 0), ev('stage_completed', 'planner', {}, plannerSec)]
  const planner = (s: number) => timeShares(mk(s), T0 + 1e9)!.phases[0]
  assert.equal(planner(71).slower, false); assert.equal(planner(72).slower, true)
  assert.match(slowerHint(planner(100))!, /slower than the two measured runs/); assert.match(slowerHint(planner(100))!, new RegExp(TYPICAL_NOTE))
  assert.deepEqual(TYPICAL_SECONDS.planner, [40, 55]); assert.deepEqual(TYPICAL_SECONDS.retrieval, [360, 510]); assert.deepEqual(TYPICAL_SECONDS.evidence, [270, 420]); assert.deepEqual(TYPICAL_SECONDS.stage4After, [360, 480])
  assert.equal(timeShares([], T0), null)
})

// ------------------------------------------------------------------------------------------------------------------------ T5 ETA
test('ETA text: whole minutes, a range when unsure, never below 0, nothing when it rounds to 0', () => {
  assert.equal(etaText(300, 330), 'about 6 min left (estimate)')
  assert.equal(etaText(180, 540), 'about 3 to 9 min left (estimate)')
  assert.equal(etaText(-50, 20), 'about 1 min left (estimate)')
  assert.equal(etaText(0, 0), null); assert.equal(etaText(-100, -20), null)
})

test('ETA from real progress: papers parsed out of the target, sub-questions judged, sub-questions fact-checked; hidden with too little data or when the run is over', () => {
  reset()
  const parse = (n: number) => Array.from({ length: n }, (_, k) => step('papers', 'paper_parse', 'completed', { paperId: `p${k}`, outcome: 'parsed' }, 100 + k * 10))
  const retrieval = (n: number) => [ev('stage_started', 'retrieval', {}, 0), step('papers', 'parsing', 'running', { target: 10, attempted: 0 }, 100), ...parse(n)]
  assert.equal(estimateTimeLeft(retrieval(0), T0 + 110_000), null, 'nothing parsed yet: too little to say')
  assert.equal(estimateTimeLeft(retrieval(2), T0 + 130_000), null, 'two papers are not enough')
  const e = estimateTimeLeft(retrieval(5), T0 + 160_000)!
  assert.match(e.text, /^about \d+( to \d+)? min left \(estimate\)$/); assert.match(e.basis, /5 of 10 papers parsed/)
  assert.ok(e.loSec >= 0 && e.hiSec >= e.loSec)
  assert.equal(estimateTimeLeft([...retrieval(5), ev('run_completed', null, {}, 200)], T0 + 300_000), null, 'a finished run has no time left')
  // judging: 2 of 4 sub-questions done after 100 s
  reset()
  const judge = [ev('stage_started', 'summarizer', {}, 0), step('summarizer', 'digest', 'completed', { done: 5, total: 5 }, 10),
    step('summarizer', 'judge', 'running', { subQuestionIndex: 1, subQuestions: 4, done: 0, total: 4 }, 12, 10),
    step('summarizer', 'judge', 'running', { subQuestionIndex: 1, subQuestions: 4, done: 1, total: 4, sufficient: true }, 50, 50),
    step('summarizer', 'judge', 'running', { subQuestionIndex: 2, subQuestions: 4, done: 2, total: 4, sufficient: true }, 110, 110)]
  const j = estimateTimeLeft(judge, T0 + 110_000)!
  assert.match(j.basis, /2 of 4 sub-questions judged/)
  assert.equal(estimateTimeLeft(judge, T0 + 110_000, false)!.hiSec < j.hiSec, true, 'with the fact check switched off nothing is added for it')
  // Stage 4: 2 of 4 sub-questions done, 60 s each, 2 workers: 1 batch of 60 s left
  reset()
  const f = [ev('stage_completed', 'summarizer', {}, 0), ev('stage_started', 'factcheck', {}, 0),
    ...[1, 2].flatMap(i => [step('factcheck', 'claims', 'running', { subQuestion: i, subQuestions: 4, worker: i }, 1), step('factcheck', 'done', 'running', { subQuestion: i, subQuestions: 4, worker: i }, 61)])]
  const s4 = estimateTimeLeft(f, T0 + 70_000)!
  assert.match(s4.basis, /2 of 4 sub-questions fact-checked/); assert.ok(s4.hiSec <= 60 * 1.3 + 1 && s4.loSec >= 60 * 0.7 - 1)
  assert.equal(estimateTimeLeft([ev('stage_completed', 'summarizer', {}, 0), ev('stage_started', 'factcheck', {}, 0), step('factcheck', 'claims', 'running', { subQuestion: 1, subQuestions: 4 }, 1)], T0 + 5000), null, 'no sub-question finished yet')
})

// ------------------------------------------------------------------------------------------------------------------------ T6 event filters
test('event filters: stage, lane, sub-question, type, warnings only and text, on 400 events, quickly', () => {
  reset()
  const big: WorkflowEvent[] = []
  for (let i = 0; i < 400; i++) {
    big.push(i % 4 === 0 ? step('summarizer', 'judge', 'running', { subQuestionIndex: (i % 5) + 1, subQuestions: 5, done: 0, total: 5 }, i)
      : i % 4 === 1 ? step('factcheck', 'claims', 'running', { subQuestion: (i % 5) + 1, subQuestions: 5 }, i)
        : i % 4 === 2 ? step('notes', i % 8 === 2 ? 'parse_summary' : 'plan_cache', 'completed', { level: i % 8 === 2 ? 'warn' : 'info', stage: 'retrieval' }, i)
          : step('papers', 'paper_parse', 'completed', { paperId: `p${i}`, title: `Paper number ${i}`, outcome: 'parsed' }, i))
  }
  big.push(ev('run_failed', 'summarizer', {}, 401, 'RuntimeError: boom'))
  const rows = searchIndex(big)
  assert.equal(rows.length, 401)
  const t0 = performance.now()
  for (let k = 0; k < 20; k++) filterRows(rows, { ...NO_FILTER, text: 'paper number 3' })
  assert.ok(performance.now() - t0 < 500, 'twenty searches over 400 events took ' + (performance.now() - t0) + ' ms')
  const n = (f: Partial<typeof NO_FILTER>) => filterRows(rows, { ...NO_FILTER, ...f }).length
  assert.equal(n({}), 401); assert.equal(n({ lane: 'factcheck' }), 100); assert.equal(n({ stage: 'summarizer' }), 101)
  assert.equal(n({ subQuestion: '2' }), 40, 'sub-question 2: the judge and fact-check events that carry the index')
  assert.equal(n({ type: 'run_failed' }), 1)
  assert.equal(n({ warningsOnly: true }), 51, 'the 50 warn notes and the failure')
  assert.equal(n({ lane: 'notes', warningsOnly: true }), 50)
  assert.equal(n({ text: 'PAPER NUMBER 3' }), big.filter(e => String(e.data.title ?? '').toLowerCase().includes('paper number 3')).length, 'case does not matter'); assert.ok(n({ text: 'PAPER NUMBER 3' }) > 10)
  assert.equal(n({ text: 'zzz' }), 0)
  const o = logOptions(rows)
  assert.deepEqual(o.subQuestions, [1, 2, 3, 4, 5]); assert.ok(o.lanes.includes('notes') && o.types.includes('run_failed'))
  const json = JSON.parse(eventsJson(filterRows(rows, { ...NO_FILTER, type: 'run_failed' })))
  assert.equal(json.length, 1); assert.equal(json[0].event, 'run_failed')
  assert.equal(eventSubQuestion(big[0]), 1); assert.equal(eventSubQuestion(ev('step', null, { subQuestion: 'two' })), null, 'a string is not an index')
})

test('a warning is a warn note, a failure or a wait for a rate limit; an ordinary event is not', () => {
  reset()
  assert.equal(isWarning(step('notes', 's2_skipped', 'completed', { level: 'warn' }, 1)), true)
  assert.equal(isWarning(step('notes', 'plan_cache', 'completed', { level: 'info' }, 1)), false)
  assert.equal(isWarning(ev('run_failed', 'summarizer', {}, 1)), true)
  assert.equal(isWarning(step('factcheck', 'store', 'failed', {}, 1)), true)
  assert.equal(isWarning(ev('stage_completed', 'factcheck', { judgeWaits: 2 }, 1)), true)
  assert.equal(isWarning(ev('stage_completed', 'factcheck', { judgeWaits: 0 }, 1)), false)
  assert.equal(isWarning(step('papers', 'search', 'running', {}, 1)), false)
})

// ------------------------------------------------------------------------------------------------------------------------ T7 per-paper parsing
test('per-paper parsing: counts by outcome, reasons and routes, one entry per paper', () => {
  reset()
  const p = (id: string | null, outcome: string, route: string | null, reason: string | null, chars: number | null, sec: number) =>
    step('papers', 'paper_parse', 'completed', { ...(id ? { paperId: id } : {}), title: `T ${id}`, outcome, route, reason, chars, subQuestionId: 'sq' }, sec)
  const events = [p('a', 'parsed', 'own link', null, 1000, 1), p('b', 'parsed', 'parse cache', null, 2000, 2), p('c', 'abstract_only', 'own link', 'HTTP 403', null, 3),
    p('d', 'failed', 'own link', 'html or non-PDF response', null, 4), p('e', 'abstract-only', null, 'HTTP 403', null, 5), p('a', 'parsed', 'own link', null, 1500, 6), p('f', 'weird', null, null, null, 7)]
  const m = paperParseModel(events)
  assert.equal(m.done, 6, 'the repeated paper counts once'); assert.deepEqual([m.parsed, m.abstractOnly, m.failed, m.other], [2, 2, 1, 1])
  assert.deepEqual(m.reasons, [['HTTP 403', 2], ['html or non-PDF response', 1]]); assert.deepEqual(m.routes, [['own link', 3], ['parse cache', 1]])
  assert.equal(m.papers.find(x => x.paperId === 'a')!.chars, 1500, 'the latest report of a paper wins'); assert.equal(m.papers.find(x => x.paperId === 'f')!.outcome, 'weird')
  assert.deepEqual(paperParseModel([]).papers, [])
})

// ------------------------------------------------------------------------------------------------------------------------ T8 cache and T10 notes
test('cache and warm-up chips come from the notes, the parse summary and the cacheHits of the digest and judge steps', () => {
  reset()
  const events = [
    step('notes', 'plan_cache', 'completed', { level: 'info', stage: 'planner' }, 1), step('notes', 'chunk_warmup', 'completed', { level: 'info', stage: 'retrieval', papers: 4, chunks: 212 }, 2),
    step('notes', 'parse_summary', 'completed', { level: 'warn', stage: 'retrieval', attempted: 8, parsed: 5, abstractOnly: 2, failed: 1, fromParseCache: 2, reasons: { 'HTTP 403': 2 } }, 3),
    step('summarizer', 'digest', 'completed', { done: 10, total: 10, cacheHits: 4 }, 4), step('summarizer', 'judge', 'completed', { done: 5, total: 5, cacheHits: 6 }, 5),
  ]
  const c = cacheInfo(events)
  assert.deepEqual([c.planCache, c.digest, c.judge, c.parse, c.warmup], [true, { hits: 4, total: 10 }, { hits: 6 }, { fromCache: 2 }, { papers: 4, chunks: 212 }])
  const chips = cacheChips(c)
  assert.deepEqual(chips.planner, ['plan reused from cache']); assert.deepEqual(chips.summarizer, ['4 of 10 digests from cache', '6 judge verdicts from cache'])
  assert.deepEqual(chips.retrieval, ['2 papers from the parse cache', 'text of 4 papers prepared while others were parsed'])
  assert.deepEqual(cacheChips(cacheInfo([])), { planner: [], retrieval: [], summarizer: [] }, 'nothing without the data')
  assert.deepEqual(stageExtras(events, 'retrieval').notes, { count: 2, warn: 1 })
})

test('notes are de-duplicated by code and sub-question, friendly for known codes and raw for unknown ones', () => {
  reset()
  const n = (code: string, data: Record<string, unknown>, msg = '') => ev('step', 'summarizer', { lane: 'notes', step: code, state: 'completed', level: 'info', stage: 'summarizer', ...data }, seq, msg)
  const events = [n('loop2_gaps', { subQuestionIndex: 2, gaps: 1, searched: 2, covered: 1 }), n('loop2_gaps', { subQuestionIndex: 2, gaps: 3, searched: 4, covered: 1 }), n('loop2_gaps', { subQuestionIndex: 4, gaps: 2 }),
    n('plan_cache', {}), n('plan_cache', {}), n('brand_new_code', { level: 'warn' }, 'Something the server wants to say'), n('s2_skipped', { level: 'warn', stage: 'retrieval' })]
  const notes = notesOf(events)
  assert.deepEqual(notes.map(x => `${x.code}#${x.subQuestionIndex ?? 0}`), ['loop2_gaps#2', 'loop2_gaps#4', 'plan_cache#0', 'brand_new_code#0', 's2_skipped#0'], 'one per code and sub-question, in order of first appearance')
  assert.equal(notes[0].data.gaps, 3, 'the latest report of a note wins')
  assert.equal(noteView(notes[0]).title, 'Sub-question 2: 3 aspects stay without evidence after the second search')
  assert.equal(noteView(notes[2]).title, 'The stored plan was reused')
  assert.equal(noteView(notes[3]).title, 'Something the server wants to say', 'an unknown code shows its own message'); assert.equal(notes[3].level, 'warn')
  assert.equal(noteView({ ...notes[3], message: '' }).title, 'brand_new_code', 'and its code when there is no message')
  assert.match(noteView(notes[4]).title, /Semantic Scholar/)
  assert.equal(notesOf([ev('step', 'summarizer', { lane: 'notes', step: 'x', level: 'loud' }, 1)])[0].level, 'info', 'an unknown level is information')
})

// ------------------------------------------------------------------------------------------------------------------------ T9 Groq
test('Groq per stage is the value at stage_completed minus the value at stage_started; the total never goes backwards; purposes come from the last stage and from the end', () => {
  reset()
  const g = (tokens: number, calls = 1, rateLimits = 0, parkedSeconds = 0) => ({ groq: { tokens, calls, rateLimits, parkedSeconds } })
  const events = [
    ev('stage_started', 'planner', g(0, 0), 0), ev('stage_completed', 'planner', { ...g(1000, 2), groq: { tokens: 1000, calls: 2, rateLimits: 0, parkedSeconds: 0, byPurpose: { aspect_split: 1000 } } }, 10),
    ev('stage_started', 'summarizer', g(1500, 3), 20), step('summarizer', 'digest', 'running', g(9000, 12, 2, 30), 30), step('summarizer', 'digest', 'running', g(8800, 11, 1, 20), 31),
    ev('stage_completed', 'summarizer', { groq: { tokens: 30000, calls: 40, rateLimits: 5, parkedSeconds: 90, byPurpose: { digest: 25000, aspect_split: 1000 } } }, 60),
    ev('stage_started', 'retrieval', {}, 70),                                                       // no telemetry at its start: not guessed
    ev('stage_completed', 'retrieval', g(31000), 80),
  ]
  const by = groqByStage(events)
  assert.deepEqual(by.map(s => s.stage), ['planner', 'summarizer'], 'a stage without telemetry at its start is left out')
  assert.deepEqual(by[0].use, { tokens: 1000, calls: 2, rateLimits: 0, parkedSeconds: 0 }); assert.deepEqual(by[1].use, { tokens: 28500, calls: 37, rateLimits: 5, parkedSeconds: 90 })
  assert.deepEqual(groqTotal(events), { tokens: 31000, calls: 40, rateLimits: 5, parkedSeconds: 90 }, 'the largest value of each field: 8800 after 9000 did not lower anything')
  assert.deepEqual(groqByPurpose(events), [['digest', 25000], ['aspect_split', 1000]], 'from the last stage_completed that has them')
  const end = [...events, ev('run_completed', null, { groqTokens: 40000, groqCalls: 50, groqRateLimits: 6, groqParkedSeconds: 100, groqTokensByPurpose: { digest: 30000, stage4_near: 10000 } }, 100)]
  assert.deepEqual(groqByPurpose(end), [['digest', 30000], ['stage4_near', 10000]], 'the end of the run wins')
  assert.deepEqual(groqTotal(end), { tokens: 40000, calls: 50, rateLimits: 6, parkedSeconds: 100 })
  assert.equal(groqTotal([ev('stage_started', 'planner', {}, 1)]), null, 'RUN_TELEMETRY=false: no data.groq, nothing shown')
  assert.equal(groqOf(ev('step', null, { groq: 'lots' }, 1)), null); assert.equal(groqOf(ev('step', null, { groq: { note: 1 } }, 1)), null)
  assert.equal(groqLine({ tokens: 120_000, calls: 200, rateLimits: 8, parkedSeconds: 41 }), 'Groq 120k tokens · 8 waits · 41 s waiting')
  assert.equal(groqLine({ tokens: 900, calls: 2, rateLimits: 1, parkedSeconds: 0 }), 'Groq 900 tokens · 1 wait'); assert.equal(groqLine({ tokens: 500, calls: 1, rateLimits: 0, parkedSeconds: 0 }), 'Groq 500 tokens')
  // the usage tile works while the run goes, from the purposes so far
  assert.equal(tokenUsage(events)!.rows[0].key, 'digest'); assert.equal(tokenUsage(events)!.total, 31000)
  assert.equal(stageExtras(events, 'planner').groq, 'Groq 1.0k tokens')
})

test('the demo run carries telemetry, notes, per-paper events and cache hits end to end', () => {
  const all = demoEvents({ fact: 'on' })
  const u = groqTotal(all)!
  assert.equal(u.tokens, tokenUsage(all)!.total); assert.ok(u.rateLimits > 0 && u.parkedSeconds > 0)
  assert.ok(groqByStage(all).length === 4)
  assert.ok(notesOf(all).some(x => x.level === 'warn') && notesOf(all).some(x => x.code === 'loop2_gaps'))
  assert.equal(paperParseModel(all).done, 8); assert.equal(cacheInfo(all).planCache, true)
  const old = demoEvents({ fact: 'on', old: true })
  assert.equal(groqTotal(old)?.tokens ?? null, tokenUsage(old)!.total, 'an old-style run: totals only from run_completed'); assert.equal(notesOf(old).length, 0); assert.equal(paperParseModel(old).done, 0)
  assert.ok(old.every(e => groqOf(e) == null))
})
