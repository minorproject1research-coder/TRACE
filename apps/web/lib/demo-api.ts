import { countsOf } from './factcheck'
import { demoWrittenResponse, demoWrittenStatus, type DemoWritten } from './demo-written'
import { demoFactChecks, demoFactDisagreements, demoFactTotals, type DemoFact } from './demo-factcheck'
import { demoDetail, demoOverview, type DemoStage } from './demo-papers'
import { stripLoop2Detail } from './demo-loop2'
import { demoReport } from './demo-report'
import { ApiError, TERMINAL_EVENTS, type CreateInput, type EventName, type Report, type RunStatus, type Session, type StageId, type StageState, type TraceApi, type WorkflowEvent } from './trace-types'

// DEMO MODE ONLY. A browser-side simulator of the TRACE API so the whole journey can be exercised without the backend
// (a real run takes 15-25 minutes). Everything it returns is fictional. A question containing the word "fail" makes the
// simulated run fail in the summarizer, to exercise the failure states. A question containing "factcheck" runs Stage 4 (fact check across sources);
// one containing "factfail" makes Stage 4 fail while the run still completes. Without either word Stage 4 is switched off (stage state 'not_run').
// A new run simulates the PARALLEL pipeline (judges interleaved, concurrent Loop 2, near step, replayed burst with occurredAt); a question containing "oldstyle"
// simulates the pipeline before it, to prove that old runs still render.

const STORE_KEY = 'trace.demo.sessions.v1'
const DEMO_PREFIX = 'demo-'

/** `occ`: when the event really happened, if that is earlier than `at` (a held event that was replayed). It is sent as data.occurredAt. */
type Beat = { at: number; occ?: number; event: EventName; stage: StageId | null; status: string | null; message: string; data: Record<string, unknown> }

/** `old`: the pipeline before the parallel work (no subQuestionIndex, no occurredAt, no near step): proves that old runs still render. */
type Stored = { id: string; question: string; createdAt: string; fails: boolean; seed?: 'completed' | 'failed'; fact?: DemoFact; old?: boolean; /** What the written report (Stage 5) of this run is. Default: from the fact-check mode. */ written?: DemoWritten }

const REL = { candidates: 24, shortlisted: 12, judged: 12, passed: 5, backend: 'server' }

function branch(at: number, lane: 'papers' | 'web'): Beat {
  return { at, event: 'branch_started', stage: 'retrieval', status: 'running', message: lane === 'papers' ? 'Paper retrieval started' : 'Web search started', data: { branch: lane } }
}
function step(at: number, lane: 'papers' | 'web' | 'summarizer', stepId: string, state: 'running' | 'completed', message: string, data: Record<string, unknown> = {}): Beat {
  return { at, event: 'step', stage: lane === 'summarizer' ? 'summarizer' : 'retrieval', status: state, message, data: { lane, step: stepId, state, ...data } }
}

/** Stage 4 runs after the summarizer, one sub-question after the other (about 3 minutes each on the real server). 5 sub-questions: the third has no Stage 3 result. */
function factcheckBeatsOld(fact: Exclude<DemoFact, 'off'>): Beat[] {
  const fstep = (at: number, stepId: string, state: 'running' | 'completed' | 'failed', message: string, data: Record<string, unknown> = {}): Beat => ({ at, event: 'step', stage: 'factcheck', status: state, message, data: { lane: 'factcheck', step: stepId, state, ...data } })
  const out: Beat[] = [
    { at: 13050, event: 'stage_started', stage: 'factcheck', status: 'running', message: 'Checking claims across sources', data: {} },
    fstep(13060, 'branch', 'running', 'Checking claims across sources'),                    // a step the page does not know: it must be ignored
  ]
  const N = 5
  const last = fact === 'failed' ? 2 : N                       // a failing stage stops in the second sub-question
  for (let i = 1; i <= last; i++) {
    const at = 13100 + (i - 1) * 600
    const c = { subQuestion: i, subQuestions: N }
    out.push(fstep(at, 'claims', 'running', `Reading the claims of ${i + 1} sources`, { ...c, sources: i + 1 }),
      fstep(at + 150, 'clusters', 'running', 'Grouping the claims that say the same thing', { ...c, claims: 4 + i }),
      fstep(at + 300, 'support', 'running', 'Checking that the quotes support the grouped claims', { ...c, clusters: 3 + i }),
      fstep(at + 450, 'conflicts', 'running', 'Looking for sources that disagree', c))
  }
  if (fact === 'failed') {
    out.push(fstep(14400, 'store', 'failed', 'Fact checking failed: ConnectionError'),
      { at: 14500, event: 'stage_completed', stage: 'factcheck', status: 'failed', message: 'Fact checking failed: ConnectionError', data: { error: 'ConnectionError: the database stayed unreachable (simulated)' } })
    return out
  }
  const t = demoFactTotals()
  const claims = t.supported + t.partially_supported + t.unverified + t.contradicted
  out.push(fstep(16050, 'store', 'running', 'Saving the fact-check results', { claims, disagreements: demoFactDisagreements() }),
    fstep(16150, 'store', 'completed', `${claims} claims checked`, { claims, supported: t.supported, partially_supported: t.partially_supported, contradicted: t.contradicted, unverified: t.unverified }),
    { at: 16300, event: 'stage_completed', stage: 'factcheck', status: 'completed', message: `Checked ${claims} claims: ${t.supported} supported, ${t.partially_supported} partially supported, ${t.unverified} unverified, ${t.contradicted} contradicted`,
      data: { claims, subQuestions: N, failedSubQuestions: 1, supported: t.supported, partially_supported: t.partially_supported, unverified: t.unverified, contradicted: t.contradicted, contested: t.contested, disagreements: demoFactDisagreements(), judgeFailures: 3 } })
  return out
}

