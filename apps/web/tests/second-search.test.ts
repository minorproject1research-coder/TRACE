// Run with:  pnpm test. The "Second search" tab: the view built from a report and from events, before/after verdicts, rung details, stopped reasons, old runs.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { demoEvents } from '../lib/demo-api'
import { stripLoop2Detail } from '../lib/demo-loop2'
import { demoReport } from '../lib/demo-report'
import {
  afterBar, aspectChip, buildSecondSearch, EMPTY_TEXT, BEFORE_TEXT, ladder, loop2SpanSeconds, nowText, queriesAsked, rungDetails, spanLine, stoppedText, timelineLine, verdictBar, yesAggregate, aspectView,
} from '../lib/second-search'
import { loop2RungResults, loop2Tip } from '../lib/stream'
import { buildTimeline } from '../lib/timeline'
import { stageGantt } from '../lib/swimlanes'
import type { EventName, Loop2, StageId, WorkflowEvent } from '../lib/trace-types'

const T0 = Date.parse('2026-11-10T10:00:00Z')
let seq = 0
const iso = (sec: number) => new Date(T0 + sec * 1000).toISOString()
const l2 = (data: Record<string, unknown>, sec: number, occ?: number): WorkflowEvent =>
  ({ seq: seq++, event: 'step' as EventName, stage: 'summarizer' as StageId, status: null, message: '', data: { lane: 'summarizer', state: 'running', subQuestions: 5, ...data, ...(occ != null ? { occurredAt: iso(occ) } : {}) }, timestamp: iso(sec) })
const rungStart = (sq: number, rung: string, aspects: number, sec: number) => l2({ step: 'loop2', subQuestionIndex: sq, loop2Step: rung, aspects }, sec)
const rungDone = (sq: number, rung: string, d: Record<string, unknown>, sec: number) => l2({ step: 'loop2_step', state: 'completed', subQuestionIndex: sq, loop2Step: rung, error: null, ...d }, sec)
const closing = (sq: number, searched: number, covered: number, sec: number) => l2({ step: 'loop2', subQuestionIndex: sq, searched, covered }, sec)
const Q = { 'Is it cheap?': ['cost of the sample method', 'sample method price per request'] }

const report = () => demoReport('demo-x', 'Q?', null, 'on')
const sqOf = (v: ReturnType<typeof buildSecondSearch>, i: number) => v.sqs.find(s => s.index === i)!

// ------------------------------------------------------------------------------------------------------------------------ from a report
test('the summary strip from a report: sub-questions that needed it, aspects searched and covered, gaps, new sources, new verified findings, time', () => {
  const v = buildSecondSearch({ report: report(), events: [], running: false })
  assert.equal(v.state, 'done'); assert.equal(v.source, 'report')
  assert.deepEqual(v.sqs.filter(s => s.needed).map(s => s.index), [2, 4, 5]); assert.equal(v.summary.total, 5)
  assert.deepEqual([v.summary.searched, v.summary.covered, v.summary.knownGaps], [11, 6, 7])
  assert.equal(v.summary.newSources, 6, 'sources with foundByLoop2Step'); assert.equal(v.summary.newFindings, 5 + 30 + 2, 'the sum of the steps newVerifiedFindings')
  assert.ok(Math.abs(v.summary.sumSeconds! - (231.4 + 412.7 + 29.5)) < 1e-6); assert.equal(v.summary.spanSeconds, null, 'no events, no span'); assert.equal(v.badge, 11)
  assert.equal(timelineLine(v), 'Second search: 11 aspects searched, 6 covered')
  assert.match(spanLine(v.summary)!, /^up to 11 min added up over the sub-questions, because they overlap$/)
  assert.equal(sqOf(v, 1).needed, false); assert.equal(sqOf(v, 1).line, 'Judged sufficient first time, no second search needed.')
  assert.equal(sqOf(v, 3).line, null, 'a sub-question that did not finish has no verdict to quote')
})

