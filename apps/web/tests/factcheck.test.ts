// Run with:  pnpm test   (tsx --test tests/*.test.ts). Pure logic and fixtures only: no browser, no network.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  checkedByJudge, countsOf, elapsedLabel, EMPTY_STATE, factCheckRan, factProgress, factSummaryLine, factTotals, failedSubQuestionsNote, judgeFailuresNote,
  labelView, mustShowDisagreement, NEAR_HEADING, PARTIAL_HINT, progressLine, sourcesLine, splitEvidence, STAGE_FAILED_NOTE, STAGE_SKIPPED_LABEL, STRENGTH_TOOLTIP, strengthOf,
} from '../lib/factcheck'
import { stageStateLabel } from '../lib/format'
import { demoFactChecks, demoFactTotals, withFactcheckFixtures } from '../lib/demo-factcheck'
import { demoReport } from '../lib/demo-report'
import { buildTimeline } from '../lib/timeline'
import type { EventName, FactClaim, StageId, WorkflowEvent } from '../lib/trace-types'

// ---------------------------------------------------------------------------------------------------------------- labels, strength, evidence
test('the three labels never say true or false, and an unverified claim is never styled like a fact', () => {
  const s = labelView('supported'), u = labelView('unverified'), c = labelView('contradicted')
  assert.equal(s.tone, 'mint'); assert.equal(c.tone, 'coral'); assert.equal(u.tone, 'neutral')
  assert.equal(u.text, 'Not yet confirmed by a second source')
  for (const v of [s, u, c]) assert.ok(!/\b(true|false|fact|proven|wrong)\b/i.test(v.text), v.text)
  assert.match(s.hint, /not proof/i)
  assert.match(u.hint, /does not mean it is false/i)
  assert.equal(c.hint, 'One source asserts the opposite; the other source may be the wrong one.')
})

test('an unknown label gets a neutral chip with its own word, not a crash', () => {
  const v = labelView('partly_supported')
  assert.equal(v.tone, 'neutral'); assert.equal(v.kind, 'other'); assert.equal(v.text, 'Partly_supported')
  assert.equal(labelView(null).text, 'Unlabelled')
})

test('strength is a bar and a word, never a percent, and the tooltip says it is a ranking', () => {
  assert.equal(strengthOf(0.2).word, 'low'); assert.equal(strengthOf(0.5).word, 'medium'); assert.equal(strengthOf(0.9).word, 'high')
  assert.equal(strengthOf(0.95).fraction, 1)
  assert.equal(strengthOf(2).fraction, 1, 'out of range is clamped')
  assert.equal(strengthOf(null).level, 'unknown'); assert.equal(strengthOf(Number.NaN).level, 'unknown')
  for (const c of [0, 0.3, 0.6, 0.95]) assert.ok(!/%|percent|probab/i.test(strengthOf(c).word))
  assert.equal(STRENGTH_TOOLTIP, 'A ranking of how much independent evidence backs the claim; not the chance that it is true.')
})

test('contradicted and contested claims must show the disagreeing source; the evidence is split by relation', () => {
  assert.ok(mustShowDisagreement({ label: 'contradicted', contested: false }))
  assert.ok(mustShowDisagreement({ label: 'supported', contested: true }))
  assert.ok(!mustShowDisagreement({ label: 'supported', contested: false }))
  assert.ok(!mustShowDisagreement({ label: 'unverified', contested: false }))
  const claim = demoFactChecks()['demo-sq-1']!.claims[0]
  const sp = splitEvidence(claim)
  assert.equal(sp.contradicts.length, 1); assert.equal(sp.supports.length, 1); assert.equal(sp.other.length, 0)
  const odd = splitEvidence({ evidence: [{ sourceId: 'x', sourceTitle: null, quote: 'q', relation: 'mentions' }] })
  assert.equal(odd.other.length, 1, 'an unknown relation is kept, not dropped')
  assert.deepEqual(splitEvidence({ evidence: undefined as unknown as FactClaim['evidence'] }), { supports: [], contradicts: [], near: [], other: [] })
})

