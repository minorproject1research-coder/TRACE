'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, Download, FileSearch, Info, ShieldAlert } from 'lucide-react'
import { AnswerCard } from '@/components/AnswerCard'
import { Fold, FoldBar } from '@/components/Fold'
import { Disagreement, ReportActionsContext, Sentence, type ReportActions } from '@/components/ReportParts'
import { StatusPill } from '@/components/trace/status-pill'
import { formatDateTime } from '@/lib/format'
import { BACK_KEY, downloadName, reportModel, type SectionView } from '@/lib/written-report'
import type { WrittenReportResponse } from '@/lib/trace-types'

// The written report of Stage 5. The rules (lib/written-report.ts): every sentence shows its markers from `refs` and each marker opens the paper at its quote (or the reference);
// "partly supported" and "one source, not confirmed" are always written out; the legend, the Answer, the limitations and the "Sources disagree" blocks are never collapsed;
// the introduction, the sentences of a section, the evidence under a sentence and the references are under collapse bars (closed by default).

const reducedMotion = (): boolean => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

function SectionBlock({ s, open, onToggle }: { s: SectionView; open: boolean; onToggle: () => void }) {
  const body = `wr-${s.id}-body`, gaps = `wr-${s.id}-gaps`
  const nothing = s.sentences.length === 0 && s.disagreements.length === 0 && s.gaps.length === 0
  return (
    <section className="wr-section wr-fold" aria-labelledby={`wr-${s.id}`}>
      <h3 id={`wr-${s.id}`} className="wr-fold-h" tabIndex={-1}>
        <FoldBar controls={`${body} ${gaps}`} open={open} onToggle={onToggle}>
          <span className="wr-bar-title">{s.title}</span>
          <span className="wr-bar-sub">{s.summary}{s.hints.map(h => <span key={h} className="tag gap">{h}</span>)}</span>
        </FoldBar>
      </h3>
      <div id={body} className="wr-fold-body" hidden={!open}>
        {s.detailQuestions.length > 0 && <ul className="wr-details" aria-label="Detail questions">{s.detailQuestions.map((q, i) => <li key={`${i}:${q}`}>{q}</li>)}</ul>}
        {s.sentences.map((v, i) => <Sentence key={i} v={v} />)}
        {nothing && <p className="meta">Nothing was written for this sub-question.</p>}
      </div>
      {/* "Sources disagree" is never collapsed: both sides stay visible even when the section is closed. */}
      {s.disagreements.length > 0 && <div className="wr-disagrees">{s.disagreements.map((d, i) => <Disagreement key={i} d={d} index={i} id={`wr-dis-${s.id}-${i}`} />)}</div>}
      <div id={gaps} className="wr-fold-body" hidden={!open}>
        {s.gaps.length > 0 && <div className="wr-gaps"><h4><Info size={15} aria-hidden="true" /> Evidence gaps</h4><ul>{s.gaps.map((g, i) => <li key={`${i}:${g}`}>{g}</li>)}</ul></div>}
      </div>
    </section>
  )
}

/** A link to the Markdown of the report as a file. The blob is created for the link and released when the page goes away. */
function DownloadMarkdown({ markdown, name }: { markdown: string; name: string }) {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    const u = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }))
    setUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [markdown])
  if (!markdown) return null
  return <a className="start-button" href={url ?? undefined} download={name} aria-disabled={!url}><Download size={15} aria-hidden="true" />Download Markdown</a>
}