test('time: first to last event for the span, "up to" the sum because sub-questions overlap, tokens of the second search from the end of the run', () => {
  const all = demoEvents({ fact: 'on' })
  const v = buildSecondSearch({ report: report(), events: all, running: false })
  assert.ok(loop2SpanSeconds(all)! > 0); assert.equal(v.summary.spanSeconds, loop2SpanSeconds(all))
  assert.match(spanLine(v.summary)!, /from the first to the last event · up to 11 min added up/)
  assert.equal(v.summary.tokens, 9600, 'digest_loop2 from groqTokensByPurpose')
  assert.equal(buildSecondSearch({ report: report(), events: [], running: false }).summary.tokens, null)
})

test('before and after bars: the numbers of each aspect, "covered: now N yes from M sources", and nothing made up', () => {
  assert.deepEqual(verdictBar({ yes: 2, partial: 1, no: 3 }), { yes: 2, partial: 1, no: 3, total: 6 })
  assert.deepEqual(verdictBar({ yes: 2 }), { yes: 2, partial: 0, no: 0, total: 2 }, 'a missing count beside a real one is 0')
  for (const bad of [null, undefined, {}, 'x', [], { yes: 'many' }, { yes: -1 }]) assert.equal(verdictBar(bad), null, JSON.stringify(bad))
  assert.deepEqual(afterBar({ yes: 3, partial: 1, no: 2, sources: 3 }), { yes: 3, partial: 1, no: 2, total: 6, sources: 3 }); assert.equal(afterBar({ yes: 1, partial: 0, no: 0 })!.sources, null)
  const v = buildSecondSearch({ report: report(), events: [], running: false })
  const asp = (i: number, text: RegExp) => sqOf(v, i).aspects.find(a => text.test(a.text))!
  const noise = asp(4, /robust/)
  assert.deepEqual([noise.before, noise.after], [{ yes: 0, partial: 2, no: 3, total: 5 }, { yes: 3, partial: 1, no: 2, total: 6, sources: 3 }])
  assert.equal(noise.nowText, 'covered: now 3 yes from 3 sources'); assert.equal(asp(4, /2019 baseline/).nowText, 'covered: now 2 yes from 2 sources')
  assert.equal(asp(4, /licence/).nowText, null, 'a gap is not "covered"'); assert.equal(nowText('covered', null), null, 'no after, no sentence')
  assert.equal(nowText('covered', afterBar({ yes: 1, partial: 0, no: 0 })), 'covered: now 1 yes', 'without a source count the sentence says no number of sources')
  const skipped = asp(4, /hardware/)
  assert.ok(skipped.before && skipped.after === null, 'an aspect that was not searched has a before only: the after is never made from the before')
  assert.equal(asp(2, /memory layout/).before, null)
})

test('the aggregate of a sub-question: yes verdicts before and after over the aspects that were searched and have both', () => {
  const v = buildSecondSearch({ report: report(), events: [], running: false })
  assert.equal(sqOf(v, 4).yesAgg!.text, 'yes verdicts 2 → 10 across 7 aspects', 'the skipped aspect has no after and is not in it')
  assert.equal(sqOf(v, 2).yesAgg!.text, 'yes verdicts 0 → 2 across 2 aspects'); assert.equal(sqOf(v, 5).yesAgg!.text, 'yes verdicts 2 → 3 across 2 aspects')
  assert.equal(yesAggregate([]), null)
  const one = aspectView({ text: 'x', status: 'covered', steps: ['pool'], before: { yes: 0, partial: 1, no: 0 }, after: { yes: 4, partial: 0, no: 0, sources: 2 } })
  assert.equal(yesAggregate([one])!.text, 'yes verdicts 0 → 4 across 1 aspect')
  assert.equal(yesAggregate([{ ...one, after: null }]), null, 'before only: no aggregate')
  assert.equal(yesAggregate([{ ...one, steps: [] }]), null, 'an aspect that was not searched does not count')
})

