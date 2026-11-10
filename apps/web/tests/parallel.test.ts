// Run with:  pnpm test   (tsx --test tests/*.test.ts). The parallel pipeline (docs/API_HANDOFF.md, "Work that now runs at the same time"):
// interleaved judge and Loop 2 events, monotonic counters, the replayed Stage 4 burst, occurredAt timing, the near step, old-style events, unknown purposes.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { elapsedLabel, factProgress, judgeFailuresNote, judgeWaitsNote, overlapNote, progressLineFor } from '../lib/factcheck'
import { ETA_ESTIMATE_NOTE, FULL_RUN_ETA, LIVE_RUN_EXPECTATION, stageMeta } from '../lib/format'
import { demoEvents } from '../lib/demo-api'
import { eventIso, eventMs, factModel, judgeModel, loop2Model, mergeBySeq, mergedData, posInt, purposeLabel, stageStartedAt, tokenUsage } from '../lib/stream'
import { buildTimeline } from '../lib/timeline'
import type { EventName, StageId, WorkflowEvent } from '../lib/trace-types'

const T0 = Date.parse('2026-11-08T10:00:00Z')
let seq = 0
const at = (sec: number) => new Date(T0 + sec * 1000).toISOString()
function ev(event: EventName, stage: StageId | null, data: Record<string, unknown> = {}, sec = seq, message = ''): WorkflowEvent {
  return { seq: seq++, event, stage, status: null, message, data, timestamp: at(sec) }
}
const step = (lane: string, id: string, state: string, data: Record<string, unknown>, sec: number, message = '') =>
  ev('step', lane === 'papers' || lane === 'web' ? 'retrieval' : (lane as StageId), { lane, step: id, state, ...data }, sec, message)
const judge = (state: string, data: Record<string, unknown>, sec: number, message = '') => step('summarizer', 'judge', state, data, sec, message)
const fstep = (id: string, data: Record<string, unknown>, sec: number) => step('factcheck', id, 'running', data, sec)
const reset = () => { seq = 0 }
const judgeStart = (i: number, done: number, sec: number, extra: Record<string, unknown> = {}) => judge('running', { done, total: 5, subQuestionIndex: i, subQuestions: 5, ...extra }, sec)
const judgeEnd = (i: number, done: number, sufficient: boolean, sec: number, soFar = 1, extra: Record<string, unknown> = {}) =>
  judge('running', { done, total: 5, subQuestionIndex: i, subQuestions: 5, sufficient, judgeUsed: true, sufficientSoFar: soFar, ...extra }, sec)

function upToDigest(): WorkflowEvent[] {
  reset()
  return [
    ev('stage_started', 'summarizer', {}, 10),
    step('summarizer', 'digest', 'running', { done: 3, total: 10, failures: 0 }, 11),
    step('summarizer', 'digest', 'completed', { done: 10, total: 10, failures: 1 }, 20),
  ]
}

// ------------------------------------------------------------------------------------------------------------------------ time and order
test('the real time of an event is occurredAt when it has one, otherwise its timestamp', () => {
  const a = ev('step', 'summarizer', { occurredAt: at(5) }, 30)
  assert.equal(eventMs(a), T0 + 5000); assert.equal(eventIso(a), at(5))
  const plain = ev('step', 'summarizer', {}, 30)
  assert.equal(eventIso(plain), plain.timestamp, 'untouched when there is no occurredAt')
  assert.equal(eventMs(ev('step', 'summarizer', { occurredAt: 'yesterday-ish' }, 30)), T0 + 30_000, 'an unreadable occurredAt falls back to the timestamp')
  assert.equal(eventMs(ev('step', 'summarizer', { occurredAt: 12 }, 30)), T0 + 30_000)
  assert.equal(eventMs({ data: {}, timestamp: null }), null)
})

test('events are merged by seq: any arrival order, each seq once, the same array when already in order', () => {
  reset()
  const list = [ev('run_started', null, {}, 1), ev('stage_started', 'planner', {}, 2), ev('stage_completed', 'planner', {}, 3), ev('stage_started', 'retrieval', {}, 4)]
  assert.equal(mergeBySeq(list), list, 'no copy when it is already ordered')
  const shuffled = [list[2], list[0], list[3], list[1], list[2]]
  assert.deepEqual(mergeBySeq(shuffled).map(e => e.seq), [0, 1, 2, 3], 'a duplicate seq counts once')
  const newer = { ...list[1], message: 'second copy' }
  assert.equal(mergeBySeq([list[0], list[1], newer]).find(e => e.seq === 1)!.message, 'second copy', 'the copy that arrived last wins')
  assert.deepEqual(mergeBySeq([]), [])
})

