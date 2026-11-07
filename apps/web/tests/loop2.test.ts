// Run with:  pnpm test   (tsx --test tests/*.test.ts). Pure logic only: no browser, no network.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { stanceInfo } from '../lib/format'
import {
  aspectStateHint, digestWarning, ladderLabel, loop2AspectView, loop2Summary, noEvidenceGaps, secondsLabel, sufficiencyMeaning, sufficiencyNote, synthesisAspects,
} from '../lib/loop2'
import { demoReport } from '../lib/demo-report'
import { buildTimeline } from '../lib/timeline'
import type { Coverage, EventName, Loop2, StageId, WorkflowEvent } from '../lib/trace-types'

// ---------------------------------------------------------------------------------------------------------------- labels and numbers
test('the three ladder steps have plain-language labels, and an unknown step is passed through', () => {
  assert.equal(ladderLabel('reselect'), 're-reading papers we already have')
  assert.equal(ladderLabel('pool'), 'reading more papers from the search results')
  assert.equal(ladderLabel('queries'), 'searching with new queries')
  assert.equal(ladderLabel('synthesis'), 'combining the findings of several sources')
  assert.equal(ladderLabel('future_rung'), 'future_rung')
  assert.equal(ladderLabel(null), 'an unknown step')
})

test('seconds are shown as a person would say them', () => {
  assert.equal(secondsLabel(0.4), 'under a second')
  assert.equal(secondsLabel(18.5), '19 s')
  assert.equal(secondsLabel(60), '1 min')
  assert.equal(secondsLabel(178.7), '2 min 59 s')
  assert.equal(secondsLabel(1200), '20 min')
  for (const bad of [null, undefined, NaN, -5, Infinity]) assert.equal(secondsLabel(bad as number), 'unknown time')
})

test('the one-line summary of a second search', () => {
  assert.equal(loop2Summary({ searched: 4, covered: 3, seconds: 120 }), 'searched 4 aspects, found evidence for 3, 2 min')
  assert.equal(loop2Summary({ searched: 1, covered: 0, seconds: 18.5 }), 'searched 1 aspect, found evidence for 0, 19 s')
})

// ---------------------------------------------------------------------------------------------------------------- aspect statuses
test('every aspect status of the second search is shown the way the spec says', () => {
  const v = (status: string, extra = {}) => loop2AspectView({ status, ...extra })
  assert.deepEqual([v('covered', { coveredBy: 'pool' }).label, v('covered', { coveredBy: 'pool' }).tone], ['Covered', 'mint'])
  assert.match(v('covered', { coveredBy: 'synthesis' }).detail, /combining the findings of several sources/)
  assert.match(v('covered', { coveredBy: 'queries' }).detail, /searching with new queries/)
  assert.deepEqual([v('known_gap_no_evidence').label, v('known_gap_no_evidence').tone, v('known_gap_no_evidence').blocksSufficient], ['Evidence not found', 'neutral', false])
  assert.deepEqual([v('known_gap', { nearMiss: true }).label, v('known_gap', { nearMiss: true }).tone, v('known_gap', { nearMiss: true }).blocksSufficient], ['Partly answered', 'amber', true])
  for (const nm of [false, null, undefined]) assert.deepEqual([v('known_gap', { nearMiss: nm }).label, v('known_gap', { nearMiss: nm }).tone], ['Not found', 'amber'])
  assert.deepEqual([v('known_gap_skipped_triage').label, v('known_gap_skipped_triage').blocksSufficient], ['Not searched', false])
  assert.deepEqual([v('known_gap_skipped_cap').label, v('known_gap_skipped_cap').blocksSufficient], ['Not searched', true])
  assert.deepEqual([v('unjudged_not_searched').label, v('unjudged_not_searched').tone], ['Not judged', 'neutral'])
})

