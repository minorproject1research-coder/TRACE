'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { AlertTriangle, ArrowLeft, Hourglass, ShieldAlert } from 'lucide-react'
import { CoverageBlock, SourceCard } from '@/components/trace/evidence'
import { StatusPill } from '@/components/trace/status-pill'
import { ErrorState, Skeleton } from '@/components/trace/states'
import { formatDateTime } from '@/lib/format'
import { useMode } from '@/lib/mode'
import { useReport } from '@/lib/use-research'

export default function ReportPage() {
  const { id: rawId } = useParams<{ id: string }>()
  const id = decodeURIComponent(rawId)
  const { mode } = useMode()
  const report = useReport(id, true)
  const back = <Link className="back-link" href={`/research/${encodeURIComponent(id)}`}><ArrowLeft size={14} aria-hidden="true" /> Back to run</Link>

  if (report.loading && !report.data) return <>{back}<h1 className="sr-only">Evidence report</h1><Skeleton rows={6} label="Loading evidence report" /></>
  if (report.error || !report.data) {
    const e = report.error
    if (e?.status === 409) return <>{back}<h1 className="sr-only">Evidence report</h1><div className="state-box"><Hourglass size={22} aria-hidden="true" /><div><b>The run is still going</b><p>The evidence report can be read once the run finishes. Follow its progress on the run page.</p><Link className="link-button" href={`/research/${encodeURIComponent(id)}`}>Go to the run</Link></div></div></>
    return <>{back}<h1 className="sr-only">Evidence report</h1><ErrorState title={e?.status === 404 ? 'No report for this run' : 'Could not load the report'} message={e?.status === 404 ? 'This run does not exist here, ended before any evidence was saved, or the server could not read it just now.' : (e?.message ?? 'Unknown error')} status={e?.status} onRetry={report.reload} /></>
  }

  const r = report.data
  const t = r.totals
  return (
    <article className="report">
      {back}
      <header className="report-head rise">
        <div className="eyebrow research">{mode === 'demo' ? 'Demo evidence report' : 'Evidence report'}</div>
        <h1>{r.question}</h1>
        <p className="meta">Run {r.id.slice(0, 8)} · {formatDateTime(r.createdAt)}</p>
      </header>

      <div className="callout-box lav rise" style={{ '--i': 1 } as React.CSSProperties} role="note">
        <ShieldAlert size={18} aria-hidden="true" />
        <div><b>This is collected evidence, not an answer</b><p>TRACE has not written an answer or checked that claims are true. Read the findings and their quotes, and treat any sub-question marked as not sufficient or not finished as open.</p></div>
      </div>

      {r.runError && <div className="banner offline" role="alert" style={{ margin: '16px 0', borderRadius: 12 }}><AlertTriangle size={16} aria-hidden="true" /><p><b>The run failed part-way.</b> {r.runError} This report is partial.</p></div>}

      <section className="metrics report-metrics rise" style={{ '--i': 2 } as React.CSSProperties} aria-label="Report totals">
        <div><strong>{t.subQuestionsSufficient}/{t.subQuestions}</strong><span>sub-questions sufficient</span></div>
        <div><strong>{t.sources}</strong><span>sources</span></div>
        <div><strong>{t.findings}</strong><span>findings</span></div>
        <div><strong>{t.findingsQuoteFound}/{t.findings}</strong><span>quotes found in source</span></div>
      </section>

      <section className="panel rise" style={{ '--i': 3 } as React.CSSProperties} aria-labelledby="lim-title">
        <h2 id="lim-title">Limitations</h2>
        <ul className="plain-list">{r.limitations.map(l => <li key={l}>{l}</li>)}</ul>
      </section>

      <nav className="toc" aria-label="Sub-questions">
        {r.subQuestions.map((sq, i) => <a key={sq.id} href={`#sq-${sq.id}`}><span className="n">{i + 1}</span>{sq.topic}{!sq.coverage ? <StatusPill tone="coral">Not finished</StatusPill> : sq.coverage.sufficient ? <StatusPill tone="mint">Sufficient</StatusPill> : <StatusPill tone="amber">Not sufficient</StatusPill>}</a>)}
      </nav>

      {r.subQuestions.map((sq, i) => (
        <section key={sq.id} id={`sq-${sq.id}`} className="sq-section" aria-labelledby={`h-${sq.id}`}>
          <div className="eyebrow">Sub-question {i + 1}</div>
          <h2 id={`h-${sq.id}`}>{sq.topic}</h2>
          {sq.detailQuestions.length > 0 && <p className="meta">Also asked: {sq.detailQuestions.join(' · ')}</p>}
          <CoverageBlock sq={sq} />
          <h3 className="sub-h">Sources ({sq.sources.length})</h3>
          {sq.sources.length === 0 ? <p className="meta">No sources were kept for this sub-question.</p> : <div className="card-list">{sq.sources.map(s => <SourceCard key={s.id} source={s} />)}</div>}
        </section>
      ))}
    </article>
  )
}