test('counts come from `counts`, or from the claims when they are missing', () => {
  const fc = demoFactChecks()['demo-sq-1']!
  assert.deepEqual(countsOf(fc), { supported: 1, partially_supported: 1, unverified: 1, contradicted: 1, contested: 0 })
  assert.deepEqual(countsOf({ counts: undefined as never, claims: fc.claims, disagreements: [] }), { supported: 1, partially_supported: 1, unverified: 1, contradicted: 1, contested: 0 })
  assert.deepEqual(countsOf(null), { supported: 0, partially_supported: 0, unverified: 0, contradicted: 0, contested: 0 })
  assert.equal(factSummaryLine({ supported: 2, partially_supported: 1, unverified: 3, contradicted: 1, contested: 0 }), '2 supported · 1 partly supported · 3 not yet confirmed · 1 contradicted')
  assert.match(factSummaryLine({ supported: 2, partially_supported: 1, unverified: 3, contradicted: 1, contested: 1 }), /2 supported · 1 partly supported · 3 not yet confirmed · 1 contradicted · 1 contested/)
})

// ---------------------------------------------------------------------------------------------------------------- the report
test('Stage 4 off: nothing about it is shown, and the stage is not_run', () => {
  const r = demoReport('demo-x', 'q?', null)
  assert.equal(r.stages.factcheck, 'not_run')
  assert.equal(r.totals.factChecked, null)
  assert.equal(factTotals(r), null, 'the summary row is hidden')
  assert.ok(!factCheckRan(r))
  assert.ok(r.subQuestions.every(sq => sq.factCheck == null))
  assert.match(r.limitations[1], /^Stage 4 \(fact checking\) did not run/, 'the line that says Stage 4 did not run is kept')
  assert.equal(stageStateLabel.not_run, STAGE_SKIPPED_LABEL)
  assert.equal(STAGE_SKIPPED_LABEL, 'skipped (switched off)')
})

test('Stage 4 on: contradicted, supported, partially_supported, unverified; a supported claim with two sources, one checked by the judge', () => {
  const r = demoReport('demo-x', 'q?', null, 'on')
  assert.equal(r.stages.factcheck, 'completed')
  assert.ok(factCheckRan(r))
  const sq1 = r.subQuestions.find(s => s.id === 'demo-sq-1')!.factCheck!
  assert.deepEqual(sq1.claims.map(c => c.label), ['contradicted', 'supported', 'partially_supported', 'unverified'])
  const supported = sq1.claims[1]
  assert.equal(supported.supportDocCount, 2)
  assert.equal(supported.evidence.length, 2)
  assert.deepEqual(supported.evidence.map(e => checkedByJudge(e)), [true, false], 'one quote was already checked by the Stage 3 judge')
  assert.ok(sq1.claims[2].supportDocCount === 1 && sq1.claims[2].confidence! <= 0.6, 'a partially supported claim still rests on one source and never exceeds 0.6')
  assert.ok(sq1.claims[3].supportDocCount === 1 && sq1.claims[3].confidence! <= 0.5, 'an unverified claim rests on one source and never exceeds 0.5')
  // the contradicted claim comes with the disagreeing source and a disagreement card
  assert.ok(splitEvidence(sq1.claims[0]).contradicts.length > 0)
  assert.equal(sq1.disagreements.length, 1)
  assert.ok(sq1.disagreements[0].quoteA && sq1.disagreements[0].quoteB && sq1.disagreements[0].reason)
  assert.deepEqual(r.totals.factChecked, demoFactTotals())
  assert.ok(r.limitations.some(l => l.startsWith('Stage 4 compared the claims across sources.')))
  assert.ok(r.limitations.some(l => l.startsWith('Sources disagree (')))
})

