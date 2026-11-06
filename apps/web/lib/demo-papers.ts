import type { PaperDetail, PaperEvidence, PaperFinding, PaperSummary, PapersOverview, WebSummary } from './trace-types'

// DEMO MODE ONLY. Fictional papers in the exact shape of GET /api/research/{id}/papers and /papers/{paper_id}.
// None of these publications exist, and nothing here comes from the TRACE backend.

const SQ1 = { id: 'demo-sq-1', topic: 'What is the sample method and how does it work?' }
const SQ2 = { id: 'demo-sq-2', topic: 'How does the sample method scale to long inputs?' }
const SQ3 = { id: 'demo-sq-3', topic: 'What are the open problems of the sample method?' }

const Q_TRAIN = 'Training proceeds in two phases, a broad pretraining phase followed by a short task-specific tuning phase.'
const Q_COST = 'Annotation cost fell by roughly half compared with a fully supervised baseline.'
const Q_SMALL = 'On datasets below one thousand examples the advantage was not significant.'
const Q_MISSING = 'The method needs no tuning at all for any downstream task or dataset size.'

const SURVEY_TEXT = `## [Sample] A Fictional Survey of Signal Tracing Methods

A. Example 1 B. Placeholder 2

1 Department of Fictional Studies, Example University 2 Placeholder Institute

## Abstract

Signal tracing methods connect weak observations to their sources. We survey how such methods are trained, what they cost and where they fail. This is invented sample text for demo mode.

## 1 Introduction

Signal tracing has been studied for many years [1, 2]. Early methods relied on hand-written rules, while recent methods learn the mapping from data. In this survey we describe the sample method, a learned tracer that is trained in a staged way.

## 2 The sample method

### 2.1 Training

${Q_TRAIN} The first phase uses unlabeled traces; the second phase uses a small labelled set.

### 2.2 Cost

Labelling is the main expense of any supervised approach. ${Q_COST} The saving comes almost entirely from the second phase.

| Setting | Labels used | Relative cost |
|---|---|---|
| Fully supervised | 10,000 | 1.00 |
| Sample method | 2,000 | 0.52 |
| Sample method, small data | 800 | 0.49 |

## 3 Limitations

${Q_SMALL} In that regime the pretraining phase has too little data to help, and a plain supervised model is just as good.

### 3.1 Open questions

How the method behaves on very long traces is not covered by the experiments reported here.

## References

See the list below.`

const GUIDE_TEXT = `## [Sample] Training Tricks for Sample Models

## Abstract

A grab bag of practical tips for training sample models. This paper was parsed but no finding was taken from it.

## 1 Tips

Use a warm-up. Use a decay schedule. Check your data twice.`

type Fixture = { summary: PaperSummary; abstract: string; text: string | null; outline: { heading: string; level: number }[]; figures: { page: number; label: string; caption: string }[]; refs: string[] }

const base = (o: Partial<PaperSummary> & Pick<PaperSummary, 'id' | 'title'>): PaperSummary => ({
  authors: [], year: null, venue: null, source: 'openalex', doi: null, arxivId: null, url: null, pdfUrl: null, citations: null, isPreprint: false,
  publishedDate: null, fieldsOfStudy: [], scores: { relevance: null, reliability: null, combined: null },
  judge: { relevant: true, confidence: 0.9, reason: 'The abstract addresses the sub-question directly.' }, tldr: null, abstractPreview: '',
  subQuestionId: SQ1.id, subQuestion: SQ1.topic, parse: { status: 'not_parsed', parserVersion: null }, evidence: null, ...o,
})