test('a sub-question index is a whole number from 1; a string, 0 or a fraction is not an index', () => {
  assert.equal(posInt(3), 3); for (const bad of [0, -1, 2.5, '2', null, undefined, NaN]) assert.equal(posInt(bad), null)
})

// ------------------------------------------------------------------------------------------------------------------------ judge
test('judge events of different sub-questions interleave: the index decides the chip, two can be judging at once, done counts finished ones', () => {
  const events = upToDigest()
  events.push(judgeStart(1, 0, 21), judgeStart(2, 0, 22))
  let m = judgeModel(events)
  assert.deepEqual(m.sqs.map(s => s.phase), ['active', 'active', 'waiting', 'waiting', 'waiting'])
  assert.equal(m.judging, 2, 'two chips are judging at the same time'); assert.equal(m.done, 0); assert.equal(m.total, 5)
  events.push(judgeEnd(2, 1, true, 30))                                          // sub-question 2 finishes FIRST
  m = judgeModel(events)
  assert.deepEqual(m.sqs.map(s => s.phase), ['active', 'done', 'waiting', 'waiting', 'waiting'])
  assert.equal(m.done, 1, 'done is the number of finished sub-questions, not an index'); assert.equal(m.sqs[1].sufficient, true)
  events.push(judgeStart(3, 1, 31), judgeEnd(1, 2, false, 40, 1))
  m = judgeModel(events)
  assert.deepEqual(m.sqs.map(s => s.phase), ['done', 'done', 'active', 'waiting', 'waiting'])
  assert.equal(m.sqs[0].sufficient, false); assert.equal(m.done, 2); assert.equal(m.sufficient, 1)
})

test('the index comes from the field, never from the message text', () => {
  const events = upToDigest()
  events.push(judge('running', { done: 0, total: 3, subQuestionIndex: 3, subQuestions: 3 }, 21, 'Judging the evidence for sub-question 1 of 3'))
  const m = judgeModel(events)
  assert.deepEqual(m.sqs.map(s => s.phase), ['waiting', 'waiting', 'active'], 'the message says 1, the field says 3')
  const noField = upToDigest(); noField.push(judge('running', { done: 0, total: 3 }, 21, 'Judging the evidence for sub-question 1 of 3'))
  assert.equal(judgeModel(noField).indexed, false, 'a message alone gives no chips')
  assert.deepEqual(judgeModel(noField).sqs, [])
})

test('counters never go backwards: done=5 followed by a late done=4 stays at 5', () => {
  const events = upToDigest()
  events.push(judgeStart(4, 3, 21), judgeStart(5, 3, 22), judgeEnd(5, 5, true, 30, 3), judgeEnd(4, 4, false, 31, 2))
  const m = judgeModel(events)
  assert.equal(m.done, 5); assert.equal(m.sufficient, 3)
  assert.deepEqual([m.sqs[3].phase, m.sqs[4].phase], ['done', 'done'])
  const lane = buildTimeline(events, null).summarizer.steps.find(s => s.id === 'judge')!
  assert.deepEqual(lane.progress, { done: 5, total: 5 }, 'the bar reads done / total from the merged counters')
  const d = mergedData([judgeStart(1, 2, 1), judgeStart(2, 4, 2), judgeStart(3, 3, 3)])
  assert.equal(d.done, 4, 'mergedData keeps the largest cumulative counter')
  // digest failures and parsing never go back either
  assert.equal(mergedData([step('summarizer', 'digest', 'running', { done: 7, total: 10, failures: 2 }, 1), step('summarizer', 'digest', 'running', { done: 6, total: 10, failures: 1 }, 2)]).failures, 2)
})

test('a late "started" event never takes a finished chip back', () => {
  const events = upToDigest()
  events.push(judgeEnd(2, 1, true, 30), judgeStart(2, 0, 31))
  assert.equal(judgeModel(events).sqs[1].phase, 'done')
})