test('Stage 4 on: an empty result, a sub-question that was not cross-checked, and long texts', () => {
  const r = demoReport('demo-x', 'q?', null, 'on')
  const sq2 = r.subQuestions.find(s => s.id === 'demo-sq-2')!.factCheck
  assert.ok(sq2 && sq2.claims.length === 0, 'factCheck is not null but claims is []: the empty state')
  assert.equal(EMPTY_STATE, 'No claim could be cross-checked for this sub-question.')
  assert.equal(r.subQuestions.find(s => s.id === 'demo-sq-3')!.factCheck, null, 'ran, but not for this sub-question')
  const sq4 = r.subQuestions.find(s => s.id === 'demo-sq-4')!.factCheck!
  assert.ok(sq4.claims[0].claim.length > 250 && sq4.claims[0].evidence[0].quote.length > 250)
  assert.ok(sq4.claims[0].contested && mustShowDisagreement(sq4.claims[0]) && splitEvidence(sq4.claims[0]).contradicts.length > 0, 'a contested claim shows its disagreeing source')
  assert.ok(sq4.disagreements[0].claimA.length > 250)
  // the fixture can be applied twice without changing the result (it works on a copy)
  const again = withFactcheckFixtures(r, 'on')
  assert.deepEqual(again.totals.factChecked, r.totals.factChecked)
})

test('old reports without any of the new fields are read without a crash', () => {
  const r = demoReport('demo-x', 'q?', null)
  delete (r.totals as { factChecked?: unknown }).factChecked
  for (const sq of r.subQuestions) delete (sq as { factCheck?: unknown }).factCheck
  assert.equal(factTotals(r), null); assert.ok(!factCheckRan(r))
})

// ---------------------------------------------------------------------------------------------------------------- the event sequence
let seq = 0
const T0 = Date.parse('2026-11-07T10:00:00Z')
function ev(event: EventName, stage: StageId | null, data: Record<string, unknown> = {}, message = '', atSec = seq, status: string | null = null): WorkflowEvent {
  return { seq: seq++, event, stage, status, message, data, timestamp: new Date(T0 + atSec * 1000).toISOString() }
}
const fstep = (stepId: string, state: string, data: Record<string, unknown>, atSec: number) => ev('step', 'factcheck', { lane: 'factcheck', step: stepId, state, ...data }, '', atSec, state)

function runUpToStage4(): WorkflowEvent[] {
  seq = 0
  return [
    ev('run_queued', null, {}, 'Run queued', 0), ev('run_started', null, {}, 'Run started', 1),
    ev('stage_started', 'planner', {}, '', 2), ev('stage_completed', 'planner', { subQuestions: 5, queries: 15, topics: ['a', 'b', 'c', 'd', 'e'] }, '', 30),
    ev('stage_started', 'retrieval', {}, '', 31), ev('stage_completed', 'retrieval', {}, '', 400),
    ev('stage_started', 'summarizer', {}, '', 401),
    ev('step', 'summarizer', { lane: 'summarizer', step: 'judge', state: 'completed', done: 5, total: 5, sufficientSubQuestions: 3 }, '', 900, 'completed'),
    ev('stage_completed', 'summarizer', { digests: 20, subQuestions: 5, sufficientSubQuestions: 3 }, '', 910),
  ]
}

test('no fact-check event: no progress, no lane (a run without Stage 4 looks as before)', () => {
  const events = runUpToStage4()
  assert.equal(factProgress(events), null)
  assert.equal(buildTimeline(events, null).factcheck, null)
  assert.equal(factProgress([]), null)
})

test('the steps of a running stage give the line "sub-question 2 of 5 - looking for sources that disagree" and the time it started', () => {
  const events = runUpToStage4()
  events.push(ev('stage_started', 'factcheck', {}, 'Checking claims across sources', 911))
  events.push(fstep('branch', 'running', {}, 912))                                   // a step nobody documented: ignored
  assert.equal(factProgress(events)!.line, 'Checking claims across sources')
  events.push(fstep('claims', 'running', { subQuestion: 1, subQuestions: 5, sources: 4 }, 920))
  assert.equal(factProgress(events)!.line, 'Checking claims across sources: sub-question 1 of 5 - reading the claims of each source')
  events.push(fstep('conflicts', 'running', { subQuestion: 2, subQuestions: 5 }, 1100))
  const p = factProgress(events)!
  assert.equal(p.state, 'running')
  assert.equal(p.line, 'Checking claims across sources: sub-question 2 of 5 - looking for sources that disagree')
  assert.equal(p.startedAt, new Date(T0 + 911 * 1000).toISOString())
  assert.equal(elapsedLabel(p.startedAt, T0 + 1151 * 1000), '4 min 0 s', 'elapsed time since the stage started')
  assert.equal(elapsedLabel(p.startedAt, T0 + 925 * 1000), '14 s')
  assert.equal(elapsedLabel(null, 0), null)
  assert.equal(progressLine('nonsense', 2, 5), 'Checking claims across sources: sub-question 2 of 5', 'an unknown step leaves out the tail')
  assert.equal(progressLine('claims', null, null), 'Checking claims across sources - reading the claims of each source')
})