test('an unknown aspect status is shown as itself, neutrally, and never throws', () => {
  const x = loop2AspectView({ status: 'brand_new_status' })
  assert.deepEqual([x.label, x.tone, x.blocksSufficient], ['Brand new status', 'neutral', false])
  assert.equal(loop2AspectView({ status: '' }).label, 'Unknown')
  assert.doesNotThrow(() => loop2AspectView({ status: undefined as unknown as string }))
})

test('the judge states keep their meaning: an unjudged aspect is never described as covered', () => {
  assert.match(aspectStateHint('unjudged') ?? '', /not counted as covered/)
  assert.match(aspectStateHint('judged_insufficient') ?? '', /too few/)
  assert.match(aspectStateHint('no_candidates') ?? '', /nothing to judge/i)
  assert.equal(aspectStateHint('covered'), undefined)
})

// ---------------------------------------------------------------------------------------------------------------- sufficiency
const cov = (over: Partial<Coverage>): Coverage => ({ sufficient: true, judgeUsed: true, sourceCount: 4, fullTextSourceCount: 2, digestFailures: 0, aspects: [], uncoveredAspects: [], unjudgedAspects: [], fallbackReason: null, ...over })
const l2 = (over: Partial<Loop2> = {}): Loop2 => ({ searched: 2, covered: 1, seconds: 60, ...over })

test('"sufficient, with gaps" appears only when sufficient is true and the strict value is false', () => {
  assert.equal(sufficiencyNote(cov({ loop2: l2({ sufficientStrict: false }) })), 'Sufficient, with gaps where no evidence was found.')
  assert.equal(sufficiencyNote(cov({ loop2: l2({ sufficientStrict: true }) })), null)
  assert.equal(sufficiencyNote(cov({ loop2: l2({ sufficientStrict: null }) })), null)            // older runs
  assert.equal(sufficiencyNote(cov({ loop2: l2() })), null)
  assert.equal(sufficiencyNote(cov({ sufficient: false, loop2: l2({ sufficientStrict: false }) })), null)
  assert.equal(sufficiencyNote(cov({ loop2: null })), null)
  assert.equal(sufficiencyNote(cov({})), null)                                                    // loop2 absent
  assert.equal(sufficiencyNote(null), null)
})

test('"evidence not found" gaps are listed from the second search only, and tolerate odd data', () => {
  assert.deepEqual(noEvidenceGaps(cov({ loop2: l2({ knownGapsNoEvidence: ['a', 'b'] }) })), ['a', 'b'])
  assert.deepEqual(noEvidenceGaps(cov({})), [])
  assert.deepEqual(noEvidenceGaps(cov({ loop2: null })), [])
  assert.deepEqual(noEvidenceGaps(cov({ loop2: l2({ knownGapsNoEvidence: undefined }) })), [])
  assert.deepEqual(noEvidenceGaps(cov({ loop2: l2({ knownGapsNoEvidence: 'oops' as unknown as string[] }) })), [])
  assert.deepEqual(noEvidenceGaps(cov({ loop2: l2({ knownGapsNoEvidence: ['x', '', null as unknown as string] }) })), ['x'])
  assert.deepEqual(noEvidenceGaps(null), [])
})

test('what "sufficient" means stays exactly as before unless the core gap rule ran, and never claims the question is answered', () => {
  const before = '“Sufficient” means each aspect has at least two independent supporting sources. It does not mean the question is answered.'
  assert.equal(sufficiencyMeaning(cov({})), before)
  assert.equal(sufficiencyMeaning(cov({ loop2: null })), before)
  assert.equal(sufficiencyMeaning(cov({ loop2: l2({ gapRule: null }) })), before)
  assert.equal(sufficiencyMeaning(cov({ loop2: l2({ gapRule: 'strict' }) })), before)
  const core = sufficiencyMeaning(cov({ loop2: l2({ gapRule: 'core' }) }))
  assert.match(core, /every aspect that has evidence is covered/)
  assert.match(core, /does not mean the question is answered/)
})