test('the digest step ends before any judge chip changes (the server holds the judge events until then)', () => {
  const all = demoEvents({ fact: 'on' })
  const digestDone = all.findIndex(e => e.event === 'step' && e.data.step === 'digest' && e.data.state === 'completed')
  const firstJudge = all.findIndex(e => e.event === 'step' && e.data.step === 'judge')
  assert.ok(digestDone >= 0 && firstJudge > digestDone, `judge at ${firstJudge}, digest completed at ${digestDone}`)
  const before = judgeModel(all.slice(0, digestDone + 1))
  assert.ok(before.sqs.length === 0 || before.sqs.every(s => s.phase === 'waiting'), 'no chip has moved yet')
  assert.ok(before.digestDone)
  const after = judgeModel(all.slice(0, firstJudge + 1))
  assert.ok(after.sqs.some(s => s.phase === 'active'), 'the first judge event starts a chip')
})

test('old-style judge events (no subQuestionIndex): no chips, the bar and the counters as before', () => {
  const events = upToDigest()
  events.push(judge('running', { done: 0, total: 3 }, 21), judge('running', { done: 1, total: 3, sufficient: true, judgeUsed: true, sufficientSoFar: 1 }, 30))
  const m = judgeModel(events)
  assert.equal(m.indexed, false); assert.deepEqual(m.sqs, []); assert.equal(m.done, 1); assert.equal(m.total, 3)
  const s = buildTimeline(events, null).summarizer.steps.find(x => x.id === 'judge')!
  assert.equal(s.subs, undefined, 'no per-sub-question chips'); assert.deepEqual(s.progress, { done: 1, total: 3 })
  assert.ok(!s.chips.some(c => /judging at once/.test(c)))
})

test('the judge step in the timeline shows one chip per sub-question, with the verdict on sufficiency', () => {
  const events = upToDigest()
  events.push(judgeStart(1, 0, 21), judgeStart(2, 0, 22), judgeEnd(2, 1, true, 30))
  const s = buildTimeline(events, null).summarizer.steps.find(x => x.id === 'judge')!
  assert.deepEqual(s.subs!.map(x => `${x.label}: ${x.text}`), [
    'Sub-question 1: judging', 'Sub-question 2: done · enough evidence', 'Sub-question 3: waiting', 'Sub-question 4: waiting', 'Sub-question 5: waiting'])
  assert.ok(s.chips.includes('1 judging at once')); assert.deepEqual(s.progress, { done: 1, total: 5 })
  assert.equal(s.startedAt, at(21)); assert.equal(s.status, 'running')
})

// ------------------------------------------------------------------------------------------------------------------------ Loop 2
test('two sub-questions can be in different Loop 2 steps at once: one line each, no single "now" step', () => {
  const events = upToDigest()
  const l2 = (data: Record<string, unknown>, sec: number) => step('summarizer', 'loop2', 'running', data, sec)
  events.push(judgeStart(1, 0, 21), judgeStart(3, 0, 22),
    l2({ loop2Step: 'reselect', aspects: 2, subQuestionIndex: 1, subQuestions: 5 }, 23), l2({ loop2Step: 'queries', aspects: 1, subQuestionIndex: 3, subQuestions: 5 }, 24))
  const lm = loop2Model(events)
  assert.equal(lm.indexed, true); assert.deepEqual(lm.sqs.map(x => [x.index, x.rung, x.done]), [[1, 'reselect', false], [3, 'queries', false]])
  const s = buildTimeline(events, null).summarizer.steps.find(x => x.id === 'loop2')!
  assert.deepEqual(s.subs!.map(x => `${x.label}: ${x.text}`), ['Sub-question 1: now: re-reading papers we already have (2 aspects)', 'Sub-question 3: now: searching with new queries (1 aspect)'])
  assert.ok(!s.chips.some(c => c.startsWith('now:')), 'no run-wide "current step" chip: ' + s.chips.join(' | '))
  events.push(l2({ loop2Step: 'pool', aspects: 1, subQuestionIndex: 1, subQuestions: 5 }, 25), l2({ subQuestion: 'text of the question', subQuestionIndex: 3, subQuestions: 5, searched: 1, covered: 1 }, 26))
  const s2 = buildTimeline(events, null).summarizer.steps.find(x => x.id === 'loop2')!
  assert.deepEqual(s2.subs!.map(x => x.text), ['now: reading more papers from the search results (1 aspect)', 'searched 1 aspect, 1 covered'])
  assert.ok(s2.chips.includes('1 aspect searched again') && s2.chips.includes('1 covered'))
  // the judge chip of sub-question 1 says its second search is still going
  const j = buildTimeline(events, null).summarizer.steps.find(x => x.id === 'judge')!
  assert.equal(j.subs![0].text, 'judging · second search'); assert.equal(j.subs![2].text, 'judging')
})

