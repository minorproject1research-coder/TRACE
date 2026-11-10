import type { PillTone } from '@/components/trace/status-pill'
import { factModel, FACT_STEPS, mergeBySeq, type FactModel } from './stream'
import type { FactCheck, FactClaim, FactCounts, FactEvidence, Report, StageState, WorkflowEvent } from './trace-types'

/** Every count of a fact check as a number: a missing partially_supported (old reports and events) is 0. */
export type FactCountsFull = Required<FactCounts>

// Pure helpers for Stage 4 (fact checking across sources; the server runs it only with FACTCHECK=true). No React here, so they are unit-tested
// (tests/factcheck.test.ts). Everything tolerates null and unknown values: a label or relation this page does not know gets a neutral chip.
//
// Rules that come from docs/STAGE4_OUTPUT.md and must hold wherever a claim is shown:
//  - "supported" is NOT "true": two papers can be wrong, or one can have copied the other.
//  - "unverified" is NOT "false": it is simply not confirmed by a second source. It is never styled like a fact.
//  - "partially_supported" rests on ONE document plus a close variant (not the same claim) in another: a lead, never a fact, and never worded as two-source agreement.
//  - "contradicted" and contested claims are always shown together with the source that disagrees.
//  - "confidence" is a ranking number, not a probability, so it is shown as a bar with a word, never as a percent.

export const STAGE_SKIPPED_LABEL = 'skipped (switched off)'
export const STAGE_FAILED_NOTE = 'Fact checking failed; the evidence below is not cross-checked.'
export const NOT_CROSS_CHECKED_NOTE = 'Not cross-checked: Stage 4 did not finish for this sub-question.'
export const EMPTY_STATE = 'No claim could be cross-checked for this sub-question.'
export const PANEL_TITLE = 'Cross-check'
export const PANEL_INTRO = 'TRACE grouped the verified findings that state the same thing and compared them across sources. These labels say how many sources agree: “supported” needs two independent sources; “partly supported” rests on one source, with a close variant in another. They do not say what is true.'
export const STRENGTH_TOOLTIP = 'A ranking of how much independent evidence backs the claim; not the chance that it is true.'
export const DISAGREEMENT_TOOLTIP = 'One source asserts the opposite; the other source may be the wrong one.'
export const JUDGE_BADGE = 'checked by the independent judge'
export const JUDGE_BADGE_TOOLTIP = 'The independent Stage 3 judge had already established that this quote supports the claim.'
export const UNVERIFIED_WORDS = 'Not yet confirmed by a second source'
export const PARTIAL_WORDS = 'Partly supported'
export const PARTIAL_HINT = 'One source states this; another source states a close variant. A lead, not a confirmed fact.'
export const NEAR_HEADING = 'Close variant in another source'
export const NEAR_HINT = 'A different document says something close to this, in its own words. It is not the same claim, so it does not confirm it.'
export const CHECKING_WORDS = 'Checking claims across sources'
export const TIME_HINT = 'about 3 minutes per sub-question, partly during the evidence stage (an estimate)'
export const OVERLAP_TAG = 'overlapped with Stage 3'

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
const count = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) && v >= 0 ? Math.floor(v) : 0)
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null)
const num = (d: Record<string, unknown> | undefined, k: string): number | null => (typeof d?.[k] === 'number' && Number.isFinite(d[k] as number) ? (d[k] as number) : null)

// ------------------------------------------------------------------------------------------------------------------------ labels
export type LabelView = { text: string; short: string; tone: PillTone; hint: string; kind: 'supported' | 'partially_supported' | 'unverified' | 'contradicted' | 'other' }

/** How to show a claim's label. `text` is the full wording on a claim, `short` the word on a count chip. */
export function labelView(label: string | null | undefined): LabelView {
  switch ((label ?? '').trim().toLowerCase()) {
    case 'supported':
      return { text: 'Supported', short: 'Supported', tone: 'mint', kind: 'supported',
        hint: 'At least two different documents state this with a supporting quote. That is not proof that it is true: two papers can be wrong, or one can have copied the other.' }
    case 'partially_supported':
      // between unverified (grey) and supported (green): blue, dashed card, never the green of a fact
      return { text: PARTIAL_WORDS, short: 'Partly supported', tone: 'blue', kind: 'partially_supported', hint: PARTIAL_HINT }
    case 'unverified':
      return { text: UNVERIFIED_WORDS, short: 'Unverified', tone: 'neutral', kind: 'unverified',
        hint: 'Only one document states this, so there is no second source yet. That does not mean it is false.' }
    case 'contradicted':
      return { text: 'Contradicted', short: 'Contradicted', tone: 'coral', kind: 'contradicted', hint: DISAGREEMENT_TOOLTIP }
    default: {
      const w = (label ?? '').trim()
      return { text: w ? w[0].toUpperCase() + w.slice(1) : 'Unlabelled', short: w || 'Unlabelled', tone: 'neutral', kind: 'other', hint: 'A label this page does not know. Read the evidence under it.' }
    }
  }
}

