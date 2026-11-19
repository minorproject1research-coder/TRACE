import type { PillTone } from '@/components/trace/status-pill'
import type { Citation, CitedQuote, StageState, WrittenAnswer, WrittenDisagreement, WrittenReference, WrittenReport, WrittenReportResponse, WrittenSection, WrittenSentence } from './trace-types'

// Pure view-model of the written report (Stage 5, docs/STAGE5_OUTPUT.md). No React here, so the rules are unit-tested (tests/written-report.test.ts).
//
// Rules that must hold wherever a sentence is shown:
//  - the text of a sentence never contains a marker; the renderer adds "[1, 3]" from `refs`, before the final full stop
//  - each marker links to the reference with that number
//  - the strength of the evidence is shown ONLY by the tier label and the markers (s5-v3: a sentence is a plain claim), so every `partly` and `single` sentence carries its label wherever it is shown (Answer, sections, Conclusion)
//  - tier `note` (a template sentence, no refs, s5-v2) is shown as a plain muted note: NO tier label and NO "plain wording" hint
//  - tier `partly` always carries the label "partly supported"; tier `single` always carries "one source, not confirmed" and never looks like a confirmed finding;
//    a tier this page does not know is treated like `single` (labelled with its own word, never styled as confirmed)
//  - sources that disagree are shown with both sides, each with its quote and reference; never "X is false"
//  - the legend is always shown; the limitations are never collapsed; warnings and the non-completed statuses are visible states
//  - a missing field shows as nothing, never as an error
//  - what may be collapsed (the page folds it under a bar): the introduction, the sentences of a section, the evidence under a sentence, the references.
//    What is NEVER collapsed: title and status, warnings, the legend, the Answer, the limitations, the "Sources disagree" blocks, the tier label of every sentence
//  - a marker opens the parsed paper at the quote of its citation (paperHref); a web source opens its url in a new tab (safeUrl); without a citation it is the anchor of the reference, as before

/** The legend (template s5-v3, `LEGEND_NATURAL` of the Markdown). It does not depend on how a sentence starts, so it is also right for a report stored with the older wording (s5-v2: "Two sources report ..."). */
export const LEGEND = 'How to read the findings: a sentence without a label is stated by two or more documents; a finding marked (partly supported) rests on one document with a close variant in another; a finding marked (one source, not confirmed) is stated by a single document and says what that source is. Citation numbers point to the references at the end.'

export const PARTLY_LABEL = 'partly supported'
export const SINGLE_LABEL = 'one source, not confirmed'
export const NOT_A_VERIFIED_ANSWER = 'This report is not a verified answer. Every check is automatic (language models and rules); none was reviewed by a person.'

/** The title of the first block: it answers the question that was asked (it was "Research Overview and Executive Summary" before template s5-v2). */
export const ANSWER_TITLE = 'Answer'

/** sessionStorage key: the report sets it (to the run id) when a link opens a paper, so that the paper page's "Back to the written report" can go back in the history, which keeps the scroll position. */
export const BACK_KEY = 'trace.wr.back'

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