test('stopped reasons: time budget, sources could not be read, unknown values raw, nothing when null', () => {
  assert.equal(stoppedText('time_budget'), 'stopped: time budget used up'); assert.equal(stoppedText('digests_failed'), 'stopped: the sources could not be read')
  assert.equal(stoppedText('moon_phase'), 'stopped: moon_phase'); assert.equal(stoppedText(null), null); assert.equal(stoppedText(''), null); assert.equal(stoppedText(undefined), null)
  const v = buildSecondSearch({ report: report(), events: [], running: false })
  assert.equal(sqOf(v, 4).aspects.find(a => /ethical/.test(a.text))!.stopped, 'stopped: time budget used up')
  assert.equal(sqOf(v, 5).aspects.find(a => /learning rate/.test(a.text))!.stopped, 'stopped: the sources could not be read')
  assert.equal(sqOf(v, 4).aspects.filter(a => a.stopped).length, 1)
})

test('rung details from a report: aspects and covered, the queries by aspect, the funnel, digests, a calm warning for failed digests, note and error', () => {
  const v = buildSecondSearch({ report: report(), events: [], running: false })
  const rung = (i: number, id: string) => sqOf(v, i).rungs.find(r => r.id === id)!
  const q = rung(4, 'queries').details!
  assert.equal(q.queryCount, 9); assert.equal(q.queries!.length, 4); assert.equal(q.queries![0].aspect, 'How robust is it to noise?'); assert.equal(q.queries![0].list.length, 3)
  assert.ok(q.queriesCopy!.startsWith('How robust is it to noise?\n- robustness of tracers to input noise')); assert.equal(queriesAsked(sqOf(v, 4)), 9)
  assert.deepEqual(q.funnel, ['14 papers found → 6 kept → 4 parsed', '11 web pages found → 3 kept'])
  assert.deepEqual(q.coveredTexts, ['How robust is it to noise?', 'What does it cost to run in production?']); assert.deepEqual(q.digests, { total: 8, failed: 0, tried: 10 }); assert.equal(q.digestWarning, null)
  const pool = rung(4, 'pool').details!
  assert.equal(pool.digestWarning, '2 sources could not be read (rate limit?), so “no evidence” may be wrong.'); assert.equal(pool.note, 'Parsed the next 4 ranked papers of the search results.'); assert.equal(pool.queries, null, 'no queries for a rung that asks none')
  assert.equal(rung(2, 'queries').greyed, true, 'a rung with 0 new sources is greyed'); assert.equal(rung(2, 'reselect').greyed, false)
  assert.deepEqual(rung(2, 'queries').details!.funnel, ['5 papers found → 0 kept → 0 parsed', '6 web pages found → 0 kept'], 'the kept counts are what Stage 3 then read')
  assert.equal(rung(4, 'reselect').highlighted, true); assert.equal(rung(2, 'pool').highlighted, true); assert.equal(rung(2, 'queries').highlighted, false)
  assert.equal(rung(5, 'queries').state, 'did_not_run', 'the ladder stopped before it'); assert.equal(rung(5, 'queries').details, null)
  assert.equal(rungDetails({ step: 'queries', aspects: 1, newSources: 0, newVerifiedFindings: 0, covered: 0, seconds: 1, error: 'ConnectionError: gone' })!.error, 'ConnectionError: gone')
  assert.equal(rungDetails({ step: 'pool', aspects: 1, newSources: 0, newVerifiedFindings: 0, covered: 0, seconds: 1 }), null, 'none of the newer fields: no Details block')
  assert.equal(rungDetails(null), null)
  assert.deepEqual(rungDetails({ step: 'queries', aspects: 1, newSources: 1, newVerifiedFindings: 1, covered: 0, seconds: 1, newPapersFound: 1, newWebFound: 1, newWebKept: 0 })!.funnel, ['1 paper found', '1 web page found → 0 kept'])
})

