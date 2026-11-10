import type { PillTone } from '@/components/trace/status-pill'
import { ladderLabel, loop2AspectView, secondsLabel } from './loop2'
import { countQueries, eventMs, groqByPurpose, loop2Model, loop2RungResults, mergeBySeq, notesOf, stepEvents, toMs, type Loop2RungResult } from './stream'
import { plannedTopics as plannedTopicsOf } from './swimlanes'
import type { EvidenceLevel, Loop2, Loop2Aspect, Loop2StepRow, Report, SourceReport, WorkflowEvent } from './trace-types'

// The "Second search" tab (Loop 2), as pure functions. The view is built from the report once the run has finished and from the events while it runs
// (or when no report could be read). Every field is optional: an unknown step, a status word or a missing number is shown as it is, never an error, and
// nothing is invented: no "after" from "before", no query text for a run that has none.

export const TAB_TITLE = 'Second search'
export const BEFORE_TEXT = 'Starts when the evidence stage judges a sub-question as not covered.'
export const EMPTY_TEXT = 'No sub-question needed a second search (or it is switched off on the server).'
export const NOT_NEEDED_LINE = 'Judged sufficient first time, no second search needed.'
export const NOT_STORED = 'not stored for this run'
export const BAR_CAPTION = 'Judge verdicts per finding: yes, partial, no. “Before” is the count after Stage 3, “after” the count after the second search.'
export const FUNNEL_NOTE = 'The kept counts are what Stage 3 then read.'

export const WHY_TEXT = 'An aspect is searched again when it has 2 or more yes or partial verdicts, or no candidate findings at all. An aspect with only “no” verdicts is not searched: it is recorded as a known gap without evidence.'

export type RungId = 'reselect' | 'pool' | 'queries'
export const RUNGS: { id: RungId; title: string; explain: string }[] = [
  { id: 'reselect', title: 'Reselect', explain: 'Re-read other passages of papers that are already parsed.' },
  { id: 'pool', title: 'Pool', explain: 'Parse the next-ranked papers of the search results.' },
  { id: 'queries', title: 'Queries', explain: 'Search again with new queries.' },
]

const num = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0)
const numOrNull = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : null)
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

// ------------------------------------------------------------------------------------------------------------------------ verdict bars
export type VerdictBar = { yes: number; partial: number; no: number; total: number }
export type AfterBar = VerdictBar & { sources: number | null }

/** {yes, partial, no} as a bar. A missing count is 0 once at least one count is a number; anything else (null, a string) is "not stored": null. */
export function verdictBar(v: unknown): VerdictBar | null {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return null
  const o = v as Record<string, unknown>
  if (!['yes', 'partial', 'no'].some(k => numOrNull(o[k]) != null)) return null
  const yes = numOrNull(o.yes) ?? 0, partial = numOrNull(o.partial) ?? 0, no = numOrNull(o.no) ?? 0
  return { yes, partial, no, total: yes + partial + no }
}

export function afterBar(v: unknown): AfterBar | null {
  const b = verdictBar(v)
  return b ? { ...b, sources: numOrNull((v as Record<string, unknown>).sources) } : null
}

/** "covered: now 3 yes from 2 sources". Only for a covered aspect that has an after. */
export function nowText(status: string, after: AfterBar | null): string | null {
  if (status !== 'covered' || !after) return null
  return after.sources != null ? `covered: now ${after.yes} yes from ${plural(after.sources, 'source', 'sources')}` : `covered: now ${after.yes} yes`
}

export function stoppedText(code: string | null | undefined): string | null {
  if (typeof code !== 'string' || !code.trim()) return null
  if (code === 'time_budget') return 'stopped: time budget used up'
  if (code === 'digests_failed') return 'stopped: the sources could not be read'
  return `stopped: ${code}`                                                         // an unknown value is shown raw
}

// ------------------------------------------------------------------------------------------------------------------------ aspects
export type AspectView = {
  text: string
  chip: { label: string; tone: PillTone }
  /** "single claims" or "combined from several sources"; null when the server did not say; an unknown word as it is. */
  how: string | null
  steps: string[]
  coveredBy: string | null
  nearMiss: boolean
  /** Which rule applied: searched (and why) or not searched (and why). null for a status this page does not know. */
  rule: string | null
  /** Verdicts before and after the second search; null when not stored (older runs). `after` is never made up from `before`. */
  before: VerdictBar | null
  after: AfterBar | null
  nowText: string | null
  stopped: string | null
}

