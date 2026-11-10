import { cacheInfo, eventMs, factModel, groqByStage, mergeBySeq, notesOf, tokensLabel, toMs, type CacheInfo, type GroqUse, type Note, type StageGroq } from './stream'
import type { WorkflowEvent } from './trace-types'

// Pure derivations for the timeline's measurements: the time-share bar (T4), the Groq lines (T9), the cache chips (T8) and the notes (T10).

// ------------------------------------------------------------------------------------------------------------------------ T4: time shares
/** What a phase usually takes, in seconds [low, high]. MEASURED ON TWO RUNS (13 min 54 s and 19 min 42 s): the one place these numbers live. */
export const TYPICAL_SECONDS = { planner: [40, 55], retrieval: [360, 510], evidence: [270, 420], stage4After: [360, 480] } as const
export const TYPICAL_NOTE = 'measured on two runs'
/** A phase is "slower" when it took more than this many times the HIGH end of its typical range. */
export const SLOW_FACTOR = 1.3

export type PhaseId = 'planner' | 'retrieval' | 'evidence' | 'stage4After'
export const PHASE_LABEL: Record<PhaseId, string> = { planner: 'Planner', retrieval: 'Retrieval', evidence: 'Evidence', stage4After: 'Fact check after the evidence stage' }

export type ShareSeg = { id: 'planner' | 'search' | 'parsing' | 'evidence' | 'stage4After'; label: string; ms: number; share: number; running: boolean }
export type PhaseHint = { id: PhaseId; label: string; ms: number; running: boolean; slower: boolean; typical: string }
export type TimeShare = {
  totalMs: number
  segs: ShareSeg[]
  phases: PhaseHint[]
  /** Stage 4 work that ran during the evidence stage: drawn hatched inside the evidence segment. */
  overlap: { ms: number; shareOfRun: number; shareOfEvidence: number } | null
}

const minutes = (s: number) => (s >= 60 ? `${Math.round((s / 60) * 10) / 10}`.replace(/\.0$/, '') : null)
/** "40 to 55 s", "6 to 8.5 min". */
export function typicalText([lo, hi]: readonly [number, number]): string {
  return hi >= 120 ? `${minutes(lo)} to ${minutes(hi)} min` : `${lo} to ${hi} s`
}

const T = (events: WorkflowEvent[], event: string, stage: string) => toMs(events.find(e => e.event === event && e.stage === stage)?.timestamp)

