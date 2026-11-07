import { factProgress } from './factcheck'
import { ladderLabel, SUBSTEP_TITLE } from './loop2'
import type { PapersOverview, StepState, WorkflowEvent } from './trace-types'

// Builds what the Timeline view draws, from the run's events (live, exact) or, for a run that finished before the pipeline reported
// steps, from the timestamps of the rows it wrote to the database (approximate, and labelled as such).

export type LaneId = 'papers' | 'web' | 'summarizer' | 'factcheck'
export type StepStatus = StepState | 'pending' | 'unreported'

export type StepView = {
  id: string
  label: string
  status: StepStatus
  startedAt: string | null
  endedAt: string | null
  message: string
  chips: string[]
  progress: { done: number; total: number } | null
  approx: boolean
}

export type LaneView = {
  id: LaneId
  title: string
  subtitle: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  startedAt: string | null
  endedAt: string | null
  summary: string
  steps: StepView[]
}

export type TimelineModel = {
  source: 'events' | 'reconstructed' | 'none'
  planner: { status: 'pending' | 'running' | 'completed' | 'failed'; startedAt: string | null; endedAt: string | null; subQuestions: number | null; queries: number | null; anchor: string | null; topics: string[] }
  retrieval: { startedAt: string | null; endedAt: string | null; lanes: [LaneView, LaneView] }
  summarizer: LaneView
  /** Stage 4. null unless a fact-check event arrived, so a run without it looks as before. */
  factcheck: LaneView | null
}

const DEFS: Record<LaneId, { id: string; label: string }[]> = {
  papers: [
    { id: 'search', label: 'Search OpenAlex, Scopus and arXiv' },
    { id: 'relevance_filter', label: 'Judge relevance (embedding shortlist, then the LLM judge)' },
    { id: 'citations', label: 'Fetch citation counts' },
    { id: 'scoring', label: 'Score reliability and rank' },
    { id: 'store', label: 'Save the papers' },
    { id: 'parsing', label: 'Parse the best PDFs to text' },
  ],
  web: [
    { id: 'search', label: 'Search the web' },
    { id: 'scoring', label: 'Score source reliability' },
    { id: 'store', label: 'Save the web sources' },
  ],
  summarizer: [
    { id: 'prepare', label: 'Select the passages to read' },
    { id: 'digest', label: 'Read the sources (LLM digests)' },
    { id: 'judge', label: 'Judge the evidence (LLM judge, coverage)' },
    // Only when the server runs Loop 2 (LOOP2=true). Left out of the lane when no such event arrives, so a run without it looks as before.
    { id: 'loop2', label: SUBSTEP_TITLE },
    { id: 'store', label: 'Save digests and coverage' },
  ],
  // Stage 4. These steps repeat for every sub-question (about 3 minutes each).
  factcheck: [
    { id: 'claims', label: 'Read the claims of each source' },
    { id: 'clusters', label: 'Group the claims that say the same thing' },
    { id: 'support', label: 'Check that each quote supports its claim' },
    { id: 'conflicts', label: 'Look for sources that disagree' },
    { id: 'store', label: 'Save the results' },
  ],
}

const n = (d: Record<string, unknown>, k: string): number | null => (typeof d[k] === 'number' ? (d[k] as number) : null)
const s = (d: Record<string, unknown>, k: string): string | null => (typeof d[k] === 'string' && d[k] ? (d[k] as string) : null)

