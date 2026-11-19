'use client'

import Link from 'next/link'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, ArrowLeft, ExternalLink, FileWarning, Highlighter, Info, Quote, ShieldAlert } from 'lucide-react'
import { FindingCard } from '@/components/trace/evidence'
import { authorLine, EvidenceChip, safeUrl, score, sourceLabel } from '@/components/trace/paper-card'
import { ParsedText, type Mark, type ParsedTextHandle } from '@/components/trace/parsed-text'
import { StatusPill } from '@/components/trace/status-pill'
import { ErrorState, Skeleton } from '@/components/trace/states'
import { useMode } from '@/lib/mode'
import { usePaper } from '@/lib/use-research'
import { BACK_KEY } from '@/lib/written-report'

function ScoreBar({ label, value, hint }: { label: string; value: number | null; hint: string }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(1, value)) * 100
  return (
    <div className="score" title={hint}>
      <div className="score-head"><span>{label}</span><b>{score(value)}</b></div>
      <div className="score-bar" role="img" aria-label={`${label} ${score(value)} out of 1`}><span style={{ width: `${pct}%` }} /></div>
    </div>
  )
}

/** useSearchParams needs a Suspense boundary (docs: use-search-params): the page is the boundary, the view below reads the query. */
export default function PaperPage() {
  return <Suspense fallback={<h1 className="sr-only">Paper</h1>}><PaperView /></Suspense>
}