test('old-style Loop 2 events (no subQuestionIndex) keep the single "now" line', () => {
  const events = upToDigest()
  events.push(judge('running', { done: 0, total: 3 }, 21), step('summarizer', 'loop2', 'running', { loop2Step: 'pool', aspects: 1 }, 22))
  const s = buildTimeline(events, null).summarizer.steps.find(x => x.id === 'loop2')!
  assert.equal(s.subs, undefined); assert.ok(s.chips.includes('now: reading more papers from the search results (1 aspect)'))
  assert.equal(loop2Model(events).indexed, false)
})

test('a failed run marks the sub-questions that were still judging', () => {
  const events = upToDigest()
  events.push(judgeStart(1, 0, 21), judgeStart(2, 0, 22), judgeEnd(2, 1, true, 30), ev('run_failed', 'summarizer', {}, 40, 'RuntimeError: boom'))
  const s = buildTimeline(events, null).summarizer.steps.find(x => x.id === 'judge')!
  assert.equal(s.status, 'failed'); assert.equal(s.subs![0].state, 'failed'); assert.equal(s.subs![1].state, 'done')
})

// ------------------------------------------------------------------------------------------------------------------------ Stage 4
function stage4Start(): WorkflowEvent[] {
  const e = upToDigest()
  e.push(ev('stage_completed', 'summarizer', { digests: 10, subQuestions: 5 }, 100), ev('stage_started', 'factcheck', {}, 101))
  return e
}
const c = (i: number) => ({ subQuestion: i, subQuestions: 5 })

test('the near step: near and conflicts of one sub-question are both active, and the line says so', () => {
  const events = stage4Start()
  events.push(fstep('claims', { ...c(2), sources: 3 }, 102), fstep('clusters', { ...c(2), claims: 6 }, 103), fstep('support', { ...c(2), clusters: 4 }, 104), fstep('near', c(2), 105))
  let m = factModel(events)
  assert.deepEqual(m.sqs[1].active, ['near']); assert.ok(m.hasNear)
  assert.equal(factProgress(events)!.line, 'Checking claims across sources: sub-question 2 of 5 - looking for close variants in other sources')
  events.push(fstep('conflicts', c(2), 105))
  m = factModel(events)
  assert.deepEqual(m.sqs[1].active, ['near', 'conflicts'], 'both are active')
  assert.equal(factProgress(events)!.line, 'Checking claims across sources: sub-question 2 of 5 - looking for close variants in other sources and for sources that disagree')
  const lane = buildTimeline(events, null).factcheck!
  assert.deepEqual(lane.steps.map(s => s.id), ['claims', 'clusters', 'support', 'near', 'conflicts', 'store'])
  const by = (id: string) => lane.steps.find(s => s.id === id)!
  assert.equal(by('near').status, 'running'); assert.equal(by('conflicts').status, 'running'); assert.equal(by('support').status, 'completed')
  const row = lane.rows!.find(r => r.index === 2)!
  assert.deepEqual(row.steps.map(s => `${s.id}:${s.status}`), ['claims:completed', 'clusters:completed', 'support:completed', 'near:running', 'conflicts:running', 'store:pending'], 'the six steps of the row')
  assert.equal(progressLineFor(['near', 'conflicts', 'nonsense'], 2, 5), 'Checking claims across sources: sub-question 2 of 5 - looking for close variants in other sources and for sources that disagree')
})

test('without any near event (an older server) the lane has the five old steps and no near column', () => {
  const events = stage4Start()
  events.push(fstep('claims', c(1), 102), fstep('conflicts', c(1), 103))
  const lane = buildTimeline(events, null).factcheck!
  assert.deepEqual(lane.steps.map(s => s.id), ['claims', 'clusters', 'support', 'conflicts', 'store'])
  assert.equal(lane.rows, undefined, 'the per-sub-question rows belong to the parallel Stage 4: older events render as before')
  assert.equal(factModel(events).hasNear, false)
  assert.equal(factProgress(events)!.overlapped, 0); assert.equal(lane.note, null, 'no overlap note for an old run')
})