export const CONTESTED_HINT = 'Supported by two or more sources, but a weaker source says the opposite. The disagreeing source is shown below.'

// ------------------------------------------------------------------------------------------------------------------------ strength
export type Strength = { level: 'low' | 'medium' | 'high' | 'unknown'; fraction: number; word: string }

/** The confidence is a ranking number (at most 0.95), shown as a bar and a word. Never as a percent: it is not a probability. */
export function strengthOf(confidence: number | null | undefined): Strength {
  if (typeof confidence !== 'number' || !Number.isFinite(confidence)) return { level: 'unknown', fraction: 0, word: 'not given' }
  const c = Math.max(0, Math.min(0.95, confidence))
  const level = c < 0.35 ? 'low' : c < 0.7 ? 'medium' : 'high'
  return { level, fraction: c / 0.95, word: level }
}

// ------------------------------------------------------------------------------------------------------------------------ claims
export const independentSources = (n: number | null | undefined) => plural(count(n), 'independent source', 'independent sources')

/** How many sources a claim rests on. A partly supported claim rests on ONE source (plus a close variant): it never gets a number or a word of two-source agreement. */
export const sourcesLine = (c: Pick<FactClaim, 'label' | 'supportDocCount'>): string =>
  (c.label ?? '').toLowerCase() === 'partially_supported' ? 'Rests on one source, plus a close variant in another' : independentSources(c.supportDocCount)
export const againstSources = (n: number | null | undefined) => `${count(n)} against`

/** A contradicted claim, and a supported claim that is contested, must always be shown with the source that disagrees. */
export const mustShowDisagreement = (c: Pick<FactClaim, 'label' | 'contested'>): boolean => (c.label ?? '').toLowerCase() === 'contradicted' || !!c.contested

/** Splits a claim's evidence by relation. A relation outside supports / contradicts goes to `other` and keeps its own word. */
export function splitEvidence(c: Pick<FactClaim, 'evidence'>): { supports: FactEvidence[]; contradicts: FactEvidence[]; near: FactEvidence[]; other: FactEvidence[] } {
  const out = { supports: [] as FactEvidence[], contradicts: [] as FactEvidence[], near: [] as FactEvidence[], other: [] as FactEvidence[] }
  for (const e of Array.isArray(c.evidence) ? c.evidence : []) {
    const r = (e?.relation ?? '').toLowerCase()
    if (r === 'supports') out.supports.push(e)
    else if (r === 'contradicts') out.contradicts.push(e)
    else if (r === 'near_match') out.near.push(e)
    else out.other.push(e)
  }
  return out
}

export const checkedByJudge = (e: Pick<FactEvidence, 'via'>): boolean => e?.via === 'stage3_judge'

/** The counts of a fact check, taken from `counts` and, where that is missing, from the claims. Always four numbers. */
export function countsOf(fc: FactCheck | null | undefined): FactCountsFull {
  const claims = Array.isArray(fc?.claims) ? fc!.claims : []
  const given = fc?.counts
  const by = (l: string) => claims.filter(c => (c.label ?? '').toLowerCase() === l).length
  return {
    supported: given ? count(given.supported) : by('supported'),
    partially_supported: given ? count(given.partially_supported) : by('partially_supported'),          // missing in old reports: 0
    unverified: given ? count(given.unverified) : by('unverified'),
    contradicted: given ? count(given.contradicted) : by('contradicted'),
    contested: given ? count(given.contested) : claims.filter(c => c.contested).length,
  }
}

/** The report's summary row: null (Stage 4 did not run) hides it. */
export const factTotals = (r: Pick<Report, 'totals'>): FactCountsFull | null => (r.totals?.factChecked ? countsOf({ counts: r.totals.factChecked, claims: [], disagreements: [] }) : null)

/** Did Stage 4 run for this report? Totals say so; a sub-question's own factCheck says so too (older shapes). */
export const factCheckRan = (r: Pick<Report, 'totals' | 'subQuestions'>): boolean => !!r.totals?.factChecked || r.subQuestions.some(sq => !!sq.factCheck)