/** The retrieval branches run AT THE SAME TIME (like the real graph); each reports its steps. */
function timelineOld(fails: boolean, fact: DemoFact = 'off'): Beat[] {
  const beats: Beat[] = [
    { at: 0, event: 'run_queued', stage: null, status: 'pending', message: 'Run queued', data: {} },
    { at: 700, event: 'run_started', stage: null, status: 'running', message: 'Run started', data: {} },
    { at: 900, event: 'stage_started', stage: 'planner', status: 'running', message: 'Planner started', data: {} },
    { at: 3200, event: 'stage_completed', stage: 'planner', status: 'completed', message: 'Planned 3 sub-questions and 9 search queries', data: { subQuestions: 3, queries: 9, domainAnchor: 'sample research field', topics: ['What is the sample method and how does it work?', 'How does the sample method scale to long inputs?', 'What are the open problems of the sample method?'] } },
    { at: 3500, event: 'stage_started', stage: 'retrieval', status: 'running', message: 'Retrieval started', data: {} },

    // ---- paper lane
    branch(3600, 'papers'),
    step(3650, 'papers', 'search', 'running', 'Searching OpenAlex, Scopus and arXiv', { subQuestions: 3, queries: 9 }),
    step(4600, 'papers', 'search', 'completed', 'Found 24 candidate papers', { candidates: 24 }),
    step(4650, 'papers', 'relevance_filter', 'running', 'Judging relevance (embedding shortlist, then the LLM judge)', { candidates: 24, done: 0, total: 3 }),
    step(5100, 'papers', 'relevance_filter', 'running', 'Judged sub-question 1 of 3', { done: 1, total: 3, candidates: 8, shortlisted: 4, judged: 4, passed: 2, backend: 'server' }),
    step(5600, 'papers', 'relevance_filter', 'running', 'Judged sub-question 2 of 3', { done: 2, total: 3, candidates: 16, shortlisted: 8, judged: 8, passed: 3, backend: 'server' }),
    step(6100, 'papers', 'relevance_filter', 'running', 'Judged sub-question 3 of 3', { done: 3, total: 3, ...REL }),
    step(6150, 'papers', 'relevance_filter', 'completed', '5 of 24 candidates passed (12 judge calls)', REL),
    step(6200, 'papers', 'citations', 'running', 'Fetching citation counts for the papers that passed', { papers: 5 }),
    step(6350, 'papers', 'citations', 'completed', '5 papers kept', { kept: 5 }),
    step(6400, 'papers', 'scoring', 'running', 'Scoring reliability and ranking', { papers: 5 }),
    step(6500, 'papers', 'scoring', 'completed', 'Scored 5 papers', { scored: 5 }),
    step(6550, 'papers', 'store', 'running', 'Saving the papers', { papers: 5 }),
    step(6650, 'papers', 'store', 'completed', 'Saved 5 papers', { stored: 5 }),
    step(6700, 'papers', 'parsing', 'running', 'Parsing the best 3 papers (PDF to text)', { target: 3, attempted: 0, usable: 0, papers: 5 }),
    step(7300, 'papers', 'parsing', 'running', 'Parsed 1 of 3 papers', { target: 3, attempted: 1, usable: 1 }),
    step(8000, 'papers', 'parsing', 'running', 'Parsed 2 of 3 papers', { target: 3, attempted: 2, usable: 2 }),
    step(8700, 'papers', 'parsing', 'running', 'Parsed 2 of 3 papers', { target: 3, attempted: 3, usable: 2 }),
    step(9000, 'papers', 'parsing', 'completed', '2 of 3 papers parsed', { target: 3, attempted: 3, usable: 2 }),
    { at: 9100, event: 'branch_completed', stage: 'retrieval', status: 'completed', message: 'Kept 5 papers', data: { branch: 'papers', papers: 5 } },

    // ---- web lane (same time as the paper lane)
    branch(3600, 'web'),
    step(3650, 'web', 'search', 'running', 'Searching the web', { subQuestions: 3, queries: 9, done: 0, total: 3 }),
    step(4200, 'web', 'search', 'running', 'Searched sub-question 1 of 3', { done: 1, total: 3, found: 1 }),
    step(4800, 'web', 'search', 'running', 'Searched sub-question 2 of 3', { done: 2, total: 3, found: 2 }),
    step(5400, 'web', 'search', 'running', 'Searched sub-question 3 of 3', { done: 3, total: 3, found: 3 }),
    step(5500, 'web', 'search', 'completed', 'Found 3 web sources', { found: 3 }),
    step(5550, 'web', 'scoring', 'running', 'Scoring source reliability', { sources: 3 }),
    step(5650, 'web', 'scoring', 'completed', 'Scored 3 sources', { scored: 3 }),
    step(5700, 'web', 'store', 'running', 'Saving the web sources', { sources: 3 }),
    step(5800, 'web', 'store', 'completed', 'Saved 3 web sources', { stored: 3 }),
    { at: 5900, event: 'branch_completed', stage: 'retrieval', status: 'completed', message: 'Found 3 web sources', data: { branch: 'web', webSources: 3 } },

    { at: 9200, event: 'stage_completed', stage: 'retrieval', status: 'completed', message: 'Retrieval finished', data: {} },
    { at: 9400, event: 'stage_started', stage: 'summarizer', status: 'running', message: 'Reading sources and checking evidence', data: {} },
    step(9450, 'summarizer', 'prepare', 'running', 'Selecting the passages to read (chunking, embeddings)', { subQuestions: 3 }),
    step(9700, 'summarizer', 'prepare', 'completed', '3 sources to read', { jobs: 3, papers: 2, web: 1 }),
    step(9800, 'summarizer', 'digest', 'running', 'Reading 3 sources with the LLM', { done: 0, total: 3, failures: 0 }),
    step(10500, 'summarizer', 'digest', 'running', 'Read 1 of 3 sources', { done: 1, total: 3, failures: 0 }),
    step(11200, 'summarizer', 'digest', 'running', 'Read 2 of 3 sources', { done: 2, total: 3, failures: 0 }),
    step(11900, 'summarizer', 'digest', 'running', 'Read 3 of 3 sources', { done: 3, total: 3, failures: 0 }),
    step(11950, 'summarizer', 'digest', 'completed', 'Read 3 sources', { done: 3, total: 3, failures: 0 }),
    step(12000, 'summarizer', 'judge', 'running', 'Judging the evidence for sub-question 1 of 3', { done: 0, total: 3 }),
    step(12250, 'summarizer', 'judge', 'running', 'Judged sub-question 1 of 3', { done: 1, total: 3, sufficient: true, judgeUsed: true, sufficientSoFar: 1 }),
    // Loop 2 (the optional second search) runs between the judge events: judge, loop2, judge, loop2, judge
    step(12300, 'summarizer', 'loop2', 'running', "Loop 2 (reselect): 2 aspect(s) of 'How does the sample method scale to long inputs?'", { loop2Step: 'reselect', aspects: 2 }),
    step(12400, 'summarizer', 'loop2', 'running', "Loop 2 searched again: 'How does the sample method scale to long inputs?'", { subQuestion: 'How does the sample method scale to long inputs?', searched: 2, covered: 1 }),
    step(12500, 'summarizer', 'judge', 'running', 'Judged sub-question 2 of 3', { done: 2, total: 3, sufficient: false, judgeUsed: true, sufficientSoFar: 1 }),
    step(12550, 'summarizer', 'loop2', 'running', "Loop 2 (pool): 1 aspect(s) of 'What are the open problems of the sample method?'", { loop2Step: 'pool', aspects: 1 }),
    step(12620, 'summarizer', 'loop2', 'running', "Loop 2 searched again: 'What are the open problems of the sample method?'", { subQuestion: 'What are the open problems of the sample method?', searched: 1, covered: 0 }),
    step(12700, 'summarizer', 'judge', 'running', 'Judged sub-question 3 of 3', { done: 3, total: 3, sufficient: false, judgeUsed: null, sufficientSoFar: 1 }),
    step(12730, 'summarizer', 'loop2', 'completed', 'Loop 2 finished: 3 aspect(s) searched again, 1 covered', { searched: 3, covered: 1 }),
    step(12750, 'summarizer', 'judge', 'completed', '1 of 3 sub-questions have enough evidence', { done: 3, total: 3, sufficientSubQuestions: 1 }),
    step(12800, 'summarizer', 'store', 'running', 'Saving the digests and coverage', { digests: 3 }),
    step(12900, 'summarizer', 'store', 'completed', 'Saved 3 digests', { stored: 3 }),
  ]
  if (fails) {
    // the summarizer stops while it is reading sources
    const failure: Beat = { at: 12500, event: 'run_failed', stage: 'summarizer', status: 'failed', message: 'DemoError: simulated failure in the summarizer', data: {} }
    return [...beats.filter(b => b.at < 11000), failure].sort((x, y) => x.at - y.at)
  }
  beats.push({ at: 13000, event: 'stage_completed', stage: 'summarizer', status: 'completed', message: 'Digested 3 sources; 1 of 3 sub-questions have sufficient evidence', data: { digests: 3, subQuestions: 3, sufficientSubQuestions: 1 } })
  if (fact === 'off') beats.push({ at: 13500, event: 'run_completed', stage: null, status: 'completed', message: 'Run finished', data: { reportUrl: '', stagesNotRun: ['factcheck', 'report'], ...oldUsage('off') } })
  else beats.push(...factcheckBeatsOld(fact), { at: fact === 'on' ? 16500 : 14800, event: 'run_completed', stage: null, status: 'completed', message: 'Run finished', data: { reportUrl: '', stagesNotRun: ['report'], ...oldUsage(fact) } })
  return beats.sort((x, y) => x.at - y.at)
}

