import type { PillTone } from '@/components/trace/status-pill'
import type { StageState, WrittenDisagreement, WrittenReference, WrittenReport, WrittenReportResponse, WrittenSection, WrittenSentence } from './trace-types'

// Pure view-model of the written report (Stage 5, docs/STAGE5_OUTPUT.md). No React here, so the rules are unit-tested (tests/written-report.test.ts).
//
// Rules that must hold wherever a sentence is shown:
//  - the text of a sentence never contains a marker; the renderer adds "[1, 3]" from `refs`, before the final full stop
//  - each marker links to the reference with that number
//  - tier `partly` always carries the label "partly supported"; tier `single` always carries "one source, not confirmed" and never looks like a confirmed finding;
//    a tier this page does not know is treated like `single` (labelled with its own word, never styled as confirmed)
//  - sources that disagree are shown with both sides, each with its quote and reference; never "X is false"
//  - the legend is always shown; the limitations are never collapsed; warnings and the non-completed statuses are visible states
//  - a missing field shows as nothing, never as an error

/** The single-source legend of the Markdown (STAGE5_OUTPUT.md, "What must always be shown"). */
export const LEGEND = 'How to read the findings: a sentence that starts with “Two sources report” is stated by two or more documents; a finding marked (partly supported) rests on one document with a related point in another; single-source findings are attributed to one document and are not confirmed. Citation numbers point to the references at the end.'

export const PARTLY_LABEL = 'partly supported'
export const SINGLE_LABEL = 'one source, not confirmed'
export const NOT_A_VERIFIED_ANSWER = 'This report is not a verified answer. Every check is automatic (language models and rules); none was reviewed by a person.'

export const POLL_MS = 3000

// ------------------------------------------------------------------------------------------------------------------------ markers and tiers
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const arr = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : [])
const strs = (v: unknown): string[] => arr<unknown>(v).filter((x): x is string => typeof x === 'string' && x.trim() !== '')

/** "[1, 3]": the numbers of `refs`, joined with ", " in one pair of brackets, in the order given. Empty for a sentence without references. */
export function markers(refs: unknown): string {
  const n = arr<unknown>(refs).filter(isNum)
  return n.length ? `[${n.join(', ')}]` : ''
}