export const factSummaryLine = (c: FactCounts): string => {
  const parts = [`${count(c.supported)} supported`, `${count(c.partially_supported)} partly supported`, `${count(c.unverified)} not yet confirmed`, `${count(c.contradicted)} contradicted`]
  if (c.contested > 0) parts.push(`${c.contested} contested`)
  return parts.join(' · ')
}

// ------------------------------------------------------------------------------------------------------------------------ stage and progress
/** The text of a stage state on the pipeline. not_run is a stage that was switched off for this run. */
export const stageLabel = (state: StageState, fallback: string): string => (state === 'not_run' ? STAGE_SKIPPED_LABEL : fallback)

/** What each step of lane "factcheck" is doing, as the tail of the progress line. Steps repeat for every sub-question. */
export const FACT_STEP_LABEL: Record<string, string> = {
  claims: 'reading the claims of each source',
  clusters: 'grouping claims that say the same thing',
  support: 'checking that each quote supports its claim',
  near: 'looking for close variants in other sources',
  conflicts: 'looking for sources that disagree',
  store: 'saving the results',
}
/** The same labels as a heading ("Looking for close variants in other sources"). */
export const FACT_STEP_HEADING: Record<string, string> = Object.fromEntries(Object.entries(FACT_STEP_LABEL).map(([k, v]) => [k, v[0].toUpperCase() + v.slice(1)]))
/** The short names on the per-sub-question row. */
export const FACT_STEP_SHORT: Record<string, string> = { claims: 'Claims', clusters: 'Group', support: 'Quotes', near: 'Close variants', conflicts: 'Disagreements', store: 'Save' }
export const FACT_STEP_ORDER: readonly string[] = FACT_STEPS

export type FactResult = {
  claims: number | null; subQuestions: number | null; failedSubQuestions: number | null
  supported: number | null; partiallySupported: number | null; unverified: number | null; contradicted: number | null; contested: number | null
  disagreements: number | null; judgeFailures: number | null; judgeWaits: number | null
}

export type FactProgress = {
  state: 'running' | 'completed' | 'failed'
  /** The REAL start of the stage work: the earliest time of any of its steps (a replayed step carries occurredAt), not only stage_started. */
  startedAt: string | null
  endedAt: string | null
  /** The step reported last, and the 1-based sub-question counters of the sub-question that reported last. */
  step: string | null
  subQuestion: number | null
  subQuestions: number | null
  /** The steps running now for that sub-question; near and conflicts can both be in it. */
  activeSteps: string[]
  /** "Checking claims across sources: sub-question 2 of 5 - looking for sources that disagree" */
  line: string
  result: FactResult | null
  error: string | null
  judgeFailures: number
  judgeWaits: number
  failedSubQuestions: number
  /** How many sub-questions were checked while Stage 3 was still running (0 for runs before the overlap). */
  overlapped: number
  total: number | null
}

/** The progress line for a step. Counters that are missing are left out; an unknown step gives just the first part. */
export function progressLine(step: string | null, sub: number | null, total: number | null): string {
  return progressLineFor(step ? [step] : [], sub, total)
}

/** The same for several steps at once: "... - looking for close variants in other sources and for sources that disagree". */
export function progressLineFor(steps: string[], sub: number | null, total: number | null): string {
  const where = sub != null && total != null && total > 0 ? `${CHECKING_WORDS}: sub-question ${Math.min(sub, total)} of ${total}` : CHECKING_WORDS
  const labels = steps.filter(s => Object.prototype.hasOwnProperty.call(FACT_STEP_LABEL, s)).map(s => FACT_STEP_LABEL[s])
  if (labels.length === 0) return where
  const tail = labels.map((l, i) => (i > 0 && l.startsWith('looking for ') && labels[i - 1].startsWith('looking for ') ? l.slice('looking '.length) : l))
  return `${where} - ${tail.length > 1 ? `${tail.slice(0, -1).join(', ')} and ${tail[tail.length - 1]}` : tail[0]}`
}

/** With two workers (the stream has done events) two sub-questions can be running: the line names both. Older streams keep the single line. */
function runningLine(m: FactModel, single: string): string {
  if (!m.hasDone || m.stage !== 'running') return single
  const running = m.sqs.filter(s => s.status === 'running' && s.index > 0).map(s => s.index)
  if (running.length < 2) return single
  const list = running.length === 2 ? `${running[0]} and ${running[1]}` : `${running.slice(0, -1).join(', ')} and ${running[running.length - 1]}`
  return `${CHECKING_WORDS}: sub-questions ${list} at the same time`
}