test('malformed step data is ignored, never a crash', () => {
  const events = runUpToStage4()
  events.push(ev('stage_started', 'factcheck', {}, '', 911))
  events.push(ev('step', 'factcheck', { lane: 'factcheck', step: 'claims', subQuestion: 'two', subQuestions: null }, '', 912))
  events.push(ev('step', 'factcheck', { lane: 'factcheck' }, '', 913))
  events.push(ev('step', 'factcheck', {}, '', 914))
  assert.equal(factProgress(events)!.line, 'Checking claims across sources - reading the claims of each source')
})

test('the timeline lane: the latest step is running, the earlier ones are done, steps that never reported are pending; the summarizer lane is untouched', () => {
  const events = runUpToStage4()
  const before = JSON.stringify(buildTimeline(events, null).summarizer)
  events.push(ev('stage_started', 'factcheck', {}, '', 911))
  events.push(fstep('claims', 'running', { subQuestion: 1, subQuestions: 5, sources: 4 }, 920))
  events.push(fstep('clusters', 'running', { subQuestion: 1, subQuestions: 5, claims: 9 }, 930))
  const lane = buildTimeline(events, null).factcheck!
  assert.equal(lane.status, 'running')
  const by = (id: string) => lane.steps.find(s => s.id === id)!
  assert.equal(by('claims').status, 'completed'); assert.equal(by('clusters').status, 'running'); assert.equal(by('support').status, 'pending')
  assert.ok(by('clusters').chips.includes('sub-question 1 of 5') && by('clusters').chips.includes('9 claims'), by('clusters').chips.join(' | '))
  assert.equal(JSON.stringify(buildTimeline(events, null).summarizer), before)
})

test('completed: the totals, the judge-failure warning and the sub-questions that failed', () => {
  const events = runUpToStage4()
  events.push(ev('stage_started', 'factcheck', {}, '', 911))
  events.push(fstep('store', 'completed', { claims: 12 }, 1900))
  events.push(ev('stage_completed', 'factcheck', { claims: 12, subQuestions: 5, failedSubQuestions: 1, supported: 3, partially_supported: 2, unverified: 7, contradicted: 2, contested: 1, disagreements: 2, judgeFailures: 4 }, 'Checked 12 claims', 1910, 'completed'))
  const p = factProgress(events)!
  assert.equal(p.state, 'completed')
  assert.deepEqual([p.result!.claims, p.result!.supported, p.result!.unverified, p.result!.contradicted, p.result!.contested, p.result!.disagreements], [12, 3, 7, 2, 1, 2])
  assert.equal(p.result!.partiallySupported, 2)
  assert.equal(judgeFailuresNote(p), '4 judge answers failed; labels for that part are conservative.')
  assert.equal(failedSubQuestionsNote(p), 'Fact checking failed for 1 of 5 sub-questions; their claims are not cross-checked.')
  assert.equal(buildTimeline(events, null).factcheck!.status, 'completed')
  // judgeFailures 0 or missing: no warning
  const ok = runUpToStage4(); ok.push(ev('stage_started', 'factcheck'), ev('stage_completed', 'factcheck', { claims: 3, judgeFailures: 0 }))
  assert.equal(judgeFailuresNote(factProgress(ok)), null)
  assert.equal(judgeFailuresNote(null), null)
})