// ------------------------------------------------------------------------------------------------------------------------ the parallel pipeline (2026-11-08)
// What the real stream looks like now (docs/API_HANDOFF.md, "Work that now runs at the same time"):
//  - 5 sub-questions, judged two at a time, each as soon as its own digests are done, so the judge events of different sub-questions interleave and
//    finish in any order; every judge and loop2 event carries subQuestionIndex; `done` counts finished sub-questions
//  - the judge and loop2 events that happened before the digest step ended are held and replayed right after it, each with data.occurredAt
//  - Stage 4 starts during Stage 3, one sub-question at a time in the order they were stored (2, 3, 1, 5, 4 here), with near and conflicts side by side;
//    its events are held until stage_started and then replayed as a burst, each with occurredAt; the rest arrive live
//  - the fact-check stage_completed has judgeWaits, and run_completed has the new Groq token purposes

const NEW_N = 5
const NEW_TOPICS = [
  'What is the sample method and how does it work?', 'How does the sample method scale to long inputs?', 'What are the open problems of the sample method?',
  'Which training settings does the sample method prefer?', 'How does the sample method compare with its baselines?',
]
const NEW_TOKENS = { digest: 41200, digest_loop2: 9600, aspect_split: 3300, query_expansion: 2500, stage4_merge: 18400, stage4_support: 22100, stage4_near: 9300, stage4_conflict: 14700, rerank_probe: 700, stage5_write: 9800, stage5_summary: 2100, stage5_check: 6400 }
const OLD_TOKENS = { digest: 41200, digest_loop2: 8800, aspect_split: 3100, query_expansion: 2400 }
const sumOf = (o: Record<string, number>) => Object.values(o).reduce((a, b) => a + b, 0)

/** Both retrieval branches for n sub-questions (the same shape as the old timeline, with the counts spread over n). */
function retrievalBeats(n: number): Beat[] {
  const candidates = 8 * n
  const rel = { candidates, shortlisted: 4 * n, judged: 4 * n, passed: 8, backend: 'server' }
  const out: Beat[] = [
    branch(3600, 'papers'),
    step(3650, 'papers', 'search', 'running', 'Searching OpenAlex, Scopus and arXiv', { subQuestions: n, queries: 3 * n }),
    step(4600, 'papers', 'search', 'completed', `Found ${candidates} candidate papers`, { candidates }),
    step(4650, 'papers', 'relevance_filter', 'running', 'Judging relevance (embedding shortlist, then the LLM judge)', { candidates, done: 0, total: n }),
  ]
  for (let i = 1; i <= n; i++) {
    out.push(step(Math.round(5100 + (i - 1) * (1000 / (n - 1))), 'papers', 'relevance_filter', 'running', `Judged sub-question ${i} of ${n}`,
      i === n ? { done: i, total: n, ...rel } : { done: i, total: n, candidates: 8 * i, shortlisted: 4 * i, judged: 4 * i, passed: Math.round((8 * i) / n), backend: 'server' }))
  }
  out.push(
    step(6150, 'papers', 'relevance_filter', 'completed', `8 of ${candidates} candidates passed (${4 * n} judge calls)`, rel),
    step(6200, 'papers', 'citations', 'running', 'Fetching citation counts for the papers that passed', { papers: 8 }),
    step(6350, 'papers', 'citations', 'completed', '8 papers kept', { kept: 8 }),
    step(6400, 'papers', 'scoring', 'running', 'Scoring reliability and ranking', { papers: 8 }),
    step(6500, 'papers', 'scoring', 'completed', 'Scored 8 papers', { scored: 8 }),
    step(6550, 'papers', 'store', 'running', 'Saving the papers', { papers: 8 }),
    step(6650, 'papers', 'store', 'completed', 'Saved 8 papers', { stored: 8 }),
    // the parsing step is silent between its start and the end of the round (the paper_parse events fill the gap)
    step(6700, 'papers', 'parsing', 'running', 'Parsing the best 8 papers (PDF to text)', { target: 8, attempted: 0, usable: 0, papers: 8 }),
    step(8750, 'papers', 'parsing', 'running', 'Parsed 5 of 8 papers', { target: 8, attempted: 8, usable: 5 }),
    step(9000, 'papers', 'parsing', 'completed', '5 of 8 papers parsed', { target: 8, attempted: 8, usable: 5 }),
    { at: 9100, event: 'branch_completed', stage: 'retrieval', status: 'completed', message: 'Kept 8 papers', data: { branch: 'papers', papers: 8 } },
    branch(3600, 'web'),
    step(3650, 'web', 'search', 'running', 'Searching the web', { subQuestions: n, queries: 3 * n, done: 0, total: n }),
  )
  for (let i = 1; i <= n; i++) out.push(step(Math.round(4200 + (i - 1) * (1200 / (n - 1))), 'web', 'search', 'running', `Searched sub-question ${i} of ${n}`, { done: i, total: n, found: i }))
  out.push(
    step(5500, 'web', 'search', 'completed', `Found ${n} web sources`, { found: n }),
    step(5550, 'web', 'scoring', 'running', 'Scoring source reliability', { sources: n }),
    step(5650, 'web', 'scoring', 'completed', `Scored ${n} sources`, { scored: n }),
    step(5700, 'web', 'store', 'running', 'Saving the web sources', { sources: n }),
    step(5800, 'web', 'store', 'completed', `Saved ${n} web sources`, { stored: n }),
    { at: 5900, event: 'branch_completed', stage: 'retrieval', status: 'completed', message: `Found ${n} web sources`, data: { branch: 'web', webSources: n } },
  )
  return out
}

/** A note (lane "notes"): data.step is the code, data.level info or warn, data.stage the stage it belongs to. */
function note(at: number, code: string, stage: 'planner' | 'retrieval' | 'summarizer' | 'report', level: 'info' | 'warn', message: string, data: Record<string, unknown> = {}, occ?: number): Beat {
  return { at, ...(occ != null ? { occ } : {}), event: 'step', stage, status: 'completed', message, data: { lane: 'notes', step: code, state: 'completed', level, stage, ...data } }
}

/** One event per paper that reached an end of its parsing (lane "papers", step "paper_parse"). */
const DEMO_PAPERS: [string, 'parsed' | 'abstract_only' | 'failed', string | null, string | null, number | null, string][] = [
  ['[Sample] A Fictional Method for Signal Tracing', 'parsed', 'own link', null, 48210, 'demo-sq-1'],
  ['[Sample] Scaling Fictional Tracers to Long Inputs', 'parsed', 'parse cache', null, 51377, 'demo-sq-2'],
  ['[Sample] Open Problems of Fictional Tracers', 'parsed', 'parse cache', null, 33940, 'demo-sq-3'],
  ['[Sample] Training Recipes For Fictional Tracers', 'parsed', 'own link', null, 40102, 'demo-sq-5'],
  ['[Sample] Re-reading Pays Off', 'parsed', 'own link', null, 27655, 'demo-sq-4'],
  ['[Sample] Production Costs of Fictional Tracers', 'abstract_only', 'own link', 'HTTP 403', null, 'demo-sq-4'],
  ['[Sample] A Paywalled Survey of Tracers', 'abstract_only', 'own link', 'known failure (publisher paywall)', null, 'demo-sq-1'],
  ['[Sample] Robustness of Tracers Under Noise (landing page)', 'failed', 'own link', 'html or non-PDF response', null, 'demo-sq-4'],
]
function paperParseBeats(): Beat[] {
  return DEMO_PAPERS.map(([title, outcome, route, reason, chars, sq], k) => ({
    at: 6900 + k * 230, event: 'step' as const, stage: 'retrieval' as const, status: 'completed', message: `${outcome === 'parsed' ? 'Parsed' : outcome === 'failed' ? 'Could not parse' : 'Kept the abstract of'} ${title}`,
    data: { lane: 'papers', step: 'paper_parse', state: 'completed', paperId: `demo-paper-${k + 1}`, title, outcome, route, reason, chars, subQuestionId: sq },
  }))
}