const RULE_SEARCHED = 'Searched again: it had 2 or more yes or partial verdicts, or no candidate findings at all.'
const RULE_TRIAGE = 'Not searched: it had only “no” verdicts (or fewer than 2 yes or partial ones), so another search was judged not worth it. Recorded as a known gap without evidence.'

/** The status chip of an aspect: covered by which rung, covered by combining sources, known gap without evidence, still uncovered; an unknown word as it is. */
export function aspectChip(a: Pick<Loop2Aspect, 'status' | 'coveredBy' | 'nearMiss'>): { label: string; tone: PillTone } {
  if (a.status === 'covered') {
    if (a.coveredBy === 'synthesis') return { label: 'Covered by combining sources', tone: 'lav' }
    return { label: a.coveredBy ? `Covered by ${a.coveredBy}` : 'Covered', tone: 'mint' }
  }
  switch (a.status) {
    case 'known_gap_no_evidence': return { label: 'Known gap, no evidence', tone: 'neutral' }
    case 'known_gap': return { label: a.nearMiss === true ? 'Still uncovered, partly answered' : 'Still uncovered', tone: 'amber' }
    case 'known_gap_skipped_triage': case 'known_gap_skipped_cap': return { label: 'Not searched', tone: 'neutral' }
    case 'unjudged_not_searched': return { label: 'Not judged', tone: 'neutral' }
    default: return { label: a.status || 'Unknown', tone: 'neutral' }                       // unknown words are shown raw
  }
}

export function howText(a: Pick<Loop2Aspect, 'how' | 'coveredBy'>): string | null {
  if (a.how === 'synthesis' || a.coveredBy === 'synthesis') return 'combined from several sources'
  if (a.how === 'single claims') return 'single claims'
  return a.how ? a.how : null
}

export function ruleText(a: Pick<Loop2Aspect, 'status' | 'steps'>): string | null {
  const searched = Array.isArray(a.steps) && a.steps.length > 0
  if (a.status === 'known_gap_skipped_cap') return 'Not searched: the limit of aspects per sub-question was reached.'
  if (a.status === 'unjudged_not_searched') return 'Not searched: a judge call failed for this aspect.'
  if (a.status === 'known_gap_skipped_triage') return RULE_TRIAGE
  if (searched) return RULE_SEARCHED
  if (a.status === 'known_gap_no_evidence') return RULE_TRIAGE
  return null
}

export function aspectView(a: Loop2Aspect): AspectView {
  const after = afterBar(a.after)
  return {
    text: a.text, chip: aspectChip(a), how: howText(a), steps: Array.isArray(a.steps) ? a.steps : [], coveredBy: a.coveredBy ?? null, nearMiss: a.nearMiss === true, rule: ruleText(a),
    before: verdictBar(a.before), after, nowText: nowText(a.status, after), stopped: stoppedText(a.stopped),
  }
}

/** "yes verdicts 1 → 9 across 3 aspects": the yes verdicts of the aspects that were searched and have both a before and an after. null when no aspect has both. */
export function yesAggregate(aspects: AspectView[]): { before: number; after: number; aspects: number; text: string } | null {
  const both = aspects.filter(a => a.steps.length > 0 && a.before && a.after)
  if (both.length === 0) return null
  const before = both.reduce((n, a) => n + a.before!.yes, 0), after = both.reduce((n, a) => n + a.after!.yes, 0)
  return { before, after, aspects: both.length, text: `yes verdicts ${before} → ${after} across ${plural(both.length, 'aspect', 'aspects')}` }
}

// ------------------------------------------------------------------------------------------------------------------------ the ladder
export type RungState = 'ran' | 'not_needed' | 'did_not_run'

export type RungDetails = {
  aspectTexts: string[]
  coveredTexts: string[]
  /** The queries asked, grouped by aspect (the queries rung of newer runs only). null: none stored, nothing is shown. */
  queries: { aspect: string; list: string[] }[] | null
  queryCount: number | null
  /** The same list as plain text for the clipboard. */
  queriesCopy: string | null
  /** "14 papers found → 6 kept → 4 parsed", "11 web pages found → 3 kept". */
  funnel: string[]
  digests: { total: number | null; failed: number | null; tried: number | null }
  /** A calm warning when some digests failed. */
  digestWarning: string | null
  error: string | null
  note: string | null
}