test('a failed fact-check stage: the warning, the error, and the run is still completed', () => {
  const events = runUpToStage4()
  events.push(ev('stage_started', 'factcheck', {}, '', 911))
  events.push(fstep('claims', 'running', { subQuestion: 1, subQuestions: 5 }, 920))
  events.push(ev('stage_completed', 'factcheck', { error: 'ConnectionError: gone' }, 'Fact checking failed: ConnectionError: gone', 1000, 'failed'))
  events.push(ev('run_completed', null, { reportUrl: '/x', stagesNotRun: ['report'] }, 'Run finished', 1001, 'completed'))
  const p = factProgress(events)!
  assert.equal(p.state, 'failed'); assert.equal(p.error, 'ConnectionError: gone'); assert.equal(p.result, null)
  assert.equal(STAGE_FAILED_NOTE, 'Fact checking failed; the evidence below is not cross-checked.')
  const lane = buildTimeline(events, null).factcheck!
  assert.equal(lane.status, 'failed')
  assert.ok(!lane.steps.some(s => s.status === 'running'), 'the step that was running is marked failed')
  assert.equal(lane.steps.find(s => s.id === 'claims')!.status, 'failed')
  // the other lanes do not read the run as failed
  const t = buildTimeline(events, null)
  assert.equal(t.summarizer.status, 'completed')
  // run_completed after it: nothing marks the whole run as failed
  assert.ok(!events.some(e => e.event === 'run_failed'))
})

// ---------------------------------------------------------------------------------------------------------------- partially_supported
test('a partly supported claim is not styled like a fact: not green, not grey, and its hint calls it a lead', () => {
  const p = labelView('partially_supported'), s = labelView('supported'), u = labelView('unverified')
  assert.equal(p.kind, 'partially_supported'); assert.equal(p.text, 'Partly supported'); assert.equal(p.short, 'Partly supported')
  assert.notEqual(p.tone, s.tone, 'not the green of a supported claim'); assert.notEqual(p.tone, 'mint')
  assert.notEqual(p.tone, u.tone, 'and not a bare unconfirmed claim either')
  assert.equal(p.hint, PARTIAL_HINT)
  assert.match(p.hint, /close variant/); assert.match(p.hint, /A lead, not a confirmed fact/)
  assert.ok(!/\b(true|false|fact|proven|wrong)\b/i.test(p.text), p.text)
  assert.equal(labelView('Partially_Supported').kind, 'partially_supported', 'case does not matter')
  assert.ok(!mustShowDisagreement({ label: 'partially_supported', contested: false }), 'it has no disagreeing source of its own')
  assert.ok(mustShowDisagreement({ label: 'partially_supported', contested: true }), 'but a contested one still shows it')
})

test('a partly supported claim never reads as two-source agreement', () => {
  const claim = (label: string, n: number) => ({ label, supportDocCount: n })
  assert.equal(sourcesLine(claim('partially_supported', 1)), 'Rests on one source, plus a close variant in another')
  assert.equal(sourcesLine(claim('partially_supported', 2)), 'Rests on one source, plus a close variant in another', 'even if the server sent a wrong count')
  for (const n of [1, 2]) assert.ok(!/\b(2|two|independent|sources)\b/i.test(sourcesLine(claim('partially_supported', n))), sourcesLine(claim('partially_supported', n)))
  assert.equal(sourcesLine(claim('supported', 2)), '2 independent sources')
  assert.equal(sourcesLine(claim('unverified', 1)), '1 independent source')
})