/** A held event of the summarizer: emitted at `at`, but it happened at `occ`. Without `occ` it is live. */
function held(occ: number | null, at: number, stepId: 'judge' | 'loop2' | 'loop2_step', message: string, data: Record<string, unknown>): Beat {
  return { ...step(at, 'summarizer', stepId, 'running', message, { ...data }), ...(occ != null ? { occ } : {}) }
}

/** The Loop 2 scenario (also in the report of lib/demo-loop2.ts): sub-question 4 goes through all three rungs, 5 is covered by the first, 2 is covered by the
 *  second and keeps a gap. Judges run two at a time, so they finish out of order; the ones that happened before the digest step ended are held and replayed. */
function summarizerBeatsNew(): Beat[] {
  const N = NEW_N
  const sq = (i: number) => ({ subQuestion: NEW_TOPICS[i - 1], subQuestionIndex: i, subQuestions: N })
  const start = (occ: number | null, at: number, i: number, done: number) => held(occ, at, 'judge', `Judging the evidence for sub-question ${i} of ${N}`, { ...sq(i), done, total: N })
  const finish = (occ: number | null, at: number, i: number, done: number, sufficient: boolean, soFar: number) =>
    held(occ, at, 'judge', `Judged sub-question ${i} of ${N}`, { done, total: N, subQuestionIndex: i, subQuestions: N, sufficient, judgeUsed: true, sufficientSoFar: soFar })
  const rung = (occ: number | null, at: number, i: number, r: 'reselect' | 'pool' | 'queries', aspects: number) =>
    held(occ, at, 'loop2', `Loop 2 (${r}): ${aspects} aspect(s) of '${NEW_TOPICS[i - 1]}'`, { loop2Step: r, aspects, subQuestionIndex: i, subQuestions: N })
  const loop2Done = (occ: number | null, at: number, i: number, searched: number, covered: number) =>
    held(occ, at, 'loop2', `Loop 2 done for sub-question ${i}`, { ...sq(i), searched, covered })
  // The result of one rung, as soon as it is finished (a separate step id: the loop2 events above are unchanged)
  const res = (occ: number | null, at: number, i: number, r: 'reselect' | 'pool' | 'queries', aspects: number, newSources: number, findings: number, covered: number, seconds: number, queries: Record<string, string[]> | null = null) =>
    held(occ, at, 'loop2_step', `Loop 2 (${r}) finished for sub-question ${i}`, { loop2Step: r, aspects, newSources, newVerifiedFindings: findings, covered, seconds, queries, error: null, subQuestionIndex: i, subQuestions: N })
  const gaps = (occ: number | null, at: number, i: number, g: number, searched: number, covered: number) =>
    note(at, 'loop2_gaps', 'summarizer', 'info', `Sub-question ${i}: ${g} aspect(s) stay without evidence`, { subQuestionIndex: i, subQuestions: N, gaps: g, searched, covered }, occ ?? undefined)

  const beats: Beat[] = [
    { at: 9400, event: 'stage_started', stage: 'summarizer', status: 'running', message: 'Reading sources and checking evidence', data: {} },
    step(9450, 'summarizer', 'prepare', 'running', 'Selecting the passages to read (chunking, embeddings)', { subQuestions: N }),
    step(9700, 'summarizer', 'prepare', 'completed', '10 sources to read', { jobs: 10, papers: 6, web: 4 }),
    step(9800, 'summarizer', 'digest', 'running', 'Reading 10 sources with the LLM', { done: 0, total: 10, failures: 0 }),
  ]
  for (let k = 1; k <= 10; k++) beats.push(step(9800 + k * 190, 'summarizer', 'digest', 'running', `Read ${k} of 10 sources`, { done: k, total: 10, failures: k > 7 ? 1 : 0 }))
  beats.push(step(11950, 'summarizer', 'digest', 'completed', 'Read 10 sources', { done: 10, total: 10, failures: 1, cacheHits: 4 }))

  // What happened before 11950, in the order it happened, replayed right after the digest step ended (each with occurredAt).
  const Q2 = { 'How does the sample method scale to long inputs?': ['scaling behaviour of the sample method on long inputs', 'sample method memory cost against sequence length benchmark', 'sample method long-context ablation study'] }
  const Q4 = {
    'How robust is it to noise?': ['robustness of tracers to input noise', 'noise injection training for tracing', 'signal-to-noise ratio and tracing accuracy'],
    'Is the licence compatible with commercial use?': ['sample tracer licence commercial use', 'open source licence of the sample tracing method'],
    'What does it cost to run in production?': ['production cost of sample tracers', 'inference cost per request sample method'],
    'Can it be distilled?': ['distilling sample tracers into small models', 'knowledge distillation for tracing methods'],
  }
  const earlier: [number, (at: number) => Beat][] = [
    [10200, at => start(10200, at, 1, 0)],
    [10500, at => start(10500, at, 2, 0)],
    [10800, at => rung(10800, at, 2, 'reselect', 2)],
    [10900, at => finish(10900, at, 1, 1, true, 1)],
    [10905, at => start(10905, at, 3, 1)],
    [11000, at => res(11000, at, 2, 'reselect', 2, 1, 3, 0, 14.2)],
    [11050, at => rung(11050, at, 2, 'pool', 2)],
    [11400, at => finish(11400, at, 3, 2, true, 2)],
    [11405, at => start(11405, at, 4, 2)],
    [11450, at => res(11450, at, 2, 'pool', 2, 1, 2, 1, 41.8)],
    [11460, at => rung(11460, at, 2, 'queries', 1)],
    [11700, at => rung(11700, at, 4, 'reselect', 7)],
    [11780, at => res(11780, at, 2, 'queries', 1, 0, 0, 0, 175.4, Q2)],
    [11800, at => loop2Done(11800, at, 2, 2, 1)],
    [11801, at => gaps(11800, at, 2, 1, 2, 1)],
    [11850, at => finish(11850, at, 2, 3, false, 2)],
    [11855, at => start(11855, at, 5, 3)],
  ]
  earlier.forEach(([, make], k) => beats.push(make(11960 + k * 15)))

  // After the gate opened the events are live. Sub-questions 4 and 5 finish within 5 ms and reach the stream in the other order: done=5 before done=4.
  beats.push(
    rung(null, 12000, 5, 'reselect', 2),
    res(null, 12050, 4, 'reselect', 7, 3, 11, 1, 38.9),
    rung(null, 12100, 4, 'pool', 6),
    res(null, 12300, 5, 'reselect', 2, 1, 2, 1, 17.1),
    rung(null, 12310, 5, 'pool', 1),
    res(null, 12450, 4, 'pool', 6, 2, 6, 1, 71.5),
    rung(null, 12500, 4, 'queries', 4),
    res(null, 12800, 5, 'pool', 1, 0, 0, 0, 12.4),
    loop2Done(null, 12850, 5, 2, 1), gaps(null, 12851, 5, 1, 2, 1),
    res(null, 12880, 4, 'queries', 4, 4, 13, 2, 302.3, Q4),
    loop2Done(null, 12900, 4, 7, 4), gaps(null, 12901, 4, 2, 7, 4),
    finish(null, 12950, 4, 5, true, 3),
    finish(null, 12955, 5, 4, false, 2),
    step(13000, 'summarizer', 'loop2', 'completed', 'Loop 2 finished: 11 aspect(s) searched again, 6 covered', { searched: 11, covered: 6 }),
    step(13020, 'summarizer', 'judge', 'completed', '3 of 5 sub-questions have enough evidence', { done: N, total: N, sufficientSubQuestions: 3, cacheHits: 6 }),
    step(13060, 'summarizer', 'store', 'running', 'Saving the digests and coverage', { digests: 10 }),
    step(13100, 'summarizer', 'store', 'completed', 'Saved 10 digests', { stored: 10 }),
    { at: 13150, event: 'stage_completed', stage: 'summarizer', status: 'completed', message: 'Digested 10 sources; 3 of 5 sub-questions have sufficient evidence', data: { digests: 10, subQuestions: N, sufficientSubQuestions: 3 } },
  )
  return beats
}

