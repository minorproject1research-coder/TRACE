// Run with:  pnpm test. Faults found on a live run with FACTCHECK=true: the notes under the Timeline, the stage clock, the waiting copy, the parsing counter.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ETA_ESTIMATE_NOTE, FULL_RUN_ETA, LIVE_RUN_EXPECTATION, stageClockLabel, stageMeta, waitingCopy } from '../lib/format'
import { parsingNote } from '../lib/stream'
import { buildTimeline, timelineNotes } from '../lib/timeline'
import type { EventName, StageId, WorkflowEvent } from '../lib/trace-types'

const T0 = Date.parse('2026-11-09T16:00:00Z')
let seq = 0
const ev = (event: EventName, stage: StageId | null, data: Record<string, unknown> = {}, sec = seq): WorkflowEvent => ({ seq: seq++, event, stage, status: null, message: '', data, timestamp: new Date(T0 + sec * 1000).toISOString() })
const parse = (state: string, data: Record<string, unknown>, sec: number) => ev('step', 'retrieval', { lane: 'papers', step: 'parsing', state, ...data }, sec)

// ---- 1. the notes under the Timeline
test('while Stage 3 runs the Timeline does not say the fact check is not built: pending and running mean it is part of the pipeline', () => {
  for (const state of ['pending', 'running'] as const) {
    const n = timelineNotes(state, false)
    assert.equal(n.stage4!.tag, 'queued', state)
    assert.ok(!/not built|not part of the pipeline/i.test(n.stage4!.text), n.stage4!.text)
    assert.match(n.stage4!.text, /part of this run/)
  }
})

test('nothing says "not built yet": not_run says it did not run, queued says it is coming, an older server says "not available"', () => {
  const off = timelineNotes('not_run', false, 'not_run')
  assert.equal(off.stage4!.tag, 'skipped (switched off)'); assert.match(off.stage4!.text, /switched off/)
  assert.equal(off.stage5!.tag, 'not run'); assert.match(off.stage5!.text, /switched off on the server, or Stage 4 did not run/)
  for (const state of ['pending', 'running', 'not_run', 'completed', 'failed', 'not_built', undefined] as const) {
    for (const rep of ['pending', 'running', 'not_run', 'completed', 'failed', 'not_built', undefined] as const) {
      const n = timelineNotes(state, false, rep)
      for (const note of [n.stage4, n.stage5]) assert.ok(!note || !/not built/i.test(`${note.tag} ${note.text}`), `${state}/${rep}: ${note?.text}`)
    }
  }
  assert.equal(timelineNotes('running', true).stage4, null, 'once the lane exists it says everything itself')
  assert.equal(timelineNotes('completed', false).stage4, null); assert.equal(timelineNotes('failed', false).stage4, null)
  assert.equal(timelineNotes('not_built', false).stage4!.tag, 'not available', 'an older server that really has no Stage 4')
  assert.ok(timelineNotes(undefined, false).stage4)
  // Stage 5: queued while it is pending or running, nothing once its lane exists or it is completed or failed (its own card says it)
  assert.equal(timelineNotes('completed', true, 'pending').stage5!.tag, 'queued'); assert.equal(timelineNotes('completed', true, 'running').stage5!.tag, 'queued')
  assert.equal(timelineNotes('completed', true, 'running', true).stage5, null); assert.equal(timelineNotes('completed', true, 'completed').stage5, null); assert.equal(timelineNotes('completed', true, 'failed').stage5, null)
  assert.equal(timelineNotes('completed', true, undefined).stage5!.tag, 'not available')
})

test('no fact-check event yet: the Timeline has no fact-check lane, so the queued note stands in for it', () => {
  seq = 0
  const events = [ev('run_started', null), ev('stage_started', 'summarizer', {}, 5)]
  assert.equal(buildTimeline(events, null).factcheck, null)
})

// ---- 3. the estimates
test('the estimate follows the two measured runs and is still called an estimate', () => {
  assert.equal(FULL_RUN_ETA, 'about 15 to 25 minutes')
  assert.match(ETA_ESTIMATE_NOTE, /measured on two runs/); assert.match(LIVE_RUN_EXPECTATION, /about 15 to 25 minutes \(measured on two runs, so an estimate\)/)
  assert.match(stageMeta.planner.hint, /about a minute/); assert.match(stageMeta.retrieval.hint, /about 6 minutes/); assert.match(stageMeta.summarizer.hint, /4 to 5 minutes/)
  for (const m of Object.values(stageMeta)) assert.ok(!/usually 8 to 11|2 to 9 minutes|about 30 seconds/.test(m.hint), m.hint)
})