test('failed digests produce a warning that "no evidence" may be wrong', () => {
  assert.equal(digestWarning(cov({ digestFailures: 0 })), null)
  assert.equal(digestWarning(cov({ digestFailures: null })), null)
  assert.equal(digestWarning(null), null)
  assert.match(digestWarning(cov({ digestFailures: 1 })) ?? '', /^1 source could not be read.*no evidence.*may be wrong/)
  assert.match(digestWarning(cov({ digestFailures: 8 })) ?? '', /^8 sources could not be read/)
})

test('aspects covered by synthesis are counted, other ways of covering are not', () => {
  const rows = [{ index: 0, text: 'a', state: 'covered' as const, coveredBy: 'synthesis', yesVerdicts: 3, sources: 3 }, { index: 1, text: 'b', state: 'covered' as const, coveredBy: 'single_claims', yesVerdicts: 2, sources: 2 }, { index: 2, text: 'c', state: 'covered' as const, yesVerdicts: 2, sources: 2 }]
  assert.equal(synthesisAspects({ aspects: rows }), 1)
  assert.equal(synthesisAspects(null), 0)
})

test('a stance the model invents is shown, not crashed on', () => {
  assert.equal(stanceInfo('challenges').group, 'opposes')
  assert.equal(stanceInfo('sort of agrees').label, 'Sort of agrees')
  assert.equal(stanceInfo(null).label, 'Unclassified')
})

// ---------------------------------------------------------------------------------------------------------------- the event sequence
let seq = 0
const T0 = Date.parse('2026-11-07T10:00:00Z')
function ev(event: EventName, stage: StageId | null, data: Record<string, unknown> = {}, message = '', atSec = seq): WorkflowEvent {
  return { seq: seq++, event, stage, status: null, message, data, timestamp: new Date(T0 + atSec * 1000).toISOString() }
}
const step = (lane: string, stepId: string, state: string, data: Record<string, unknown>, message: string, atSec: number) => ev('step', lane === 'summarizer' ? 'summarizer' : 'retrieval', { lane, step: stepId, state, ...data }, message, atSec)

function baseEvents(): WorkflowEvent[] {
  seq = 0
  return [
    ev('run_queued', null, {}, 'Run queued', 0), ev('run_started', null, {}, 'Run started', 1),
    ev('stage_started', 'planner', {}, '', 2), ev('stage_completed', 'planner', { subQuestions: 3, queries: 9, topics: ['a', 'b', 'c'] }, '', 30),
    ev('stage_started', 'retrieval', {}, '', 31), ev('stage_completed', 'retrieval', {}, '', 400),
    ev('stage_started', 'summarizer', {}, '', 401),
    step('summarizer', 'prepare', 'completed', { jobs: 8, papers: 5, web: 3 }, '8 sources to read', 410),
    step('summarizer', 'digest', 'completed', { done: 8, total: 8, failures: 0 }, 'Read 8 sources', 500),
  ]
}

const summarizerSteps = (events: WorkflowEvent[]) => buildTimeline(events, null).summarizer.steps
const loop2Step = (events: WorkflowEvent[]) => summarizerSteps(events).find(s => s.id === 'loop2')