test('sub-questions are not assumed to come in order or one at a time', () => {
  const events = stage4Start()
  // 2 and 5 are interleaved, 1 never reported
  events.push(fstep('claims', c(5), 102), fstep('claims', c(2), 103), fstep('clusters', c(5), 104), fstep('clusters', c(2), 105))
  const m = factModel(events)
  assert.deepEqual(m.sqs.map(s => `${s.index}:${s.status}`), ['1:waiting', '2:running', '3:waiting', '4:waiting', '5:running'], 'two are running; the others have not started')
  assert.equal(m.newest!.index, 2, 'the line follows the one that reported last')
  assert.equal(factProgress(events)!.line, 'Checking claims across sources: sub-question 2 of 5 - grouping claims that say the same thing')
})

test('a sub-question that reached its last steps is finished once another one reports; one that has not keeps its step running', () => {
  const events = stage4Start()
  events.push(fstep('claims', c(2), 102), fstep('support', c(2), 103), fstep('near', c(2), 104), fstep('conflicts', c(2), 104), fstep('claims', c(3), 105))
  const m = factModel(events)
  assert.equal(m.sqs[1].status, 'done'); assert.deepEqual(m.sqs[1].active, [])
  assert.equal(m.sqs[2].status, 'running'); assert.deepEqual(m.sqs[2].active, ['claims'])
  // sub-question 4 reported claims after 3 but 3 has not reached near/conflicts: 3 is still running
  events.push(fstep('claims', c(4), 106))
  assert.equal(factModel(events).sqs[2].status, 'running', 'it did not reach the last group, so a newer sub-question does not finish it')
})

test('store is global: once the node is saving, every sub-question that reported is done and the store step of each row follows it', () => {
  const events = stage4Start()
  events.push(fstep('claims', c(1), 102), fstep('near', c(1), 102), fstep('claims', c(2), 103))
  events.push(step('factcheck', 'store', 'running', { claims: 9, disagreements: 1 }, 110))
  let lane = buildTimeline(events, null).factcheck!
  assert.ok(lane.rows!.filter(r => r.index <= 2).every(r => r.status === 'done'))
  assert.equal(lane.rows![0].steps.find(s => s.id === 'store')!.status, 'running')
  events.push(step('factcheck', 'store', 'completed', { claims: 9 }, 111), ev('stage_completed', 'factcheck', { claims: 9, subQuestions: 5 }, 112))
  lane = buildTimeline(events, null).factcheck!
  assert.equal(lane.rows![0].steps.find(s => s.id === 'store')!.status, 'completed')
  assert.deepEqual(lane.rows!.map(r => r.status), ['done', 'done', 'not_reported', 'not_reported', 'not_reported'], 'a sub-question that never reported has no result')
})

test('the replayed burst renders its final state at once: the result only depends on the events, not on how they arrived', () => {
  const all = demoEvents({ fact: 'on' })
  const start = all.findIndex(e => e.event === 'stage_started' && e.stage === 'factcheck')
  const burst = all.filter((e, i) => i > start && e.event === 'step' && e.data.lane === 'factcheck' && typeof e.data.occurredAt === 'string')
  assert.ok(burst.length >= 10, 'a burst: ' + burst.length)
  const lastBurst = all.indexOf(burst[burst.length - 1])
  const upToBurst = all.slice(0, lastBurst + 1)
  const once = buildTimeline(upToBurst, null).factcheck!
  // the same events one by one, and in a scrambled arrival order, end in the same place
  let stepwise: WorkflowEvent[] = []
  for (const e of upToBurst) stepwise = [...stepwise, e]
  const scrambled = [...upToBurst].reverse()
  assert.deepEqual(buildTimeline(stepwise, null).factcheck, once)
  assert.deepEqual(buildTimeline(scrambled, null).factcheck, once, 'merged by seq')
  assert.deepEqual(factModel(scrambled), factModel(upToBurst))
  // what it shows: sub-questions 2 and 3 are finished, 1 is at its third step, and the rest have not started
  assert.deepEqual(once.rows!.map(r => `${r.index}:${r.status}`), ['1:done', '2:done', '3:done', '4:running', '5:running'], 'finished ones come from their done events; two are still running')
  assert.equal(once.status, 'running')
  assert.equal(once.note, overlapNote(5, 5))
  assert.equal(factProgress(upToBurst)!.line, 'Checking claims across sources: sub-questions 4 and 5 at the same time', 'two workers: the line names both')
})