/** A sentence split around its final full stop, so the markers go before it: `Compute grows linearly [1, 3].` Without a final stop the markers follow the text. */
export function sentenceParts(s: Pick<WrittenSentence, 'text' | 'refs'>): { body: string; stop: string; refs: number[] } {
  const text = typeof s?.text === 'string' ? s.text.trimEnd() : ''
  const m = /^([\s\S]*?)([.!?]["”')\]]*)$/.exec(text)
  const refs = arr<unknown>(s?.refs).filter(isNum)
  return m && m[1].trim() !== '' ? { body: m[1], stop: m[2], refs } : { body: text, stop: '', refs }
}

export type TierKind = 'supported' | 'partly' | 'single' | 'note' | 'other'
export type TierView = { kind: TierKind; /** The label that must accompany the sentence; null only for a supported sentence and for a plain note. */ label: string | null; tone: PillTone; hint: string }

export function tierView(tier: string | null | undefined): TierView {
  switch ((tier ?? '').trim().toLowerCase()) {
    case 'supported': return { kind: 'supported', label: null, tone: 'mint', hint: 'Stated by two or more documents.' }
    case 'partly': return { kind: 'partly', label: PARTLY_LABEL, tone: 'blue', hint: 'One document states this and another document makes a related point. A lead, not a confirmed fact.' }
    case 'note': return { kind: 'note', label: null, tone: 'neutral', hint: '' }
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
/** What a marker does: `paper` opens the parsed paper page (same tab), `web` opens the url of a web source (new tab), `anchor` goes to the reference in the list (the old behaviour), `plain` has no reference to go to. */
export type MarkerKind = 'paper' | 'web' | 'anchor' | 'plain'
export type MarkerView = {
  n: number; href: string; /** The reference title, when the reference exists. */ title: string | null; found: boolean
  kind: MarkerKind; external: boolean; /** The tooltip (title attribute). */ tooltip: string | null; /** The accessible name of the marker. */ label: string
}

/** The page of a paper of this run. With `findingId` it opens at that quote (`?finding=`); `from=written-report` makes the paper page offer the way back. */
export function paperHref(runId: string, paperId: string, findingId?: string | null): string {
  const q = findingId ? `?finding=${encodeURIComponent(findingId)}&from=written-report` : '?from=written-report'
  return `/research/${encodeURIComponent(runId)}/papers/${encodeURIComponent(paperId)}${q}`
}

const NOT_PARSED_OPEN = 'open the paper (not parsed: abstract and findings only)'

/** One marker. From a citation with a paper it opens that paper at the first quote; a citation without a paper opens the web url of the reference; everything else is the anchor of the reference. */
export function markerFor(n: number, refs: WrittenReference[] | undefined, cites: Citation[] | undefined, runId?: string): MarkerView {
  const r = refFor(refs, n)
  const title = r?.title ?? null
  const named = `Reference ${n}${title ? `: ${title}` : ''}`
  const anchor: MarkerView = { n, href: refHref(n), title, found: !!r, kind: r ? 'anchor' : 'plain', external: false, tooltip: r ? title : null, label: named }
  const c = arr<Citation>(cites).find(x => x && x.ref === n)
  if (!r || !c) return anchor
  if (typeof c.paperId === 'string' && c.paperId && runId) {
    const how = c.parsed ? 'open the parsed paper' : NOT_PARSED_OPEN
    return { ...anchor, href: paperHref(runId, c.paperId, arr<CitedQuote>(c.quotes)[0]?.findingId), kind: 'paper', tooltip: `${title ?? named}. ${how[0].toUpperCase()}${how.slice(1)}`, label: `${named}, ${how}` }
  }
  const url = !c.paperId ? safeUrl(r.url) : null
  if (url) return { ...anchor, href: url, kind: 'web', external: true, tooltip: `${title ?? named}. Open the web page (no parsed copy)`, label: `${named}, open the web page (no parsed copy), opens in a new tab` }
  return anchor
}

export type QuoteView = {
  text: string; relation: 'supports' | 'near_match' | 'other'; /** "supports" or "close variant (another document)". */ relationLabel: string
  /** "abstract only" / "web snippet" when the quote comes from a source that was read only in part. */ hint: string | null
  /** The action of the quote: "Open in the paper", or "Open the web page" for a web source; null when there is nowhere to go. */
  open: { href: string; label: string; external: boolean } | null
}
export type EvidenceView = { ref: number; title: string | null; found: boolean; href: string; hint: string | null; parsed: boolean; quotes: QuoteView[] }

export const RELATION_LABELS: Record<string, string> = { supports: 'supports', near_match: 'close variant (another document)' }

function evidenceOf(s: WrittenSentence, refs: WrittenReference[] | undefined, runId: string | undefined): EvidenceView[] {
  return arr<Citation>(s?.citations).filter(c => c && isNum(c.ref)).map((c): EvidenceView => {
    const r = refFor(refs, c.ref)
    const url = safeUrl(r?.url)
    const quotes = arr<CitedQuote>(c.quotes).filter(q => q && typeof q.text === 'string' && q.text.trim() !== '').map((q): QuoteView => {
      const paperId = (typeof q.paperId === 'string' && q.paperId) || (typeof c.paperId === 'string' && c.paperId) || null
      const rel = q.relation === 'supports' || q.relation === 'near_match' ? q.relation : 'other'
      return {
        text: q.text.trim(), relation: rel, relationLabel: RELATION_LABELS[q.relation] ?? (q.relation ? String(q.relation).replace(/_/g, ' ') : 'quote'),
        hint: evidenceHint(q.evidenceLevel ?? r?.evidenceLevel),
        open: paperId && runId ? { href: paperHref(runId, paperId, q.findingId), label: 'Open in the paper', external: false } : !paperId && url ? { href: url, label: 'Open the web page', external: true } : null,
      }
    })
    return { ref: c.ref, title: r?.title ?? null, found: !!r, href: refHref(c.ref), hint: evidenceHint(r?.evidenceLevel), parsed: c.parsed === true, quotes }
  }).filter(e => e.quotes.length > 0)
}

export type SentenceView = {
  body: string
  stop: string
  /** "[1, 3]" as text (the same as the links below). */
  markers: string
  links: MarkerView[]
  tier: TierView
  /** The deterministic wording of the template stands in for the model's (origin fallback or template): an optional hint, not a quality grade. */
  plainWording: boolean
  /** The verbatim quotes behind the sentence, per reference (empty for a note, an old report, or a sentence whose claims were not found). */
  evidence: EvidenceView[]
  /** How many quotes there are in all: the n of the bar "Evidence (n)". */
  evidenceCount: number
}

export function sentenceView(s: WrittenSentence, refs: WrittenReference[] | undefined, runId?: string): SentenceView {
  const p = sentenceParts(s)
  const tier = tierView(s?.tier)
  const note = tier.kind === 'note'
  const evidence = note ? [] : evidenceOf(s, refs, runId)
  return {
    body: p.body, stop: p.stop, markers: markers(p.refs),
    links: p.refs.map(n => markerFor(n, refs, note ? [] : s?.citations, runId)),
    tier, plainWording: !note && (s?.origin === 'fallback' || s?.origin === 'template'),
    evidence, evidenceCount: evidence.reduce((t, e) => t + e.quotes.length, 0),
  }
}

export type SideView = { quote: string | null; title: string | null; marker: MarkerView | null }
export type DisagreementView = { claimA: string | null; claimB: string | null; note: string | null; sideA: SideView; sideB: SideView }

const side = (s: WrittenDisagreement['sideA'], refs: WrittenReference[] | undefined): SideView => {
  const n = isNum(s?.ref) ? s!.ref! : null
  const r = n != null ? refFor(refs, n) : null
  return { quote: typeof s?.quote === 'string' && s.quote ? s.quote : null, title: typeof s?.title === 'string' && s.title ? s.title : null, marker: n != null ? markerFor(n, refs, []) : null }
}

export function disagreementView(d: WrittenDisagreement, refs: WrittenReference[] | undefined): DisagreementView {
  return { claimA: d?.claimA ?? null, claimB: d?.claimB ?? null, note: d?.note ? d.note : null, sideA: side(d?.sideA, refs), sideB: side(d?.sideB, refs) }
}

export type SectionView = {
  id: string; title: string; detailQuestions: string[]; sentences: SentenceView[]; disagreements: DisagreementView[]; gaps: string[]
  /** The line on the collapse bar: "12 findings · 2 partly supported · 5 one source, not confirmed · 1 disagreement". */
  summary: string
  /** Small words that stay visible on the bar, so that nothing important hides behind it: "sources disagree", "evidence gaps". */
  hints: string[]
}
export type ReferenceView = {
  number: number; anchor: string; text: string; url: string | null; doi: string | null; kind: string | null; hint: string | null
  /** The parsed (or not parsed) paper page to open from the list; null for a web page and for an old report. */
  paper: { href: string; parsed: boolean; label: string } | null
  /** In how many sentences of the report the reference is cited; null when the server did not say. */
  citedIn: number | null
}

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

export function referenceView(r: WrittenReference, runId?: string): ReferenceView {
  const pid = r.paper && typeof r.paper.id === 'string' && r.paper.id ? r.paper : null
  return {
    number: r.number, anchor: `ref-${r.number}`, text: referenceText(r), url: safeUrl(r.url), doi: typeof r.doi === 'string' && r.doi ? r.doi : null, kind: r.kind ?? null, hint: evidenceHint(r.evidenceLevel),
    paper: pid && runId ? { href: paperHref(runId, pid.id), parsed: pid.parsed === true, label: pid.parsed === true ? 'Open parsed paper' : 'Open paper page (not parsed)' } : null,
    citedIn: isNum(r.citedIn) ? r.citedIn : null,
  }
}

/** The line of a collapsed section: counts from its own sentences, in words that do not claim more than the data. */
export function sectionSummary(sentences: Pick<SentenceView, 'tier'>[], disagreements: number, counts?: Record<string, number> | null): string {
  const n = sentences.length
  if (n === 0 && disagreements === 0) return 'no findings written'
  const by = (k: TierKind) => sentences.filter(s => s.tier.kind === k).length
  const plural = (k: number, one: string, many: string) => `${k} ${k === 1 ? one : many}`
  const parts = [plural(n, 'finding', 'findings')]
  if (by('supported')) parts.push(`${by('supported')} supported`)
  if (by('partly')) parts.push(`${by('partly')} ${PARTLY_LABEL}`)
  if (by('single')) parts.push(`${by('single')} ${SINGLE_LABEL}`)
  if (by('other')) parts.push(`${by('other')} not confirmed (kind unknown)`)
  if (disagreements) parts.push(plural(disagreements, 'disagreement', 'disagreements'))
  const left = counts?.filtered
  if (isNum(left) && left > 0) parts.push(`${left} left out (filtered)`)
  return parts.join(' · ')
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
  /** The Answer, organised (overview.answer); null when the server did not send it: the page then shows `summary` as before. */
  answer: AnswerView | null
  notVerified: string
  /** The report has no body at all (a failed or insufficient report): say so instead of showing empty blocks. */
  empty: boolean
  generatedAt: string | null
  model: string | null
  templateVersion: string | null
}

// ------------------------------------------------------------------------------------------------------------------------ the Answer (overview.answer)
export const summaryAnchor = (index: number): string => `wr-sum-${index}`
export const disputeAnchor = (sectionId: string): string => `wr-dis-${sectionId}-0`

export type AnswerSentence = { index: number; id: string; view: SentenceView }
export type AnswerPartView = {
  index: number; id: string; sectionId: string | null; title: string | null
  /** null when this part is the headline itself (it is shown once, in large type). */
  sentence: SentenceView | null; isHeadline: boolean; supporting: SentenceView[]
}
export type StrengthTier = { key: 'supported' | 'partly' | 'single'; label: string; value: number; pct: number }
export type StrengthView = {
  /** The sentence the server wrote about how well the answer rests on the evidence. Shown as it is: never reworded, never turned into a verdict. */
  line: string
  documents: number | null; fullTextDocuments: number | null; partsCovered: number | null; sections: number | null
  tiers: StrengthTier[]; total: number
  /** The text of the bar that is split by tier (the numbers in words, so that it can be read without colour). */
  barLabel: string
}
export type FigureView = { value: string; index: number; /** Id of the sentence the chip scrolls to; null when that sentence is not on the page. */ anchor: string | null; /** The label of that sentence when it is not a confirmed one: a figure from one source is never shown as more. */ tierLabel: string | null; tierKind: TierKind | null; refs: MarkerView[] }
export type DisputeView = { sectionId: string; title: string; claimA: string; claimB: string; refs: MarkerView[]; /** Id of the "Sources disagree" block of that section, when the page has it. */ anchor: string | null }
export type AnswerView = {
  headline: AnswerSentence | null
  parts: AnswerPartView[]
  /** Sentences of overview.summary that neither the headline nor a part shows: they are never dropped. */
  others: AnswerSentence[]
  /** Template notes ("The evidence collected does not settle: ..."): shown only when answer.openQuestions has nothing to show instead. */
  notes: AnswerSentence[]
  strength: StrengthView | null
  figures: FigureView[]
  openQuestions: string[]
  disputes: { count: number; items: DisputeView[] }
}

/** overview.answer as a view; null when the report has none (or it is not an object), so that the page falls back to overview.summary. Nothing of overview.summary gets lost. */
export function answerView(r: WrittenReport, refs: WrittenReference[], runId: string | undefined, sections: SectionView[]): AnswerView | null {
  const a = r.overview?.answer as WrittenAnswer | undefined
  if (!a || typeof a !== 'object') return null
  const raw = arr<WrittenSentence>(r.overview?.summary)
  const valid = (i: unknown): i is number => isNum(i) && Number.isInteger(i) && i >= 0 && i < raw.length && !!raw[i] && typeof raw[i].text === 'string'
  const at = (i: number): AnswerSentence => ({ index: i, id: summaryAnchor(i), view: sentenceView(raw[i], refs, runId) })
  const hi = valid(a.headline?.sentenceIndex) ? a.headline!.sentenceIndex : null
  const parts = arr<WrittenAnswer['parts'][number]>(a.parts).filter(p => p && valid(p.sentenceIndex)).map((p): AnswerPartView => {
    const own = p.sentence && typeof p.sentence.text === 'string' ? p.sentence : raw[p.sentenceIndex]
    return {
      index: p.sentenceIndex, id: summaryAnchor(p.sentenceIndex), sectionId: typeof p.sectionId === 'string' ? p.sectionId : null, title: typeof p.title === 'string' && p.title ? p.title : null,
      isHeadline: p.sentenceIndex === hi, sentence: p.sentenceIndex === hi ? null : sentenceView(own, refs, runId),
      supporting: arr<WrittenSentence>(p.supporting).filter(x => x && typeof x.text === 'string').map(x => sentenceView(x, refs, runId)),
    }
  })
  const shown = new Set<number>([...(hi != null ? [hi] : []), ...parts.map(p => p.index)])
  const rest = raw.map((_, i) => i).filter(i => valid(i) && !shown.has(i)).map(at)
  const isNote = (x: AnswerSentence) => x.view.tier.kind === 'note'
  const openQuestions = strs(a.openQuestions)
  const st = a.strength && typeof a.strength === 'object' ? a.strength : null
  const num = (v: unknown): number | null => (isNum(v) ? v : null)
  let strength: StrengthView | null = null
  if (st) {
    const by = st.byTier ?? { supported: 0, partly: 0, single: 0 }
    const tiers = (['supported', 'partly', 'single'] as const).map(key => ({ key, label: key === 'supported' ? 'stated by two or more documents' : key === 'partly' ? PARTLY_LABEL : SINGLE_LABEL, value: isNum(by[key]) ? by[key] : 0 }))
    const total = tiers.reduce((t, x) => t + x.value, 0)
    strength = {
      line: typeof st.line === 'string' ? st.line : '', documents: num(st.documents), fullTextDocuments: num(st.fullTextDocuments), partsCovered: num(st.partsCovered), sections: num(st.sections),
      tiers: tiers.map(t => ({ ...t, pct: total > 0 ? (t.value / total) * 100 : 0 })), total,
      barLabel: tiers.map(t => `${t.value} ${t.label}`).join(', '),
    }
  }
  const figures = arr<WrittenAnswer['figures'][number]>(a.figures).filter(f => f && typeof f.value === 'string' && f.value.trim() !== '' && isNum(f.sentenceIndex)).map((f): FigureView => {
    const ok = valid(f.sentenceIndex)
    return { value: f.value.trim(), index: f.sentenceIndex, anchor: ok ? summaryAnchor(f.sentenceIndex) : null, tierLabel: ok ? tierView(raw[f.sentenceIndex].tier).label : null, tierKind: ok ? tierView(raw[f.sentenceIndex].tier).kind : null, refs: arr<unknown>(f.refs).filter(isNum).map(n => markerFor(n, refs, [])) }
  })
  const items = arr<WrittenAnswer['disputes']['items'][number]>(a.disputes?.items).filter(d => d && typeof d.claimA === 'string' && typeof d.claimB === 'string').map((d): DisputeView => {
    const sec = sections.find(s => s.id === d.sectionId)
    return { sectionId: String(d.sectionId ?? ''), title: typeof d.title === 'string' ? d.title : sec?.title ?? '', claimA: d.claimA, claimB: d.claimB, refs: arr<unknown>(d.refs).filter(isNum).map(n => markerFor(n, refs, [])), anchor: sec && sec.disagreements.length > 0 ? disputeAnchor(sec.id) : null }
  })
  return {
    headline: hi != null ? at(hi) : null, parts, others: rest.filter(x => !isNote(x)), notes: openQuestions.length > 0 ? [] : rest.filter(isNote),
    strength, figures, openQuestions, disputes: { count: isNum(a.disputes?.count) ? a.disputes.count : items.length, items },
  }
}

export function reportModel(res: Pick<WrittenReportResponse, 'status' | 'report'> & Partial<WrittenReportResponse>, runId?: string): ReportModel {
  const r: WrittenReport = (res.report && typeof res.report === 'object' ? res.report : {}) as WrittenReport
  const rawStatus = String(res.status ?? r.status ?? '')
  const refs = arr<WrittenReference>(r.references).filter(x => x && isNum(x.number))
  const sections = arr<WrittenSection>(r.sections).map((s, i): SectionView => {
    const sentences = arr<WrittenSentence>(s.sentences).filter(x => x && typeof x.text === 'string').map(x => sentenceView(x, refs, runId))
    const disagreements = arr<WrittenDisagreement>(s.disagreements).map(d => disagreementView(d, refs))
    const gaps = strs(s.gaps)
    return {
      id: s.id ?? `section-${i + 1}`, title: s.title ?? `Section ${i + 1}`, detailQuestions: strs(s.detailQuestions), sentences, disagreements, gaps,
      summary: sectionSummary(sentences, disagreements.length, s.counts), hints: [...(disagreements.length ? ['sources disagree'] : []), ...(gaps.length ? ['evidence gaps'] : [])],
    }
  })
  const counts = COUNT_LABELS.filter(([k]) => isNum(r.overview?.counts?.[k])).map(([key, label]) => ({ key, label, value: r.overview!.counts![key] }))
  const summary = arr<WrittenSentence>(r.overview?.summary).filter(x => x && typeof x.text === 'string').map(x => sentenceView(x, refs, runId))
  const conclusion = arr<WrittenSentence>(r.conclusion).filter(x => x && typeof x.text === 'string').map(x => sentenceView(x, refs, runId))
  return {
    status: statusView(rawStatus), rawStatus, legend: LEGEND, question: typeof r.question === 'string' && r.question ? r.question : null, warnings: strs(r.warnings), counts, summary,
    introduction: strs(r.introduction), sections, limitations: strs(r.limitations), conclusion, references: refs.map(x => referenceView(x, runId)), answer: answerView(r, refs, runId, sections), notVerified: NOT_A_VERIFIED_ANSWER,
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
