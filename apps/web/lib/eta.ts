import { TYPICAL_NOTE, TYPICAL_SECONDS } from './telemetry'
import { eventMs, factModel, judgeModel, mergeBySeq, mergedData, paperParseModel, stepEvents, toMs } from './stream'
import type { WorkflowEvent } from './trace-types'

// T5: "about N min left (estimate)". Built only from real progress: papers parsed out of the target, digests read out of the total, sub-questions
// judged, sub-questions fact-checked. A part that has not started yet comes from the typical durations of lib/telemetry.ts (measured on two runs).
// Too little data gives null (nothing is shown), a value never goes below 0, and it is always called an estimate.

export type Eta = { loSec: number; hiSec: number; text: string; basis: string }

/** The uncertainty of an extrapolation from progress so far. */
const SPREAD = 0.3

type Range = [number, number]
const add = (a: Range, b: Range): Range => [a[0] + b[0], a[1] + b[1]]
const widen = (s: number): Range => [Math.max(0, s * (1 - SPREAD)), s * (1 + SPREAD)]
const typical = (k: keyof typeof TYPICAL_SECONDS): Range => [TYPICAL_SECONDS[k][0], TYPICAL_SECONDS[k][1]]

/** Extrapolates the time left of one phase: it took `elapsedSec` for `done` of `total` units. Needs at least `minShare` of the work done. */
function extrapolate(elapsedSec: number, done: number, total: number, minShare = 0.2): Range | null {
  if (!(total > 0) || !(done > 0) || done / total < minShare || elapsedSec <= 0) return null
  return widen((elapsedSec * (total - Math.min(done, total))) / Math.min(done, total))
}

export function etaText(loSec: number, hiSec: number): string | null {
  const lo = Math.max(0, Math.floor(loSec / 60)), hi = Math.max(0, Math.ceil(hiSec / 60))
  if (hi <= 0) return null
  if (hi - lo <= 1 || lo === hi) return `about ${Math.max(1, hi)} min left (estimate)`
  return `about ${Math.max(1, lo)} to ${hi} min left (estimate)`
}

/** `factEnabled`: false when the run's fact-check stage is switched off (then nothing is added for it). */
export function estimateTimeLeft(input: WorkflowEvent[], nowMs: number, factEnabled = true): Eta | null {
  const events = mergeBySeq(input)
  if (events.some(e => e.event === 'run_completed' || e.event === 'run_failed')) return null
  const at = (event: string, stage: string) => toMs(events.find(e => e.event === event && e.stage === stage)?.timestamp)
  const sumStart = at('stage_started', 'summarizer'), sumEnd = at('stage_completed', 'summarizer')
  const factEnd = at('stage_completed', 'factcheck')
  if (factEnd != null) return null
  const fm = factModel(events)
  const stage4Left = (basis: string[]): Range | null => {
    if (!factEnabled) return [0, 0]
    const done = fm.sqs.filter(s => s.status === 'done')
    const total = fm.total
    const took = done.map(s => (s.doneAt && s.firstAt ? toMs(s.doneAt)! - toMs(s.firstAt)! : null)).filter((x): x is number => x != null && x >= 0)
    if (fm.hasStage && total && done.length > 0 && took.length > 0) {
      const mean = took.reduce((a, b) => a + b, 0) / took.length / 1000
      const workers = Math.max(1, fm.workers)
      basis.push(`${done.length} of ${total} sub-questions fact-checked`)
      return widen(Math.ceil(Math.max(0, total - done.length) / workers) * mean)
    }
    return fm.hasStage ? null : typical('stage4After')
  }

  const basis: string[] = []
  let left: Range | null = null

  if (sumEnd != null) {                                                  // Stage 4 is the only thing left
    left = stage4Left(basis)
  } else if (sumStart != null) {                                         // the evidence stage
    const jm = judgeModel(events)
    const digest = stepEvents(events, 'summarizer', 'digest')
    const dd = mergedData(digest)
    const judgeStart = jm.sqs.map(s => toMs(s.startedAt)).filter((x): x is number => x != null)
    let own: Range | null = null
    if (jm.indexed && jm.total && jm.done >= 1 && judgeStart.length) {
      own = extrapolate((nowMs - Math.min(...judgeStart)) / 1000, jm.done, jm.total, 0)
      basis.push(`${jm.done} of ${jm.total} sub-questions judged`)
    } else if (typeof dd.done === 'number' && typeof dd.total === 'number' && digest.length && digest[digest.length - 1].data.state !== 'completed') {
      const first = Math.min(...digest.map(e => eventMs(e) ?? nowMs))
      own = extrapolate((nowMs - first) / 1000, dd.done, dd.total)
      if (own) basis.push(`${dd.done} of ${dd.total} sources read`)
    }
    const after = own ? stage4Left(basis) : null
    left = own && after ? add(own, after) : null
  } else if (at('stage_started', 'retrieval') != null) {                 // retrieval: only the PDF parsing has real progress
    const parse = stepEvents(events, 'papers', 'parsing')
    const pd = mergedData(parse)
    const pm = paperParseModel(events)
    const target = typeof pd.target === 'number' ? pd.target : null
    const parsingOpen = parse.length > 0 && parse[parse.length - 1].data.state !== 'completed'
    if (parsingOpen && target && pm.done >= 3) {
      const first = Math.min(...parse.map(e => eventMs(e) ?? nowMs))
      const own = extrapolate((nowMs - first) / 1000, Math.min(pm.done, target), target, 0.1)
      if (own) {
        basis.push(`${Math.min(pm.done, target)} of ${target} papers parsed`)
        const after = stage4Left(basis)
        left = after ? add(add(own, typical('evidence')), after) : null
      }
    }
  }
  if (!left) return null
  const text = etaText(left[0], left[1])
  return text ? { loSec: left[0], hiSec: left[1], text, basis: `${basis.join('; ')}${basis.length ? '; ' : ''}later stages use typical times (${TYPICAL_NOTE})` } : null
}
