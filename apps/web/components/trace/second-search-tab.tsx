'use client'

import Link from 'next/link'
import { useState } from 'react'
import { ArrowRight, ChevronDown, Copy, Hourglass, Layers, Search } from 'lucide-react'
import { EmptyState, Skeleton } from '@/components/trace/states'
import { StatusPill } from '@/components/trace/status-pill'
import { evidenceLevelLabel } from '@/lib/format'
import { ladderLabel, secondsLabel } from '@/lib/loop2'
import { BAR_CAPTION, FUNNEL_NOTE, neededLine, NOT_NEEDED_LINE, NOT_STORED, spanLine, WHY_TEXT, type AspectView, type NewSource, type RungDetails, type RungView, type SecondSearchView, type SqView, type VerdictBar } from '@/lib/second-search'
import { tokensLabel } from '@/lib/stream'
import { TabScroll } from '@/components/trace/tab-layout'

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

function CopyList({ text, label }: { text: string; label: string }) {
  const [state, setState] = useState<'' | 'done' | 'failed'>('')
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setState('done') } catch { setState('failed') }
    setTimeout(() => setState(''), 2500)
  }
  return (
    <>
      <button type="button" className="tool-button" onClick={copy}><Copy size={13} aria-hidden="true" /> {label}</button>
      <span className="meta" role="status">{state === 'done' ? 'Copied.' : state === 'failed' ? 'Could not copy: the browser blocked the clipboard.' : ''}</span>
    </>
  )
}

function Details({ d }: { d: RungDetails }) {
  const digests = [d.digests.total != null ? `digests: ${d.digests.total}` : null, d.digests.failed != null ? `failed: ${d.digests.failed}` : null, d.digests.tried != null ? `sources tried: ${d.digests.tried}` : null].filter(Boolean).join(' · ')
  return (
    <details className="ss-details">
      <summary>Details</summary>
      <div className="ss-details-body">
        {d.aspectTexts.length > 0 && <div><p className="ss-h">Aspects it worked on</p><ul className="ss-list">{d.aspectTexts.map((t, i) => <li key={`${i}:${t}`}>{t}{d.coveredTexts.includes(t) && <span className="tag good">covered</span>}</li>)}</ul></div>}
        {d.aspectTexts.length === 0 && d.coveredTexts.length > 0 && <div><p className="ss-h">Covered</p><ul className="ss-list">{d.coveredTexts.map((t, i) => <li key={`${i}:${t}`}>{t}</li>)}</ul></div>}
        {d.queries && (
          <div>
            <p className="ss-h">{d.queryCount != null ? `${d.queryCount} ${d.queryCount === 1 ? 'query' : 'queries'} asked` : 'Queries asked'}</p>
            {d.queries.map((g, i) => <div key={`${i}:${g.aspect}`} className="ss-qgroup"><p className="meta">{g.aspect}</p><ul className="ss-list ss-queries">{g.list.map((q, k) => <li key={`${k}:${q}`}><code>{q}</code></li>)}</ul></div>)}
            {d.queriesCopy && <CopyList text={d.queriesCopy} label="Copy the queries" />}
          </div>
        )}
        {d.funnel.length > 0 && <div><p className="ss-h">What they found</p><ul className="ss-list">{d.funnel.map(f => <li key={f}>{f}</li>)}</ul><p className="meta">{FUNNEL_NOTE}</p></div>}
        {digests && <p className="ss-nums">{digests}</p>}
        {d.digestWarning && <p className="stage-info-note" role="note">{d.digestWarning}</p>}
        {d.error && <p className="ss-plain"><b>Error:</b> {d.error}</p>}
        {d.note && <p className="ss-plain">{d.note}</p>}
      </div>
    </details>
  )
}

function Rung({ r }: { r: RungView }) {
  const nums: string[] = []
  if (r.state === 'ran') {
    if (r.aspects != null) nums.push(plural(r.aspects, 'aspect', 'aspects'))
    if (r.newSources != null) nums.push(plural(r.newSources, 'new source', 'new sources'))
    if (r.newFindings != null) nums.push(plural(r.newFindings, 'new verified finding', 'new verified findings'))
    if (r.covered != null) nums.push(`${r.covered} covered`)
    if (r.seconds != null) nums.push(secondsLabel(r.seconds))
  }
  return (
    <li className={`ss-rung ${r.state} ${r.greyed ? 'grey' : ''} ${r.highlighted ? 'hit' : ''}`}>
      <div className="ss-rung-head">
        <b>{r.title}</b>
        {r.highlighted && <span className="tag good">covered an aspect</span>}
        {r.state === 'not_needed' && <span className="tag">not needed</span>}
        {r.state === 'did_not_run' && <span className="tag">did not run</span>}
        {r.state === 'ran' && r.greyed && <span className="tag">no new sources</span>}
        {r.running && <span className="tag live">running…</span>}
      </div>
      {r.explain && <p className="meta">{r.explain}</p>}
      {nums.length > 0 && <p className="ss-nums">{nums.join(' · ')}</p>}
      {r.details && <Details d={r.details} />}
    </li>
  )
}