/** The short facts shown next to a step, taken from the latest report of that step. Only numbers the pipeline actually reported. */
function chipsFor(lane: LaneId, step: string, d: Record<string, unknown>, done: boolean): string[] {
  const out: string[] = []
  const add = (v: number | null, text: (v: number) => string) => { if (v != null) out.push(text(v)) }
  if (lane === 'papers') {
    if (step === 'search') { done ? add(n(d, 'candidates'), v => `${v} candidate papers`) : (add(n(d, 'queries'), v => `${v} queries`), add(n(d, 'subQuestions'), v => `${v} sub-questions`)) }
    if (step === 'relevance_filter') {
      add(n(d, 'candidates'), v => `${v} candidates`); add(n(d, 'shortlisted'), v => `${v} shortlisted by embeddings`); add(n(d, 'judged'), v => `${v} LLM judge calls`)
      add(n(d, 'passed'), v => `${v} passed`); add(n(d, 'judgeUnavailable'), v => (v > 0 ? `${v} kept without a verdict` : ''))
      const b = s(d, 'backend'); if (b && b !== 'none') out.push(`judge: ${b}`)
    }
    if (step === 'citations') add(n(d, 'kept'), v => `${v} kept`)
    if (step === 'scoring') add(n(d, 'scored'), v => `${v} scored`)
    if (step === 'store') add(n(d, 'stored'), v => `${v} saved`)
    if (step === 'parsing') { add(n(d, 'usable'), v => `${v} parsed`); add(n(d, 'target'), v => `target ${v}`); add(n(d, 'attempted'), v => `${v} PDFs tried`) }
  } else if (lane === 'web') {
    if (step === 'search') add(n(d, 'found'), v => `${v} sources found`)
    if (step === 'scoring') add(n(d, 'scored'), v => `${v} scored`)
    if (step === 'store') add(n(d, 'stored'), v => `${v} saved`)
  } else if (lane === 'factcheck') {
    // the counts the step carried for the sub-question it is working on now
    if (step === 'claims') add(n(d, 'sources'), v => `${v} sources`)
    if (step === 'clusters') add(n(d, 'claims'), v => `${v} claims`)
    if (step === 'support') add(n(d, 'clusters'), v => `${v} grouped claims`)
    if (step === 'store') { add(n(d, 'claims'), v => `${v} claims checked`); add(n(d, 'disagreements'), v => (v > 0 ? `${v} disagreements` : '')) }
  } else {
    if (step === 'prepare') { add(n(d, 'jobs'), v => `${v} sources to read`); add(n(d, 'papers'), v => `${v} papers`); add(n(d, 'web'), v => `${v} web`) }
    if (step === 'digest') { add(n(d, 'done'), v => `${v} read`); add(n(d, 'failures'), v => (v > 0 ? `${v} failed` : '')) }
    if (step === 'judge') { add(n(d, 'sufficientSubQuestions') ?? n(d, 'sufficientSoFar'), v => `${v} with enough evidence`) }
    if (step === 'store') add(n(d, 'stored'), v => `${v} digests saved`)
  }
  return out.filter(Boolean)
}

/** Loop 2 reports in two shapes: {loop2Step, aspects} when it climbs a rung of the ladder, and {subQuestion, searched, covered} per sub-question searched
 *  again; the last event (completed) carries the totals. Unknown or malformed data is ignored. */
function loop2Chips(evs: WorkflowEvent[], done: boolean): string[] {
  const out: string[] = []
  const rung = [...evs].reverse().find(e => typeof e.data.loop2Step === 'string')
  if (rung && !done) {
    const a = n(rung.data, 'aspects')
    out.push(`now: ${ladderLabel(String(rung.data.loop2Step))}${a != null ? ` (${a} aspect${a === 1 ? '' : 's'})` : ''}`)
  }
  const completed = [...evs].reverse().find(e => e.data.state === 'completed')
  let searched = completed ? n(completed.data, 'searched') : null
  let covered = completed ? n(completed.data, 'covered') : null
  if (searched == null || covered == null) {                       // still running: add up the latest report of each sub-question
    const per = new Map<string, { searched: number; covered: number }>()
    for (const e of evs) {
      const sq = s(e.data, 'subQuestion')
      const a = n(e.data, 'searched')
      const c = n(e.data, 'covered')
      if (sq && a != null && c != null) per.set(sq, { searched: a, covered: c })
    }
    if (per.size > 0) { searched = [...per.values()].reduce((x, y) => x + y.searched, 0); covered = [...per.values()].reduce((x, y) => x + y.covered, 0) }
  }
  if (searched != null) out.push(`${searched} aspect${searched === 1 ? '' : 's'} searched again`)
  if (covered != null) out.push(`${covered} covered`)
  return out
}

function progressFor(step: string, d: Record<string, unknown>): { done: number; total: number } | null {
  const [a, b] = step === 'parsing' ? [n(d, 'usable'), n(d, 'target')] : [n(d, 'done'), n(d, 'total')]
  return a != null && b != null && b > 0 ? { done: Math.min(a, b), total: b } : null
}