/** The whole run in phases. null until the planner has started. While a phase runs its length is the time so far. */
export function timeShares(input: WorkflowEvent[], nowMs: number): TimeShare | null {
  const events = mergeBySeq(input)
  const runEnd = events.find(e => e.event === 'run_completed' || e.event === 'run_failed')
  const endMs = runEnd ? (eventMs(runEnd) ?? nowMs) : Math.max(nowMs, ...events.map(e => eventMs(e) ?? 0))
  const pStart = T(events, 'stage_started', 'planner')
  if (pStart == null) return null
  const span = (from: number | null, to: number | null, closed: boolean) => (from == null ? null : { ms: Math.max(0, (to ?? (closed ? from : endMs)) - from), running: to == null && !runEnd })
  const pEnd = T(events, 'stage_completed', 'planner')
  const rStart = T(events, 'stage_started', 'retrieval'), rEnd = T(events, 'stage_completed', 'retrieval')
  const parseStart = toMs(events.find(e => e.event === 'step' && e.data?.lane === 'papers' && e.data?.step === 'parsing')?.timestamp)
  const sStart = T(events, 'stage_started', 'summarizer'), sEnd = T(events, 'stage_completed', 'summarizer')
  const fm = factModel(events)
  const fEnd = T(events, 'stage_completed', 'factcheck')
  const segs: Omit<ShareSeg, 'share'>[] = []
  const planner = span(pStart, pEnd, false)
  if (planner) segs.push({ id: 'planner', label: 'Planner', ...planner })
  const retrieval = span(rStart, rEnd, false)
  if (retrieval && rStart != null) {
    const split = parseStart != null && parseStart >= rStart && (rEnd == null || parseStart <= rEnd) ? parseStart : null
    if (split == null) segs.push({ id: 'search', label: 'Search and filter', ...retrieval })
    else {
      segs.push({ id: 'search', label: 'Search and filter', ms: split - rStart, running: false })
      segs.push({ id: 'parsing', label: 'PDF parsing', ms: Math.max(0, (rEnd ?? endMs) - split), running: rEnd == null && !runEnd })
    }
  }
  const evidence = span(sStart, sEnd, false)
  if (evidence) segs.push({ id: 'evidence', label: 'Evidence (digests, judge, second search)', ...evidence })
  const factStarted = fm.hasStage && sEnd != null
  if (factStarted) {
    const f = span(sEnd, fEnd ?? (fm.stage === 'failed' ? toMs(fm.endedAt) : null), false)
    if (f) segs.push({ id: 'stage4After', label: 'Fact check after the evidence stage', ...f })
  }
  const sum = segs.reduce((a, s) => a + s.ms, 0)
  if (sum <= 0) return null
  const full: ShareSeg[] = segs.map(s => ({ ...s, share: s.ms / sum }))

  let overlap: TimeShare['overlap'] = null
  const factReal = toMs(fm.startedAt)
  if (factReal != null && sEnd != null && sStart != null && factReal < sEnd) {
    const ms = Math.max(0, sEnd - Math.max(factReal, sStart))
    const evMs = full.find(s => s.id === 'evidence')?.ms ?? 0
    overlap = { ms, shareOfRun: ms / sum, shareOfEvidence: evMs > 0 ? Math.min(1, ms / evMs) : 0 }
  }

  const phase = (id: PhaseId, ms: number, running: boolean): PhaseHint => {
    const [, hi] = TYPICAL_SECONDS[id]
    return { id, label: PHASE_LABEL[id], ms, running, slower: ms / 1000 > hi * SLOW_FACTOR, typical: typicalText(TYPICAL_SECONDS[id]) }
  }
  const phases: PhaseHint[] = []
  const get = (id: ShareSeg['id']) => full.find(s => s.id === id)
  if (get('planner')) phases.push(phase('planner', get('planner')!.ms, get('planner')!.running))
  const search = get('search'), parsing = get('parsing')
  if (search) phases.push(phase('retrieval', search.ms + (parsing?.ms ?? 0), (parsing ?? search).running))
  if (get('evidence')) phases.push(phase('evidence', get('evidence')!.ms, get('evidence')!.running))
  if (get('stage4After')) phases.push(phase('stage4After', get('stage4After')!.ms, get('stage4After')!.running))
  return { totalMs: sum, segs: full, phases, overlap }
}

export const percentLabel = (share: number): string => `${Math.round(share * 100)}%`

export const slowerHint = (p: PhaseHint): string | null => (p.slower ? `slower than the two measured runs (typical: ${p.typical}, ${TYPICAL_NOTE})` : null)

// ------------------------------------------------------------------------------------------------------------------------ T9: Groq lines
export const GROQ_TOOLTIP = 'Wait seconds are summed over the 7 keys, so they can exceed the run time.'