/** The small note for a run whose Stage 4 work began during Stage 3. */
export function overlapNote(overlapped: number, total: number | null): string | null {
  if (!(overlapped > 0)) return null
  // "1 of 5 sub-questions was checked", "2 of 5 sub-questions were checked"; without a total: "1 sub-question was", "2 sub-questions were"
  const noun = total != null && total >= overlapped ? `${overlapped} of ${total} sub-questions` : `${overlapped} sub-question${overlapped === 1 ? '' : 's'}`
  return `Overlapped with Stage 3: ${noun} ${overlapped === 1 ? 'was' : 'were'} checked while the evidence stage was still running, so the time of this stage alone is shorter than the work it did.`
}

/** Reads the fact-check stage from the run's events. null: no event mentions it (Stage 4 is off, or has not started). Unknown steps and malformed data are ignored. */
export function factProgress(events: WorkflowEvent[]): FactProgress | null {
  const m: FactModel = factModel(events)
  if (!m.hasStage || !m.stage) return null
  const ev = mergeBySeq(events)
  const closed = ev.find(e => e.event === 'stage_completed' && e.stage === 'factcheck')
  const runFailedHere = ev.find(e => e.event === 'run_failed' && e.stage === 'factcheck')
  const failed = m.stage === 'failed'
  const newest = m.newest
  const storing = m.lastStep === 'store'
  const sub = storing || !newest || newest.index < 1 ? null : newest.index
  const total = storing ? null : (newest?.totalSeen ?? m.total)
  const steps = storing ? ['store'] : newest && newest.active.length ? newest.active : m.lastStep ? [m.lastStep] : []
  const d = closed?.data ?? {}
  const result: FactResult | null = closed && !failed
    ? { claims: num(d, 'claims'), subQuestions: num(d, 'subQuestions'), failedSubQuestions: num(d, 'failedSubQuestions'), supported: num(d, 'supported'), partiallySupported: num(d, 'partially_supported'), unverified: num(d, 'unverified'),
        contradicted: num(d, 'contradicted'), contested: num(d, 'contested'), disagreements: num(d, 'disagreements'), judgeFailures: num(d, 'judgeFailures'), judgeWaits: num(d, 'judgeWaits') }
    : null
  return {
    state: m.stage, startedAt: m.startedAt, endedAt: m.endedAt,
    step: m.lastStep, subQuestion: sub, subQuestions: total, activeSteps: steps,
    line: runningLine(m, progressLineFor(steps, sub, total)),
    result, error: failed ? (str(closed?.data?.error) ?? runFailedHere?.message ?? closed?.message ?? null) : null,
    judgeFailures: count(result?.judgeFailures), judgeWaits: count(result?.judgeWaits), failedSubQuestions: count(result?.failedSubQuestions),
    overlapped: m.overlapped, total: m.total,
  }
}

/** "4 judge answers failed; labels for that part are conservative." Shown when the stage reports judgeFailures > 0. */
export const judgeFailuresNote = (p: Pick<FactProgress, 'judgeFailures'> | null | undefined): string | null =>
  p && p.judgeFailures > 0 ? `${plural(p.judgeFailures, 'judge answer', 'judge answers')} failed; labels for that part are conservative.` : null

/** Not an alarm: a judge call that waited out a Groq rate limit instead of failing. It only costs time. */
export const judgeWaitsNote = (p: Pick<FactProgress, 'judgeWaits'> | null | undefined): string | null =>
  p && p.judgeWaits > 0 ? `${plural(p.judgeWaits, 'judge call', 'judge calls')} waited for a Groq rate limit. This only made the run slower.` : null

export const failedSubQuestionsNote = (p: Pick<FactProgress, 'failedSubQuestions' | 'result'> | null | undefined): string | null =>
  p && p.failedSubQuestions > 0 ? `Fact checking failed for ${p.failedSubQuestions} of ${p.result?.subQuestions ?? '?'} sub-questions; their claims are not cross-checked.` : null

/** "4 min 12 s" for a running stage. The time is shown and not a progress bar: how long the stage takes depends on how much of it ran during Stage 3. */
export function elapsedLabel(from: string | null, nowMs: number): string | null {
  if (!from) return null
  const t = new Date(from).getTime()
  if (Number.isNaN(t)) return null
  const s = Math.max(0, Math.round((nowMs - t) / 1000))
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`
}