function laneFromEvents(lane: LaneId, events: WorkflowEvent[], title: string, subtitle: string, runFailed: boolean): LaneView {
  const mine = events.filter(e => (e.event === 'step' && e.data.lane === lane) || (e.event === 'branch_started' && e.data.branch === lane))
  const hasLoop2 = lane === 'summarizer' && mine.some(e => e.event === 'step' && e.data.step === 'loop2')
  const steps: StepView[] = DEFS[lane].filter(def => def.id !== 'loop2' || hasLoop2).map(def => {
    const evs = mine.filter(e => e.event === 'step' && e.data.step === def.id)
    if (evs.length === 0) return { id: def.id, label: def.label, status: 'pending' as StepStatus, startedAt: null, endedAt: null, message: '', chips: [], progress: null, approx: false }
    const last = evs[evs.length - 1]
    const status = String(last.data.state ?? 'running') as StepState
    const closed = status !== 'running'
    let chips = def.id === 'loop2' ? loop2Chips(evs, status === 'completed') : chipsFor(lane, def.id, last.data, status === 'completed')
    if (def.id === 'judge' && hasLoop2) chips = [...chips, 'includes the second search']          // loop2 runs between the judge events, inside its span
    return {
      id: def.id, label: def.label, status, startedAt: evs[0].timestamp, endedAt: closed ? last.timestamp : null, message: last.message,
      chips, progress: closed || def.id === 'loop2' ? null : progressFor(def.id, last.data), approx: false,
    }
  })
  const started = mine[0]?.timestamp ?? null
  const completedEv = lane === 'summarizer'
    ? events.find(e => e.event === 'stage_completed' && e.stage === 'summarizer')
    : events.find(e => e.event === 'branch_completed' && e.data.branch === lane)
  const startedLane = lane === 'summarizer' ? events.find(e => e.event === 'stage_started' && e.stage === 'summarizer')?.timestamp ?? started : started
  const status: LaneView['status'] = completedEv ? 'completed' : startedLane ? (runFailed ? 'failed' : 'running') : 'pending'
  if (status === 'completed') for (const st of steps) if (st.status === 'pending') st.status = 'unreported'
  if (status === 'failed') {                      // the step that was running when the run failed
    const failedAt = events.find(e => e.event === 'run_failed')?.timestamp ?? null
    for (const st of steps) if (st.status === 'running') { st.status = 'failed'; st.endedAt = failedAt; st.progress = null }
  }
  return { id: lane, title, subtitle, status, startedAt: startedLane, endedAt: completedEv?.timestamp ?? null, summary: '', steps }
}

const PAPERS_TITLE: [string, string] = ['Paper retrieval', 'OpenAlex, Scopus, arXiv · relevance judge · scoring · PDF parsing']
const WEB_TITLE: [string, string] = ['Web search', 'search providers · reliability scoring']
const SUM_TITLE: [string, string] = ['Evidence digest and judging', 'LLM reads each source, then an independent judge checks the findings']
const FACT_TITLE: [string, string] = ['Fact check across sources', 'groups the claims that say the same thing · looks for sources that disagree']

/** Stage 4 as a lane. null when no fact-check event exists. The pipeline reports only "running" for the repeating steps, so a step that is not the
 *  latest one is shown as done (it moved on to the next), and a step that never reported is pending. A failed stage does not fail the run. */