const secs = (s: number): string => (s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`)

/** "Groq 120k tokens · 8 waits · 41 s waiting". A part that is 0 is left out of the sentence, but the tokens are always there. */
export function groqLine(u: GroqUse): string {
  const parts = [`Groq ${tokensLabel(u.tokens)} tokens`]
  if (u.rateLimits > 0) parts.push(`${u.rateLimits} ${u.rateLimits === 1 ? 'wait' : 'waits'}`)
  if (u.parkedSeconds > 0) parts.push(`${secs(u.parkedSeconds)} waiting`)
  return parts.join(' · ')
}

/** Groq use of one stage for its card; Stage 4's work that ran during the evidence stage is counted in that stage (the stage_started it is measured from is later). */
export function stageGroqLine(list: StageGroq[], stage: string): string | null {
  const g = list.find(x => x.stage === stage)
  return g ? groqLine(g.use) : null
}

export const FACT_GROQ_FOOTNOTE = 'The part of the fact check that ran during the evidence stage is counted in the evidence stage.'

// ------------------------------------------------------------------------------------------------------------------------ T8: cache and warm-up chips
export type StageChips = { planner: string[]; retrieval: string[]; summarizer: string[] }

const papersWord = (n: number) => `${n} ${n === 1 ? 'paper' : 'papers'}`

export function cacheChips(c: CacheInfo): StageChips {
  const out: StageChips = { planner: [], retrieval: [], summarizer: [] }
  if (c.planCache) out.planner.push('plan reused from cache')
  if (c.parse && c.parse.fromCache > 0) out.retrieval.push(`${papersWord(c.parse.fromCache)} from the parse cache`)
  if (c.warmup && c.warmup.papers != null) out.retrieval.push(`text of ${papersWord(c.warmup.papers)} prepared while others were parsed`)
  if (c.digest && c.digest.hits > 0) out.summarizer.push(c.digest.total != null ? `${c.digest.hits} of ${c.digest.total} digests from cache` : `${c.digest.hits} digests from cache`)
  if (c.judge && c.judge.hits > 0) out.summarizer.push(`${c.judge.hits} judge ${c.judge.hits === 1 ? 'verdict' : 'verdicts'} from cache`)
  return out
}

// ------------------------------------------------------------------------------------------------------------------------ T10: notes
const n = (d: Record<string, unknown>, k: string): number | null => (typeof d[k] === 'number' && Number.isFinite(d[k] as number) ? (d[k] as number) : null)

/** A friendly title and detail for a note. Known codes are written from the note's numbers; an unknown code shows its own message (or the code). */
export function noteView(note: Note): { title: string; detail: string | null } {
  const d = note.data
  switch (note.code) {
    case 'plan_cache': return { title: 'The stored plan was reused', detail: 'The planner did not have to run again for this question.' }
    case 'plan_fallback': return { title: 'The planner model was unreachable', detail: 'Groq wrote the plan instead.' }
    case 's2_skipped': return { title: 'Semantic Scholar was skipped', detail: 'It answered with a rate limit (HTTP 429), so the other sources were used for the rest of the run.' }
    case 'parse_summary': {
      const parts = [n(d, 'parsed') != null ? `${n(d, 'parsed')} parsed` : null, n(d, 'abstractOnly') != null ? `${n(d, 'abstractOnly')} abstract only` : null, n(d, 'failed') ? `${n(d, 'failed')} failed` : null, n(d, 'fromParseCache') ? `${n(d, 'fromParseCache')} from the parse cache` : null].filter(Boolean)
      const reasons = d.reasons && typeof d.reasons === 'object' && !Array.isArray(d.reasons) ? Object.entries(d.reasons as Record<string, unknown>).filter(([, v]) => typeof v === 'number').map(([k, v]) => `${k}: ${v}`) : []
      return { title: `PDF parsing${n(d, 'attempted') != null ? `: ${n(d, 'attempted')} tried` : ''}`, detail: [parts.join(', '), reasons.length ? `Reasons: ${reasons.join(', ')}` : ''].filter(Boolean).join('. ') || null }
    }
    case 'chunk_warmup': return { title: 'Text prepared while papers were still parsed', detail: [n(d, 'papers') != null ? `${n(d, 'papers')} papers` : null, n(d, 'chunks') != null ? `${n(d, 'chunks')} passages` : null].filter(Boolean).join(', ') || null }
    case 'loop2_gaps': {
      const g = n(d, 'gaps')
      const sq = note.subQuestionIndex != null ? `Sub-question ${note.subQuestionIndex}` : 'A sub-question'
      return { title: `${sq}: ${g != null ? `${g} ${g === 1 ? 'aspect stays' : 'aspects stay'}` : 'some aspects stay'} without evidence after the second search`, detail: n(d, 'searched') != null ? `${n(d, 'searched')} searched again, ${n(d, 'covered') ?? 0} covered.` : null }
    }
    default: return { title: note.message || note.code, detail: null }
  }
}

// ------------------------------------------------------------------------------------------------------------------------ the extras of one stage card
export type StageExtras = {
  /** Cache and warm-up chips (T8). */
  chips: string[]
  /** "Groq 120k tokens · 8 waits · 41 s waiting" (T9); null without telemetry. */
  groq: string | null
  /** How many notes belong to this stage, and how many of them are warnings (T10). */
  notes: { count: number; warn: number }
}

export function stageExtras(events: WorkflowEvent[], stage: 'planner' | 'retrieval' | 'summarizer' | 'factcheck'): StageExtras {
  const ev = mergeBySeq(events)
  const chips = stage === 'factcheck' ? [] : cacheChips(cacheInfo(ev))[stage]
  const notes = notesOf(ev).filter(x => x.stage === stage)
  return { chips, groq: stageGroqLine(groqByStage(ev), stage), notes: { count: notes.length, warn: notes.filter(x => x.level === 'warn').length } }
}
