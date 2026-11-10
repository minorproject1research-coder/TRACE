import { mergeBySeq, posInt } from './stream'
import type { WorkflowEvent } from './trace-types'

// T6: filters for the "All events" log. Pure and cheap: the search text of every event is built once per list (searchIndex) so that typing in the
// search box only runs a substring test per event, which stays fast with 300 or more events.

export type LogFilter = { stage: string; lane: string; subQuestion: string; type: string; warningsOnly: boolean; text: string }
export const NO_FILTER: LogFilter = { stage: 'all', lane: 'all', subQuestion: 'all', type: 'all', warningsOnly: false, text: '' }

/** The lane of a step event, or the branch of a branch event. */
export const eventLane = (e: WorkflowEvent): string | null => (typeof e.data?.lane === 'string' ? e.data.lane : typeof e.data?.branch === 'string' ? e.data.branch : null)

/** The 1-based sub-question an event is about, from the numeric fields (subQuestionIndex for judge, Loop 2 and notes; subQuestion for Stage 4). Never from the message. */
export const eventSubQuestion = (e: WorkflowEvent): number | null => posInt(e.data?.subQuestionIndex) ?? posInt(e.data?.subQuestion)

/** A warning is: a note with level warn, a failure (run_failed, a failed stage or step), or a wait for a rate limit (judgeWaits, rateLimits on a step). */
export function isWarning(e: WorkflowEvent): boolean {
  const d = e.data ?? {}
  if (e.event === 'run_failed') return true
  if (eventLane(e) === 'notes') return d.level === 'warn'
  if (e.status === 'failed' || d.state === 'failed' || (typeof d.error === 'string' && d.error)) return true
  if (typeof d.judgeWaits === 'number' && d.judgeWaits > 0) return true
  if (typeof d.rateLimit === 'boolean' && d.rateLimit) return true
  return false
}

/** Everything searchable about an event, lower case. The message is searched as text; it is never parsed for numbers. */
function searchText(e: WorkflowEvent): string {
  const d = e.data ?? {}
  return [e.message, e.event, e.stage, eventLane(e), typeof d.step === 'string' ? d.step : '', typeof d.title === 'string' ? d.title : '', typeof d.reason === 'string' ? d.reason : ''].filter(Boolean).join(' ').toLowerCase()
}

export type LogRow = { e: WorkflowEvent; text: string; lane: string | null; sq: number | null; warn: boolean }

export const searchIndex = (events: WorkflowEvent[]): LogRow[] => mergeBySeq(events).map(e => ({ e, text: searchText(e), lane: eventLane(e), sq: eventSubQuestion(e), warn: isWarning(e) }))

export function filterRows(rows: LogRow[], f: LogFilter): LogRow[] {
  const q = f.text.trim().toLowerCase()
  const sq = f.subQuestion === 'all' ? null : Number(f.subQuestion)
  return rows.filter(r =>
    (f.stage === 'all' || r.e.stage === f.stage) && (f.lane === 'all' || r.lane === f.lane) && (sq == null || r.sq === sq) && (f.type === 'all' || r.e.event === f.type) &&
    (!f.warningsOnly || r.warn) && (!q || r.text.includes(q)))
}

export type LogOptions = { stages: string[]; lanes: string[]; subQuestions: number[]; types: string[] }

/** The values the filter menus offer: only what the events contain, so an unknown stage or lane shows up under its own word. */
export function logOptions(rows: LogRow[]): LogOptions {
  const u = <T,>(xs: (T | null | undefined)[]) => [...new Set(xs.filter((x): x is T => x != null && x !== ''))]
  return {
    stages: u(rows.map(r => r.e.stage)).sort(), lanes: u(rows.map(r => r.lane)).sort(),
    subQuestions: u(rows.map(r => r.sq)).sort((a, b) => a - b), types: u(rows.map(r => r.e.event)).sort(),
  }
}

/** The filtered events as JSON text for the clipboard. */
export const eventsJson = (rows: LogRow[]): string => JSON.stringify(rows.map(r => r.e), null, 2)

export const logCountLabel = (shown: number, total: number): string => (shown === total ? `${total} events` : `${shown} of ${total} events`)