export type RungView = {
  id: string
  title: string
  explain: string
  state: RungState
  /** Live only: the sub-question is in this rung now and it has not reported its result. */
  running: boolean
  aspects: number | null
  newSources: number | null
  newFindings: number | null
  covered: number | null
  seconds: number | null
  /** It ran and found no new source: shown greyed. */
  greyed: boolean
  /** It covered at least one aspect (by the step's own count or by an aspect's coveredBy). */
  highlighted: boolean
  /** null when none of the detail fields is stored (an older run): no "Details" block. */
  details: RungDetails | null
}

function funnelLines(s: Loop2StepRow): string[] {
  const out: string[] = []
  const chain = (parts: [number | null, string][]) => parts.filter(([n]) => n != null).map(([n, w]) => `${n} ${w}`).join(' → ')
  const papers = chain([[numOrNull(s.newPapersFound), numOrNull(s.newPapersFound) === 1 ? 'paper found' : 'papers found'], [numOrNull(s.newPapersKept), 'kept'], [numOrNull(s.newPapersParsed), 'parsed']])
  if (numOrNull(s.newPapersFound) != null && papers) out.push(papers)
  const web = chain([[numOrNull(s.newWebFound), numOrNull(s.newWebFound) === 1 ? 'web page found' : 'web pages found'], [numOrNull(s.newWebKept), 'kept']])
  if (numOrNull(s.newWebFound) != null && web) out.push(web)
  return out
}

/** The details of a rung from its report row. null when the row has none of the newer fields. */
export function rungDetails(s: Loop2StepRow | null | undefined): RungDetails | null {
  if (!s) return null
  const queriesMap = s.queries && typeof s.queries === 'object' && !Array.isArray(s.queries) ? s.queries : null
  const queries = queriesMap ? Object.entries(queriesMap).filter(([, l]) => Array.isArray(l) && l.length > 0).map(([aspect, list]) => ({ aspect, list: list.filter(x => typeof x === 'string' && x) })) : null
  const aspectTexts = Array.isArray(s.aspectTexts) ? s.aspectTexts.filter(x => typeof x === 'string') : []
  const coveredTexts = Array.isArray(s.coveredTexts) ? s.coveredTexts.filter(x => typeof x === 'string') : []
  const digestTotal = numOrNull(s.digestTotal), digestFailed = numOrNull(s.digestFailed), tried = numOrNull(s.sourcesTried)
  const funnel = funnelLines(s)
  const error = typeof s.error === 'string' && s.error ? s.error : null, note = typeof s.note === 'string' && s.note ? s.note : null
  const any = aspectTexts.length || coveredTexts.length || (queries && queries.length) || funnel.length || digestTotal != null || digestFailed != null || tried != null || error || note || numOrNull(s.queryCount) != null
  if (!any) return null
  const list = queries && queries.length ? queries : null
  return {
    aspectTexts, coveredTexts, queries: list, queryCount: numOrNull(s.queryCount) ?? (list ? list.reduce((n, g) => n + g.list.length, 0) : null),
    queriesCopy: list ? list.map(g => `${g.aspect}\n${g.list.map(q => `- ${q}`).join('\n')}`).join('\n\n') : null,
    funnel, digests: { total: digestTotal, failed: digestFailed, tried },
    digestWarning: digestFailed != null && digestFailed > 0 ? `${plural(digestFailed, 'source', 'sources')} could not be read (rate limit?), so “no evidence” may be wrong.` : null,
    error, note,
  }
}

/** The details a live loop2_step event can give: the queries and an error. */
export function liveDetails(r: Loop2RungResult): RungDetails | null {
  const list = r.queries ? Object.entries(r.queries).filter(([, l]) => l.length > 0).map(([aspect, l]) => ({ aspect, list: l })) : null
  if (!list?.length && !r.error) return null
  return {
    aspectTexts: [], coveredTexts: [], queries: list?.length ? list : null, queryCount: r.queryCount, queriesCopy: list?.length ? list.map(g => `${g.aspect}\n${g.list.map(q => `- ${q}`).join('\n')}`).join('\n\n') : null,
    funnel: [], digests: { total: null, failed: null, tried: null }, digestWarning: null, error: r.error, note: null,
  }
}

/** The three rungs in order (plus any other step the server reports, after them). A rung that never ran says "not needed" when everything searched was
 *  covered before it, otherwise "did not run". */