/** Stage 4 with two workers. A sub-question joins the queue when its judge ends; the sub-questions are checked in the order they were stored (1, 3, 2, 5, 4),
 *  two at a time, and each ends with a `done` step. Everything that happened before stage_started arrives as a burst, in order, each with occurredAt. */
const FACT_PLAN: { i: number; start: number; dur: number; worker: 1 | 2 }[] = [
  { i: 1, start: 10950, dur: 1100, worker: 1 }, { i: 3, start: 11450, dur: 700, worker: 2 }, { i: 2, start: 12050, dur: 700, worker: 1 },
  { i: 5, start: 12945, dur: 700, worker: 1 }, { i: 4, start: 12950, dur: 700, worker: 2 },
]
const FSTART = 13200

function factcheckBeatsNew(fact: Exclude<DemoFact, 'off'>): Beat[] {
  const N = NEW_N
  const raw: Beat[] = []
  const f = (t: number, stepId: string, message: string, data: Record<string, unknown>): void => { raw.push({ at: t, event: 'step', stage: 'factcheck', status: 'running', message, data: { lane: 'factcheck', step: stepId, state: 'running', ...data } }) }
  const checks = demoFactChecks()
  for (const { i, start, dur, worker } of FACT_PLAN) {
    const c = { subQuestion: i, subQuestions: N }
    f(start, 'claims', `Reading the claims of ${i + 1} sources`, { ...c, sources: i + 1, worker })
    f(start + dur * 0.24, 'clusters', `Grouping ${4 + i} claims that say the same thing`, { ...c, claims: 4 + i })
    f(start + dur * 0.49, 'support', `Checking that the quotes support ${3 + i} grouped claims`, { ...c, clusters: 3 + i })
    f(start + dur * 0.73, 'near', 'Looking for close variants of single-source claims in other documents', c)
    f(start + dur * 0.73, 'conflicts', 'Looking for sources that disagree', c)
    const k = countsOf(checks[`demo-sq-${i}`])
    f(start + dur, 'done', `Sub-question ${i} checked`, { ...c, claims: k.supported + k.partially_supported + k.unverified + k.contradicted, supported: k.supported, partially_supported: k.partially_supported, unverified: k.unverified,
      contradicted: k.contradicted, disagreements: checks[`demo-sq-${i}`]?.disagreements.length ?? 0, judgeCalls: 6 + i, judgeCacheHits: i % 2, judgeWaits: i === 4 ? 2 : 0, judgeFailures: i === 3 ? 1 : 0, worker })
  }
  raw.sort((a, b) => a.at - b.at)
  const out: Beat[] = [
    { at: FSTART, event: 'stage_started', stage: 'factcheck', status: 'running', message: 'Checking claims across sources', data: {} },
    { at: FSTART + 2, event: 'step', stage: 'factcheck', status: 'running', message: 'Checking claims across sources', data: { lane: 'factcheck', step: 'branch', state: 'running' } },      // unknown to the page: ignored
  ]
  let k = 0
  for (const b of raw) {
    if (b.at < FSTART) out.push({ ...b, at: FSTART + 10 + k++ * 8, occ: Math.round(b.at) })        // held, then replayed in order after stage_started
    else out.push({ ...b, at: Math.round(b.at) })                                                 // live
  }
  if (fact === 'failed') {
    const cut = out.filter(b => b.at <= 13300 || b.occ != null)
    cut.push({ at: 13400, event: 'step', stage: 'factcheck', status: 'failed', message: 'Fact checking failed: ConnectionError', data: { lane: 'factcheck', step: 'store', state: 'failed' } },
      { at: 13500, event: 'stage_completed', stage: 'factcheck', status: 'failed', message: 'Fact checking failed: ConnectionError', data: { error: 'ConnectionError: the database stayed unreachable (simulated)' } })
    return cut
  }
  const t = demoFactTotals()
  const claims = t.supported + t.partially_supported + t.unverified + t.contradicted
  out.push({ at: 13700, event: 'step', stage: 'factcheck', status: 'running', message: 'Saving the fact-check results', data: { lane: 'factcheck', step: 'store', state: 'running', claims, disagreements: demoFactDisagreements() } },
    { at: 13800, event: 'step', stage: 'factcheck', status: 'completed', message: `${claims} claims checked`, data: { lane: 'factcheck', step: 'store', state: 'completed', claims, supported: t.supported, partially_supported: t.partially_supported, contradicted: t.contradicted, unverified: t.unverified } },
    { at: 13900, event: 'stage_completed', stage: 'factcheck', status: 'completed', message: `Checked ${claims} claims: ${t.supported} supported, ${t.partially_supported} partially supported, ${t.unverified} unverified, ${t.contradicted} contradicted`,
      data: { claims, subQuestions: N, failedSubQuestions: 1, supported: t.supported, partially_supported: t.partially_supported, unverified: t.unverified, contradicted: t.contradicted, contested: t.contested, disagreements: demoFactDisagreements(), judgeFailures: 1, judgeWaits: 2 } })
  return out
}

/** What a run's written report is: an explicit `written`, else from the fact-check mode (a new run with Stage 4 writes one; one whose Stage 4 failed has nothing to write from;
 *  an old-style run, and a run without Stage 4, never had Stage 5 on). */
export function writtenKind(s: Pick<Stored, 'fact' | 'old' | 'written'>): DemoWritten {
  if (s.written) return s.written
  if (s.fact === 'on') return s.old ? 'none' : 'warnings'
  return s.fact === 'failed' ? 'none' : 'off'
}