// ---- 4. wording
test('"Evidence appears", "Sources appear", and the Verification tab says when its own results are saved', () => {
  assert.equal(waitingCopy('Evidence').title, 'Evidence appears when the run finishes')
  assert.equal(waitingCopy('Sources').title, 'Sources appear when the run finishes')
  assert.equal(waitingCopy('Verification results').title, 'Verification results appear when the run finishes')
  const ver = waitingCopy('Verification results').body
  assert.match(ver, /end of the fact check \(Stage 4\)/)
  assert.ok(!/as each sub-question is judged/.test(ver), 'not the Evidence sentence')
  assert.match(waitingCopy('Evidence').body, /as each sub-question is judged/)
  assert.ok(!/Evidence appear /.test(waitingCopy('Evidence').title))
})

// ---- 6. the clock on a stage card
test('the stage clock says started while the stage runs and finished when it is done', () => {
  const iso = '2026-11-09T16:29:10Z'
  const run = stageClockLabel('running', iso)!, done = stageClockLabel('completed', iso)!
  assert.match(run, /^started \d/); assert.match(done, /^finished \d/)
  assert.equal(run.replace('started ', ''), done.replace('finished ', ''), 'the same clock format')
  assert.equal(stageClockLabel('pending', iso), null); assert.equal(stageClockLabel('failed', iso), null); assert.equal(stageClockLabel('running', null), null)
})

// ---- 7. PDF parsing
test('while the parser runs and nothing has been attempted, the page says what it is doing instead of a bare 0', () => {
  seq = 0
  const events = [ev('branch_started', 'retrieval', { branch: 'papers' }), parse('running', { target: 25, attempted: 0, usable: 0, papers: 62 }, 10)]
  assert.equal(parsingNote(events), 'parsing up to 25 papers…')
  assert.equal(buildTimeline([...events], { counts: { papersKept: 62, papersParsed: 0 } } as never).retrieval.lanes[0].summary, '62 kept · parsing up to 25 papers…')
  assert.equal(parsingNote([parse('running', { target: 1, attempted: 0, usable: 0 }, 10)]), 'parsing up to 1 paper…')
  assert.equal(parsingNote([parse('running', { attempted: 0 }, 10)]), 'parsing papers…', 'no target: still not a bare 0')
})

test('once the parser reports real counts, finishes or the run fails, the real numbers are shown', () => {
  seq = 0
  assert.equal(parsingNote([parse('running', { target: 25, attempted: 0 }, 1), parse('running', { target: 25, attempted: 12, usable: 9 }, 200)]), null)
  assert.equal(parsingNote([parse('running', { target: 25, attempted: 0 }, 1), parse('running', { target: 25, attempted: 0, usable: 4 }, 2)]), null, 'usable counts')
  assert.equal(parsingNote([parse('running', { target: 25, attempted: 0 }, 1), parse('completed', { target: 25, attempted: 25, usable: 20 }, 300)]), null)
  assert.equal(parsingNote([parse('running', { target: 25, attempted: 0 }, 1), ev('run_failed', 'retrieval', {}, 50)]), null)
  assert.equal(parsingNote([]), null)
  const done = [parse('running', { target: 25, attempted: 0 }, 1), parse('completed', { target: 25, attempted: 25, usable: 20 }, 300)]
  assert.equal(buildTimeline(done, { counts: { papersKept: 62, papersParsed: 20 } } as never).retrieval.lanes[0].summary, '62 kept · 20 parsed')
  // a stale parsed count of 0 from the database after parsing has produced something is shown as it is
  const now = [parse('running', { target: 25, attempted: 0 }, 1), parse('running', { target: 25, attempted: 5, usable: 0 }, 200)]
  assert.equal(buildTimeline(now, { counts: { papersKept: 62, papersParsed: 0 } } as never).retrieval.lanes[0].summary, '62 kept · 0 parsed')
})