test('a rung that was not needed: everything searched was covered before it', () => {
  const l: Loop2 = { searched: 1, covered: 1, seconds: 5, steps: [{ step: 'reselect', aspects: 1, newSources: 1, newVerifiedFindings: 2, covered: 1, seconds: 5 }], aspects: [{ text: 'a', status: 'covered', coveredBy: 'reselect', steps: ['reselect'] }] }
  assert.deepEqual(ladder(l).map(r => `${r.id}:${r.state}`), ['reselect:ran', 'pool:not_needed', 'queries:not_needed'])
  assert.deepEqual(ladder({ ...l, covered: 0 }).map(r => `${r.id}:${r.state}`), ['reselect:ran', 'pool:did_not_run', 'queries:did_not_run'])
  const odd = ladder({ ...l, steps: [...(l.steps ?? []), { step: 'teleport', aspects: 1, newSources: 0, newVerifiedFindings: 0, covered: 0, seconds: 1 }] })
  assert.equal(odd[3].id, 'teleport'); assert.equal(odd[3].title, 'teleport', 'an unknown rung is shown raw')
  assert.equal(aspectChip({ status: 'weather', coveredBy: null }).label, 'weather'); assert.equal(aspectChip({ status: 'covered', coveredBy: 'queries' }).label, 'Covered by queries')
})

// ------------------------------------------------------------------------------------------------------------------------ old runs
test('an old run (null or missing new fields) renders as before: no bars, no aggregate, no details, no stopped reason, nothing invented', () => {
  const old = stripLoop2Detail(report())
  const v = buildSecondSearch({ report: old, events: [], running: false })
  assert.equal(v.state, 'done'); assert.equal(v.summary.searched, 11)
  for (const sq of v.sqs.filter(s => s.needed)) {
    assert.equal(sq.yesAgg, null)
    for (const a of sq.aspects) { assert.deepEqual([a.before, a.after, a.nowText, a.stopped], [null, null, null, null]) }
    for (const r of sq.rungs) assert.equal(r.details, null)
    assert.equal(queriesAsked(sq), null, 'no query text for a run that has none')
  }
  // explicit nulls (the server sends null for runs stored before)
  const nulls = report(); for (const sq of nulls.subQuestions) for (const a of sq.coverage?.loop2?.aspects ?? []) { a.before = null; a.after = null; a.stopped = null }
  assert.equal(buildSecondSearch({ report: nulls, events: [], running: false }).sqs[3].yesAgg, null)
  // a before without an after: only the before
  const onlyBefore = aspectView({ text: 'x', status: 'known_gap', steps: ['pool'], before: { yes: 1, partial: 1, no: 0 } })
  assert.deepEqual([onlyBefore.before!.total, onlyBefore.after, onlyBefore.nowText], [2, null, null])
})