function Bar({ label, v }: { label: string; v: VerdictBar }) {
  return (
    <div className="ss-bar-row">
      <span className="ss-bar-label">{label}</span>
      <div className="verdict-bar small" role="img" aria-label={`${label}: ${v.yes} yes, ${v.partial} partial, ${v.no} no`}>
        {v.total === 0 ? <span className="empty" style={{ flex: 1 }} /> : (['yes', 'partial', 'no'] as const).map(k => v[k] > 0 && <span key={k} className={k} style={{ flex: v[k] }} />)}
      </div>
      <span className="ss-bar-n">{v.total === 0 ? 'no findings' : `${v.yes} · ${v.partial} · ${v.no}`}</span>
    </div>
  )
}

/** Before and after the second search, as two small bars of yes, partial and no verdicts. Without an after (an older run) only the before is drawn. */
function BeforeAfter({ a }: { a: AspectView }) {
  if (!a.before && !a.after) return <span className="meta">{NOT_STORED}</span>
  return (
    <div className="ss-ba">
      {a.before ? <Bar label="before" v={a.before} /> : <span className="meta">before: {NOT_STORED}</span>}
      {a.after ? <Bar label="after" v={a.after} /> : <span className="meta">after: {NOT_STORED}</span>}
      {a.nowText && <span className="ss-now">{a.nowText}</span>}
    </div>
  )
}