test('the real start of Stage 4 is the earliest occurredAt of its steps, not stage_started', () => {
  const all = demoEvents({ fact: 'on' })
  const started = all.find(e => e.event === 'stage_started' && e.stage === 'factcheck')!
  const closed = all.find(e => e.event === 'stage_completed' && e.stage === 'factcheck')!
  const first = Math.min(...all.filter(e => e.data.lane === 'factcheck' && typeof e.data.occurredAt === 'string').map(e => Date.parse(e.data.occurredAt as string)))
  assert.ok(first < Date.parse(started.timestamp!), 'the first sub-question was checked before the stage started')
  const p = factProgress(all)!
  assert.equal(p.startedAt, new Date(first).toISOString())
  assert.equal(stageStartedAt(all, 'factcheck'), p.startedAt)
  assert.equal(stageStartedAt(all, 'summarizer'), all.find(e => e.event === 'stage_started' && e.stage === 'summarizer')!.timestamp, 'other stages still start at stage_started')
  const wrong = Date.parse(closed.timestamp!) - Date.parse(started.timestamp!)
  const real = Date.parse(closed.timestamp!) - Date.parse(p.startedAt!)
  assert.ok(real > wrong + 1000, `the work took ${real} ms, not the ${wrong} ms between stage_started and stage_completed`)
  assert.equal(elapsedLabel(p.startedAt, Date.parse(p.startedAt!) + 75_000), '1 min 15 s', 'the elapsed time runs from the real start')
  const lane = buildTimeline(all, null).factcheck!
  assert.equal(lane.startedAt, p.startedAt); assert.equal(lane.endedAt, closed.timestamp)
  // the timeline of the evidence stage overlaps with it
  const sum = buildTimeline(all, null).summarizer
  assert.ok(Date.parse(lane.startedAt!) < Date.parse(sum.endedAt!), 'the two bars overlap')
})

test('judge and loop2 steps are timed by occurredAt: a replayed event is not placed at its replay time', () => {
  const all = demoEvents({ fact: 'on' })
  const sum = buildTimeline(all, null).summarizer
  const j = sum.steps.find(s => s.id === 'judge')!
  const digest = sum.steps.find(s => s.id === 'digest')!
  const firstOccurred = Math.min(...all.filter(e => e.data.step === 'judge' && typeof e.data.occurredAt === 'string').map(e => Date.parse(e.data.occurredAt as string)))
  assert.equal(j.startedAt, new Date(firstOccurred).toISOString())
  assert.ok(Date.parse(j.startedAt!) < Date.parse(digest.endedAt!), 'judging began while the digests were still being read')
})

test('warnings: a judge call that waited for a Groq limit is a plain note, failures stay a warning, 0 or missing shows nothing', () => {
  const done = (data: Record<string, unknown>) => { const e = stage4Start(); e.push(ev('stage_completed', 'factcheck', { claims: 3, subQuestions: 5, ...data }, 200)); return factProgress(e)! }
  assert.equal(judgeWaitsNote(done({ judgeWaits: 2 })), '2 judge calls waited for a Groq rate limit. This only made the run slower.')
  assert.equal(judgeWaitsNote(done({ judgeWaits: 1 })), '1 judge call waited for a Groq rate limit. This only made the run slower.')
  assert.equal(judgeWaitsNote(done({ judgeWaits: 0 })), null); assert.equal(judgeWaitsNote(done({})), null); assert.equal(judgeWaitsNote(null), null)
  assert.equal(judgeWaitsNote(done({ judgeWaits: 'many' })), null, 'garbage is not a number')
  assert.equal(judgeFailuresNote(done({ judgeFailures: 3 })), '3 judge answers failed; labels for that part are conservative.')
  assert.equal(judgeFailuresNote(done({ judgeFailures: 1 })), '1 judge answer failed; labels for that part are conservative.')
  assert.equal(judgeFailuresNote(done({})), null)
  assert.ok(!/fail|error/i.test(judgeWaitsNote(done({ judgeWaits: 2 }))!), 'not worded as a failure')
  const both = factProgress(demoEvents({ fact: 'on' }))!
  assert.equal(both.judgeWaits, 2); assert.equal(both.judgeFailures, 1)
})