export function ladder(l: Loop2): RungView[] {
  const steps = Array.isArray(l.steps) ? l.steps : []
  const aspects = Array.isArray(l.aspects) ? l.aspects : []
  const allCovered = l.searched > 0 && l.covered >= l.searched
  const known = RUNGS.map(r => ({ id: r.id as string, title: r.title, explain: r.explain }))
  for (const s of steps) if (!known.some(k => k.id === s.step)) known.push({ id: s.step, title: ladderLabel(s.step), explain: '' })
  return known.map(r => {
    const s = steps.find(x => x.step === r.id)
    const coveredHere = aspects.filter(a => a.coveredBy === r.id).length
    if (!s) return { ...r, state: allCovered ? 'not_needed' : 'did_not_run', running: false, aspects: null, newSources: null, newFindings: null, covered: null, seconds: null, greyed: false, highlighted: coveredHere > 0, details: null }
    return {
      ...r, state: 'ran', running: false, aspects: num(s.aspects), newSources: num(s.newSources), newFindings: num(s.newVerifiedFindings), covered: num(s.covered), seconds: typeof s.seconds === 'number' ? s.seconds : null,
      greyed: num(s.newSources) === 0, highlighted: num(s.covered) > 0 || coveredHere > 0, details: rungDetails(s),
    }
  })
}

// ------------------------------------------------------------------------------------------------------------------------ the view
export type LiveSq = { rung: string | null; aspects: number | null; done: boolean; searched: number | null; covered: number | null; gaps: number | null }

export type SqView = {
  id: string
  index: number
  topic: string
  /** The sub-question needed a second search (loop2 is not null in the report, or loop2 events exist). */
  needed: boolean
  /** The muted line for a sub-question that needed none. */
  line: string | null
  searched: number
  covered: number
  seconds: number | null
  /** "Sufficient, with gaps": it is sufficient but not under the strict rule. */
  withGaps: boolean
  sufficient: boolean | null
  triage: string | null
  gapRule: string | null
  coveredBySynthesis: number
  rungs: RungView[]
  aspects: AspectView[]
  knownGaps: string[]
  /** "yes verdicts 1 → 9 across 3 aspects"; null when the run did not store the after counts. */
  yesAgg: ReturnType<typeof yesAggregate>
  /** Live only: the rung it is on now. */
  live: LiveSq | null
}

export type NewSource = { id: string; title: string | null; type: 'paper' | 'web'; rung: string; evidenceLevel: EvidenceLevel | string; findings: number; url: string | null; topic: string }

export type Summary = {
  needed: number
  total: number
  searched: number
  covered: number
  knownGaps: number
  newSources: number
  newFindings: number
  /** Sum of the sub-questions' own seconds: an upper bound of the time, because sub-questions overlap. */
  sumSeconds: number | null
  /** First to last loop2 event, when events exist. */
  spanSeconds: number | null
  tokens: number | null
}

export type SecondSearchView = {
  /** before: nothing yet and the evidence stage has not asked for it; live: some sub-question is in it; done: it is over; empty: none needed. */
  state: 'before' | 'live' | 'done' | 'empty'
  source: 'report' | 'events' | 'none'
  summary: Summary
  sqs: SqView[]
  newSources: NewSource[]
  /** The badge on the tab: aspects searched, only when above 0. */
  badge: number
  message: string | null
}

const ZERO: Summary = { needed: 0, total: 0, searched: 0, covered: 0, knownGaps: 0, newSources: 0, newFindings: 0, sumSeconds: null, spanSeconds: null, tokens: null }

/** The time from the first to the last loop2 event, in seconds (real times: occurredAt when present). null with fewer than two events. */
export function loop2SpanSeconds(input: WorkflowEvent[]): number | null {
  const ts = [...stepEvents(mergeBySeq(input), 'summarizer', 'loop2'), ...stepEvents(mergeBySeq(input), 'summarizer', 'loop2_step')].map(e => eventMs(e)).filter((x): x is number => x != null)
  return ts.length >= 2 ? (Math.max(...ts) - Math.min(...ts)) / 1000 : null
}

const loop2Tokens = (events: WorkflowEvent[]): number | null => groqByPurpose(events)?.find(([k]) => k === 'digest_loop2')?.[1] ?? null

export function safeHref(u: string | null | undefined): string | null {
  if (!u) return null
  try { const p = new URL(u); return p.protocol === 'http:' || p.protocol === 'https:' ? p.href : null } catch { return null }
}