test('judge -> loop2 (running x2) -> judge -> loop2 (running x2, completed) -> judge: the sub-step appears, ticks, and completes', () => {
  const events = baseEvents()
  events.push(step('summarizer', 'judge', 'running', { done: 1, total: 3 }, 'Judged sub-question 1 of 3', 510))
  assert.equal(loop2Step(events), undefined, 'no loop2 event yet: the step is not in the lane')

  events.push(step('summarizer', 'loop2', 'running', { loop2Step: 'reselect', aspects: 2 }, "Loop 2 (reselect): 2 aspect(s) of 'X'", 520))
  let s = loop2Step(events)!
  assert.equal(s.label, 'Searching again for missing evidence')
  assert.equal(s.status, 'running')
  assert.ok(s.startedAt && !s.endedAt, 'it has a start (for the elapsed time) and no end yet')
  assert.ok(s.chips.some(c => c === 'now: re-reading papers we already have (2 aspects)'), s.chips.join(' | '))

  events.push(step('summarizer', 'loop2', 'running', { subQuestion: 'X', searched: 2, covered: 1 }, "Loop 2 searched again: 'X'", 560))
  events.push(step('summarizer', 'judge', 'running', { done: 2, total: 3 }, 'Judged sub-question 2 of 3', 570))
  events.push(step('summarizer', 'loop2', 'running', { loop2Step: 'pool', aspects: 1 }, "Loop 2 (pool): 1 aspect(s) of 'Y'", 580))
  s = loop2Step(events)!
  assert.ok(s.chips.some(c => c.startsWith('now: reading more papers from the search results')), s.chips.join(' | '))
  assert.ok(s.chips.includes('2 aspects searched again') && s.chips.includes('1 covered'), s.chips.join(' | '))

  events.push(step('summarizer', 'loop2', 'running', { subQuestion: 'Y', searched: 1, covered: 0 }, "Loop 2 searched again: 'Y'", 600))
  events.push(step('summarizer', 'judge', 'running', { done: 3, total: 3 }, 'Judged sub-question 3 of 3', 610))
  events.push(step('summarizer', 'loop2', 'completed', { searched: 3, covered: 1 }, 'Loop 2 finished', 620))
  events.push(step('summarizer', 'judge', 'completed', { done: 3, total: 3, sufficientSubQuestions: 1 }, '1 of 3 have enough evidence', 621))
  s = loop2Step(events)!
  assert.equal(s.status, 'completed')
  assert.equal(s.endedAt, new Date(T0 + 620 * 1000).toISOString())
  assert.equal(s.startedAt, new Date(T0 + 520 * 1000).toISOString(), 'elapsed time runs from the first loop2 event to the last: 100 s')
  assert.deepEqual(s.chips, ['3 aspects searched again', '1 covered'])
  assert.equal(s.progress, null)

  const order = summarizerSteps(events).map(x => x.id)
  assert.deepEqual(order, ['prepare', 'digest', 'judge', 'loop2', 'store'], 'it sits between judge and store')
  const judge = summarizerSteps(events).find(x => x.id === 'judge')!
  assert.equal(judge.status, 'completed')
  assert.ok(judge.chips.includes('includes the second search'), 'the judge span contains the loop2 time, and says so')
})

test('without Loop 2 the summarizer lane is exactly as before', () => {
  const events = baseEvents()
  events.push(step('summarizer', 'judge', 'completed', { done: 3, total: 3, sufficientSubQuestions: 2 }, 'done', 510))
  events.push(step('summarizer', 'store', 'completed', { stored: 8 }, 'Saved', 520))
  const steps = summarizerSteps(events)
  assert.deepEqual(steps.map(s => s.id), ['prepare', 'digest', 'judge', 'store'])
  assert.ok(!steps.find(s => s.id === 'judge')!.chips.includes('includes the second search'))
})

