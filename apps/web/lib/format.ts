import type { PillTone } from '@/components/trace/status-pill'
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

export const stageMeta: Record<StageId, { name: string; detail: string; hint: string }> = {
  planner: { name: 'Planner', detail: 'Breaks the question into sub-questions and search queries.', hint: 'usually about 30 seconds' },
  retrieval: { name: 'Retrieval', detail: 'Searches papers and the web in parallel, then reads the sources it keeps.', hint: 'usually 2 to 9 minutes, longer for a new topic' },
  summarizer: { name: 'Evidence digest and judging', detail: 'Extracts findings, finds the quote behind each, and has an independent judge check them against the sub-question.', hint: 'usually 8 to 11 minutes' },
  factcheck: { name: 'Fact check', detail: 'Will check whether each claim is actually true.', hint: '' },
  report: { name: 'Written report', detail: 'Will write an answer from the verified evidence.', hint: '' },
}

export const stageStateLabel: Record<StageState, string> = {
  pending: 'queued', running: 'running', completed: 'done', failed: 'failed', not_built: 'not built yet', unknown: 'unknown',
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