// Query parameters (from the written report): `finding` = the id of the finding (the quote behind a citation) to open at, `from=written-report` = the way back.
function PaperView() {
  const params = useParams<{ id: string; paperId: string }>()
  const search = useSearchParams()
  const router = useRouter()
  const runId = decodeURIComponent(params.id)
  const paperId = decodeURIComponent(params.paperId)
  const wanted = search.get('finding') || null
  const fromReport = search.get('from') === 'written-report'
  const { mode } = useMode()
  const detail = usePaper(runId, paperId)
  const text = useRef<ParsedTextHandle>(null)
  const parsedSection = useRef<HTMLElement>(null)
  const handled = useRef('')
  // The finding that is highlighted. Until the reader chooses one, it is the quote that was asked for (when it can be located); the key makes a choice belong to this paper and this citation.
  const key = `${paperId}:${wanted ?? ''}`
  const [picked, setPicked] = useState<{ key: string; value: number | null } | null>(null)

  const findings = detail.data?.findings
  const parsedText = detail.data?.parsed?.text ?? ''
  const askedIdx = useMemo(() => (wanted && findings ? findings.findIndex(f => f.id === wanted) : -1), [wanted, findings])
  const askedPlaced = askedIdx >= 0 && !!findings && findings[askedIdx].spans.length > 0 && parsedText.trim() !== ''
  const active = picked?.key === key ? picked.value : askedPlaced ? askedIdx : null
  const marks = useMemo<Mark[]>(() => (findings ?? []).flatMap((f, i) => f.spans.map(s => ({ ...s, id: i }))), [findings])

  // Arriving from a citation: show the Parsed content, and the quote in it (the same as "Show in the parsed text"). Once per paper and citation.
  useEffect(() => {
    if (!wanted || askedIdx < 0 || handled.current === key) return
    handled.current = key
    parsedSection.current?.scrollIntoView({ block: 'start', behavior: 'auto' })
    if (askedPlaced) text.current?.jumpToMark(askedIdx)
  }, [wanted, askedIdx, askedPlaced, key])

  const enc = encodeURIComponent(runId)
  const backToReport = (e: React.MouseEvent) => {
    // The report put a note in this tab: go back in the history, so that the report is where the reader left it. Otherwise follow the link.
    try { if (sessionStorage.getItem(BACK_KEY) === runId) { sessionStorage.removeItem(BACK_KEY); e.preventDefault(); router.back() } } catch { /* no storage: the link works */ }
  }
  const back = fromReport
    ? <Link className="back-link" href={`/research/${enc}/written-report`} onClick={backToReport}><ArrowLeft size={14} aria-hidden="true" /> Back to the written report</Link>
    : <Link className="back-link" href={`/research/${enc}#activity`}><ArrowLeft size={14} aria-hidden="true" /> Back to the run</Link>

  if (detail.loading && !detail.data) return <>{back}<h1 className="sr-only">Paper</h1><Skeleton rows={6} label="Loading the paper" /></>
  if (detail.error || !detail.data) {
    const nf = detail.error?.status === 404
    return <>{back}<h1 className="sr-only">Paper</h1><ErrorState title={nf ? 'Paper not found' : 'Could not load the paper'} message={nf ? 'This paper does not belong to this research run, or it no longer exists.' : (detail.error?.message ?? 'Unknown error')} status={detail.error?.status} onRetry={detail.reload} /></>
  }

  const { paper, abstract, parsed, findings: list } = detail.data
  const ext = safeUrl(paper.url)
  const pdf = safeUrl(paper.pdfUrl)
  const meta = [paper.year, paper.venue, sourceLabel(paper.source), paper.citations != null ? `${paper.citations} citations` : null, paper.isPreprint ? 'preprint' : null].filter(Boolean).join(' · ')
  const placed = list.filter(f => f.spans.length > 0).length
  const hasText = !!parsed && parsed.text.trim() !== ''
  const asked = askedIdx >= 0 ? list[askedIdx] : null

  const show = (i: number) => { setPicked({ key, value: i }); text.current?.jumpToMark(i) }
  // the quote that was asked for comes first in the list; the others keep their order (the index stays the finding's own, it is what the highlights are keyed by)
  const order = list.map((_, i) => i).sort((a, b) => (a === askedIdx ? -1 : b === askedIdx ? 1 : a - b))

  const evidenceSection = (
    <section className="panel rise" style={{ '--i': 2 } as React.CSSProperties} aria-labelledby="ev-title">
      <h2 id="ev-title">Evidence taken from this paper</h2>
      {list.length === 0 ? (
        <p className="meta">{paper.evidence ? 'The run recorded evidence from this paper, but no finding text is available.' : 'No finding was taken from this paper. It was kept by the relevance filter, but it was not used as evidence for any sub-question.'}</p>
      ) : (
        <>
          <div className="callout-box lav" role="note"><ShieldAlert size={18} aria-hidden="true" /><div><b>Findings, not facts</b><p>Each quote below is highlighted at the place it appears in the parsed text. {placed} of {list.length} could be located. A quote that cannot be located is not highlighted: a missing highlight is better than a misleading one. Nothing has checked that a claim is true.</p></div></div>
          <div className="finding-list">
            {order.map(i => {
              const f = list[i]
              const isAsked = i === askedIdx
              return (
                <div key={i} className={isAsked ? 'finding-asked' : undefined} id={isAsked ? 'finding-asked' : undefined}>
                  {isAsked && <p className="asked-tag"><Quote size={13} aria-hidden="true" /> The quote behind the citation in the written report</p>}
                  <FindingCard finding={f}>
                    <div className="finding-actions">
                      {f.spans.length > 0 && hasText
                        ? <button type="button" className="tool-button" onClick={() => show(i)}><Highlighter size={14} aria-hidden="true" /> Show in the parsed text</button>
                        : <span className="meta">{!parsed ? 'This paper was not parsed, so there is no text to show.' : f.quoteFound ? 'Position in the text could not be determined.' : 'The quote could not be located in the text.'}</span>}
                      {f.subQuestion && <span className="tag topic" title={f.subQuestion}>{f.subQuestion}</span>}
                    </div>
                  </FindingCard>
                </div>
              )
            })}
          </div>
        </>
      )}
    </section>
  )

  // What the page tells a reader who came from a citation: which quote it is, or why nothing is highlighted. Never a highlight at a guessed place.
  const fromCitation = asked && (
    <div className="callout-box lav asked-banner" role="status">
      <Highlighter size={18} aria-hidden="true" />
      <div>
        {askedPlaced ? (
          <>
            <p><b>Opened from the written report:</b> this is the quote behind the citation.</p>
            <blockquote className="asked-quote">{asked.quote}</blockquote>
            {active === askedIdx
              ? <button type="button" className="tool-button" onClick={() => setPicked({ key, value: null })}>Clear the highlight</button>
              : <button type="button" className="tool-button" onClick={() => show(askedIdx)}><Highlighter size={14} aria-hidden="true" /> Highlight it again</button>}
          </>
        ) : (
          <>
            <p><b>Opened from the written report.</b> {parsed ? (hasText ? 'The quote behind the citation could not be located in the parsed text, so nothing is highlighted.' : 'The parsed copy has no readable text, so the quote cannot be highlighted.') : 'This paper was not parsed, so there is no text to highlight.'} The quote as stored:</p>
            <blockquote className="asked-quote">{asked.quote}</blockquote>
          </>
        )}
      </div>
    </div>
  )

  const parsedContent = (
    <section ref={parsedSection} id="parsed-content" className="rise parsed-content" style={{ '--i': 4 } as React.CSSProperties} aria-labelledby="parsed-title">
      <h2 id="parsed-title" className="section-title">Parsed content</h2>
      {fromCitation}
      {!parsed && (
        <div className="callout-box amber" role="note"><FileWarning size={18} aria-hidden="true" /><div><b>This paper was not parsed</b><p>TRACE did not extract its content: no open full-text copy was reachable, or the paper was not selected for reading. Only the abstract above is available.{pdf || ext ? ' Use the links at the top to read it at the source.' : ''}</p></div></div>
      )}
      {parsed && !parsed.text.trim() && (
        <div className="callout-box amber" role="note"><AlertTriangle size={18} aria-hidden="true" /><div><b>Parsed, but no text was extracted</b><p>The parser stored this paper without any readable text (parser version {parsed.parserVersion ?? '?'}). It cannot be read or highlighted here.</p></div></div>
      )}
      {parsed && parsed.text.trim() && (
        <>
          <p className="meta parse-facts">{parsed.chars.toLocaleString()} characters · {parsed.outline.length} headings · {parsed.figures.length} figures · {parsed.referenceCount} references · parser v{parsed.parserVersion ?? '?'}. Extracted automatically from the PDF, so line breaks, tables and equations may be imperfect.</p>
          <div className="parsed-layout">
            {parsed.outline.length > 0 && (
              <nav className="outline" aria-label="Paper outline">
                <b>Outline</b>
                <ul>{parsed.outline.map((h, i) => <li key={i} style={{ paddingLeft: Math.max(0, h.level - 1) * 12 }}><button type="button" onClick={() => text.current?.jumpToHeading(h.heading)}>{h.heading}</button></li>)}</ul>
              </nav>
            )}
            <div className="parsed-main"><ParsedText ref={text} text={parsed.text} marks={marks} active={active} /></div>
          </div>
        </>
      )}
    </section>
  )

  // Coming from a citation to a paper that has parsed text: the Parsed content comes first, not behind the list of findings.
  const parsedFirst = asked != null && hasText

  return (
    <article className="paper-page">
      {back}
      <header className="paper-header rise">
        <div className="eyebrow research">{mode === 'demo' ? 'Demo paper' : 'Paper'}</div>
        <h1>{paper.title ?? 'Untitled paper'}</h1>
        <p className="authors">{authorLine(paper.authors, 8)}</p>
        <p className="meta">{meta}</p>
        <div className="paper-links">
          {ext && <a className="start-button small" href={ext} target="_blank" rel="noopener noreferrer"><ExternalLink size={14} aria-hidden="true" />Open source page<span className="sr-only"> (opens in a new tab)</span></a>}
          {pdf && pdf !== ext && <a className="tool-button" href={pdf} target="_blank" rel="noopener noreferrer"><ExternalLink size={14} aria-hidden="true" />PDF<span className="sr-only"> (opens in a new tab)</span></a>}
          {paper.doi && <span className="tag">DOI {paper.doi}</span>}
          {paper.arxivId && <span className="tag">arXiv {paper.arxivId}</span>}
          <StatusPill tone={parsed ? 'blue' : 'neutral'}>{parsed ? 'Parsed by TRACE' : 'Not parsed'}</StatusPill>
          <EvidenceChip evidence={paper.evidence} />
        </div>
        {paper.subQuestion && <p className="meta topic">Retrieved for: {paper.subQuestion}</p>}
      </header>

      {wanted && !asked && <p className="callout-line" role="status"><Info size={14} aria-hidden="true" /> Opened from the written report, but this paper has no finding for that citation, so no quote is highlighted.</p>}

      {parsedFirst && parsedContent}

      <section className="panel rise" style={{ '--i': 1 } as React.CSSProperties} aria-labelledby="why-title">
        <h2 id="why-title">Why TRACE kept this paper</h2>
        <div className="scores">
          <ScoreBar label="Relevance" value={paper.scores.relevance} hint="How close the abstract is to the sub-question (embedding similarity)" />
          <ScoreBar label="Reliability" value={paper.scores.reliability} hint="Venue, citations and source quality" />
          <ScoreBar label="Combined" value={paper.scores.combined} hint="Used to rank papers within a sub-question" />
        </div>
        {paper.judge.relevant != null && (
          <p className="judge-line"><StatusPill tone={paper.judge.relevant ? 'mint' : 'amber'}>{paper.judge.relevant ? 'Judge: relevant' : 'Judge: not relevant'}</StatusPill>
            {paper.judge.confidence != null && <span className="tag">confidence {score(paper.judge.confidence)}</span>}
            {paper.judge.reason && <span className="meta"> {paper.judge.reason}</span>}</p>
        )}
        {paper.tldr && <p className="paper-blurb"><b>TL;DR </b>{paper.tldr}</p>}
      </section>

      {evidenceSection}

      <section className="panel rise" style={{ '--i': 3 } as React.CSSProperties} aria-labelledby="abs-title">
        <h2 id="abs-title">Abstract</h2>
        {abstract ? <p className="abstract">{abstract}</p> : <p className="meta">No abstract is stored for this paper.</p>}
        <p className="meta">From the search index. An abstract is a summary written by the authors: TRACE does not treat it as evidence on its own{paper.evidence?.level && paper.evidence.level !== 'full_text' ? '. Findings from this paper were taken from its abstract only' : ''}.</p>
      </section>

      {!parsedFirst && parsedContent}

      {parsed && parsed.figures.length > 0 && (
        <details className="panel fold">
          <summary>Figures ({parsed.figures.length})</summary>
          <ol className="plain-list">{parsed.figures.map((f, i) => <li key={i}>{f.caption || `Figure ${f.label ?? i + 1}`}{f.page != null && <span className="meta"> (page {f.page})</span>}</li>)}</ol>
        </details>
      )}
      {parsed && parsed.referenceCount > 0 && (
        <details className="panel fold">
          <summary>References ({parsed.referenceCount})</summary>
          <ol className="plain-list refs">{parsed.references.map((r, i) => <li key={i}>{r}</li>)}</ol>
          {parsed.referenceCount > parsed.references.length && <p className="meta">Showing the first {parsed.references.length} of {parsed.referenceCount}.</p>}
        </details>
      )}
    </article>
  )
}