function factLane(events: WorkflowEvent[]): LaneView | null {
  const p = factProgress(events)
  if (!p) return null
  const mine = events.filter(e => e.event === 'step' && e.data.lane === 'factcheck' && DEFS.factcheck.some(d => d.id === e.data.step))
  const steps: StepView[] = DEFS.factcheck.map(def => {
    const evs = mine.filter(e => e.data.step === def.id)
    if (evs.length === 0) return { id: def.id, label: def.label, status: (p.state === 'completed' ? 'unreported' : 'pending') as StepStatus, startedAt: null, endedAt: null, message: '', chips: [], progress: null, approx: false }
    const last = evs[evs.length - 1]
    const own = String(last.data.state ?? 'running') as StepState
    // a stage that failed stopped in the step that reported last
    let status: StepState = def.id === 'store' ? own : p.step === def.id && p.state !== 'completed' ? (p.state === 'failed' ? 'failed' : 'running') : 'completed'
    if (p.state === 'failed' && status === 'running') status = 'failed'
    const current = status === 'running'
    const chips = chipsFor('factcheck', def.id, last.data, !current)
    const sub = n(last.data, 'subQuestion'); const total = n(last.data, 'subQuestions')
    if (current && sub != null && total != null) chips.unshift(`sub-question ${sub} of ${total}`)
    return {
      id: def.id, label: def.label, status,
      startedAt: current ? last.timestamp : def.id === 'store' ? evs[0].timestamp : null, endedAt: def.id === 'store' && status !== 'running' ? last.timestamp : null,
      message: current ? p.line : '', chips, progress: null, approx: false,
    }
  })
  const r = p.result
  const summary = p.state === 'running' && p.subQuestion != null && p.subQuestions != null ? `sub-question ${p.subQuestion} of ${p.subQuestions} · about 3 minutes per sub-question`
    : r && r.claims != null ? `${r.claims} claims checked` : ''
  return { id: 'factcheck', title: FACT_TITLE[0], subtitle: FACT_TITLE[1], status: p.state, startedAt: p.startedAt, endedAt: p.endedAt, summary, steps }
}

export function buildTimeline(events: WorkflowEvent[], overview: PapersOverview | null): TimelineModel {
  const runFailed = events.some(e => e.event === 'run_failed')
  const hasSteps = events.some(e => e.event === 'step' || e.event === 'branch_started')

  const pStart = events.find(e => e.event === 'stage_started' && e.stage === 'planner')
  const pDone = events.find(e => e.event === 'stage_completed' && e.stage === 'planner')
  const planner: TimelineModel['planner'] = {
    status: pDone ? 'completed' : pStart ? (runFailed ? 'failed' : 'running') : 'pending', startedAt: pStart?.timestamp ?? null, endedAt: pDone?.timestamp ?? null,
    subQuestions: pDone ? n(pDone.data, 'subQuestions') : null, queries: pDone ? n(pDone.data, 'queries') : null, anchor: pDone ? s(pDone.data, 'domainAnchor') : null,
    topics: Array.isArray(pDone?.data.topics) ? (pDone!.data.topics as string[]) : [],
  }
  const rStart = events.find(e => e.event === 'stage_started' && e.stage === 'retrieval')?.timestamp ?? null
  const rEnd = events.find(e => e.event === 'stage_completed' && e.stage === 'retrieval')?.timestamp ?? null

  if (hasSteps) {
    const papers = laneFromEvents('papers', events, ...PAPERS_TITLE, runFailed)
    const web = laneFromEvents('web', events, ...WEB_TITLE, runFailed)
    const summarizer = laneFromEvents('summarizer', events, ...SUM_TITLE, runFailed)
    const c = overview?.counts
    papers.summary = c ? `${c.papersKept} kept · ${c.papersParsed} parsed` : ''
    web.summary = c ? `${c.webFound} sources` : ''
    summarizer.summary = c ? `${c.papersUsedAsEvidence} papers and ${c.webUsedAsEvidence} web sources used` : ''
    return { source: 'events', planner, retrieval: { startedAt: rStart, endedAt: rEnd, lanes: [papers, web] }, summarizer, factcheck: factLane(events) }
  }

  const t = overview?.timing
  if (overview && t && (t.papersStoredAt || t.webStoredAt || t.digestsFirstAt)) return reconstruct(overview, planner)

  const empty = (id: LaneId, title: string, subtitle: string): LaneView => ({ id, title, subtitle, status: 'pending', startedAt: null, endedAt: null, summary: '', steps: [] })
  return { source: 'none', planner, retrieval: { startedAt: rStart, endedAt: rEnd, lanes: [empty('papers', ...PAPERS_TITLE), empty('web', ...WEB_TITLE)] }, summarizer: empty('summarizer', ...SUM_TITLE), factcheck: factLane(events) }
}