const FIXTURES: Fixture[] = [
  {
    summary: base({
      id: 'demo-paper-1', title: '[Sample] A Fictional Survey of Signal Tracing Methods', authors: ['A. Example', 'B. Placeholder'], year: 2024, venue: 'Journal of Sample Research',
      source: 'openalex', url: 'https://example.org/sample-survey', pdfUrl: 'https://example.org/sample-survey.pdf', citations: 120, scores: { relevance: 0.83, reliability: 0.95, combined: 0.81 },
      tldr: 'A survey of how signal tracing methods are trained, what they cost and where they fail.', parse: { status: 'parsed', parserVersion: 1 },
      fieldsOfStudy: ['Fictional studies'],
    }),
    abstract: 'Signal tracing methods connect weak observations to their sources. We survey how such methods are trained, what they cost and where they fail.',
    text: SURVEY_TEXT,
    outline: [{ heading: '1 Introduction', level: 1 }, { heading: '2 The sample method', level: 1 }, { heading: '2.1 Training', level: 2 }, { heading: '2.2 Cost', level: 2 }, { heading: '3 Limitations', level: 1 }, { heading: '3.1 Open questions', level: 2 }],
    figures: [{ page: 3, label: '1', caption: 'Figure 1: The two training phases of the sample method (invented figure).' }, { page: 5, label: '2', caption: 'Figure 2: Relative labelling cost by setting (invented figure).' }],
    refs: ['Example, A. (2019). Hand-written rules for tracing. Journal of Sample Research.', 'Placeholder, B. (2021). Learning to trace. Sample Proceedings.'],
  },
  {
    summary: base({
      id: 'demo-paper-2', title: '[Sample] Length Limits in Fictional Sequence Models', authors: ['C. Fiction'], year: 2023, venue: 'Sample Proceedings', source: 'arxiv', arxivId: '0000.00000',
      url: 'https://example.org/sample-length', pdfUrl: 'https://example.org/sample-length.pdf', isPreprint: true, citations: 12, scores: { relevance: 0.74, reliability: 0.55, combined: 0.62 },
      subQuestionId: SQ2.id, subQuestion: SQ2.topic,
    }),
    abstract: 'Memory use grows with the input length and is the main practical limit. We measure how compute grows with the number of tokens processed.',
    text: null, outline: [], figures: [], refs: [],
  },
  {
    summary: base({
      id: 'demo-paper-3', title: '[Sample] Training Tricks for Sample Models', authors: ['D. Practitioner'], year: 2022, venue: 'Sample Workshop', source: 'scopus',
      url: 'https://example.org/sample-tricks', citations: 4, scores: { relevance: 0.69, reliability: 0.5, combined: 0.58 }, parse: { status: 'parsed', parserVersion: 1 },
    }),
    abstract: 'A grab bag of practical tips for training sample models.',
    text: GUIDE_TEXT, outline: [{ heading: '1 Tips', level: 1 }], figures: [], refs: [],
  },
  {
    summary: base({
      id: 'demo-paper-4', title: '[Sample] Benchmarks for Signal Tracing', authors: ['E. Benchmark', 'F. Suite', 'G. Metric', 'H. Score'], year: 2025, venue: null, source: 'both',
      pdfUrl: 'https://example.org/sample-bench.pdf', citations: 31, scores: { relevance: 0.66, reliability: 0.35, combined: 0.5 }, subQuestionId: SQ2.id, subQuestion: SQ2.topic,
      judge: { relevant: true, confidence: 0.62, reason: 'Relevant to evaluation, only indirectly to scaling.' },
    }),
    abstract: 'We introduce a benchmark suite for signal tracing methods.', text: null, outline: [], figures: [], refs: [],
  },
  {
    summary: base({
      id: 'demo-paper-5', title: '[Sample] Open Problems in Fictional Tracing', authors: [], year: 2022, venue: null, source: 'scopus', citations: null, scores: { relevance: 0.6, reliability: 0.35, combined: 0.44 },
      subQuestionId: SQ3.id, subQuestion: SQ3.topic, parse: { status: 'parsed', parserVersion: 1 },
    }),
    abstract: '', text: '', outline: [], figures: [], refs: [],
  },
]

const FINDINGS: Record<string, { claim: string; quote: string; stance: PaperFinding['stance']; sq: typeof SQ1; reason: string }[]> = {
  'demo-paper-1': [
    { claim: 'The sample method is trained in two phases: a broad pretraining phase and a short task-specific tuning phase.', quote: Q_TRAIN, stance: 'supports', sq: SQ1, reason: 'The quote states both phases and their order.' },
    { claim: 'It reduces annotation cost compared with fully supervised approaches.', quote: Q_COST, stance: 'supports', sq: SQ1, reason: 'Direct statement of a measured advantage.' },
    { claim: 'Gains disappear on very small datasets.', quote: Q_SMALL, stance: 'contradicts', sq: SQ1, reason: 'Qualifies the advantage rather than stating one.' },
    { claim: 'No tuning is needed for any downstream task.', quote: Q_MISSING, stance: 'supports', sq: SQ1, reason: 'The quote could not be located in the source, so it cannot support the claim.' },
  ],
  'demo-paper-2': [
    { claim: 'Input length is limited mainly by memory use.', quote: 'Memory use grows with the input length and is the main practical limit.', stance: 'supports', sq: SQ2, reason: 'The quote names memory as the main limit.' },
  ],
}

export type DemoStage = 'kept' | 'parsed' | 'evidence'

const evidenceFor = (id: string, stage: DemoStage): PaperEvidence | null => {
  if (stage !== 'evidence') return null
  const f = FINDINGS[id]
  if (!f) return null
  const found = f.filter(x => locate(FIXTURES.find(p => p.summary.id === id)?.text ?? '', x.quote).length > 0).length
  return { level: id === 'demo-paper-1' ? 'full_text' : 'abstract', findings: f.length, quotesFound: id === 'demo-paper-2' ? f.length : found, weight: id === 'demo-paper-1' ? 0.81 : 0.55 }
}