// ------------------------------------------------------------------------------------------------------------------------ live: loop2_step
test('loop2_step fills in each rung as soon as it finishes, keyed by (sub-question, rung), for two sub-questions at once and in any order', () => {
  seq = 0
  const events = [
    rungStart(4, 'reselect', 7, 1), rungStart(2, 'reselect', 2, 2),
    rungDone(4, 'reselect', { aspects: 7, newSources: 3, newVerifiedFindings: 11, covered: 1, seconds: 38.9, queries: null }, 5),
    rungStart(4, 'queries', 4, 6),
    rungDone(2, 'reselect', { aspects: 2, newSources: 0, newVerifiedFindings: 0, covered: 0, seconds: 14.2, queries: null }, 7),
    rungDone(4, 'queries', { aspects: 4, newSources: 4, newVerifiedFindings: 13, covered: 2, seconds: 302.3, queries: { 'Is it cheap?': ['a', 'b'] } }, 9),
    rungStart(2, 'pool', 2, 10),
  ]
  const shuffled = [...events].reverse()
  const v = buildSecondSearch({ report: null, events, running: true, topics: ['t1', 't2', 't3', 't4', 't5'] })
  assert.deepEqual(buildSecondSearch({ report: null, events: shuffled, running: true, topics: ['t1', 't2', 't3', 't4', 't5'] }), v, 'merged by seq: the arrival order does not matter')
  assert.equal(v.state, 'live'); assert.deepEqual(v.sqs.filter(s => s.needed).map(s => s.index), [2, 4])
  const r = (i: number, id: string) => sqOf(v, i).rungs.find(x => x.id === id)!
  assert.deepEqual([r(4, 'reselect').newSources, r(4, 'reselect').newFindings, r(4, 'reselect').covered, r(4, 'reselect').seconds, r(4, 'reselect').running], [3, 11, 1, 38.9, false])
  assert.equal(r(4, 'queries').details!.queryCount, 2); assert.deepEqual(r(4, 'queries').details!.queries, [{ aspect: 'Is it cheap?', list: ['a', 'b'] }])
  assert.equal(r(4, 'pool').state, 'did_not_run', 'no event for this rung: nothing is shown as done'); assert.equal(r(4, 'pool').newSources, null, 'its result is not invented')
  assert.equal(r(2, 'reselect').greyed, true); assert.equal(r(2, 'pool').running, true, 'sub-question 2 is in pool now'); assert.equal(r(2, 'pool').newSources, null)
  assert.equal(r(2, 'queries').state, 'did_not_run')
  assert.equal(sqOf(v, 4).live!.rung, 'queries', 'the current-rung display of the loop2 events is unchanged'); assert.equal(sqOf(v, 4).live!.done, false)
  assert.deepEqual([v.summary.newSources, v.summary.newFindings], [7, 24])
  assert.equal(queriesAsked(sqOf(v, 4)), 2)
})

test('loop2_step events without an index or a rung, or with garbage, are ignored; a rung reported twice keeps the latest', () => {
  seq = 0
  const events = [rungDone(2, 'pool', { newSources: 1 }, 1), l2({ step: 'loop2_step', state: 'completed', loop2Step: 'pool' }, 2), l2({ step: 'loop2_step', state: 'completed', subQuestionIndex: 'two', loop2Step: 'pool' }, 3),
    rungDone(2, 'pool', { newSources: 5, queries: 'not a map', covered: 'x', seconds: null }, 4), rungDone(3, 'queries', { queries: { a: [1, 'q', ''] } }, 5)]
  const res = loop2RungResults(events)
  assert.deepEqual(res.map(r => `${r.subQuestionIndex}:${r.rung}:${r.newSources}`), ['2:pool:5', '3:queries:null'])
  assert.equal(res[0].queries, null); assert.equal(res[0].covered, null); assert.deepEqual(res[1].queries, { a: ['q'] }); assert.equal(res[1].queryCount, 1)
  assert.equal(loop2Tip(res, 9), null)
})

test('the timeline: the tooltip says how many queries were asked and what each finished rung found; the Gantt bar carries it too', () => {
  seq = 0
  const events = [rungStart(2, 'reselect', 2, 1), rungDone(2, 'reselect', { aspects: 2, newSources: 1, newVerifiedFindings: 3, covered: 0, seconds: 10 }, 5), rungStart(2, 'queries', 1, 6),
    rungDone(2, 'queries', { aspects: 1, newSources: 0, newVerifiedFindings: 0, covered: 0, seconds: 20, queries: Q }, 9), rungStart(2, 'pool', 1, 10)]
  events.unshift({ seq: seq++, event: 'step', stage: 'summarizer', status: null, message: '', timestamp: iso(0), data: { lane: 'summarizer', step: 'judge', state: 'running', subQuestionIndex: 2, subQuestions: 3, done: 0, total: 3 } })
  const tip = loop2Tip(loop2RungResults(events), 2)!
  assert.equal(tip, '2 queries asked. reselect: 1 new source, 3 new verified findings, 0 covered. queries: 0 new sources, 0 new verified findings, 0 covered')
  const step = buildTimeline(events, null).summarizer.steps.find(s => s.id === 'loop2')!
  assert.equal(step.subs![0].tip, tip); assert.match(step.subs![0].text, /^now: .* · queries: 0 new sources, 0 covered$/, 'the result of the last finished rung is added; the current-rung text is unchanged')
  const g = stageGantt([...events, { seq: seq++, event: 'step', stage: 'factcheck', status: null, message: '', timestamp: iso(11), data: { lane: 'factcheck', step: 'near', state: 'running', subQuestion: 2, subQuestions: 3 } }], T0 + 30_000)!
  assert.equal(g.lanes[0].bars.find(b => b.kind === 'second')!.tip, tip)
  // without loop2_step there is no tip: the chip is as before
  const plain = buildTimeline([events[0], rungStart(2, 'pool', 1, 3)], null).summarizer.steps.find(s => s.id === 'loop2')!
  assert.equal(plain.subs![0].tip, undefined); assert.equal(plain.subs![0].text, 'now: reading more papers from the search results (1 aspect)')
})