/** The sources a second search added, with the rung that found each. */
export function newSourcesOf(report: Pick<Report, 'subQuestions'>): NewSource[] {
  const out: NewSource[] = []
  for (const sq of report.subQuestions) for (const s of sq.sources ?? []) if (s.foundByLoop2Step) out.push(toNew(s, sq.topic))
  return out
}
const toNew = (s: SourceReport, topic: string): NewSource => ({ id: s.id, title: s.title, type: s.type === 'web' ? 'web' : 'paper', rung: String(s.foundByLoop2Step), evidenceLevel: s.evidenceLevel, findings: num(s.findingsTotal), url: safeHref(s.url), topic })

const blankSq = (id: string, index: number, topic: string, line: string | null): SqView => ({ id, index, topic, needed: false, line, searched: 0, covered: 0, seconds: null, withGaps: false, sufficient: null, triage: null, gapRule: null, coveredBySynthesis: 0, rungs: [], aspects: [], knownGaps: [], yesAgg: null, live: null })

function fromReport(report: Report, events: WorkflowEvent[]): SecondSearchView {
  const sqs: SqView[] = report.subQuestions.map((sq, i) => {
    const l = sq.coverage?.loop2 ?? null
    if (!l) return { ...blankSq(sq.id, i + 1, sq.topic, sq.coverage ? NOT_NEEDED_LINE : null), sufficient: sq.coverage?.sufficient ?? null }
    const aspects = (Array.isArray(l.aspects) ? l.aspects : []).map(aspectView)
    return {
      id: sq.id, index: i + 1, topic: sq.topic, needed: true, line: null, searched: num(l.searched), covered: num(l.covered), seconds: typeof l.seconds === 'number' ? l.seconds : null,
      withGaps: !!sq.coverage?.sufficient && l.sufficientStrict === false, sufficient: sq.coverage?.sufficient ?? null, triage: l.triage ?? null, gapRule: l.gapRule ?? null, coveredBySynthesis: num(l.coveredBySynthesis),
      rungs: ladder(l), aspects, yesAgg: yesAggregate(aspects),
      knownGaps: Array.isArray(l.knownGaps) ? l.knownGaps : Array.isArray(l.knownGapsNoEvidence) ? l.knownGapsNoEvidence : [], live: null,
    }
  })
  const needed = sqs.filter(s => s.needed)
  const newSources = newSourcesOf(report)
  const sumSeconds = needed.some(s => s.seconds != null) ? needed.reduce((a, s) => a + (s.seconds ?? 0), 0) : null
  const summary: Summary = {
    needed: needed.length, total: sqs.length, searched: needed.reduce((a, s) => a + s.searched, 0), covered: needed.reduce((a, s) => a + s.covered, 0),
    knownGaps: needed.reduce((a, s) => a + s.knownGaps.length, 0), newSources: newSources.length,
    newFindings: needed.reduce((a, s) => a + s.rungs.reduce((b, r) => b + (r.newFindings ?? 0), 0), 0), sumSeconds, spanSeconds: loop2SpanSeconds(events), tokens: loop2Tokens(events),
  }
  return { state: needed.length === 0 ? 'empty' : 'done', source: 'report', summary, sqs, newSources, badge: summary.searched, message: needed.length === 0 ? EMPTY_TEXT : null }
}

/** A rung built from the live events: its result as soon as its loop2_step arrived, "running" while the sub-question is in it, otherwise not shown as done. */
function liveRung(r: { id: RungId; title: string; explain: string }, l: { rungs: string[]; rung: string | null; done: boolean; aspects: number | null }, res: Loop2RungResult | undefined): RungView {
  if (res) {
    return {
      id: r.id, title: r.title, explain: r.explain, state: 'ran', running: false, aspects: res.aspects, newSources: res.newSources, newFindings: res.newVerifiedFindings, covered: res.covered, seconds: res.seconds,
      greyed: res.newSources === 0, highlighted: (res.covered ?? 0) > 0, details: liveDetails(res),
    }
  }
  const started = l.rungs.includes(r.id)
  return {
    id: r.id, title: r.title, explain: r.explain, state: started ? 'ran' : l.done ? 'not_needed' : 'did_not_run', running: started && !l.done && l.rung === r.id,
    aspects: l.rung === r.id ? l.aspects : null, newSources: null, newFindings: null, covered: null, seconds: null, greyed: false, highlighted: false, details: null,
  }
}