/** Case-insensitive placement of a quote in the text, like the backend does (without its fuzzy fallback). */
function locate(text: string, quote: string) {
  const at = text.toLowerCase().indexOf(quote.toLowerCase())
  return at < 0 ? [] : [{ start: at, end: at + quote.length }]
}

const WEB: WebSummary[] = [
  { id: 'demo-web-1', title: '[Sample] Sample Method Explained: A Practitioner Guide', url: 'https://example.org/sample-guide', provider: 'sample-search', publishedDate: '2025-02-11', reliability: 0.41,
    snippet: 'Most teams start from a public checkpoint and tune it on their own task data. This is invented sample text.', subQuestionId: SQ1.id, subQuestion: SQ1.topic, evidence: null },
  { id: 'demo-web-2', title: '[Sample] Blog: What Happens When Inputs Get Long', url: 'https://example.org/sample-blog', provider: 'sample-search', publishedDate: null, reliability: 0.22,
    snippet: 'Once inputs get long, everything gets slower. This is invented sample text.', subQuestionId: SQ2.id, subQuestion: SQ2.topic, evidence: null },
  { id: 'demo-web-3', title: '[Sample] Forum thread: is tracing worth it?', url: 'https://example.org/sample-forum', provider: 'sample-search', publishedDate: '2024-11-30', reliability: 0.12,
    snippet: 'Opinions differ. This is invented sample text.', subQuestionId: SQ3.id, subQuestion: SQ3.topic, evidence: null },
]

export function demoOverview(id: string, stage: DemoStage, createdAt?: string): PapersOverview {
  const base = createdAt ? new Date(createdAt).getTime() : Date.now()
  const at = (offsetMs: number) => new Date(base + offsetMs).toISOString()
  const papers = FIXTURES.map(f => ({
    ...f.summary,
    abstractPreview: f.abstract.slice(0, 320),
    parse: stage === 'kept' ? { status: 'not_parsed' as const, parserVersion: null } : f.summary.parse,
    evidence: evidenceFor(f.summary.id, stage),
  })).sort((a, b) => (b.scores.combined ?? 0) - (a.scores.combined ?? 0))
  const web = WEB.map((w, i) => ({ ...w, evidence: stage === 'evidence' && i === 0 ? { level: 'web_snippet', findings: 1, quotesFound: 1, weight: 0.41 } : null }))
  const used = papers.filter(p => p.evidence)
  return {
    id,
    counts: {
      papersKept: papers.length, papersJudged: papers.length, papersParsed: papers.filter(p => p.parse.status === 'parsed').length, papersUsedAsEvidence: used.length,
      papersUsedFullText: used.filter(p => p.evidence?.level === 'full_text').length, papersUsedAbstractOnly: used.filter(p => p.evidence?.level !== 'full_text').length,
      papersWithPdfLink: papers.filter(p => p.pdfUrl).length, webFound: web.length, webUsedAsEvidence: web.filter(w => w.evidence).length, subQuestions: 3,
    },
    // what a run without step events is reconstructed from; the demo's own live runs have step events and do not use it
    timing: { plannedAt: at(3200), papersStoredAt: at(6650), parsingFirstAt: at(7300), parsingLastAt: at(9000), webStoredAt: at(5800), digestsFirstAt: at(12900), digestsLastAt: at(12900), coverageAt: at(12900) },
    subQuestions: [SQ1, SQ2, SQ3], papers, web,
  }
}

export function demoDetail(paperId: string, stage: DemoStage): PaperDetail | null {
  const f = FIXTURES.find(p => p.summary.id === paperId)
  if (!f) return null
  const summary = demoOverview('', stage).papers.find(p => p.id === paperId)!
  const text = f.text
  const findings: PaperFinding[] = stage !== 'evidence' ? [] : (FINDINGS[paperId] ?? []).map(x => {
    const spans = text ? locate(text, x.quote) : []
    return {
      claim: x.claim, quote: x.quote, stance: x.stance, quoteFound: paperId === 'demo-paper-2' ? true : spans.length > 0, subQuestion: x.sq.topic, spans,
      judgements: [{ aspect: x.sq.topic, verdict: spans.length > 0 || paperId === 'demo-paper-2' ? 'yes' : 'no', quoteSupportsClaim: spans.length > 0 ? 'yes' : 'no', answersAspect: 'yes', reason: x.reason }],
    }
  })
  return {
    paper: summary, abstract: f.abstract,
    parsed: summary.parse.status === 'parsed' ? { parserVersion: 1, chars: (text ?? '').length, text: text ?? '', outline: f.outline, figures: f.figures, references: f.refs, referenceCount: f.refs.length } : null,
    findings,
  }
}