export function ReportView({ runId, res }: { runId: string; res: WrittenReportResponse }) {
  const m = useMemo(() => reportModel(res, runId), [res, runId])
  const evidence = `/research/${encodeURIComponent(runId)}/report`

  // Which bars are open: the sections and the references are controlled here, because a marker or a link elsewhere on the page can ask for them to open.
  const [openSections, setOpenSections] = useState<ReadonlySet<string>>(() => new Set())
  const [refsOpen, setRefsOpen] = useState(false)
  const allOpen = m.sections.length > 0 && m.sections.every(s => openSections.has(s.id))
  const toggleSection = (id: string) => setOpenSections(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n })
  const toggleAll = () => setOpenSections(allOpen ? new Set() : new Set(m.sections.map(s => s.id)))

  // "Open this bar, then show that element": the element exists (hidden) before the bar opens, so the scroll waits for the render in which the bar is open.
  const pending = useRef<string | null>(null)
  const [tick, setTick] = useState(0)
  const showSoon = useCallback((id: string) => { pending.current = id; setTick(t => t + 1) }, [])
  useEffect(() => {
    const id = pending.current
    const el = id ? document.getElementById(id) : null
    if (!id || !el || el.closest('[hidden]')) return
    pending.current = null
    el.focus({ preventScroll: true })
    el.scrollIntoView({ block: 'center', behavior: reducedMotion() ? 'auto' : 'smooth' })
  }, [tick, openSections, refsOpen])

  const actions = useMemo<ReportActions>(() => ({
    openReference: n => { setRefsOpen(true); showSoon(`ref-${n}`) },
    openSection: (sectionId, targetId) => { setOpenSections(prev => new Set(prev).add(sectionId)); showSoon(targetId ?? `wr-${sectionId}`) },
    rememberBack: () => { try { sessionStorage.setItem(BACK_KEY, runId) } catch { /* private window: the Back link then follows its href */ } },
  }), [runId, showSoon])

  // A link such as #ref-3 (a bookmark, or a copied link) must open the References bar too.
  useEffect(() => {
    const h = /^#ref-(\d+)$/.exec(window.location.hash)
    if (h) actions.openReference(Number(h[1]))
  }, [actions])

  return (
    <ReportActionsContext.Provider value={actions}>
      <article className="written-report">
        <header className="wr-head">
          <div className="eyebrow research">Written report</div>
          <h1>{m.question ?? 'Written report'}</h1>
          <div className="run-meta">
            <StatusPill tone={m.status.tone}>{m.status.label}</StatusPill>
            {m.generatedAt && <span className="tag">Written {formatDateTime(m.generatedAt)}</span>}
            {m.model && <span className="tag">model: {m.model}</span>}
            {m.templateVersion && <span className="tag">template {m.templateVersion}</span>}
          </div>
          <div className="run-actions wr-actions">
            <DownloadMarkdown markdown={res.markdown} name={downloadName(runId)} />
            <Link className="start-button secondary" href={evidence}><FileSearch size={15} aria-hidden="true" />Open the evidence report</Link>
          </div>
        </header>

        {/* The legend is always here, near the top: it says how to read every sentence below. */}
        <aside className="wr-legend callout-box lav" role="note" aria-label="How to read the findings"><ShieldAlert size={18} aria-hidden="true" /><div><b>How to read the findings</b><p>{m.legend}</p><p className="meta">{m.notVerified}</p></div></aside>

        {m.status.note && (
          <div className={`callout-box ${m.status.isError ? 'coral' : 'amber'} wr-status-note`} role={m.status.isError ? 'alert' : 'note'}>
            <AlertTriangle size={18} aria-hidden="true" /><div><b>{m.status.label}</b><p>{m.status.note}</p></div>
          </div>
        )}
        {m.warnings.length > 0 && (
          <section className="wr-warnings" aria-labelledby="wr-warnings-h"><h2 id="wr-warnings-h">Warnings</h2><ul>{m.warnings.map((w, i) => <li key={`${i}:${w}`}>{w}</li>)}</ul></section>
        )}

        {m.status.isError && m.empty ? null : (
          <>
            <AnswerCard m={m} />
            {m.introduction.length > 0 && (
              <Fold heading={2} title="Introduction" className="wr-intro">
                {m.introduction.map((p, i) => <p key={`${i}:${p.slice(0, 20)}`}>{p}</p>)}
              </Fold>
            )}
            {m.sections.length > 0 && (
              <section className="wr-topics" aria-labelledby="wr-topics-h">
                <div className="wr-topics-head">
                  <h2 id="wr-topics-h">Topic-wise Research Findings</h2>
                  <button type="button" className="tool-button" onClick={toggleAll}>{allOpen ? 'Collapse all' : 'Expand all'}<span className="sr-only"> sections</span></button>
                </div>
                {m.sections.map(s => <SectionBlock key={s.id} s={s} open={openSections.has(s.id)} onToggle={() => toggleSection(s.id)} />)}
              </section>
            )}
          </>
        )}

        {/* The limitations are never collapsed: they say what the report does not cover and that every check is automatic. */}
        <section className="wr-limitations" aria-labelledby="wr-limits-h">
          <h2 id="wr-limits-h">Limitations and Evidence Gaps</h2>
          {m.limitations.length > 0 ? <ul>{m.limitations.map((l, i) => <li key={`${i}:${l.slice(0, 24)}`}>{l}</li>)}</ul> : <p className="meta">No limitations were listed. Every check in this report is automatic and none was reviewed by a person.</p>}
        </section>

        {m.conclusion.length > 0 && <section aria-labelledby="wr-conclusion-h"><h2 id="wr-conclusion-h">Conclusion</h2>{m.conclusion.map((v, i) => <Sentence key={i} v={v} />)}</section>}

        {m.references.length > 0 && (
          <Fold heading={2} title={`References (${m.references.length})`} open={refsOpen} onOpenChange={setRefsOpen} className="wr-references">
            <ol className="wr-refs">
              {m.references.map(r => (
                <li key={r.number} id={r.anchor} value={r.number} tabIndex={-1}>
                  <span className="wr-ref-num">[{r.number}]</span> <span className="wr-ref-text">{r.text}</span>
                  {r.kind && <span className="tag">{r.kind === 'web' ? 'web' : r.kind === 'paper' ? 'paper' : r.kind}</span>}
                  {r.hint && <span className="tag warn" title="Only part of this source was read">{r.hint}</span>}
                  {r.citedIn != null && <span className="meta wr-cited">cited in {r.citedIn === 1 ? '1 sentence' : `${r.citedIn} sentences`}</span>}
                  <span className="wr-ref-actions">
                    {r.paper && <Link href={r.paper.href} prefetch={false} onClick={actions.rememberBack}>{r.paper.label}</Link>}
                    {r.url && <a href={r.url} target="_blank" rel="noopener noreferrer">Open source<span className="sr-only"> (opens in a new tab)</span></a>}
                  </span>
                  {r.doi && !r.text.includes(r.doi) && <span className="meta wr-doi">doi: {r.doi}</span>}
                </li>
              ))}
            </ol>
          </Fold>
        )}
      </article>
    </ReportActionsContext.Provider>
  )
}
