// Types for the TRACE API. Source of truth: docs/API_HANDOFF.md

export type RunStatus = 'pending' | 'running' | 'completed' | 'failed'
export type StageId = 'planner' | 'retrieval' | 'summarizer' | 'factcheck' | 'report'
/** not_run: the stage exists but was switched off for this run (Stage 4 with FACTCHECK off). not_built: the stage does not exist yet (Stage 5). */
export type StageState = 'pending' | 'running' | 'completed' | 'failed' | 'not_built' | 'not_run' | 'unknown'

export type Session = {
  id: string
  question: string
  status: RunStatus
  createdAt: string | null
  startedAt: string | null
  finishedAt: string | null
  error: string | null
  stages: Record<StageId, StageState>
}

export type RunSummary = Pick<Session, 'id' | 'question' | 'status' | 'createdAt'>

export type EventName = 'run_queued' | 'run_started' | 'stage_started' | 'branch_started' | 'step' | 'branch_completed' | 'stage_completed' | 'run_completed' | 'run_failed'

/** State of one step a node reports from inside a stage (event 'step': data = { lane, step, state, ...counts }). */
export type StepState = 'running' | 'completed' | 'skipped' | 'failed'

export type WorkflowEvent = {
  seq: number
  event: EventName
  stage: StageId | null
  status: string | null
  message: string
  data: Record<string, unknown>
  timestamp: string | null
}

export const TERMINAL_EVENTS: EventName[] = ['run_completed', 'run_failed']

export type AspectState = 'covered' | 'judged_insufficient' | 'no_candidates' | 'unjudged' | 'uncovered' | 'unknown'

export type AspectRow = {
  index: number
  text: string | null
  state: AspectState
  /** 'single_claims' | 'synthesis' | null. synthesis = the judge accepted the findings of several sources TOGETHER (Loop 2): weaker evidence. Open string on purpose. */
  coveredBy?: string | null
  yesVerdicts: number
  sources: number
}

// ---- Loop 2 (optional second search; the server runs it only with LOOP2=true). Everything is optional and tolerant: older runs carry null fields
// (gapRule, sufficientStrict, coveredBySynthesis, nearMiss) and the status words are open strings, so unknown values never break the page.

/** The ladder Loop 2 climbs for an aspect: reselect, pool, queries (in this order). */
export type Loop2LadderStep = 'reselect' | 'pool' | 'queries'

/** Judge verdicts per finding for one aspect. `after` also has the distinct sources behind the yes and partial verdicts. */
export type Verdicts = { yes: number; partial: number; no: number }
export type VerdictsAfter = Verdicts & { sources?: number | null }

/** The fields after `seconds` exist only for runs from 2026-11-10 on (null or absent before): never treat a missing one as an error. */
export type Loop2StepRow = {
  step: string; aspects: number; newSources: number; newVerifiedFindings: number; covered: number; seconds: number
  aspectTexts?: string[] | null
  coveredTexts?: string[] | null
  queryCount?: number | null
  /** {aspect text: [query texts]}; only the queries rung of newer runs. */
  queries?: Record<string, string[]> | null
  newPapersFound?: number | null; newPapersKept?: number | null; newPapersParsed?: number | null
  newWebFound?: number | null; newWebKept?: number | null
  digestTotal?: number | null; digestFailed?: number | null; sourcesTried?: number | null
  error?: string | null
  note?: string | null
}

/** status: covered | known_gap | known_gap_no_evidence | known_gap_skipped_triage | known_gap_skipped_cap | unjudged_not_searched (open string). */
export type Loop2Aspect = {
  text: string; status: string; coveredBy?: string | null; how?: string | null; nearMiss?: boolean | null; steps?: string[]
  /** Verdicts before the second search (aspects that were uncovered after Stage 3) and after it (newer runs only). Null or absent on older runs. */
  before?: Verdicts | null
  after?: VerdictsAfter | null
  /** Why the ladder stopped for this aspect: "time_budget" | "digests_failed" | null (open string). */
  stopped?: string | null
}

export type Loop2 = {
  searched: number
  covered: number
  seconds: number
  triage?: string | null
  /** 'core' (default with Loop 2): an aspect that stays uncovered after the whole search and has thin evidence does not stop `sufficient`. */
  gapRule?: string | null
  /** `sufficient` under the old, stricter rule (every aspect covered). `coverage.sufficient` is the gapRule value. */
  sufficientStrict?: boolean | null
  coveredBySynthesis?: number | null
  knownGapsNoEvidence?: string[]
  steps?: Loop2StepRow[]
  aspects?: Loop2Aspect[]
  knownGaps?: string[]
}

