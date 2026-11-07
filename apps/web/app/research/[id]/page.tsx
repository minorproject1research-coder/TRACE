'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, ArrowLeft, FileText, Hourglass, ShieldAlert } from 'lucide-react'
import { ActivityTab } from '@/components/trace/activity-tab'
import { CoverageBlock, FindingCard, NoEvidenceTag, SourceCard, verificationStats } from '@/components/trace/evidence'
import { Boundary } from '@/components/trace/boundary'
import { Pipeline } from '@/components/trace/pipeline'
import { TabFixed, TabScroll } from '@/components/trace/tab-layout'
import { StatusPill } from '@/components/trace/status-pill'
import { EmptyState, ErrorState, Skeleton } from '@/components/trace/states'
import { formatDateTime, formatDuration, num, stanceInfo, statusLabel, statusTone, type StanceGroup } from '@/lib/format'
import { useMode } from '@/lib/mode'
import { radioGroupKeys } from '@/lib/radio-keys'
import type { Report, WorkflowEvent } from '@/lib/trace-types'
import { usePapers, useReport, useRunStream, useSession, type Async } from '@/lib/use-research'

const TABS = ['Activity', 'Sources', 'Evidence', 'Verification'] as const
type Tab = (typeof TABS)[number]

export default function RunPage() {
  const { id: rawId } = useParams<{ id: string }>()
  const id = decodeURIComponent(rawId)
  const { mode } = useMode()
  const session = useSession(id)
  // Every event can change a stage, so re-read the status after each one. Coalesced: replayed events arrive in a burst.
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const stream = useRunStream(id, () => { clearTimeout(refreshTimer.current); refreshTimer.current = setTimeout(session.refresh, 200) })
  useEffect(() => () => clearTimeout(refreshTimer.current), [])
  const status = session.data?.status
  const active = status === 'pending' || status === 'running'
  const finished = status === 'completed' || status === 'failed'
  const report = useReport(id, finished)
  // Papers are in the database once the retrieval branch has finished; the list is read again whenever a stage or branch finishes.
  // The pipeline reports when the papers are saved and after every parsing round, so the list fills in while the run goes.
  const papersReady = finished || stream.events.some(e => (e.event === 'branch_completed' && e.data.branch === 'papers') || (e.event === 'step' && e.data.lane === 'papers' && e.data.step === 'store' && e.data.state === 'completed'))
  const papersVersion = stream.events.filter(e => e.event === 'stage_completed' || e.event === 'branch_completed' || (e.event === 'step' && e.data.state === 'completed') || (e.event === 'step' && e.data.step === 'parsing')).length + (finished ? 1000 : 0)
  const papers = usePapers(id, papersReady, papersVersion)
  const [tab, setTab] = useState<Tab>('Activity')

  useEffect(() => {
    const read = () => { const h = window.location.hash.slice(1); const t = TABS.find(x => x.toLowerCase() === h); if (t) setTab(t) }
    read()
    window.addEventListener('hashchange', read)
    return () => window.removeEventListener('hashchange', read)
  }, [])
  const pickTab = (t: Tab) => { setTab(t); history.replaceState(null, '', `#${t.toLowerCase()}`) }

  // Safety net: if the stream drops or never connects, the status still catches up.
  useEffect(() => {
    if (!active) return
    const timer = setInterval(session.refresh, 8000)
    return () => clearInterval(timer)
  }, [active, session.refresh])

  const onTabKey = (e: React.KeyboardEvent, i: number) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const next = TABS[(i + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length]
    pickTab(next)
    document.getElementById(`tab-${next}`)?.focus()
  }

  if (session.loading && !session.data) return <><BackLink /><h1 className="sr-only">Research run</h1><Skeleton rows={6} label="Loading research run" /></>
  if (session.error || !session.data) {
    const notFound = session.error?.status === 404
    return <><BackLink /><h1 className="sr-only">Research run</h1><ErrorState title={notFound ? 'Research run not found' : 'Could not load this run'} message={notFound ? 'No run with that id exists on this backend. It may belong to a different server or mode.' : (session.error?.message ?? 'Unknown error')} status={session.error?.status} onRetry={notFound ? undefined : session.reload} /></>
  }

  const s = session.data
  const duration = formatDuration(s.startedAt, s.finishedAt)
  const reportReady = finished && !!report.data
  const failedNote = s.status === 'failed'

  return (
    <>
      <BackLink />
      <section className="run-head rise">
        <div className="run-head-main">
          <div className="eyebrow">{mode === 'demo' ? 'Demo run' : 'Research run'}</div>
          <h1>{s.question}</h1>
          <div className="run-meta">
            <StatusPill tone={statusTone[s.status]}>{statusLabel[s.status]}</StatusPill>
            <span className="tag">{s.id.slice(0, 8)}</span>
            <span className="tag">Started {formatDateTime(s.createdAt)}</span>
            {duration && <span className="tag">took {duration}</span>}
          </div>
        </div>
        <div className="run-actions">
          {!finished
            ? <span className="start-button disabled" aria-disabled="true"><Hourglass size={15} />Report after the run</span>
            : report.loading
              ? <span className="start-button disabled" aria-disabled="true"><Hourglass size={15} />Loading report…</span>
              : reportReady
                ? <Link className="start-button" href={`/research/${encodeURIComponent(s.id)}/report`}><FileText size={15} />Open evidence report</Link>
                : <span className="start-button disabled" aria-disabled="true" title="No evidence was stored for this run"><FileText size={15} />No report stored</span>}
        </div>
      </section>

      {failedNote && (
        <div className="banner offline" role="alert" style={{ margin: '0 0 20px', borderRadius: 12 }}>
          <AlertTriangle size={16} aria-hidden="true" /><p><b>This run did not finish.</b> {s.error ?? 'No reason was recorded.'}{report.data ? ' A partial evidence report was stored and can still be read.' : ''}</p>
        </div>
      )}
      {active && (
        <div className="banner running" role="status" style={{ margin: '0 0 20px', borderRadius: 12 }}>
          <Hourglass size={16} aria-hidden="true" /><p><b>{s.status === 'pending' ? 'Queued.' : 'Running.'}</b> {mode === 'live' ? 'A run takes 15 to 25 minutes. You can leave this page: it keeps running and you can reopen it from Research history.' : 'This is a simulated run and takes about 13 seconds.'}</p>
        </div>
      )}

      <section className="live-workspace ring live rise" style={{ '--i': 1 } as React.CSSProperties} aria-label="Run workspace">
        <div className="workspace-grid">
          <Pipeline stages={s.stages} events={stream.events} />
          <div className="intelligence-panel">
            <div className="intel-tabs" role="tablist" aria-label="Run details">
              {TABS.map((t, i) => (
                <button key={t} id={`tab-${t}`} role="tab" type="button" aria-selected={tab === t} aria-controls="intel-panel" tabIndex={tab === t ? 0 : -1} onClick={() => pickTab(t)} onKeyDown={e => onTabKey(e, i)}>{t}</button>
              ))}
            </div>
            <div className="intel-body" id="intel-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
              <Boundary label={tab} resetKey={tab}>
              {tab === 'Activity' && <ActivityTab runId={id} events={stream.events} streamStatus={stream.status} streamDetail={stream.detail} running={active} papers={papers} mode={mode} />}
              {tab === 'Sources' && <SourcesTab events={stream.events} active={active} report={report} finished={finished} />}
              {tab === 'Evidence' && <EvidenceTab active={active} report={report} finished={finished} />}
              {tab === 'Verification' && <VerificationTab active={active} report={report} finished={finished} />}
              </Boundary>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}

function BackLink() {
  return <Link className="back-link" href="/history"><ArrowLeft size={14} aria-hidden="true" /> Research history</Link>
}

/** What to show while the evidence is not readable yet, or could not be loaded. Returns null when the report is ready. */
function Gate({ active, finished, report, what }: { active: boolean; finished: boolean; report: Async<Report>; what: string }) {
  if (active) return <div className="state-box"><Hourglass size={22} aria-hidden="true" /><div><b>{what} appear when the run finishes</b><p>TRACE stores them in the database as each sub-question is judged. They can only be read once the run completes.</p></div></div>
  if (!finished || report.loading) return <Skeleton rows={4} label={`Loading ${what.toLowerCase()}`} />
  if (report.error) return report.error.status === 404
    ? <EmptyState title="No evidence stored for this run" message="This run ended before any evidence was saved, or the server could not read it just now." action={<button className="link-button" onClick={report.reload}>Try again</button>} />
    : <ErrorState title={`Could not load ${what.toLowerCase()}`} message={report.error.message} status={report.error.status} onRetry={report.reload} />
  return null
}

function SourcesTab({ events, active, report, finished }: { events: WorkflowEvent[]; active: boolean; report: Async<Report>; finished: boolean }) {
  const [type, setType] = useState<'all' | 'paper' | 'web'>('all')
  const [partial, setPartial] = useState(false)
  const [second, setSecond] = useState(false)
  const topics = (events.find(e => e.stage === 'planner' && e.event === 'stage_completed')?.data.topics as string[] | undefined) ?? []
  const papers = num(events.find(e => e.event === 'branch_completed' && e.data.branch === 'papers')?.data, 'papers')
  const web = num(events.find(e => e.event === 'branch_completed' && e.data.branch === 'web')?.data, 'webSources')

  // A source can appear more than once in a sub-question (a paper read again for another aspect): list every entry, flag the repeats.
  const all = useMemo(() => (report.data?.subQuestions ?? []).flatMap(sq => {
    const seen = new Set<string>()
    return sq.sources.map(src => { const repeat = seen.has(src.id); seen.add(src.id); return { src, topic: sq.topic, repeat } })
  }), [report.data])
  const secondCount = all.filter(x => !!x.src.foundByLoop2Step).length          // 0 when Loop 2 did not run: then the filter is not shown
  const rows = all.filter(x => (type === 'all' || x.src.type === type) && (!partial || x.src.evidenceLevel !== 'full_text') && (!second || !!x.src.foundByLoop2Step))

  if (active) {
    return (
      <TabScroll label="Sources so far"><div className="intel-content">
        <div className="tile"><div className="parallel-head"><b>Retrieval so far</b><span>parallel branches</span></div>
          <div className="retrieval-row"><span className="source-icon paper">P</span><div><b>Papers</b><small>{papers != null ? `${papers} kept after filtering` : 'searching…'}</small></div></div>
          <div className="retrieval-row"><span className="source-icon web">W</span><div><b>Web</b><small>{web != null ? `${web} sources found` : 'searching…'}</small></div></div></div>
        {topics.length > 0 && <div className="tile"><div className="parallel-head"><b>Sub-questions being investigated</b><span>{topics.length}</span></div><ol className="plain-list numbered">{topics.map(t => <li key={t}>{t}</li>)}</ol></div>}
        <p className="meta">The list of sources, with the findings taken from each, appears when the run finishes.</p>
      </div></TabScroll>
    )
  }
  const gate = Gate({ active, finished, report, what: 'Sources' })
  if (gate) return <TabScroll label="Sources">{gate}</TabScroll>
  return (
    <>
      <TabFixed><div className="filter-row">
        <div className="segmented" role="radiogroup" aria-label="Source type" onKeyDown={radioGroupKeys}>{(['all', 'paper', 'web'] as const).map(t => <button key={t} type="button" role="radio" aria-checked={type === t} tabIndex={type === t ? 0 : -1} className={type === t ? 'gborder' : ''} onClick={() => setType(t)}>{t === 'all' ? 'All' : t === 'paper' ? 'Papers' : 'Web'}</button>)}</div>
        <label className="check"><input type="checkbox" checked={partial} onChange={e => setPartial(e.target.checked)} /> Only partly read</label>
        {secondCount > 0 && <label className="check"><input type="checkbox" checked={second} onChange={e => setSecond(e.target.checked)} /> Found by second search ({secondCount})</label>}
        <span className="meta" aria-live="polite">{rows.length} of {all.length} sources</span>
      </div></TabFixed>
      <TabScroll label="Sources list">
        {rows.length === 0 ? <EmptyState title="No sources match" message="Change the filters to see more." /> : <div className="card-list">{rows.map(({ src, topic, repeat }, i) => <SourceCard key={`${src.id}:${topic}:${i}`} source={src} topic={topic} headingLevel={2} repeat={repeat} />)}</div>}
      </TabScroll>
    </>
  )
}

function EvidenceTab({ active, report, finished }: { active: boolean; report: Async<Report>; finished: boolean }) {
  const [stance, setStance] = useState<'all' | StanceGroup>('all')
  const [unverified, setUnverified] = useState(false)
  const gate = Gate({ active, finished, report, what: 'Evidence' })
  if (gate) return <TabScroll label="Evidence">{gate}</TabScroll>
  const r = report.data!
  const hasOther = r.subQuestions.some(sq => sq.sources.some(src => src.findings.some(f => stanceInfo(f.stance).group === 'other')))
  return (
    <>
      <TabFixed>
      <div className="callout-box lav" role="note"><ShieldAlert size={18} aria-hidden="true" /><div><b>Findings, not facts</b><p>Each finding is a claim a source makes, with the quote behind it. Nothing has checked that the claim is true.</p></div></div>
      <div className="filter-row">
        <div className="segmented" role="radiogroup" aria-label="Stance" onKeyDown={radioGroupKeys}>{(['all', 'supports', 'opposes', 'neutral', ...(hasOther ? ['other' as const] : [])] as const).map(t => <button key={t} type="button" role="radio" aria-checked={stance === t} tabIndex={stance === t ? 0 : -1} className={stance === t ? 'gborder' : ''} onClick={() => setStance(t)} title={t === 'opposes' ? 'Findings the model marked as contradicting or challenging' : undefined}>{t === 'all' ? 'All' : t === 'opposes' ? 'Contradicts / challenges' : t[0].toUpperCase() + t.slice(1)}</button>)}</div>
        <label className="check"><input type="checkbox" checked={unverified} onChange={e => setUnverified(e.target.checked)} /> Unverified quotes only</label>
      </div>
      </TabFixed>
      <TabScroll label="Evidence list"><div className="intel-content">
      {r.subQuestions.map(sq => {
        const items = sq.sources.flatMap(src => src.findings.map(f => ({ f, src }))).filter(x => (stance === 'all' || stanceInfo(x.f.stance).group === stance) && (!unverified || !x.f.quoteFound))
        return (
          <details key={sq.id} className="sq-group" open={items.length > 0 && r.subQuestions.length <= 3}>
            <summary><span>{sq.topic}</span><span className="tag">{items.length} finding{items.length === 1 ? '' : 's'}</span>{!sq.coverage ? <StatusPill tone="coral">Not finished</StatusPill> : !sq.coverage.sufficient ? <StatusPill tone="amber">Not sufficient</StatusPill> : <StatusPill tone="mint">Sufficient</StatusPill>}<NoEvidenceTag coverage={sq.coverage} /></summary>
            {items.length === 0 ? <p className="meta">No findings match.</p> : items.map(({ f, src }, i) => <div key={i} className="finding-wrap"><p className="meta from">From {src.title ?? 'untitled source'}</p><FindingCard finding={f} /></div>)}
          </details>
        )
      })}
      </div></TabScroll>
    </>
  )
}

function VerificationTab({ active, report, finished }: { active: boolean; report: Async<Report>; finished: boolean }) {
  const gate = Gate({ active, finished, report, what: 'Verification results' })
  const stats = useMemo(() => (report.data ? verificationStats(report.data) : null), [report.data])
  if (gate) return <TabScroll label="Verification results">{gate}</TabScroll>
  if (!report.data || !stats) return null
  const r = report.data
  const found = r.totals.findingsQuoteFound
  const total = r.totals.findings
  return (
    <TabScroll label="Verification results"><div className="intel-content">
      <div className="callout-box amber" role="note"><AlertTriangle size={18} aria-hidden="true" /><div><b>Fact checking is not built yet</b><p>Stage 4 would check whether each claim is true. Today TRACE only checks that the quote exists in the source, and has an independent model judge the finding against the aspect it should answer.</p></div></div>
      <div className="metrics">
        <div><strong>{found}/{total}</strong><span>quotes found in source</span></div>
        <div><strong>{r.totals.subQuestionsSufficient}/{r.totals.subQuestions}</strong><span>sub-questions sufficient</span></div>
        <div><strong>{stats.contradicting.length}</strong><span>contradicting or challenging findings</span></div>
        <div><strong>{stats.partialSources}</strong><span>sources only partly read</span></div>
      </div>
      <div className="tile"><div className="parallel-head"><b>Independent judge verdicts</b><span>{stats.verdicts.yes + stats.verdicts.partial + stats.verdicts.no} checks</span></div>
        <div className="verdict-bar" role="img" aria-label={`${stats.verdicts.yes} yes, ${stats.verdicts.partial} partial, ${stats.verdicts.no} no`}>
          {(['yes', 'partial', 'no'] as const).map(k => stats.verdicts[k] > 0 && <span key={k} className={k} style={{ flex: stats.verdicts[k] }} title={`${k}: ${stats.verdicts[k]}`} />)}
        </div>
        <p className="meta">yes {stats.verdicts.yes} · partial {stats.verdicts.partial} · no {stats.verdicts.no}</p></div>

      {r.subQuestions.map(sq => <details key={sq.id} className="sq-group"><summary><span>{sq.topic}</span>{!sq.coverage ? <StatusPill tone="coral">Not finished</StatusPill> : !sq.coverage.sufficient ? <StatusPill tone="amber">Not sufficient</StatusPill> : <StatusPill tone="mint">Sufficient</StatusPill>}<NoEvidenceTag coverage={sq.coverage} /></summary><CoverageBlock sq={sq} /></details>)}

      <h2 className="sub-h">Contradicting or challenging findings ({stats.contradicting.length})</h2>
      {stats.contradicting.length === 0 ? <p className="meta">No finding is marked as contradicting or challenging.</p> : stats.contradicting.map(({ f, s }, i) => <div key={i} className="finding-wrap"><p className="meta from">From {s.title ?? 'untitled source'}</p><FindingCard finding={f} /></div>)}
      <h2 className="sub-h">Quotes that could not be located ({stats.unverified.length})</h2>
      {stats.unverified.length === 0 ? <p className="meta">Every quote was found in its source.</p> : stats.unverified.map(({ f, s }, i) => <div key={i} className="finding-wrap"><p className="meta from">From {s.title ?? 'untitled source'}</p><FindingCard finding={f} /></div>)}
    </div></TabScroll>
  )
}