/** The report stage (Stage 5) of a new-style run: it starts when the fact check has ended. Stage 4 failed: it skips itself (stage5_skipped, ends not_run). */
function reportBeats(at0: number, fact: DemoFact, written: DemoWritten): Beat[] {
  const rstep = (at: number, id: string, state: 'running' | 'completed' | 'failed', message: string, data: Record<string, unknown> = {}): Beat =>
    ({ at, event: 'step', stage: 'report', status: state, message, data: { lane: 'report', step: id, state, ...data } })
  const out: Beat[] = [{ at: at0, event: 'stage_started', stage: 'report', status: 'running', message: 'Writing the report', data: {} }]
  if (fact !== 'on') {
    out.push(note(at0 + 40, 'stage5_skipped', 'report', 'info', 'Stage 5 was skipped: Stage 4 did not run, so there were no labels to write from'),
      { at: at0 + 80, event: 'stage_completed', stage: 'report', status: 'not_run', message: 'The written report did not run: Stage 4 did not run', data: {} })
    return out
  }
  const kind = written === 'running' ? 'completed' : written
  const res = demoWrittenResponse(kind as 'completed' | 'warnings' | 'insufficient' | 'failed')
  const sentences = res.report.overview?.counts?.sentences ?? 0, refs = res.report.references?.length ?? 0, warns = res.report.warnings?.length ?? 0
  const t = (k: number) => at0 + 60 + k * 140
  out.push({ at: at0 + 20, event: 'branch_started', stage: 'report', status: 'running', message: 'Written report started', data: { branch: 'report' } },
    rstep(t(0), 'sections', 'running', 'Planning the sections', { sections: 4 }), rstep(t(1), 'sections', 'completed', '4 sections planned', { sections: 4 }))
  if (kind === 'failed') {
    out.push(rstep(t(2), 'write', 'running', 'Writing the sentences', { jobs: 9 }), rstep(t(3), 'write', 'failed', 'RuntimeError: the writer model stayed unreachable (simulated)'),
      { at: t(4), event: 'stage_completed', stage: 'report', status: 'failed', message: 'The written report failed: RuntimeError (simulated). The evidence report is still available.', data: { status: 'failed', error: 'RuntimeError: the writer model stayed unreachable (simulated)' } })
    return out
  }
  if (kind === 'insufficient') {
    out.push(rstep(t(2), 'summary', 'completed', 'Nothing eligible to write about'), rstep(t(3), 'store', 'completed', 'Saved the report', { sections: 4, sentences: 0, references: 0, warnings: 0, stored: true }),
      { at: t(4), event: 'stage_completed', stage: 'report', status: 'completed', message: 'Written report: insufficient evidence', data: { status: 'insufficient_evidence', sections: 4, sentences: 0, references: 0, warnings: 0 } })
    return out
  }
  out.push(rstep(t(2), 'write', 'running', 'Writing the sentences', { jobs: 9 }), rstep(t(3), 'write', 'completed', '9 sentences written', { jobs: 9 }),
    rstep(t(4), 'validate', 'running', 'Checking the sentences'), rstep(t(5), 'validate', 'completed', 'Checked the sentences', { kept: kind === 'warnings' ? 8 : 9, fallback: kind === 'warnings' ? 1 : 0, dropped: kind === 'warnings' ? 1 : 0 }))
  if (kind === 'warnings') out.push(note(t(5) + 10, 'stage5_fallback', 'report', 'warn', '1 sentence uses the template wording', { count: 1 }), note(t(5) + 20, 'stage5_dropped', 'report', 'warn', '1 sentence was dropped by the final check', { count: 1 }))
  out.push(rstep(t(6), 'summary', 'completed', 'Wrote the overview and the conclusion'), rstep(t(7), 'references', 'completed', `Numbered ${refs} references`, { references: refs }),
    rstep(t(8), 'store', 'completed', 'Saved the report', { sections: 4, sentences, references: refs, warnings: warns, stored: true }),
    { at: t(9), event: 'stage_completed', stage: 'report', status: 'completed', message: `Written report: ${res.status.replace(/_/g, ' ')}`, data: { status: res.status, sections: 4, sentences, references: refs, warnings: warns } })
  return out
}

function timelineNew(fails: boolean, fact: DemoFact, written: DemoWritten = 'off'): Beat[] {
  const N = NEW_N
  const beats: Beat[] = [
    { at: 0, event: 'run_queued', stage: null, status: 'pending', message: 'Run queued', data: {} },
    { at: 700, event: 'run_started', stage: null, status: 'running', message: 'Run started', data: {} },
    { at: 900, event: 'stage_started', stage: 'planner', status: 'running', message: 'Planner started', data: {} },
    fact === 'failed' ? note(3100, 'plan_fallback', 'planner', 'warn', 'The planner model was unreachable: Groq wrote the plan') : note(3100, 'plan_cache', 'planner', 'info', 'The stored plan was reused'),
    { at: 3200, event: 'stage_completed', stage: 'planner', status: 'completed', message: `Planned ${N} sub-questions and ${3 * N} search queries`, data: { subQuestions: N, queries: 3 * N, domainAnchor: 'sample research field', topics: NEW_TOPICS } },
    { at: 3500, event: 'stage_started', stage: 'retrieval', status: 'running', message: 'Retrieval started', data: {} },
    note(4300, 's2_skipped', 'retrieval', 'warn', 'Semantic Scholar answered HTTP 429 and was skipped for this run'),
    ...retrievalBeats(N),
    ...paperParseBeats(),
    note(8800, 'chunk_warmup', 'retrieval', 'info', 'The text of 4 papers was prepared while the others were parsed', { papers: 4, chunks: 212 }),
    note(8950, 'parse_summary', 'retrieval', 'warn', '5 of 8 papers parsed', { attempted: 8, parsed: 5, abstractOnly: 2, failed: 1, fromParseCache: 2, reasons: { 'HTTP 403': 1, 'known failure (publisher paywall)': 1, 'html or non-PDF response': 1 } }),
    { at: 9200, event: 'stage_completed', stage: 'retrieval', status: 'completed', message: 'Retrieval finished', data: {} },
    ...summarizerBeatsNew(),
  ]
  if (fails) {
    // the summarizer stops while it is reading sources: the held judge events never appear
    const failure: Beat = { at: 11000, event: 'run_failed', stage: 'summarizer', status: 'failed', message: 'DemoError: simulated failure in the summarizer', data: {} }
    return slowDown(withGroq([...beats.filter(b => b.at < 10800), failure].sort((x, y) => x.at - y.at), NEW_TOKENS))
  }
  const done = (extra: Record<string, unknown>, notRun: string[]): Beat => ({ at: 0, event: 'run_completed', stage: null, status: 'completed', message: 'Run finished', data: { reportUrl: '', stagesNotRun: notRun, ...extra } })
  let tokens: Record<string, number>
  if (fact === 'off') {
    tokens = { digest: NEW_TOKENS.digest, digest_loop2: NEW_TOKENS.digest_loop2, aspect_split: NEW_TOKENS.aspect_split, query_expansion: NEW_TOKENS.query_expansion }
    beats.push({ ...done({}, ['factcheck', 'report']), at: 13500 })
  } else {
    beats.push(...factcheckBeatsNew(fact))
    const withReport = fact === 'failed' || (written !== 'off' && written !== 'none')                  // Stage 5 is on for this run (it skips itself when Stage 4 failed)
    if (withReport) beats.push(...reportBeats(Math.max(...beats.map(b => b.at)) + 100, fact, written))
    const wrote = fact === 'on' && withReport && written !== 'failed' && written !== 'insufficient'
    const drop = (o: Record<string, number>, keys: string[]) => Object.fromEntries(Object.entries(o).filter(([k, v]) => !keys.includes(k) && v > 0))
    tokens = fact === 'failed' ? { ...drop(NEW_TOKENS, ['stage5_write', 'stage5_summary', 'stage5_check', 'stage4_near', 'stage4_conflict', 'rerank_probe']), stage4_merge: 6100, stage4_support: 5200 }
      : wrote ? NEW_TOKENS : drop(NEW_TOKENS, ['stage5_write', 'stage5_summary', 'stage5_check'])
    beats.push({ ...done({}, withReport && (fact === 'on') ? [] : ['report']), at: Math.max(...beats.map(b => b.at)) + 200 })
  }
  const total = sumOf(tokens)
  const sorted = withGroq(beats.sort((x, y) => x.at - y.at), tokens)
  const end = sorted.find(b => b.event === 'run_completed')!
  end.data = { ...end.data, groqTokens: total, groqCalls: Math.round(total / 520), groqRateLimits: Math.floor(total / 14000), groqParkedSeconds: Math.floor(total / 14000) * 38, groqTokensByPurpose: tokens }
  return slowDown(sorted)
}

// ------------------------------------------------------------------------------------------------------------------------ Groq telemetry (data.groq)
/** Cumulative Groq use on every step and stage event: tokens grow with the work (digests, then the fact check), the rest follows from the tokens. The last
 *  value is the run's total. stage_completed also carries byPurpose (tokens by purpose so far). */