// ---- Stage 4 (optional fact checking across sources; the server runs it only with FACTCHECK=true). null / absent everywhere when it did not run.
// Labels and relations are open strings on purpose: an unknown word gets a neutral chip, never a crash.

/** `partially_supported` is missing in old stored reports and old events: read it as 0 (countsOf in lib/factcheck.ts does). */
export type FactCounts = { supported: number; partially_supported?: number; unverified: number; contradicted: number; contested: number }

/** One quote for, against or near a claim. `via: 'stage3_judge'` = the independent Stage 3 judge had already established that the quote supports the claim.
 *  `relation: 'near_match'` (only on a partially_supported claim, always its last row): another document's close variant of the claim, in its own wording (`nearClaim`). */
export type FactEvidence = {
  sourceId: string
  sourceTitle: string | null
  quote: string
  /** 'supports' | 'contradicts' | 'near_match' (open string) */
  relation: string
  /** Only on a near_match row: the other document's own wording of the claim. */
  nearClaim?: string | null
  reliability?: number | null
  evidenceLevel?: string | null
  prob?: number | null
  via?: string | null
}

export type FactClaim = {
  claim: string
  /** 'supported' | 'partially_supported' | 'unverified' | 'contradicted' (open string). NOT 'true' / 'false': see docs/STAGE4_OUTPUT.md. */
  label: string
  /** A ranking number (noisy-or of source weights, at most 0.95; partially_supported at most 0.6; unverified at most 0.5). NOT a probability that the claim is true. */
  confidence: number | null
  supportDocCount: number
  contraDocCount: number
  /** A supported claim that also has a weaker conflicting source. */
  contested: boolean
  evidence: FactEvidence[]
}

/** Two claims that disagree, each with its quote and source, and the judge's one-sentence reason. */
export type FactDisagreement = {
  claimA: string
  claimB: string
  sourceATitle: string | null
  sourceBTitle: string | null
  quoteA: string
  quoteB: string
  prob?: number | null
  reason: string | null
}

export type FactCheck = {
  counts: FactCounts
  /** Sorted by the server: contradicted, supported, partially_supported, unverified. */
  claims: FactClaim[]
  disagreements: FactDisagreement[]
}

export type Judgement = {
  aspect: string | null
  verdict: 'yes' | 'partial' | 'no' | null
  quoteSupportsClaim: string | null
  answersAspect: string | null
  reason: string | null
}

export type Finding = {
  claim: string
  quote: string
  /** The digest model's word for how the finding relates to the sub-question. Usually supports | contradicts | neutral, but it is free model output
   *  (a real run produced "challenges"): never index a table with it without a fallback, see stanceInfo() in lib/format.ts. */
  stance: string | null
  quoteFound: boolean
  judgements: Judgement[]
}

export type EvidenceLevel = 'full_text' | 'abstract' | 'web_snippet'

export type SourceReport = {
  id: string
  type: 'paper' | 'web'
  title: string | null
  evidenceLevel: EvidenceLevel
  weight: number | null
  findingsTotal: number
  findingsQuoteFound: number
  findings: Finding[]
  url?: string | null
  authors?: string[]
  year?: number | null
  venue?: string | null
  doi?: string | null
  arxivId?: string | null
  citations?: number | null
  origin?: string | null
  /** Set when Loop 2 added this source ('reselect' | 'pool' | 'queries'). Open string. */
  foundByLoop2Step?: string | null
  provider?: string | null
  publishedDate?: string | null
}

export type Coverage = {
  sufficient: boolean
  judgeUsed: boolean | null
  sourceCount: number | null
  fullTextSourceCount: number | null
  digestFailures: number | null
  aspects: AspectRow[]
  uncoveredAspects: string[]
  unjudgedAspects: string[]
  fallbackReason: string | null
  /** null or absent: Loop 2 did not run for this sub-question. */
  loop2?: Loop2 | null
}

export type SubQuestionReport = {
  id: string
  topic: string
  detailQuestions: string[]
  coverage: Coverage | null
  sources: SourceReport[]
  /** null or absent: Stage 4 did not run (or did not finish) for this sub-question. [] claims = it ran and found nothing to cross-check. */
  factCheck?: FactCheck | null
}

