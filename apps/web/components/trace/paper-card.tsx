import Link from 'next/link'
import { ArrowUpRight, BookOpen, ExternalLink, FileText, Globe } from 'lucide-react'
import { evidenceLevelLabel } from '@/lib/format'
import type { PaperSummary, WebSummary } from '@/lib/trace-types'
import { StatusPill } from './status-pill'

/** Only http(s) URLs become links, and they never get opener access. */
export function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null
  try { const u = new URL(url); return u.protocol === 'http:' || u.protocol === 'https:' ? u.toString() : null } catch { return null }
}

const SOURCE_LABEL: Record<string, string> = { openalex: 'OpenAlex', scopus: 'Scopus', arxiv: 'arXiv', both: 'OpenAlex + Scopus' }
export const sourceLabel = (s: string | null) => (s ? (SOURCE_LABEL[s] ?? s) : 'Unknown index')

export function authorLine(authors: string[], max = 3) {
  if (!authors.length) return 'Authors not listed'
  return authors.slice(0, max).join(', ') + (authors.length > max ? ` and ${authors.length - max} more` : '')
}

export const score = (v: number | null | undefined) => (v == null ? '–' : v.toFixed(2))

export function EvidenceChip({ evidence }: { evidence: PaperSummary['evidence'] }) {
  if (!evidence) return <StatusPill tone="neutral">Not used as evidence</StatusPill>
  const level = evidence.level ? (evidenceLevelLabel[evidence.level as keyof typeof evidenceLevelLabel]?.label ?? evidence.level) : 'read'
  return <StatusPill tone="mint">Used as evidence · {evidence.findings ?? 0} finding{evidence.findings === 1 ? '' : 's'} · {level.toLowerCase()}</StatusPill>
}

export function PaperCard({ paper, runId, parsing = false }: { paper: PaperSummary; runId: string; parsing?: boolean }) {
  const href = `/research/${encodeURIComponent(runId)}/papers/${encodeURIComponent(paper.id)}`
  const ext = safeUrl(paper.url)
  const pdf = safeUrl(paper.pdfUrl)
  const parsed = paper.parse.status === 'parsed'
  const blurb = paper.tldr || paper.abstractPreview
  const meta = [paper.year, paper.venue, sourceLabel(paper.source), paper.citations != null ? `${paper.citations} citations` : null].filter(Boolean).join(' · ')
  return (
    <article className="paper-card">
      <div className="paper-head">
        <span className="source-icon paper" aria-hidden="true"><BookOpen size={15} /></span>
        <div className="source-title">
          <h3><Link href={href}>{paper.title ?? 'Untitled paper'}</Link></h3>
          <p className="meta">{authorLine(paper.authors)}</p>
          <p className="meta">{meta}</p>
        </div>
      </div>
      {blurb && <p className="paper-blurb">{paper.tldr ? <><b>TL;DR </b>{blurb}</> : blurb}{!paper.tldr && paper.abstractPreview.length >= 320 ? '…' : ''}</p>}
      <div className="source-tags">
        <StatusPill tone={parsed ? 'blue' : 'neutral'}>{parsed ? 'Parsed' : parsing ? 'Not parsed yet' : 'Not parsed'}</StatusPill>
        <EvidenceChip evidence={paper.evidence} />
        <span className="tag" title="How close the abstract is to the sub-question">relevance {score(paper.scores.relevance)}</span>
        <span className="tag" title="Venue, citations and source quality">reliability {score(paper.scores.reliability)}</span>
        {paper.isPreprint && <span className="tag">preprint</span>}
        {paper.subQuestion && <span className="tag topic" title={paper.subQuestion}>{paper.subQuestion}</span>}
      </div>
      <div className="paper-actions">
        <Link className="link-button strong" href={href}><FileText size={14} aria-hidden="true" />{parsed ? 'Open parsed content' : 'Open details'}<ArrowUpRight size={13} aria-hidden="true" /></Link>
        {ext && <a className="link-button muted" href={ext} target="_blank" rel="noopener noreferrer">Source page<ExternalLink size={12} aria-hidden="true" /><span className="sr-only"> (opens in a new tab)</span></a>}
        {pdf && pdf !== ext && <a className="link-button muted" href={pdf} target="_blank" rel="noopener noreferrer">PDF<ExternalLink size={12} aria-hidden="true" /><span className="sr-only"> (opens in a new tab)</span></a>}
      </div>
    </article>
  )
}

export function WebCard({ web }: { web: WebSummary }) {
  const href = safeUrl(web.url)
  const meta = [web.provider, web.publishedDate, web.reliability != null ? `reliability ${score(web.reliability)}` : null].filter(Boolean).join(' · ')
  return (
    <article className="paper-card">
      <div className="paper-head">
        <span className="source-icon web" aria-hidden="true"><Globe size={15} /></span>
        <div className="source-title">
          <h3>{href ? <a href={href} target="_blank" rel="noopener noreferrer">{web.title ?? href}<ExternalLink size={12} aria-hidden="true" /><span className="sr-only"> (opens in a new tab)</span></a> : (web.title ?? 'Untitled page')}</h3>
          {meta && <p className="meta">{meta}</p>}
        </div>
      </div>
      {web.snippet && <p className="paper-blurb">{web.snippet}</p>}
      <p className="partial-note">Only the search snippet was read, not the page. Findings from it are weaker evidence.</p>
      <div className="source-tags">
        <EvidenceChip evidence={web.evidence} />
        {web.subQuestion && <span className="tag topic" title={web.subQuestion}>{web.subQuestion}</span>}
      </div>
    </article>
  )
}