const PURPOSE_STAGE: Record<string, number> = { aspect_split: 0, query_expansion: 0, rerank_probe: 1, digest: 2, digest_loop2: 2, stage4_merge: 3, stage4_support: 3, stage4_near: 3, stage4_conflict: 3, stage5_write: 4, stage5_summary: 4, stage5_check: 4 }
const STAGE_ORDER = ['planner', 'retrieval', 'summarizer', 'factcheck', 'report']

function withGroq(beats: Beat[], tokens: Record<string, number>): Beat[] {
  const total = sumOf(tokens)
  const lastAt = Math.max(...beats.map(b => b.at))
  const pts: [number, number][] = [[0, 0], [3200, 0.03], [9200, 0.06], [11950, 0.38], [13150, 0.55], [Math.max(lastAt, 13151), 1]]
  const cum = (t: number): number => {
    for (let i = 1; i < pts.length; i++) if (t <= pts[i][0]) { const [t0, f0] = pts[i - 1], [t1, f1] = pts[i]; return (f0 + ((t - t0) / (t1 - t0)) * (f1 - f0)) * total }
    return total
  }
  const use = (t: number) => { const tk = Math.round(cum(t)); const rl = Math.floor(tk / 14000); return { tokens: tk, calls: Math.round(tk / 520), rateLimits: rl, parkedSeconds: rl * 38 } }
  return beats.map(b => {
    if (b.event !== 'step' && b.event !== 'stage_started' && b.event !== 'stage_completed') return b
    const g = use(b.at)
    if (b.event !== 'stage_completed' || !b.stage) return { ...b, data: { ...b.data, groq: g } }
    const idx = STAGE_ORDER.indexOf(b.stage)
    const by: Record<string, number> = {}
    for (const [k, v] of Object.entries(tokens)) { const ps = PURPOSE_STAGE[k] ?? 3; const part = ps <= idx ? 1 : b.stage === 'summarizer' && ps === 3 ? 0.6 : 0; if (part > 0 && v > 0) by[k] = Math.round(v * part) }
    return { ...b, data: { ...b.data, groq: { ...g, byPurpose: by } } }
  })
}

/** The real pipeline judges for minutes, the demo for seconds. Everything after the digest step ended is stretched, so the chips can be watched: two
 *  judging at once, Loop 2 on three sub-questions, the burst. The mapping is monotone, so the order of events, and of when things really happened, is kept. */
const GATE = 11950
const SLOW = 3
const stretch = (t: number) => (t <= GATE ? t : Math.round(GATE + (t - GATE) * SLOW))
const slowDown = (beats: Beat[]): Beat[] => beats.map(b => ({ ...b, at: stretch(b.at), ...(b.occ != null ? { occ: stretch(b.occ) } : {}) }))

/** Everything the old pipeline sent, and nothing it did not: no subQuestionIndex, no occurredAt, no near step, no judgeWaits, one stage4_judge purpose. */
const oldUsage = (fact: DemoFact) => {
  const t: Record<string, number> = fact === 'off' ? OLD_TOKENS : { ...OLD_TOKENS, stage4_judge: 61800 }
  return { groqTokens: sumOf(t), groqCalls: Math.round(sumOf(t) / 520), groqTokensByPurpose: t }
}

/** The timeline of a stored run: the parallel pipeline, or (old: true) the one before it. */
function timeline(s: Pick<Stored, 'fails' | 'fact' | 'old' | 'written'>): Beat[] {
  return s.old ? timelineOld(s.fails, s.fact ?? 'off') : timelineNew(s.fails, s.fact ?? 'off', writtenKind(s))
}

function load(): Stored[] {
  if (typeof window === 'undefined') return []
  try { return JSON.parse(localStorage.getItem(STORE_KEY) ?? '[]') as Stored[] } catch { return [] }
}
function save(items: Stored[]) { try { localStorage.setItem(STORE_KEY, JSON.stringify(items.slice(0, 50))) } catch { /* storage full or blocked: the demo just forgets */ } }

function seeded(): Stored[] {
  const ago = (min: number) => new Date(Date.now() - min * 60_000).toISOString()
  return [
    { id: 'demo-completed', question: 'How does the sample method compare with the baseline? (demo, old-style events)', createdAt: ago(95), fails: false, seed: 'completed', old: true },
    { id: 'demo-interrupted', question: 'What happened to this interrupted demo run?', createdAt: ago(300), fails: true, seed: 'failed' },
    { id: 'demo-factcheck', question: 'How does the sample method compare with the baseline? (demo, with the cross-check)', createdAt: ago(130), fails: false, seed: 'completed', fact: 'on' },
    { id: 'demo-factcheck-old', question: 'How does the sample method compare with the baseline? (demo, cross-check, old-style events)', createdAt: ago(145), fails: false, seed: 'completed', fact: 'on', old: true },
    { id: 'demo-written-ok', question: 'How does the sample method compare with the baseline? (demo, written report: completed)', createdAt: ago(110), fails: false, seed: 'completed', fact: 'on', written: 'completed' },
    { id: 'demo-written-insufficient', question: 'What is the sample method? (demo, written report: insufficient evidence)', createdAt: ago(115), fails: false, seed: 'completed', fact: 'on', written: 'insufficient' },
    { id: 'demo-written-failed', question: 'How does the sample method scale? (demo, written report: failed)', createdAt: ago(120), fails: false, seed: 'completed', fact: 'on', written: 'failed' },
    { id: 'demo-written-running', question: 'Which settings does the sample method prefer? (demo, the report is still being written)', createdAt: ago(125), fails: false, seed: 'completed', fact: 'on', written: 'running' },
    { id: 'demo-factcheck-failed', question: 'How does the sample method scale? (demo, the cross-check failed)', createdAt: ago(160), fails: false, seed: 'completed', fact: 'failed' },
  ]
}
function all(): Stored[] {
  const mine = load()
  return [...mine, ...seeded().filter(s => !mine.some(m => m.id === s.id))].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
}

function elapsed(s: Stored) { return s.seed ? Infinity : Date.now() - new Date(s.createdAt).getTime() }

/** The report stage before any event: queued when Stage 5 is on for the run (or will skip itself because Stage 4 failed), else not run. */
function reportInitial(s: Stored): StageState {
  if (s.old) return 'not_run'
  if (s.fact === 'failed') return 'pending'
  return s.fact === 'on' && writtenKind(s) !== 'none' && writtenKind(s) !== 'off' ? 'pending' : 'not_run'
}

function view(s: Stored): Session {
  const beats = timeline(s)
  const t = elapsed(s)
  const stages: Record<StageId, StageState> = { planner: 'pending', retrieval: 'pending', summarizer: 'pending', factcheck: s.fact ? 'pending' : 'not_run', report: reportInitial(s) }
  let status: RunStatus = 'pending'
  let error: string | null = null
  for (const b of beats) {
    if (b.at > t) break
    if (b.event === 'run_started') status = 'running'
    if (b.stage && (b.event === 'stage_started' || b.event === 'stage_completed')) stages[b.stage] = b.event === 'stage_started' ? 'running' : b.status === 'failed' ? 'failed' : b.status === 'not_run' ? 'not_run' : 'completed'
    if (b.event === 'run_completed') status = 'completed'
    if (b.event === 'run_failed') { status = 'failed'; error = b.message; if (b.stage) stages[b.stage] = 'failed' }
  }
  if (s.seed === 'failed') error = 'The run did not finish (the server restarted or the run was stopped)'
  return {
    id: s.id, question: s.question, status, createdAt: s.createdAt,
    // like the real API, a run that only exists in storage has no start/finish times
    startedAt: s.seed || status === 'pending' ? null : new Date(new Date(s.createdAt).getTime() + 700).toISOString(),
    finishedAt: !s.seed && (status === 'completed' || status === 'failed') ? new Date(new Date(s.createdAt).getTime() + beats[beats.length - 1].at).toISOString() : null,
    error, stages,
  }
}