export type Report = {
  id: string
  question: string
  createdAt: string | null
  runError?: string
  stages: Record<StageId, 'completed' | 'incomplete' | 'unknown' | 'not_built' | 'not_run'>
  totals: { subQuestions: number; subQuestionsSufficient: number; sources: number; findings: number; findingsQuoteFound: number
            /** null or absent: Stage 4 did not run. */
            factChecked?: FactCounts | null }
  subQuestions: SubQuestionReport[]
  limitations: string[]
}

export type PaperEvidence = { level: string | null; findings: number | null; quotesFound: number | null; weight: number | null }

/** One paper the run kept after relevance filtering (GET /api/research/{id}/papers). */
export type PaperSummary = {
  id: string
  title: string | null
  authors: string[]
  year: number | null
  venue: string | null
  source: string | null            // openalex | scopus | arxiv | both
  doi: string | null
  arxivId: string | null
  url: string | null               // DOI link, arXiv page or PDF
  pdfUrl: string | null
  citations: number | null
  isPreprint: boolean | null
  publishedDate: string | null
  fieldsOfStudy: string[]
  scores: { relevance: number | null; reliability: number | null; combined: number | null }
  judge: { relevant: boolean | null; confidence: number | null; reason: string | null }
  tldr: string | null
  abstractPreview: string
  subQuestionId: string | null
  subQuestion: string | null
  parse: { status: 'parsed' | 'not_parsed'; parserVersion: number | null }
  evidence: PaperEvidence | null   // null: no finding was taken from this paper
}

export type WebSummary = {
  id: string
  title: string | null
  url: string | null
  provider: string | null
  publishedDate: string | null
  reliability: number | null
  snippet: string | null
  subQuestionId: string | null
  subQuestion: string | null
  evidence: PaperEvidence | null
}

/** When parts of the run were written to the database (UTC ISO). A run without step events is reconstructed from these. */
export type Timing = {
  plannedAt: string | null
  papersStoredAt: string | null
  parsingFirstAt: string | null
  parsingLastAt: string | null
  webStoredAt: string | null
  digestsFirstAt: string | null
  digestsLastAt: string | null
  coverageAt: string | null
}

export type PapersOverview = {
  id: string
  timing: Timing
  counts: {
    papersKept: number
    papersJudged: number
    papersParsed: number
    papersUsedAsEvidence: number
    papersUsedFullText: number
    papersUsedAbstractOnly: number
    papersWithPdfLink: number
    webFound: number
    webUsedAsEvidence: number
    subQuestions: number
  }
  subQuestions: { id: string; topic: string }[]
  papers: PaperSummary[]
  web: WebSummary[]
}

/** A character range in PaperDetail.parsed.text (UTF-16 code units, i.e. JavaScript string indexes). */
export type Span = { start: number; end: number }

export type PaperFinding = Finding & { subQuestion: string | null; spans: Span[] }

export type PaperDetail = {
  paper: PaperSummary
  abstract: string
  parsed: null | {
    parserVersion: number | null
    chars: number
    text: string                   // markdown from the parser
    outline: { heading: string; level: number }[]
    figures: { page: number | null; label: string | null; caption: string | null }[]
    references: string[]
    referenceCount: number
  }
  findings: PaperFinding[]
}

export type Health = { status: string; activeRuns: number }

export type CreateInput = { question: string }

export type StreamStatus = 'connecting' | 'open' | 'reconnecting' | 'closed' | 'error'

export type StreamHandlers = {
  onEvent: (event: WorkflowEvent) => void
  onStatus: (status: StreamStatus, detail?: string) => void
}

export class ApiError extends Error {
  status?: number
  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** The surface the UI talks to. Implemented by the live client (lib/trace-api.ts) and the demo simulator (lib/demo-api.ts). */
export interface TraceApi {
  mode: 'live' | 'demo'
  health(): Promise<Health>
  list(limit?: number): Promise<RunSummary[]>
  create(input: CreateInput): Promise<Session>
  get(id: string): Promise<Session>
  report(id: string): Promise<Report>
  /** The retrieval funnel and every paper / web source kept so far. Works while the run is going. */
  papers(id: string): Promise<PapersOverview>
  paper(id: string, paperId: string): Promise<PaperDetail>
  /** Returns an unsubscribe function. The stream closes itself after run_completed / run_failed. */
  subscribe(id: string, handlers: StreamHandlers): () => void
}