test('a missing partially_supported count means 0 (old reports and old events)', () => {
  const old = { counts: { supported: 1, unverified: 2, contradicted: 0, contested: 0 }, claims: [], disagreements: [] }
  assert.equal(countsOf(old).partially_supported, 0)
  assert.equal(countsOf({ ...old, counts: { ...old.counts, partially_supported: 3 } }).partially_supported, 3)
  const r = demoReport('demo-x', 'q?', null, 'on')
  r.totals.factChecked = { supported: 1, unverified: 2, contradicted: 0, contested: 0 }
  assert.equal(factTotals(r)!.partially_supported, 0)
  assert.match(factSummaryLine(factTotals(r)!), /1 supported · 0 partly supported · 2 not yet confirmed/)
  // an old stage_completed event: no partially_supported in its data
  const events = runUpToStage4(); events.push(ev('stage_started', 'factcheck'), ev('stage_completed', 'factcheck', { claims: 5, supported: 2, unverified: 3 }))
  const p = factProgress(events)!
  assert.equal(p.result!.partiallySupported, null, 'the parser does not invent a number')
  assert.equal(p.result!.supported, 2)
})

test('the near_match row is kept apart, with the other document\'s own wording', () => {
  const sq1 = demoReport('demo-x', 'q?', null, 'on').subQuestions.find(s => s.id === 'demo-sq-1')!.factCheck!
  const partial = sq1.claims.find(c => c.label === 'partially_supported')!
  const rows = partial.evidence
  assert.equal(rows[rows.length - 1].relation, 'near_match', 'the near-match row is the last one')
  assert.equal(rows.filter(e => e.relation === 'near_match').length, 1)
  const sp = splitEvidence(partial)
  assert.equal(sp.near.length, 1); assert.equal(sp.supports.length, 1); assert.equal(sp.contradicts.length, 0); assert.equal(sp.other.length, 0)
  assert.ok(sp.near[0].nearClaim && sp.near[0].nearClaim !== partial.claim, 'nearClaim is their wording, not the claim itself')
  assert.ok(sp.near[0].quote && sp.near[0].sourceTitle)
  assert.equal(partial.supportDocCount, 1)
  assert.equal(NEAR_HEADING, 'Close variant in another source')
  // the support rows of a supported claim carry no nearClaim
  assert.ok(sq1.claims.filter(c => c.label !== 'partially_supported').every(c => c.evidence.every(e => e.nearClaim == null && e.relation !== 'near_match')))
})

test('a sub-question with only partly supported and unverified claims, and a very long close variant', () => {
  const r = demoReport('demo-x', 'q?', null, 'on')
  const sq5 = r.subQuestions.find(s => s.id === 'demo-sq-5')!
  assert.deepEqual(sq5.factCheck!.claims.map(c => c.label), ['partially_supported', 'partially_supported', 'unverified'])
  assert.equal(sq5.factCheck!.counts.supported, 0)
  assert.ok(sq5.factCheck!.claims[0].evidence.some(e => e.relation === 'near_match' && (e.nearClaim ?? '').length > 250), 'a long nearClaim')
  assert.equal(r.totals.subQuestions, r.subQuestions.length)
  assert.equal(r.totals.sources, r.subQuestions.reduce((n, s) => n + s.sources.length, 0))
  const expected = r.subQuestions.flatMap(s => s.factCheck?.claims ?? []).filter(c => c.label === 'partially_supported').length
  assert.equal(r.totals.factChecked!.partially_supported, expected)
  assert.equal(demoFactTotals().partially_supported, expected)
  assert.ok(r.limitations.some(l => l.startsWith('Stage 4 compared the claims across sources.') && l.includes('"partially supported" means it rests on one document and another document states a close variant')))
})

test('an unknown label still falls back to other and is never shown as a fact', () => {
  for (const w of ['mostly_supported', 'true', 'confirmed', 'partially']) {
    const v = labelView(w)
    assert.equal(v.kind, 'other', w); assert.equal(v.tone, 'neutral', w)
  }
  assert.equal(labelView(undefined).kind, 'other')
  assert.equal(labelView('').kind, 'other')
  // an unknown label does not count as supported or partly supported
  const fc = { counts: undefined as never, claims: [{ claim: 'x', label: 'mostly_supported', confidence: 0.9, supportDocCount: 3, contraDocCount: 0, contested: false, evidence: [] }], disagreements: [] }
  const c = countsOf(fc)
  assert.deepEqual([c.supported, c.partially_supported, c.unverified, c.contradicted], [0, 0, 0, 0])
})