function AspectTable({ aspects, label }: { aspects: AspectView[]; label: string }) {
  if (aspects.length === 0) return null
  const verdicts = aspects.some(a => a.before || a.after)
  return (
    <>
    {verdicts && <p className="meta">{BAR_CAPTION}</p>}
    <div className="table-wrap" tabIndex={0} role="region" aria-label={`Aspects searched again: ${label}`}>
      <table className="ss-aspects">
        <thead><tr><th scope="col">Aspect</th><th scope="col">Status</th>{verdicts && <th scope="col">Verdicts: yes · partial · no</th>}<th scope="col">How</th><th scope="col">Steps tried</th></tr></thead>
        <tbody>
          {aspects.map((a, i) => (
            <tr key={`${i}:${a.text}`}>
              <th scope="row"><span className="aspect-text">{a.text}</span>{a.rule && <small className="ss-rule">{a.rule}</small>}{a.nearMiss && <small className="ss-rule warn">Evidence exists, but no answer was complete. This blocks “sufficient”.</small>}</th>
              <td><StatusPill tone={a.chip.tone}>{a.chip.label}</StatusPill>{a.stopped && <small className="ss-rule warn">{a.stopped}</small>}</td>
              {verdicts && <td><BeforeAfter a={a} /></td>}
              <td>{a.how ?? <span className="meta">–</span>}</td>
              <td>{a.steps.length ? <span className="ss-tried">{a.steps.map((s, k) => <span key={`${s}-${k}`} className={`tag ${a.coveredBy === s ? 'good' : ''}`}>{ladderLabel(s)}</span>)}</span> : <span className="meta">not searched</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    </>
  )
}

function SqCard({ sq }: { sq: SqView }) {
  if (!sq.needed) return <div className="ss-muted"><b>{sq.index}. {sq.topic}</b><span>{sq.line ?? NOT_NEEDED_LINE}</span></div>
  const live = sq.live && !sq.live.done ? sq.live : null
  return (
    <details className="sq-group ss-card" open={!!live || undefined}>
      <summary>
        <span>{sq.index}. {sq.topic}</span>
        <span className="tag">{live ? `now: ${ladderLabel(live.rung)}${live.aspects != null ? ` (${plural(live.aspects, 'aspect', 'aspects')})` : ''}` : `searched ${sq.searched}, covered ${sq.covered}`}</span>
        {sq.seconds != null && <span className="tag">{secondsLabel(sq.seconds)}</span>}
        {sq.withGaps && <StatusPill tone="amber">Sufficient, with gaps</StatusPill>}
        {sq.yesAgg && <span className="tag good" title={BAR_CAPTION}>{sq.yesAgg.text}</span>}
        <ChevronDown size={14} className="chev" aria-hidden="true" />
      </summary>
      <div className="ss-body">
        <div className="source-tags">
          {sq.triage && <span className="tag">triage: {sq.triage}</span>}
          {sq.gapRule && <span className="tag">gap rule: {sq.gapRule}</span>}
          {sq.coveredBySynthesis > 0 && <span className="tag">{sq.coveredBySynthesis} covered by combining sources</span>}
        </div>
        <ol className="ss-ladder" aria-label={`The three steps of the second search: ${sq.topic}`}>{sq.rungs.map(r => <Rung key={r.id} r={r} />)}</ol>
        <AspectTable aspects={sq.aspects} label={sq.topic} />
        {sq.live && sq.live.done && sq.live.gaps != null && sq.live.gaps > 0 && <p className="meta">{plural(sq.live.gaps, 'aspect stays', 'aspects stay')} without evidence after the second search.</p>}
      </div>
    </details>
  )
}

function NewSources({ runId, list, onShowSources }: { runId: string; list: NewSource[]; onShowSources: () => void }) {
  if (list.length === 0) return null
  return (
    <>
      <div className="ss-section-head"><h2 className="sub-h">New sources ({list.length})</h2><button type="button" className="tool-button" onClick={onShowSources}>Show in Sources <ArrowRight size={13} aria-hidden="true" /></button></div>
      <ul className="ss-sources">
        {list.map((s, i) => (
          <li key={`${s.id}:${i}`}>
            {s.type === 'paper' ? <Link href={`/research/${encodeURIComponent(runId)}/papers/${encodeURIComponent(s.id)}`}>{s.title ?? 'Untitled paper'}</Link>
              : s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title ?? s.url}<span className="sr-only"> (opens in a new tab)</span></a> : <span>{s.title ?? 'Untitled source'}</span>}
            <span className="source-tags">
              <StatusPill tone="lav">{ladderLabel(s.rung)}</StatusPill>
              <span className="tag">{s.type === 'web' ? 'web' : 'paper'}</span>
              <span className="tag">{(evidenceLevelLabel as Record<string, { label: string }>)[s.evidenceLevel]?.label ?? String(s.evidenceLevel)}</span>
              <span className="tag">{plural(s.findings, 'finding', 'findings')}</span>
            </span>
            <small className="meta">{s.topic}</small>
          </li>
        ))}
      </ul>
    </>
  )
}

/** The "Second search" tab: what the optional second search (Loop 2) did, per sub-question, from the report once the run is over and from the events while it goes. */
export function SecondSearchTab({ runId, view, loading, onShowSources }: { runId: string; view: SecondSearchView; loading: boolean; onShowSources: () => void }) {
  if (loading) return <TabScroll label="Second search"><Skeleton rows={4} label="Loading the second search" /></TabScroll>
  const s = view.summary
  const span = spanLine(s)
  return (
    <TabScroll label="Second search">
      <div className="intel-content">
        {view.state === 'before' && <div className="state-box"><Hourglass size={22} aria-hidden="true" /><div><b>Not started yet</b><p>{view.message}</p></div></div>}
        {view.state === 'empty' && <EmptyState title="No second search" message={view.message ?? ''} />}
        {(view.state === 'live' || view.state === 'done') && (
          <>
            <div className="metrics ss-summary" role="group" aria-label="Second search summary">
              <div><strong>{neededLine(s)}</strong><span>sub-questions needed it</span></div>
              <div><strong>{s.searched} · {s.covered}</strong><span>aspects searched · covered</span></div>
              <div><strong>{s.knownGaps}</strong><span>known gaps</span></div>
              {view.source === 'report' && <div><strong>{s.newSources} · {s.newFindings}</strong><span>new sources · new verified findings</span></div>}
              {s.tokens != null && <div><strong>{tokensLabel(s.tokens)}</strong><span>tokens used by the second search</span></div>}
            </div>
            {span && <p className="meta ss-time"><Layers size={13} aria-hidden="true" /> {span}.</p>}
            <div className="tile ss-why"><div className="parallel-head"><b><Search size={14} aria-hidden="true" /> Why it ran</b></div><p className="meta">{WHY_TEXT}</p></div>
            <h2 className="sub-h">Sub-questions</h2>
            <div className="ss-cards">{view.sqs.map(sq => <SqCard key={sq.id} sq={sq} />)}</div>
            <NewSources runId={runId} list={view.newSources} onShowSources={onShowSources} />
            {view.source === 'events' && view.state === 'done' && <p className="meta">The sources and findings this search added are listed here once the report can be read.</p>}
          </>
        )}
      </div>
    </TabScroll>
  )
}