test('the overlap note names how many sub-questions ran during Stage 3, and says nothing for 0', () => {
  assert.equal(overlapNote(0, 5), null)
  assert.match(overlapNote(3, 5)!, /^Overlapped with Stage 3: 3 of 5 sub-questions were checked while the evidence stage was still running/)
  assert.match(overlapNote(1, 5)!, /1 of 5 sub-questions was checked/)
  assert.match(overlapNote(2, 5)!, /2 of 5 sub-questions were checked/)
  assert.match(overlapNote(1, null)!, /Stage 3: 1 sub-question was checked/)
  assert.match(overlapNote(2, null)!, /Stage 3: 2 sub-questions were checked/)
})

// ------------------------------------------------------------------------------------------------------------------------ the scenarios
test('old-style scenario: no event carries subQuestionIndex, occurredAt or the near step, and it renders as before', () => {
  for (const fact of ['off', 'on'] as const) {
    const all = demoEvents({ fact, old: true })
    assert.ok(all.every(e => e.data.subQuestionIndex === undefined && e.data.occurredAt === undefined && e.data.step !== 'near'), fact)
    const t = buildTimeline(all, null)
    assert.ok(t.summarizer.steps.every(s => s.subs === undefined))
    if (fact === 'on') { assert.equal(t.factcheck!.note, null); assert.equal(factProgress(all)!.overlapped, 0); assert.ok(!t.factcheck!.steps.some(s => s.id === 'near')) }
    else assert.equal(t.factcheck, null)
  }
  const old = tokenUsage(demoEvents({ fact: 'on', old: true }))!
  assert.ok(old.rows.some(r => r.key === 'stage4_judge' && r.label === 'Fact check: judge (older runs)'))
})

test('new-style scenario: indexed judge events interleave, Loop 2 runs on two sub-questions, a burst with occurredAt, a near step, judgeWaits and the new purposes', () => {
  const all = demoEvents({ fact: 'on' })
  const judges = all.filter(e => e.data.step === 'judge' && e.data.subQuestionIndex !== undefined)
  assert.ok(judges.length >= 10 && judges.every(e => posInt(e.data.subQuestionIndex) != null))
  const finishOrder = judges.filter(e => typeof e.data.sufficient === 'boolean').map(e => e.data.subQuestionIndex)
  assert.notDeepEqual(finishOrder, [...finishOrder].sort(), 'sub-questions finish out of order: ' + finishOrder.join(','))
  const dones = judges.filter(e => typeof e.data.sufficient === 'boolean').map(e => e.data.done as number)
  assert.ok(dones.some((d, i) => i > 0 && d < dones[i - 1]), 'done goes backwards once in the raw stream: ' + dones.join(','))
  assert.equal(judgeModel(all).done, 5, 'but never on the page')
  assert.ok(all.some(e => e.data.step === 'near') && all.some(e => typeof e.data.occurredAt === 'string'))
  const l2 = all.filter(e => e.data.step === 'loop2' && typeof e.data.loop2Step === 'string')
  assert.deepEqual([...new Set(l2.map(e => e.data.subQuestionIndex))].sort(), [2, 4, 5], 'Loop 2 on three sub-questions: all three rungs for 4, the first rung for 5, the second for 2')
  const order = all.filter(e => e.event === 'step' && e.data.lane === 'factcheck' && typeof e.data.subQuestion === 'number' && e.data.step === 'claims').map(e => e.data.subQuestion)
  assert.deepEqual(order, [1, 3, 2, 5, 4], 'Stage 4 follows the order the sub-questions were stored')
  const u = tokenUsage(all)!
  for (const k of ['digest', 'digest_loop2', 'aspect_split', 'query_expansion', 'stage4_merge', 'stage4_support', 'stage4_near', 'stage4_conflict']) assert.ok(u.rows.some(r => r.key === k && r.label !== k), k)
  assert.ok(!u.rows.some(r => r.key === 'stage4_judge'))
})