/** What the simulated pipeline has written to its 'database' by now: papers kept (after retrieval), parsed (during), digests (after the summarizer). */
function stageOf(s: Stored): DemoStage | null {
  const t = elapsed(s)
  if (s.seed) return s.seed === 'completed' ? 'evidence' : 'parsed'
  if (t < 6650) return null                     // the papers are saved at 6.65 s (see timeline())
  if (t < 7300) return 'kept'
  const saved = timeline(s).find(b => b.data.lane === 'summarizer' && b.data.step === 'store' && b.data.state === 'completed')?.at ?? 12900
  if (t < saved || s.fails) return 'parsed'
  return 'evidence'
}

function toEvent(b: Beat, seq: number, base: number, id: string): WorkflowEvent {
  return {
    seq, event: b.event, stage: b.stage, status: b.status, message: b.message, timestamp: new Date(base + b.at).toISOString(),
    data: { ...b.data, ...(b.event === 'run_completed' ? { reportUrl: `/api/research/${id}/report` } : {}), ...(b.occ != null ? { occurredAt: new Date(base + b.occ).toISOString() } : {}) },
  }
}

/** The whole event list of a simulated run, as the stream would deliver it (for the tests and for reading the scenarios). */
export function demoEvents(opts: { fails?: boolean; fact?: DemoFact; old?: boolean; written?: DemoWritten }, base = Date.parse('2026-11-08T10:00:00Z')): WorkflowEvent[] {
  return timeline({ fails: !!opts.fails, fact: opts.fact, old: opts.old, written: opts.written }).map((b, seq) => toEvent(b, seq, base, 'demo-test'))
}

const wait = (ms: number) => new Promise(r => setTimeout(r, ms))
const polls = new Map<string, number>()                // how often a run's report was asked for while it is "being written"
const generated = new Map<string, number>()            // runs whose report was started with POST: polls left before it is ready
const find = (id: string) => all().find(s => s.id === id)

export const demoApi: TraceApi = {
  mode: 'demo',
  async health() { await wait(120); return { status: 'ok', activeRuns: all().filter(s => { const v = view(s).status; return v === 'pending' || v === 'running' }).length } },
  async list(limit = 20) { await wait(200); return all().slice(0, limit).map(s => { const v = view(s); return { id: v.id, question: v.question, status: v.status, createdAt: v.createdAt } }) },
  async create(input: CreateInput) {
    await wait(300)
    const s: Stored = { id: `${DEMO_PREFIX}${crypto.randomUUID().slice(0, 8)}`, question: input.question, createdAt: new Date().toISOString(), fails: /\bfail/i.test(input.question), old: /\boldstyle\b/i.test(input.question) || undefined, fact: /\bfactfail\b/i.test(input.question) ? 'failed' : /\bfactcheck\b/i.test(input.question) ? 'on' : undefined }
    save([s, ...load()])
    return view(s)
  },
  async get(id) { await wait(150); const s = find(id); if (!s) throw new ApiError('Research session not found', 404); return view(s) },
  async report(id) {
    await wait(350)
    const s = find(id)
    if (!s) throw new ApiError('Research session not found', 404)
    const v = view(s)
    if (v.status === 'pending' || v.status === 'running') throw new ApiError('The run is not finished yet; follow /events and read the report after run_completed', 409)
    if (v.status === 'failed' && s.seed === 'failed') throw new ApiError('Research session not found', 404)
    let report: Report = demoReport(s.id, s.question, s.createdAt, s.fact ?? 'off')
    if (s.old) report = stripLoop2Detail(report)                       // an old-style run: none of the new second-search fields
    if (v.status === 'failed') report.runError = v.error ?? undefined
    return report
  },
  async papers(id) {
    await wait(250)
    const s = find(id)
    if (!s) throw new ApiError('Research session not found', 404)
    const stage = stageOf(s)
    if (!stage) {
      const empty = demoOverview(id, 'kept', s.createdAt)
      return { ...empty, counts: Object.fromEntries(Object.keys(empty.counts).map(k => [k, 0])) as typeof empty.counts, papers: [], web: [], subQuestions: [] }
    }
    return demoOverview(id, stage, s.createdAt)
  },
  async writtenReport(id) {
    await wait(250)
    const s = find(id)
    const none = { state: 'none' as const, detail: 'No written report for this run (Stage 5 did not run, or it has not been stored)' }
    if (!s) return none
    const kind = writtenKind(s)
    const v = view(s)
    if (v.stages.report === 'running' || (kind === 'running' && (polls.get(id) ?? 0) < 3)) { if (kind === 'running') polls.set(id, (polls.get(id) ?? 0) + 1); return { state: 'running' as const } }
    const g = generated.get(id)
    if (g != null) { if (g > 0) { generated.set(id, g - 1); return { state: 'running' as const } } return { state: 'ready' as const, data: demoWrittenResponse('warnings', s.question) } }
    if (kind === 'off' || kind === 'none' || v.stages.report === 'not_run' || v.stages.report === 'pending') return none
    return { state: 'ready' as const, data: demoWrittenResponse((kind === 'running' ? 'completed' : kind) as 'completed' | 'warnings' | 'insufficient' | 'failed', s.question) }
  },
  async writeWrittenReport(id) {
    await wait(250)
    const s = find(id)
    if (!s) throw new ApiError('Research session not found', 404)
    if (writtenKind(s) === 'off') throw new ApiError('Stage 5 is switched off on the server (STAGE5=false), so the report cannot be written.', 400)
    if ((generated.get(id) ?? -1) > 0 || writtenKind(s) === 'running') throw new ApiError('A written report is already being written for this run', 409)
    generated.set(id, 1)                                           // one poll answers 202, then the report is ready
    return { state: 'started' }
  },
  async paper(id, paperId) {
    await wait(300)
    const s = find(id)
    const stage = s ? stageOf(s) : null
    const detail = stage ? demoDetail(paperId, stage) : null
    if (!detail) throw new ApiError('Paper not found in this research session', 404)
    return detail
  },
  subscribe(id, { onEvent, onStatus }) {
    const s = find(id)
    onStatus('connecting')
    if (!s) { setTimeout(() => onStatus('error', 'Research session not found'), 200); return () => {} }
    const timers: ReturnType<typeof setTimeout>[] = []
    let cancelled = false
    const beats = timeline(s)
    const base = new Date(s.createdAt).getTime()
    const deliver = (b: Beat, seq: number) => {
      if (cancelled) return
      const ev = toEvent(b, seq, base, id)
      onEvent(ev)
      if (TERMINAL_EVENTS.includes(b.event)) onStatus('closed')
    }
    timers.push(setTimeout(() => {
      if (cancelled) return
      onStatus('open')
      if (s.seed) {  // a run that only exists in storage gets one closing event, like the real API after a restart
        const last = beats[beats.length - 1]
        deliver({ ...last, at: 0, message: s.seed === 'failed' ? 'The run did not finish (the server restarted or the run was stopped)' : 'Run finished' }, 0)
        return
      }
      const t = elapsed(s)
      beats.forEach((b, seq) => {   // replay what already happened, schedule the rest
        if (b.at <= t) deliver(b, seq)
        else timers.push(setTimeout(() => deliver(b, seq), b.at - t))
      })
    }, 250))
    return () => { cancelled = true; timers.forEach(clearTimeout) }
  },
}