/** A finished run without step events: rows were stamped when they were written, so each step shows the moment its result was saved. */
function reconstruct(ov: PapersOverview, planner: TimelineModel['planner']): TimelineModel {
  const t = ov.timing
  const c = ov.counts
  const step = (id: string, label: string, p: Partial<StepView>): StepView => ({ id, label, status: 'completed', startedAt: null, endedAt: null, message: '', chips: [], progress: null, approx: true, ...p })
  const plannedAt = t.plannedAt ?? null
  const papersEnd = t.parsingLastAt ?? t.papersStoredAt ?? null
  const papersSteps: StepView[] = [
    step('search', DEFS.papers[0].label, { status: 'unreported', message: 'Not recorded for this run.' }),
    step('relevance_filter', DEFS.papers[1].label, { chips: [`${c.papersJudged} papers passed the judge`], message: 'Only the papers that passed were kept; the judge calls themselves were not recorded.' }),
    step('citations', DEFS.papers[2].label, { status: 'unreported', message: 'Not recorded for this run.' }),
    step('scoring', DEFS.papers[3].label, { chips: [`${c.papersKept} scored`], endedAt: t.papersStoredAt ?? null, message: 'Saved together with the papers.' }),
    step('store', DEFS.papers[4].label, { chips: [`${c.papersKept} saved`], endedAt: t.papersStoredAt ?? null }),
    step('parsing', DEFS.papers[5].label, c.papersParsed > 0 ? { chips: [`${c.papersParsed} PDFs processed`], startedAt: t.papersStoredAt ?? t.parsingFirstAt ?? null, endedAt: t.parsingLastAt ?? null, message: 'Parsing starts as soon as the papers are saved; the end is when the last parsed paper was written.' } : { status: 'skipped', message: 'No paper was parsed.' }),
  ]
  const webSteps: StepView[] = [
    step('search', DEFS.web[0].label, { chips: [`${c.webFound} sources found`], endedAt: t.webStoredAt ?? null }),
    step('scoring', DEFS.web[1].label, { chips: [`${c.webFound} scored`], endedAt: t.webStoredAt ?? null, message: 'Saved together with the sources.' }),
    step('store', DEFS.web[2].label, { chips: [`${c.webFound} saved`], endedAt: t.webStoredAt ?? null }),
  ]
  const retrievalEnd = [papersEnd, t.webStoredAt].filter(Boolean).sort().pop() ?? null
  const sumEnd = t.coverageAt ?? t.digestsLastAt ?? null
  const sumSteps: StepView[] = [
    step('prepare', DEFS.summarizer[0].label, { status: 'unreported', message: 'Not recorded for this run.' }),
    step('digest', DEFS.summarizer[1].label, { chips: [`${c.papersUsedAsEvidence + c.webUsedAsEvidence} sources read`], endedAt: t.digestsFirstAt ?? null, message: 'Digests are saved after all of them are done.' }),
    step('judge', DEFS.summarizer[2].label, { endedAt: t.coverageAt ?? null }),
    step('store', DEFS.summarizer[4].label, { chips: [`${c.papersUsedAsEvidence + c.webUsedAsEvidence} digests saved`], endedAt: t.digestsLastAt ?? null }),
  ]
  const lane = (id: LaneId, def: [string, string], startedAt: string | null, endedAt: string | null, steps: StepView[], summary: string): LaneView => ({ id, title: def[0], subtitle: def[1], status: 'completed', startedAt, endedAt, summary, steps })
  return {
    source: 'reconstructed',
    planner: { ...planner, status: planner.status === 'pending' ? 'completed' : planner.status, endedAt: planner.endedAt ?? plannedAt },
    retrieval: { startedAt: plannedAt, endedAt: retrievalEnd, lanes: [
      lane('papers', PAPERS_TITLE, plannedAt, papersEnd, papersSteps, `${c.papersKept} kept · ${c.papersParsed} parsed`),
      lane('web', WEB_TITLE, plannedAt, t.webStoredAt ?? null, webSteps, `${c.webFound} sources`),
    ] },
    summarizer: lane('summarizer', SUM_TITLE, retrievalEnd, sumEnd, sumSteps, `${c.papersUsedAsEvidence} papers and ${c.webUsedAsEvidence} web sources used`),
    factcheck: null,
  }
}
