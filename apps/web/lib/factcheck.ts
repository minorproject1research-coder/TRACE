import type { PillTone } from '@/components/trace/status-pill'
import type { FactCheck, FactClaim, FactCounts, FactEvidence, Report, StageState, WorkflowEvent } from './trace-types'

// Pure helpers for Stage 4 (fact checking across sources; the server runs it only with FACTCHECK=true). No React here, so they are unit-tested
// (tests/factcheck.test.ts). Everything tolerates null and unknown values: a label or relation this page does not know gets a neutral chip.
//
// Rules that come from docs/STAGE4_OUTPUT.md and must hold wherever a claim is shown:
//  - "supported" is NOT "true": two papers can be wrong, or one can have copied the other.
//  - "unverified" is NOT "false": it is simply not confirmed by a second source. It is never styled like a fact.
//  - "contradicted" and contested claims are always shown together with the source that disagrees.
//  - "confidence" is a ranking number, not a probability, so it is shown as a bar with a word, never as a percent.

export const STAGE_SKIPPED_LABEL = 'skipped (switched off)'
export const STAGE_FAILED_NOTE = 'Fact checking failed; the evidence below is not cross-checked.'
export const JUDGE_FAILURES_NOTE = 'Some checks could not be answered (rate limit); labels are cautious and incomplete.'
export const NOT_CROSS_CHECKED_NOTE = 'Not cross-checked: Stage 4 did not finish for this sub-question.'
export const EMPTY_STATE = 'No claim could be cross-checked for this sub-question.'
export const PANEL_TITLE = 'Cross-check'
export const PANEL_INTRO = 'TRACE grouped the verified findings that state the same thing and compared them across sources. These labels say how many independent sources agree. They do not say what is true.'
export const STRENGTH_TOOLTIP = 'A ranking of how much independent evidence backs the claim; not the chance that it is true.'
export const DISAGREEMENT_TOOLTIP = 'One source asserts the opposite; the other source may be the wrong one.'
export const JUDGE_BADGE = 'checked by the independent judge'
export const JUDGE_BADGE_TOOLTIP = 'The independent Stage 3 judge had already established that this quote supports the claim.'
export const UNVERIFIED_WORDS = 'Not yet confirmed by a second source'
export const CHECKING_WORDS = 'Checking claims across sources'
export const TIME_HINT = 'about 3 minutes per sub-question'

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
const count = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) && v >= 0 ? Math.floor(v) : 0)
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null)
const num = (d: Record<string, unknown> | undefined, k: string): number | null => (typeof d?.[k] === 'number' && Number.isFinite(d[k] as number) ? (d[k] as number) : null)

// ------------------------------------------------------------------------------------------------------------------------ labels
export type LabelView = { text: string; short: string; tone: PillTone; hint: string; kind: 'supported' | 'unverified' | 'contradicted' | 'other' }