/** A sentence split around its final full stop, so the markers go before it: `Two sources report that X [1, 3].` Without a final stop the markers follow the text. */
export function sentenceParts(s: Pick<WrittenSentence, 'text' | 'refs'>): { body: string; stop: string; refs: number[] } {
  const text = typeof s?.text === 'string' ? s.text.trimEnd() : ''
  const m = /^([\s\S]*?)([.!?]["”')\]]*)$/.exec(text)
  const refs = arr<unknown>(s?.refs).filter(isNum)
  return m && m[1].trim() !== '' ? { body: m[1], stop: m[2], refs } : { body: text, stop: '', refs }
}

export type TierKind = 'supported' | 'partly' | 'single' | 'other'
export type TierView = { kind: TierKind; /** The label that must accompany the sentence; null only for a supported sentence. */ label: string | null; tone: PillTone; hint: string }

export function tierView(tier: string | null | undefined): TierView {
  switch ((tier ?? '').trim().toLowerCase()) {
    case 'supported': return { kind: 'supported', label: null, tone: 'mint', hint: 'Stated by two or more documents.' }
    case 'partly': return { kind: 'partly', label: PARTLY_LABEL, tone: 'blue', hint: 'One document states this and another document makes a related point. A lead, not a confirmed fact.' }
    case 'single': return { kind: 'single', label: SINGLE_LABEL, tone: 'neutral', hint: 'One document states this. It is attributed to that document and is not confirmed by a second source.' }
    default: {
      const w = (tier ?? '').trim()
      return { kind: 'other', label: w ? `${w.replace(/_/g, ' ')} (not confirmed)` : SINGLE_LABEL, tone: 'neutral', hint: 'A kind of finding this page does not know. Treat it as not confirmed.' }
    }
  }
}

export const refHref = (n: number): string => `#ref-${n}`

/** The reference a marker points to: the entry numbered n (numbers are 1-based and contiguous, so the list index n - 1 is the fallback). null for an unknown number. */
export function refFor(refs: WrittenReference[] | undefined, n: number): WrittenReference | null {
  const list = arr<WrittenReference>(refs)
  return list.find(r => r?.number === n) ?? (isNum(n) && n >= 1 ? list[n - 1] ?? null : null)
}

/** "abstract only" / "web snippet" for a source that was not read in full; nothing for full text or an unknown field. */
export function evidenceHint(level: string | null | undefined): string | null {
  if (!level || level === 'full_text') return null
  if (level === 'abstract') return 'abstract only'
  if (level === 'web_snippet') return 'web snippet'
  return String(level).replace(/_/g, ' ')
}

// ------------------------------------------------------------------------------------------------------------------------ status
export type StatusView = { label: string; tone: PillTone; /** A plain sentence for the states that are not a clean result; null for completed. */ note: string | null; isError: boolean; known: boolean }

/** completed_with_warnings, insufficient_evidence and failed are visible states, not hidden ones. An unknown status shows its own word. */
export function statusView(status: string | null | undefined): StatusView {
  switch ((status ?? '').trim()) {
    case 'completed': return { label: 'Completed', tone: 'mint', note: null, isError: false, known: true }
    case 'completed_with_warnings': return { label: 'Completed with warnings', tone: 'amber', note: 'Some sentences use the standard template wording, were dropped, or a final check complained. The reasons are listed under Warnings and in the limitations.', isError: false, known: true }
    case 'insufficient_evidence': return { label: 'Insufficient evidence', tone: 'amber', note: 'There was nothing eligible to write about: the evidence is insufficient for a written answer. The report has only its introduction, limitations and gaps.', isError: false, known: true }
    case 'failed': return { label: 'Failed', tone: 'coral', note: 'The written report could not be produced. The evidence report is still available.', isError: true, known: true }
    default: { const w = (status ?? '').trim(); return { label: w ? w.replace(/_/g, ' ') : 'Unknown status', tone: 'neutral', note: null, isError: false, known: false } }
  }
}

// ------------------------------------------------------------------------------------------------------------------------ the view model
export type MarkerView = { n: number; href: string; /** The reference title, when the reference exists. */ title: string | null; found: boolean }
export type SentenceView = {
  body: string
  stop: string
  /** "[1, 3]" as text (the same as the links below). */
  markers: string
  links: MarkerView[]
  tier: TierView
  /** The deterministic wording of the template stands in for the model's (origin fallback or template): an optional hint, not a quality grade. */
  plainWording: boolean
}

export function sentenceView(s: WrittenSentence, refs: WrittenReference[] | undefined): SentenceView {
  const p = sentenceParts(s)
  return {
    body: p.body, stop: p.stop, markers: markers(p.refs),
    links: p.refs.map(n => { const r = refFor(refs, n); return { n, href: refHref(n), title: r?.title ?? null, found: !!r } }),
    tier: tierView(s?.tier), plainWording: s?.origin === 'fallback' || s?.origin === 'template',
  }
}

export type SideView = { quote: string | null; title: string | null; marker: MarkerView | null }
export type DisagreementView = { claimA: string | null; claimB: string | null; note: string | null; sideA: SideView; sideB: SideView }

const side = (s: WrittenDisagreement['sideA'], refs: WrittenReference[] | undefined): SideView => {
  const n = isNum(s?.ref) ? s!.ref! : null
  const r = n != null ? refFor(refs, n) : null
  return { quote: typeof s?.quote === 'string' && s.quote ? s.quote : null, title: typeof s?.title === 'string' && s.title ? s.title : null, marker: n != null ? { n, href: refHref(n), title: r?.title ?? null, found: !!r } : null }
}

export function disagreementView(d: WrittenDisagreement, refs: WrittenReference[] | undefined): DisagreementView {
  return { claimA: d?.claimA ?? null, claimB: d?.claimB ?? null, note: d?.note ? d.note : null, sideA: side(d?.sideA, refs), sideB: side(d?.sideB, refs) }
}

export type SectionView = { id: string; title: string; detailQuestions: string[]; sentences: SentenceView[]; disagreements: DisagreementView[]; gaps: string[] }
export type ReferenceView = { number: number; anchor: string; text: string; url: string | null; doi: string | null; kind: string | null; hint: string | null }

/** http and https only: a reference url from the server is never put in a link unchecked. */
export function safeUrl(u: unknown): string | null {
  if (typeof u !== 'string' || !u) return null
  try { const p = new URL(u); return p.protocol === 'http:' || p.protocol === 'https:' ? p.href : null } catch { return null }
}

/** The formatted entry; built from the fields when the server sent no text. */
export function referenceText(r: WrittenReference): string {
  if (typeof r.text === 'string' && r.text.trim()) return r.text.trim()
  const authors = strs(r.authors).join(', ')
  return [authors, r.year != null ? `(${r.year})` : '', r.title ?? '', r.venue ?? ''].filter(Boolean).join(' ').trim() || `Reference ${r.number}`
}

export function referenceView(r: WrittenReference): ReferenceView {
  return { number: r.number, anchor: `ref-${r.number}`, text: referenceText(r), url: safeUrl(r.url), doi: typeof r.doi === 'string' && r.doi ? r.doi : null, kind: r.kind ?? null, hint: evidenceHint(r.evidenceLevel) }
}

/** The numbers of the overview, in words that do not claim more than the data: "partly supported", "one source, not confirmed", "sources disagree". */
export const COUNT_LABELS: [string, string][] = [
  ['sections', 'sections'], ['documents', 'documents'], ['claims', 'claims'], ['supported', 'supported'], ['partly', 'partly supported'], ['single', 'one source, not confirmed'],
  ['disputed', 'sources disagree'], ['filtered', 'left out (filtered)'], ['sentences', 'sentences'], ['disagreements', 'disagreements shown'], ['references', 'references'],
]

export type ReportModel = {
  status: StatusView
  rawStatus: string
  legend: string
  question: string | null
  warnings: string[]
  counts: { key: string; label: string; value: number }[]
  summary: SentenceView[]
  introduction: string[]
  sections: SectionView[]
  limitations: string[]
  conclusion: SentenceView[]
  references: ReferenceView[]
  notVerified: string
  /** The report has no body at all (a failed or insufficient report): say so instead of showing empty blocks. */
  empty: boolean
  generatedAt: string | null
  model: string | null
  templateVersion: string | null
}

export function reportModel(res: Pick<WrittenReportResponse, 'status' | 'report'> & Partial<WrittenReportResponse>): ReportModel {
  const r: WrittenReport = (res.report && typeof res.report === 'object' ? res.report : {}) as WrittenReport
  const rawStatus = String(res.status ?? r.status ?? '')
  const refs = arr<WrittenReference>(r.references).filter(x => x && isNum(x.number))
  const sections = arr<WrittenSection>(r.sections).map((s, i): SectionView => ({
    id: s.id ?? `section-${i + 1}`, title: s.title ?? `Section ${i + 1}`, detailQuestions: strs(s.detailQuestions),
    sentences: arr<WrittenSentence>(s.sentences).filter(x => x && typeof x.text === 'string').map(x => sentenceView(x, refs)),
    disagreements: arr<WrittenDisagreement>(s.disagreements).map(d => disagreementView(d, refs)), gaps: strs(s.gaps),
  }))
  const counts = COUNT_LABELS.filter(([k]) => isNum(r.overview?.counts?.[k])).map(([key, label]) => ({ key, label, value: r.overview!.counts![key] }))
  const summary = arr<WrittenSentence>(r.overview?.summary).filter(x => x && typeof x.text === 'string').map(x => sentenceView(x, refs))
  const conclusion = arr<WrittenSentence>(r.conclusion).filter(x => x && typeof x.text === 'string').map(x => sentenceView(x, refs))
  return {
    status: statusView(rawStatus), rawStatus, legend: LEGEND, question: typeof r.question === 'string' && r.question ? r.question : null, warnings: strs(r.warnings), counts, summary,
    introduction: strs(r.introduction), sections, limitations: strs(r.limitations), conclusion, references: refs.map(referenceView), notVerified: NOT_A_VERIFIED_ANSWER,
    empty: summary.length === 0 && conclusion.length === 0 && sections.every(s => s.sentences.length === 0 && s.disagreements.length === 0),
    generatedAt: res.generatedAt ?? r.generatedAt ?? null, model: res.model ?? null, templateVersion: res.templateVersion ?? null,
  }
}

// ------------------------------------------------------------------------------------------------------------------------ the page's states
export const WRITING_TITLE = 'Writing the report'
export const WRITING_TEXT = 'TRACE is writing the report from the checked evidence. This page looks again every 3 seconds.'
export const NONE_TITLE = 'No written report for this run'
export const NONE_TEXT = 'Stage 5 did not run for this run, or its report has not been stored yet. The evidence report is still available.'

/** What the Generate button's POST can answer, in plain words. */
export function generateMessage(status: number | undefined, detail: string | undefined): { kind: 'started' | 'running' | 'off' | 'error'; text: string } {
  if (status === undefined || status === 202) return { kind: 'started', text: 'Started. The report appears here when it is written.' }
  if (status === 400) return { kind: 'off', text: detail || 'Stage 5 is switched off on the server (STAGE5), so the report cannot be written.' }
  if (status === 409 && /already/i.test(detail ?? '')) return { kind: 'running', text: 'A report is already being written for this run.' }
  return { kind: 'error', text: detail || 'The report could not be started.' }
}

export const downloadName = (id: string): string => `trace-written-report-${id.replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 12) || 'run'}.md`

/** The "Open written report" button belongs on the run page once the report stage is completed. While it is being written the page offers a disabled hint instead. */
export function writtenReportButton(state: StageState | undefined): 'open' | 'writing' | 'failed' | null {
  if (state === 'completed') return 'open'
  if (state === 'running') return 'writing'
  if (state === 'failed') return 'failed'
  return null
}