function fromEvents(input: WorkflowEvent[], running: boolean, topics: string[]): SecondSearchView {
  const events = mergeBySeq(input)
  const lm = loop2Model(events)
  const results = loop2RungResults(events)
  const notes = notesOf(events)
  const total = Math.max(topics.length, ...lm.sqs.map(s => s.index))
  if (!lm.indexed) {
    const finished = !running
    return { state: finished ? 'empty' : 'before', source: finished && events.length === 0 ? 'none' : 'events', summary: { ...ZERO, total, tokens: loop2Tokens(events) }, sqs: [], newSources: [], badge: 0, message: finished ? EMPTY_TEXT : BEFORE_TEXT }
  }
  const sqs: SqView[] = []
  for (let i = 1; i <= total; i++) {
    const l = lm.sqs.find(s => s.index === i)
    const topic = topics[i - 1] || `Sub-question ${i}`
    if (!l) { sqs.push(blankSq(`sq-${i}`, i, topic, running ? null : NOT_NEEDED_LINE)); continue }
    const gaps = notes.find(n => n.code === 'loop2_gaps' && n.subQuestionIndex === i)?.data.gaps
    const sec = l.startedAt && l.endedAt ? (toMs(l.endedAt)! - toMs(l.startedAt)!) / 1000 : null
    const mine = results.filter(r => r.subQuestionIndex === i)
    const rungs = RUNGS.map(r => liveRung(r, l, mine.find(x => x.rung === r.id)))
    for (const x of mine) if (!rungs.some(r => r.id === x.rung)) rungs.push(liveRung({ id: x.rung as RungId, title: ladderLabel(x.rung), explain: '' }, l, x))        // a rung this page does not know
    sqs.push({
      ...blankSq(`sq-${i}`, i, topic, null), needed: true, searched: l.searched ?? 0, covered: l.covered ?? 0, seconds: sec, rungs,
      live: { rung: l.rung, aspects: l.aspects, done: l.done, searched: l.searched, covered: l.covered, gaps: typeof gaps === 'number' ? gaps : null },
    })
  }
  const needed = sqs.filter(s => s.needed)
  const anyLive = needed.some(s => s.live && !s.live.done)
  const summary: Summary = {
    needed: needed.length, total, searched: needed.reduce((a, s) => a + s.searched, 0), covered: needed.reduce((a, s) => a + s.covered, 0),
    knownGaps: needed.reduce((a, s) => a + (s.live?.gaps ?? 0), 0), newSources: results.reduce((a, r) => a + (r.newSources ?? 0), 0), newFindings: results.reduce((a, r) => a + (r.newVerifiedFindings ?? 0), 0),
    sumSeconds: needed.some(s => s.seconds != null) ? needed.reduce((a, s) => a + (s.seconds ?? 0), 0) : null, spanSeconds: loop2SpanSeconds(events), tokens: loop2Tokens(events),
  }
  return { state: anyLive && running ? 'live' : 'done', source: 'events', summary, sqs, newSources: [], badge: summary.searched, message: null }
}

/** Builds the tab. `report` is null while the run goes (or when it could not be read); then everything comes from the events. */
export function buildSecondSearch(args: { report: Report | null; events: WorkflowEvent[]; running: boolean; topics?: string[] }): SecondSearchView {
  const { report, events, running } = args
  if (report && !running && report.subQuestions.length > 0) return fromReport(report, events)
  return fromEvents(events, running, args.topics?.length ? args.topics : plannedTopicsOf(events))
}

// ------------------------------------------------------------------------------------------------------------------------ small texts for the summary strip
export function spanLine(s: Summary): string | null {
  const parts: string[] = []
  if (s.spanSeconds != null) parts.push(`${secondsLabel(s.spanSeconds)} from the first to the last event`)
  if (s.sumSeconds != null) parts.push(`up to ${secondsLabel(s.sumSeconds)} added up over the sub-questions, because they overlap`)
  return parts.length ? parts.join(' · ') : null
}

export const neededLine = (s: Summary): string => `${s.needed} of ${s.total}`

/** One line for the timeline: "Second search: N aspects searched, M covered". null when nothing was searched. */
export function timelineLine(v: SecondSearchView): string | null {
  return v.summary.searched > 0 ? `${TAB_TITLE}: ${plural(v.summary.searched, 'aspect', 'aspects')} searched, ${v.summary.covered} covered` : null
}

/** Queries asked by a sub-question's second search, for a tooltip ("7 queries asked"); null when none are stored. */
export const queriesAsked = (v: SqView): number | null => {
  const total = v.rungs.reduce((n, r) => n + (r.details?.queryCount ?? 0), 0)
  return total > 0 ? total : null
}

export { loop2AspectView, countQueries }
