// Types for the TRACE API. Source of truth: docs/API_HANDOFF.md

export type RunStatus = 'pending' | 'running' | 'completed' | 'failed'
export type StageId = 'planner' | 'retrieval' | 'summarizer' | 'factcheck' | 'report'
export type StageState = 'pending' | 'running' | 'completed' | 'failed' | 'not_built' | 'unknown'

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

export type EventName = 'run_queued' | 'run_started' | 'stage_started' | 'branch_completed' | 'stage_completed' | 'run_completed' | 'run_failed'

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

export type AspectRow = { index: number; text: string | null; state: AspectState; yesVerdicts: number; sources: number }

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
  stance: 'supports' | 'contradicts' | 'neutral'
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
}

export type SubQuestionReport = {
  id: string
  topic: string
  detailQuestions: string[]
  coverage: Coverage | null
  sources: SourceReport[]
}

export type Report = {
  id: string
  question: string
  createdAt: string | null
  runError?: string
  stages: Record<StageId, 'completed' | 'incomplete' | 'unknown' | 'not_built'>
  totals: { subQuestions: number; subQuestionsSufficient: number; sources: number; findings: number; findingsQuoteFound: number }
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

export type PapersOverview = {
  id: string
  counts: {
    papersKept: number
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
