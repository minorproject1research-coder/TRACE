import type { PillTone } from '@/components/trace/status-pill'
import { STAGE_SKIPPED_LABEL } from './factcheck'
import type { AspectState, EvidenceLevel, RunStatus, StageId, StageState } from './trace-types'

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return 'Unknown time'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Unknown time'
  const now = new Date()
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const sameDay = d.toDateString() === now.toDateString()
  const yesterday = new Date(now.getTime() - 86_400_000).toDateString() === d.toDateString()
  if (sameDay) return `Today, ${time}`
  if (yesterday) return `Yesterday, ${time}`
  return `${d.toLocaleDateString([], { month: 'short', day: 'numeric', ...(d.getFullYear() !== now.getFullYear() ? { year: 'numeric' } : {}) })}, ${time}`
}

export function formatClock(iso: string | null | undefined): string {
  if (!iso) return '--:--:--'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '--:--:--' : d.toLocaleTimeString([], { hour12: false })
}

export function formatDuration(from: string | null, to: string | null): string | null {
  if (!from || !to) return null
  const s = Math.max(0, Math.round((new Date(to).getTime() - new Date(from).getTime()) / 1000))
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}

export const statusLabel: Record<RunStatus, string> = { pending: 'Queued', running: 'Running', completed: 'Completed', failed: 'Failed' }
export const statusTone: Record<RunStatus, PillTone> = { pending: 'amber', running: 'blue', completed: 'mint', failed: 'coral' }

/** How long a full live run is expected to take. An ESTIMATE from two measured runs (13 min 54 s and 19 min 42 s, with the fact check on).
 *  The one place the number lives, so the composer, the run page and Settings never disagree. */
export const FULL_RUN_ETA = 'about 15 to 25 minutes'
export const ETA_ESTIMATE_NOTE = '(measured on two runs, so an estimate)'
export const LIVE_RUN_EXPECTATION = `A full run takes ${FULL_RUN_ETA} ${ETA_ESTIMATE_NOTE}.`

export const stageMeta: Record<StageId, { name: string; detail: string; hint: string }> = {
  planner: { name: 'Planner', detail: 'Breaks the question into sub-questions and search queries.', hint: 'about a minute (53 seconds on a measured run)' },
  retrieval: { name: 'Retrieval', detail: 'Searches papers and the web in parallel, then reads the sources it keeps.', hint: 'about 6 minutes on a measured run, longer for a new topic' },
  summarizer: { name: 'Evidence digest and judging', detail: 'Extracts findings, finds the quote behind each, and has an independent judge check them against the sub-question.', hint: 'about 4 to 5 minutes on a measured run (an estimate); the fact check starts during this stage' },
  factcheck: { name: 'Fact check', detail: 'Groups the verified findings that state the same thing, looks for a second source for each, and for sources that disagree. It does not decide what is true.', hint: 'about 3 minutes per sub-question, but most of it now runs during the evidence stage (an estimate)' },
  report: { name: 'Written report', detail: 'Writes a cited report from the fact-check labels. Every sentence names its sources, and a finding that rests on one source is marked as not confirmed. It is not a verified answer.', hint: 'a few minutes (an estimate)' },
}

/** The written report (Stage 5) was not run: switched off on the server, or Stage 4 did not run so there was nothing to write from. */
export const REPORT_NOT_RUN = 'not run (Stage 5 is switched off or Stage 4 did not run)'

export const stageStateLabel: Record<StageState, string> = {
  pending: 'queued', running: 'running', completed: 'done', failed: 'failed', not_built: 'not available', not_run: STAGE_SKIPPED_LABEL, unknown: 'unknown',
}

/** The word on a stage card. Stage 5 says "not run" (not "skipped"): it can also have nothing to write from. */
export const stageStateWord = (id: StageId, state: StageState): string => (id === 'report' && state === 'not_run' ? 'not run' : stageStateLabel[state])

/** The small time on a stage card. While the stage runs it is when it STARTED, once it is done it is when it FINISHED: the word says which. */
export function stageClockLabel(state: StageState, iso: string | null | undefined): string | null {
  if (!iso) return null
  if (state === 'running') return `started ${formatClock(iso)}`
  if (state === 'completed') return `finished ${formatClock(iso)}`
  return null
}

/** What a tab says while the run has not finished. The verb agrees with the noun, and each tab says when ITS results are saved. */
export function waitingCopy(what: 'Sources' | 'Evidence' | 'Verification results'): { title: string; body: string } {
  switch (what) {
    case 'Evidence': return { title: 'Evidence appears when the run finishes', body: 'TRACE stores it in the database as each sub-question is judged. It can only be read once the run completes.' }
    case 'Sources': return { title: 'Sources appear when the run finishes', body: 'TRACE stores them in the database as each sub-question is judged. They can only be read once the run completes.' }
    default: return { title: 'Verification results appear when the run finishes', body: 'They are saved at the end of the fact check (Stage 4), or with the evidence when the fact check is switched off. They can only be read once the run completes.' }
  }
}

export const evidenceLevelLabel: Record<EvidenceLevel, { label: string; partial: boolean }> = {
  full_text: { label: 'Full text read', partial: false },
  abstract: { label: 'Abstract only', partial: true },
  web_snippet: { label: 'Web snippet only', partial: true },
}

export type StanceGroup = 'supports' | 'opposes' | 'neutral' | 'other'

/** How to show a finding's stance. The value is free model output: unknown words get a neutral chip with their own label, never a crash. */
export function stanceInfo(stance: string | null | undefined): { group: StanceGroup; label: string; tone: PillTone } {
  const s = (stance ?? '').trim().toLowerCase()
  if (s === 'supports' || s === 'support' || s === 'supported') return { group: 'supports', label: 'Supports', tone: 'mint' }
  if (['contradicts', 'contradict', 'challenges', 'challenge', 'opposes', 'refutes', 'disputes'].includes(s)) return { group: 'opposes', label: s === 'contradicts' || s === 'contradict' ? 'Contradicts' : s[0].toUpperCase() + s.slice(1), tone: 'coral' }
  if (s === 'neutral') return { group: 'neutral', label: 'Neutral', tone: 'neutral' }
  return { group: 'other', label: s ? s[0].toUpperCase() + s.slice(1) : 'Unclassified', tone: 'neutral' }
}

const ASPECT_STATES: Record<AspectState, { label: string; tone: PillTone }> = {
  covered: { label: 'Covered', tone: 'mint' },
  judged_insufficient: { label: 'Not enough sources', tone: 'amber' },
  no_candidates: { label: 'No candidate evidence', tone: 'coral' },
  unjudged: { label: 'Not judged', tone: 'amber' },
  uncovered: { label: 'Uncovered', tone: 'coral' },
  unknown: { label: 'Unknown', tone: 'neutral' },
}

export const aspectStateLabel = (state: string): { label: string; tone: PillTone } => ASPECT_STATES[state as AspectState] ?? { label: state || 'Unknown', tone: 'neutral' }

/** Pull numbers out of an event's free-form data without trusting its shape. */
export function num(data: Record<string, unknown> | undefined, key: string): number | null {
  const v = data?.[key]
  return typeof v === 'number' ? v : null
}
