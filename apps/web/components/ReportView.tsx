'use client'

import Link from 'next/link'
import { Fragment, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Download, FileSearch, Info, ShieldAlert } from 'lucide-react'
import { StatusPill } from '@/components/trace/status-pill'
import { formatDateTime } from '@/lib/format'
import { ANSWER_TITLE, downloadName, reportModel, type DisagreementView, type SectionView, type SentenceView, type SideView } from '@/lib/written-report'
import type { WrittenReportResponse } from '@/lib/trace-types'

// The written report of Stage 5. The rules (lib/written-report.ts): every sentence shows its markers from `refs` before the final full stop and each
// marker links to its reference; "partly supported" and "one source, not confirmed" are always written out; the legend is always visible; the limitations
// are never collapsed; disagreements show both sides and never say that one of them is false.

function Markers({ v }: { v: SentenceView }) {
  if (v.links.length === 0) return null
  return (
    <span className="wr-markers">
      {' ['}
      {v.links.map((l, i) => (
        <Fragment key={`${l.n}-${i}`}>
          {i > 0 && ', '}
          {l.found ? <a href={l.href} title={l.title ?? undefined} aria-label={`Reference ${l.n}${l.title ? `: ${l.title}` : ''}`}>{l.n}</a> : <span title="This reference is not in the list">{l.n}</span>}
        </Fragment>
      ))}
      {']'}
    </span>
  )
}

/** One sentence: the text, the markers, the final stop, and the label of its tier (always written out for a partly supported and a one-source sentence).
 *  A note (tier "note", a template sentence such as the open questions of the answer) is a plain muted line: no chip, no "plain wording" hint. */
function Sentence({ v }: { v: SentenceView }) {
  return (
    <p className={`wr-sentence ${v.tier.kind === 'note' ? 'wr-plain-note' : v.tier.kind}`}>
      {v.body}<Markers v={v} />{v.stop}
      {v.tier.label && <> <span className={`wr-tier ${v.tier.kind}`} title={v.tier.hint}>({v.tier.label})</span></>}
      {v.plainWording && <small className="wr-plain" title="Written from the claim’s own wording by a standard template, not by the model.">plain wording</small>}
    </p>
  )
}

function Side({ label, s }: { label: string; s: SideView }) {
  return (
    <div className="wr-side" role="group" aria-label={label}>
      <p className="wr-side-title">{label}{s.title ? `: ${s.title}` : ''}</p>
      {s.quote ? <blockquote>{s.quote}</blockquote> : <p className="meta">No quote was stored for this side.</p>}
      {s.marker && <p className="meta">Reference {s.marker.found ? <a href={s.marker.href}>[{s.marker.n}]</a> : `[${s.marker.n}]`}</p>}
    </div>
  )
}

/** "Sources disagree": both claims, both quotes, each with its reference. It never says that one side is false. */
function Disagreement({ d, index }: { d: DisagreementView; index: number }) {
  return (
    <div className="wr-disagree" role="group" aria-label={`Sources disagree (${index + 1})`}>
      <h3><ShieldAlert size={15} aria-hidden="true" /> Sources disagree</h3>
      {(d.claimA || d.claimB) && <ul className="wr-claims">{d.claimA && <li>{d.claimA}</li>}{d.claimB && <li>{d.claimB}</li>}</ul>}
      <div className="wr-sides"><Side label="One source says" s={d.sideA} /><Side label="Another source says" s={d.sideB} /></div>
      {d.note && <p className="meta">{d.note}</p>}
    </div>
  )
}

function Section({ s }: { s: SectionView }) {
  return (
    <section className="wr-section" aria-labelledby={`wr-${s.id}`}>
      <h2 id={`wr-${s.id}`}>{s.title}</h2>
      {s.detailQuestions.length > 0 && <ul className="wr-details" aria-label="Detail questions">{s.detailQuestions.map((q, i) => <li key={`${i}:${q}`}>{q}</li>)}</ul>}
      {s.sentences.map((v, i) => <Sentence key={i} v={v} />)}
      {s.disagreements.map((d, i) => <Disagreement key={i} d={d} index={i} />)}
      {s.gaps.length > 0 && <div className="wr-gaps"><h3><Info size={15} aria-hidden="true" /> Evidence gaps</h3><ul>{s.gaps.map((g, i) => <li key={`${i}:${g}`}>{g}</li>)}</ul></div>}
      {s.sentences.length === 0 && s.disagreements.length === 0 && s.gaps.length === 0 && <p className="meta">Nothing was written for this sub-question.</p>}
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
  const m = useMemo(() => reportModel(res), [res])
  const evidence = `/research/${encodeURIComponent(runId)}/report`
  return (
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
          <section aria-labelledby="wr-overview-h">
            <h2 id="wr-overview-h">{ANSWER_TITLE}</h2>
            {m.summary.map((v, i) => <Sentence key={i} v={v} />)}
            {m.summary.length === 0 && <p className="meta">{m.rawStatus === 'insufficient_evidence' ? 'The evidence is insufficient for a written answer.' : 'There is no written answer.'}</p>}
            {m.counts.length > 0 && <dl className="wr-counts" aria-label="Overview of the evidence">{m.counts.map(c => <div key={c.key}><dd>{c.value}</dd><dt>{c.label}</dt></div>)}</dl>}
          </section>
          {m.introduction.length > 0 && <section aria-labelledby="wr-intro-h"><h2 id="wr-intro-h">Introduction</h2>{m.introduction.map((p, i) => <p key={`${i}:${p.slice(0, 20)}`}>{p}</p>)}</section>}
          {m.sections.map(s => <Section key={s.id} s={s} />)}
        </>
      )}

      {/* The limitations are never collapsed: they say what the report does not cover and that every check is automatic. */}
      <section className="wr-limitations" aria-labelledby="wr-limits-h">
        <h2 id="wr-limits-h">Limitations and Evidence Gaps</h2>
        {m.limitations.length > 0 ? <ul>{m.limitations.map((l, i) => <li key={`${i}:${l.slice(0, 24)}`}>{l}</li>)}</ul> : <p className="meta">No limitations were listed. Every check in this report is automatic and none was reviewed by a person.</p>}
      </section>

      {m.conclusion.length > 0 && <section aria-labelledby="wr-conclusion-h"><h2 id="wr-conclusion-h">Conclusion</h2>{m.conclusion.map((v, i) => <Sentence key={i} v={v} />)}</section>}

      {m.references.length > 0 && (
        <section aria-labelledby="wr-refs-h">
          <h2 id="wr-refs-h">References</h2>
          <ol className="wr-refs">
            {m.references.map(r => (
              <li key={r.number} id={r.anchor} value={r.number}>
                <span className="wr-ref-num">[{r.number}]</span> <span className="wr-ref-text">{r.text}</span>
                {r.kind && <span className="tag">{r.kind === 'web' ? 'web' : r.kind === 'paper' ? 'paper' : r.kind}</span>}
                {r.hint && <span className="tag warn" title="Only part of this source was read">{r.hint}</span>}
                {r.url && <a href={r.url} target="_blank" rel="noopener noreferrer">Open source<span className="sr-only"> (opens in a new tab)</span></a>}
                {r.doi && !r.text.includes(r.doi) && <span className="meta wr-doi">doi: {r.doi}</span>}
              </li>
            ))}
          </ol>
        </section>
      )}
    </article>
  )
}