test('the failed Stage 4 scenario: finished sub-questions stay done, the one that was running is stopped, the rest have no result, and the run completes', () => {
  const all = demoEvents({ fact: 'failed' })
  const t = buildTimeline(all, null)
  assert.equal(t.factcheck!.status, 'failed')
  assert.deepEqual(t.factcheck!.rows!.map(r => `${r.index}:${r.status}`), ['1:done', '2:done', '3:done', '4:failed', '5:failed'], 'the two that were running when it failed')
  assert.ok(all.some(e => e.event === 'run_completed') && !all.some(e => e.event === 'run_failed'))
  assert.equal(factProgress(all)!.state, 'failed')
})

test('the failing-summarizer scenario never produces a judge event, so nothing is replayed', () => {
  const all = demoEvents({ fails: true })
  assert.ok(all.some(e => e.event === 'run_failed') && !all.some(e => e.data.step === 'judge'))
  assert.equal(buildTimeline(all, null).summarizer.status, 'failed')
})

// ------------------------------------------------------------------------------------------------------------------------ token usage
test('token usage: friendly labels for the new purposes, the raw key for an unknown one, biggest first', () => {
  reset()
  const done = ev('run_completed', null, { groqTokens: 1000, groqCalls: 9, groqTokensByPurpose: { stage4_near: 100, digest: 600, brand_new_purpose: 250, stage4_conflict: 50, stage4_judge: 0 } }, 5)
  const u = tokenUsage([done])!
  assert.equal(u.total, 1000); assert.equal(u.calls, 9)
  assert.deepEqual(u.rows.map(r => r.key), ['digest', 'brand_new_purpose', 'stage4_near', 'stage4_conflict', 'stage4_judge'])
  assert.equal(u.rows[0].label, 'Reading the sources (digests)')
  assert.equal(u.rows[1].label, 'brand_new_purpose', 'an unknown purpose is shown as its own key')
  assert.equal(purposeLabel('stage4_near'), 'Fact check: looking for close variants'); assert.equal(purposeLabel('constructor'), 'constructor', 'a key like an object property is just a key')
  assert.ok(Math.abs(u.rows.reduce((s, r) => s + r.share, 0) - 1) < 1e-9)
})

test('token usage: absent or malformed data gives nothing, never a crash', () => {
  reset()
  assert.equal(tokenUsage([]), null)
  assert.equal(tokenUsage([ev('run_completed', null, { reportUrl: '/x' }, 1)]), null, 'a run from before the totals existed')
  const odd = tokenUsage([ev('run_completed', null, { groqTokens: 'lots', groqTokensByPurpose: { digest: 'x', stage4_near: 40, bad: -3, list: [1] } }, 1)])!
  assert.deepEqual(odd.rows.map(r => r.key), ['stage4_near']); assert.equal(odd.total, 40)
  assert.equal(tokenUsage([ev('run_completed', null, { groqTokensByPurpose: [1, 2] }, 1)]), null)
  assert.equal(tokenUsage([ev('run_failed', 'summarizer', {}, 1)]), null)
})

// ------------------------------------------------------------------------------------------------------------------------ estimate copy
test('the ETA says about 15 to 25 minutes, measured on two runs and still an estimate, in one place', () => {
  assert.equal(FULL_RUN_ETA, 'about 15 to 25 minutes')
  assert.match(ETA_ESTIMATE_NOTE, /measured on two runs/); assert.match(ETA_ESTIMATE_NOTE, /estimate/)
  assert.ok(LIVE_RUN_EXPECTATION.includes(FULL_RUN_ETA) && LIVE_RUN_EXPECTATION.includes(ETA_ESTIMATE_NOTE))
  for (const m of Object.values(stageMeta)) assert.ok(!/25 to 35|20 to 30|not been timed|usually (about 30 seconds|2 to 9|8 to 11)/.test(`${m.detail} ${m.hint}`))
  assert.match(stageMeta.factcheck.hint, /estimate/); assert.match(stageMeta.summarizer.hint, /estimate/)
})

test('mergedData and the lanes ignore steps and fields they do not know', () => {
  const events = upToDigest()
  events.push(judge('running', { done: 1, total: 5, subQuestionIndex: 2, subQuestions: 5, sufficient: true, newField: { a: 1 } }, 30), step('summarizer', 'future_step', 'running', { done: 9 }, 31))
  const t = buildTimeline(events, null)
  assert.ok(!t.summarizer.steps.some(s => s.id === 'future_step'))
  assert.equal(t.summarizer.steps.find(s => s.id === 'judge')!.subs![1].state, 'done')
})