/** How to show a claim's label. `text` is the full wording on a claim, `short` the word on a count chip. */
export function labelView(label: string | null | undefined): LabelView {
  switch ((label ?? '').trim().toLowerCase()) {
    case 'supported':
      return { text: 'Supported', short: 'Supported', tone: 'mint', kind: 'supported',
        hint: 'At least two different documents state this with a supporting quote. That is not proof that it is true: two papers can be wrong, or one can have copied the other.' }
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
export const againstSources = (n: number | null | undefined) => `${count(n)} against`

/** A contradicted claim, and a supported claim that is contested, must always be shown with the source that disagrees. */
export const mustShowDisagreement = (c: Pick<FactClaim, 'label' | 'contested'>): boolean => (c.label ?? '').toLowerCase() === 'contradicted' || !!c.contested

/** Splits a claim's evidence by relation. A relation outside supports / contradicts goes to `other` and keeps its own word. */
export function splitEvidence(c: Pick<FactClaim, 'evidence'>): { supports: FactEvidence[]; contradicts: FactEvidence[]; other: FactEvidence[] } {
  const out = { supports: [] as FactEvidence[], contradicts: [] as FactEvidence[], other: [] as FactEvidence[] }
  for (const e of Array.isArray(c.evidence) ? c.evidence : []) {
    const r = (e?.relation ?? '').toLowerCase()
    if (r === 'supports') out.supports.push(e)
    else if (r === 'contradicts') out.contradicts.push(e)
    else out.other.push(e)
  }
  return out
}

export const checkedByJudge = (e: Pick<FactEvidence, 'via'>): boolean => e?.via === 'stage3_judge'

/** The counts of a fact check, taken from `counts` and, where that is missing, from the claims. Always four numbers. */
export function countsOf(fc: FactCheck | null | undefined): FactCounts {
  const claims = Array.isArray(fc?.claims) ? fc!.claims : []
  const given = fc?.counts
  const by = (l: string) => claims.filter(c => (c.label ?? '').toLowerCase() === l).length
  return {
    supported: given ? count(given.supported) : by('supported'),
    unverified: given ? count(given.unverified) : by('unverified'),
    contradicted: given ? count(given.contradicted) : by('contradicted'),
    contested: given ? count(given.contested) : claims.filter(c => c.contested).length,
  }
}

/** The report's summary row: null (Stage 4 did not run) hides it. */
export const factTotals = (r: Pick<Report, 'totals'>): FactCounts | null => (r.totals?.factChecked ? countsOf({ counts: r.totals.factChecked, claims: [], disagreements: [] }) : null)

/** Did Stage 4 run for this report? Totals say so; a sub-question's own factCheck says so too (older shapes). */
export const factCheckRan = (r: Pick<Report, 'totals' | 'subQuestions'>): boolean => !!r.totals?.factChecked || r.subQuestions.some(sq => !!sq.factCheck)

export const factSummaryLine = (c: FactCounts): string => {
  const parts = [`${c.supported} supported`, `${c.unverified} not yet confirmed`, `${c.contradicted} contradicted`]
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
  conflicts: 'looking for sources that disagree',
  store: 'saving the results',
}
export const FACT_STEP_ORDER = ['claims', 'clusters', 'support', 'conflicts', 'store'] as const

export type FactResult = {
  claims: number | null; subQuestions: number | null; failedSubQuestions: number | null
  supported: number | null; unverified: number | null; contradicted: number | null; contested: number | null
  disagreements: number | null; judgeFailures: number | null
}

export type FactProgress = {
  state: 'running' | 'completed' | 'failed'
  startedAt: string | null
  endedAt: string | null
  /** The step reported last (one of FACT_STEP_ORDER), and the 1-based sub-question counters it carried. */
  step: string | null
  subQuestion: number | null
  subQuestions: number | null
  /** "Checking claims across sources: sub-question 2 of 5 - looking for sources that disagree" */
  line: string
  result: FactResult | null
  error: string | null
  judgeFailures: number
  failedSubQuestions: number
}

/** The progress line for a step. Counters that are missing are left out; an unknown step gives just the first part. */
export function progressLine(step: string | null, sub: number | null, total: number | null): string {
  const where = sub != null && total != null && total > 0 ? `${CHECKING_WORDS}: sub-question ${Math.min(sub, total)} of ${total}` : CHECKING_WORDS
  const what = step ? FACT_STEP_LABEL[step] : null
  return what ? `${where} - ${what}` : where
}

/** Reads the fact-check stage from the run's events. null: no event mentions it (Stage 4 is off, or has not started). Unknown steps and malformed data are ignored. */
export function factProgress(events: WorkflowEvent[]): FactProgress | null {
  const started = events.find(e => e.event === 'stage_started' && e.stage === 'factcheck')
  const closed = events.find(e => e.event === 'stage_completed' && e.stage === 'factcheck')
  const runFailedHere = events.find(e => e.event === 'run_failed' && e.stage === 'factcheck')
  if (!started && !closed && !runFailedHere) return null

  const steps = events.filter(e => e.event === 'step' && e.data?.lane === 'factcheck' && typeof e.data.step === 'string' && e.data.step in FACT_STEP_LABEL)
  const last = steps[steps.length - 1]
  const failed = !!runFailedHere || (!!closed && (closed.status === 'failed' || str(closed.data?.error) != null))
  const state: FactProgress['state'] = failed ? 'failed' : closed ? 'completed' : 'running'
  const sub = last ? num(last.data, 'subQuestion') : null
  const total = last ? num(last.data, 'subQuestions') : null
  const d = closed?.data ?? {}
  const result: FactResult | null = closed && !failed
    ? { claims: num(d, 'claims'), subQuestions: num(d, 'subQuestions'), failedSubQuestions: num(d, 'failedSubQuestions'), supported: num(d, 'supported'), unverified: num(d, 'unverified'),
        contradicted: num(d, 'contradicted'), contested: num(d, 'contested'), disagreements: num(d, 'disagreements'), judgeFailures: num(d, 'judgeFailures') }
    : null
  return {
    state, startedAt: started?.timestamp ?? null, endedAt: (closed ?? runFailedHere)?.timestamp ?? null,
    step: last ? String(last.data.step) : null, subQuestion: sub, subQuestions: total,
    line: progressLine(last ? String(last.data.step) : null, sub, total),
    result, error: failed ? (str(closed?.data?.error) ?? runFailedHere?.message ?? closed?.message ?? null) : null,
    judgeFailures: count(result?.judgeFailures), failedSubQuestions: count(result?.failedSubQuestions),
  }
}

export const judgeFailuresNote = (p: Pick<FactProgress, 'judgeFailures'> | null | undefined): string | null => (p && p.judgeFailures > 0 ? JUDGE_FAILURES_NOTE : null)

export const failedSubQuestionsNote = (p: Pick<FactProgress, 'failedSubQuestions' | 'result'> | null | undefined): string | null =>
  p && p.failedSubQuestions > 0 ? `Fact checking failed for ${p.failedSubQuestions} of ${p.result?.subQuestions ?? '?'} sub-questions; their claims are not cross-checked.` : null

/** "4 min 12 s" for a running stage. The stage takes about 3 minutes per sub-question, so the time is shown and not a progress bar. */
export function elapsedLabel(from: string | null, nowMs: number): string | null {
  if (!from) return null
  const t = new Date(from).getTime()
  if (Number.isNaN(t)) return null
  const s = Math.max(0, Math.round((nowMs - t) / 1000))
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`
}