// ------------------------------------------------------------------------------------------------------------------------ the demo run, empty states
test('the demo run: the live view from its events matches the report, and an old-style run has none of the new fields', () => {
  const all = demoEvents({ fact: 'on' })
  const live = buildSecondSearch({ report: null, events: all, running: false, topics: [] })
  assert.equal(live.source, 'events'); assert.deepEqual(live.sqs.filter(s => s.needed).map(s => s.index), [2, 4, 5])
  assert.equal(queriesAsked(sqOf(live, 4)), 9); assert.equal(queriesAsked(sqOf(live, 2)), 3); assert.equal(queriesAsked(sqOf(live, 5)), null)
  assert.deepEqual(sqOf(live, 4).rungs.map(r => r.newSources), [3, 2, 4]); assert.deepEqual(sqOf(live, 2).rungs.map(r => r.newSources), [1, 1, 0])
  assert.equal(sqOf(live, 4).rungs[2].details!.queries!.length, 4)
  const rep = buildSecondSearch({ report: report(), events: all, running: false })
  for (const i of [2, 4, 5]) assert.deepEqual(sqOf(live, i).rungs.filter(r => r.state === 'ran').map(r => [r.id, r.newSources, r.newFindings, r.covered]), sqOf(rep, i).rungs.filter(r => r.state === 'ran').map(r => [r.id, r.newSources, r.newFindings, r.covered]), `sub-question ${i}`)
  const old = demoEvents({ fact: 'on', old: true })
  assert.ok(old.every(e => e.data.step !== 'loop2_step')); assert.equal(loop2RungResults(old).length, 0)
  assert.ok(sqOf(rep, 4).aspects.some(a => a.stopped) && sqOf(rep, 4).rungs.some(r => r.details?.digestWarning), 'the demo has a stopped aspect and a rung with a digest failure')
})

test('empty states: before the evidence stage asks for it, finished with nothing, and a report without any second search', () => {
  seq = 0
  assert.equal(buildSecondSearch({ report: null, events: [], running: true }).message, BEFORE_TEXT); assert.equal(buildSecondSearch({ report: null, events: [], running: true }).state, 'before')
  const none = buildSecondSearch({ report: null, events: [], running: false }); assert.equal(none.state, 'empty'); assert.equal(none.message, EMPTY_TEXT)
  const r = report(); for (const sq of r.subQuestions) if (sq.coverage) sq.coverage.loop2 = null
  const empty = buildSecondSearch({ report: r, events: [], running: false })
  assert.equal(empty.state, 'empty'); assert.equal(empty.message, 'No sub-question needed a second search (or it is switched off on the server).'); assert.equal(empty.badge, 0); assert.equal(timelineLine(empty), null)
  assert.equal(buildSecondSearch({ report: demoReport('x', 'q', null), events: demoEvents({ fact: 'off' }), running: false }).source, 'report')
  const old = buildSecondSearch({ report: null, events: demoEvents({ fact: 'on', old: true }), running: false })
  assert.equal(old.state, 'empty', 'an old stream has no indexed loop2 events: the same line')
})