test('unknown steps, unknown loop2 rungs and malformed data are ignored, never thrown on', () => {
  const events = baseEvents()
  events.push(step('summarizer', 'a_step_from_the_future', 'running', { x: 1 }, 'whatever', 505))
  events.push(step('mystery_lane', 'x', 'running', {}, 'lane nobody knows', 506))
  events.push(step('summarizer', 'loop2', 'running', { loop2Step: 'teleport', aspects: 'many' }, 'odd', 510))
  events.push(step('summarizer', 'loop2', 'running', { subQuestion: 7, searched: 'lots', covered: null }, 'odd too', 511))
  events.push(step('summarizer', 'loop2', 'running', {}, '', 512))
  let model = buildTimeline(events, null)
  assert.deepEqual(model.summarizer.steps.map(s => s.id), ['prepare', 'digest', 'judge', 'loop2', 'store'], 'only the known steps are shown; the unknown one is ignored')
  assert.ok(!model.summarizer.steps.some(s => s.id === 'a_step_from_the_future') && model.retrieval.lanes.every(l => l.id !== ('mystery_lane' as never)))
  const s = loop2Step(events)!
  assert.equal(s.status, 'running')
  assert.ok(s.chips.includes('now: teleport'), 'an unknown rung is shown as its own word: ' + s.chips.join(' | '))
  assert.ok(s.chips.every(c => typeof c === 'string' && c.length > 0))
  model = buildTimeline([...events, ev('run_failed', 'summarizer', {}, 'RuntimeError: boom', 700)], null)
  assert.equal(model.summarizer.status, 'failed')
  assert.equal(loop2Step([...events, ev('run_failed', 'summarizer', {}, 'boom', 700)])!.status, 'failed', 'the step that was running when the run failed is marked failed')
})

// ---------------------------------------------------------------------------------------------------------------- fixtures
test('the demo fixtures cover every Loop 2 case the UI has to handle', () => {
  const r = demoReport('demo-x', 'Q?', null)
  const by = (id: string) => r.subQuestions.find(s => s.id === id)!
  assert.equal(by('demo-sq-1').coverage!.loop2 ?? null, null, 'Loop 2 not run: loop2 is absent or null')
  assert.equal(by('demo-sq-3').coverage, null, 'a sub-question that did not finish')

  const sq2 = by('demo-sq-2').coverage!
  assert.equal(sq2.sufficient, false)
  const sq2Status = sq2.loop2!.aspects!.map(a => `${a.status}${a.nearMiss ? ':nearMiss' : ''}`)
  for (const want of ['covered', 'known_gap:nearMiss', 'known_gap_skipped_cap', 'unjudged_not_searched']) assert.ok(sq2Status.includes(want), `${want} in ${sq2Status.join(',')}`)

  const sq4 = by('demo-sq-4').coverage!
  assert.equal(sq4.sufficient, true)
  assert.equal(sq4.loop2!.sufficientStrict, false, 'sufficient with gaps')
  assert.ok(sq4.loop2!.knownGapsNoEvidence!.length >= 1)
  assert.ok(sq4.aspects.some(a => a.coveredBy === 'synthesis'), 'an aspect covered by synthesis')
  assert.ok(sq4.aspects.length >= 8, '8+ aspects: ' + sq4.aspects.length)
  assert.ok(sq4.aspects.some(a => (a.text ?? '').length > 150), 'a very long aspect text')
  assert.ok(sq4.aspects.some(a => /https:\/\/\S{80,}/.test(a.text ?? '')), 'an unbreakable string')
  assert.ok(sq4.digestFailures! > 0, 'digest failures')
  const statuses = new Set(sq4.loop2!.aspects!.map(a => a.status))
  for (const want of ['covered', 'known_gap_no_evidence', 'known_gap', 'known_gap_skipped_triage']) assert.ok(statuses.has(want), want)

  const found = r.subQuestions.flatMap(s => s.sources).map(s => s.foundByLoop2Step).filter(Boolean)
  assert.ok(found.includes('queries') && found.includes('pool') && found.includes('reselect'), found.join(','))
  assert.ok(r.subQuestions.flatMap(s => s.sources).some(s => !s.foundByLoop2Step), 'sources not found by Loop 2 stay unmarked')

  assert.ok(r.limitations.some(l => l.startsWith('Evidence not found for: ')))
  assert.ok(r.limitations.some(l => l.startsWith('Covered by combining findings of several sources, not by one source: ')))
  assert.equal(r.totals.subQuestions, r.subQuestions.length)
  assert.equal(r.totals.sources, r.subQuestions.reduce((n, s) => n + s.sources.length, 0))
  assert.equal(r.totals.subQuestionsSufficient, r.subQuestions.filter(s => s.coverage?.sufficient).length)
})
