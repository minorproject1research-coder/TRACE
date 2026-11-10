'use client'

import { useCallback } from 'react'
import { formatClock } from '@/lib/format'
import { criticalPathText, msLabel, type StageGantt, type SwimRow, type WorkerView } from '@/lib/swimlanes'

// The per-sub-question views of the Timeline (T1 to T3). Shown only when the stream carries the parallel-pipeline fields; the maths is in lib/swimlanes.ts.

/** Scrolls to the details of a sub-question (its fact-check row, else its judge or second-search chip), opening the sections around it. */
export function useJumpToSubQuestion() {
  return useCallback((index: number) => {
    const root = document.querySelector('.timeline')
    const el = (root?.querySelector(`.fact-row[data-sq="${index}"]`) ?? root?.querySelector(`.sq-chip[data-sq="${index}"]`)) as HTMLElement | null
    if (!el) return
    for (let p: HTMLElement | null = el.parentElement; p; p = p.parentElement) if (p.tagName === 'DETAILS') (p as HTMLDetailsElement).open = true
    const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    el.scrollIntoView({ block: 'center', behavior: calm ? 'auto' : 'smooth' })
    el.classList.add('flash')
    setTimeout(() => el.classList.remove('flash'), 1600)
  }, [])
}

export function SwimlaneMatrix({ rows }: { rows: SwimRow[] }) {
  const jump = useJumpToSubQuestion()
  if (rows.length === 0) return null
  return (
    <section className="lane tl-swim" aria-label="Sub-questions by stage">
      <div className="lane-head"><div className="lane-title"><h3>Sub-questions</h3><p className="meta">Where each sub-question is in the judge, the second search and the fact check. Select a row to jump to its details.</p></div></div>
      <div className="table-wrap" tabIndex={0} role="region" aria-label="Sub-questions by stage, table">
        <table className="swim">
          <thead><tr><th scope="col">Sub-question</th><th scope="col">Judge</th><th scope="col">Second search</th><th scope="col">Fact check</th></tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.index}>
                <th scope="row"><button type="button" className="link-button" onClick={() => jump(r.index)}><b>{r.index}.</b> {r.topic ?? `Sub-question ${r.index}`}</button></th>
                {[r.judge, r.second, r.fact].map((c, i) => <td key={i} className={`swim-cell ${c.state} ${c.tone}`}>{c.text}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

const KIND_LABEL = { judge: 'judge', second: 'second search', fact: 'fact check' } as const

/** The bars of every sub-question on one axis. A hatched piece between a judge and its fact check is the time it waited for a free worker. */
export function StageGanttView({ g }: { g: StageGantt }) {
  const span = g.toMs - g.fromMs
  const pct = (ms: number) => Math.max(0, Math.min(100, ((ms - g.fromMs) / span) * 100))
  const w = (a: number, b: number) => Math.max(0.8, Math.min(100 - pct(a), ((b - a) / span) * 100))
  const critical = criticalPathText(g)
  const summary = g.lanes.map(l => `Sub-question ${l.index}: ${l.bars.map(b => `${KIND_LABEL[b.kind]} ${msLabel(b.toMs - b.fromMs)}${b.open ? ' so far' : ''}`).join(', ')}`).join('. ')
  return (
    <section className="lane tl-gantt34" aria-label="Evidence stage and fact check on one time axis">
      <div className="lane-head"><div className="lane-title"><h3>Time per sub-question</h3><p className="meta">Judge, second search and fact check of each sub-question on one time axis.</p></div></div>
      <div className="gantt34" role="img" aria-label={`${summary}. ${critical.join(' ')}`}>
        {g.lanes.map(l => (
          <div className="g34-row" key={l.index}>
            <span className="g34-label" title={l.topic ?? undefined}>Q{l.index}</span>
            <div className="g34-track">
              {g.stage3EndMs != null && <i className="g34-mark" style={{ left: `${pct(g.stage3EndMs)}%` }} />}
              {l.wait && <span className="g34-wait" style={{ left: `${pct(l.wait.fromMs)}%`, width: `${w(l.wait.fromMs, l.wait.toMs)}%` }} />}
              {l.bars.map((b, i) => <span key={i} title={b.tip ?? `${KIND_LABEL[b.kind]}: ${msLabel(b.toMs - b.fromMs) ?? ''}`} className={`g34-bar ${b.kind} ${b.open ? 'open' : ''}`} style={{ left: `${pct(b.fromMs)}%`, width: `${w(b.fromMs, b.toMs)}%` }} />)}
            </div>
          </div>
        ))}
        <div className="gantt-axis g34-axis"><span>start of the evidence stage</span><span>{msLabel(g.toMs - g.fromMs)}{g.running ? ' so far' : ''}</span></div>
      </div>
      <ul className="g34-legend" aria-hidden="true">
        <li><i className="g34-bar judge" /> judge</li><li><i className="g34-bar second" /> second search</li><li><i className="g34-bar fact" /> fact check</li>
        <li><i className="g34-wait" /> waited for a free worker</li>{g.stage3EndMs != null && <li><i className="g34-mark inline" /> evidence stage ended</li>}
      </ul>
      {critical.length > 0 && <ul className="g34-critical">{critical.map(t => <li key={t}>{t}</li>)}</ul>}
    </section>
  )
}

/** Stage 4 per sub-question: when it joined the queue, started, finished, how long it waited and took, which worker, and what it found. */
export function WorkerTable({ v }: { v: WorkerView }) {
  const span = v.fromMs != null && v.toMs != null ? Math.max(1000, v.toMs - v.fromMs) : null
  const t = (iso: string | null) => (iso ? formatClock(iso) : '–')
  return (
    <section className="lane tl-workers" aria-label="Fact check workers">
      <div className="lane-head"><div className="lane-title"><h3>Fact check, one sub-question at a time per worker</h3>
        <p className="meta">{v.workers > 0 ? `${v.workers} ${v.workers === 1 ? 'worker' : 'workers'} reported.` : 'The server did not say which worker checked which sub-question.'}{v.usesDone ? '' : ' This stream does not report when a sub-question finishes, so finish times and durations are not shown.'}</p></div></div>
      <div className="table-wrap" tabIndex={0} role="region" aria-label="Fact check by sub-question, table">
        <table className="swim">
          <thead><tr><th scope="col">Sub-question</th><th scope="col">Queued</th><th scope="col">Started</th><th scope="col">Finished</th><th scope="col">Waited</th><th scope="col">Took</th>{v.workers > 0 && <th scope="col">Worker</th>}<th scope="col">Result</th></tr></thead>
          <tbody>
            {v.rows.map(r => (
              <tr key={r.index}>
                <th scope="row"><b>{r.index}.</b> {r.topic ?? `Sub-question ${r.index}`}</th>
                <td>{t(r.queuedAt)}</td><td>{t(r.startedAt)}</td><td>{t(r.finishedAt)}</td><td>{msLabel(r.waitedMs) ?? '–'}</td><td>{msLabel(r.tookMs) ?? '–'}</td>
                {v.workers > 0 && <td>{r.worker ?? '–'}</td>}
                <td>{r.status === 'running' ? 'checking…' : r.counts ?? (r.status === 'done' ? 'checked' : r.status === 'failed' ? 'stopped' : '–')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {v.workers > 0 && span != null && v.fromMs != null && (
        <div className="gantt34 workers" role="img" aria-label={v.lanes.map(l => `Worker ${l.worker}: ${l.items.map(i => `sub-question ${i.index} ${msLabel(i.toMs - i.fromMs) ?? ''}`).join(', ')}`).join('. ')}>
          {v.lanes.map(l => (
            <div className="g34-row" key={l.worker}>
              <span className="g34-label">W{l.worker}</span>
              <div className="g34-track">
                {l.items.map(i => <span key={i.index} className={`g34-bar fact ${i.open ? 'open' : ''}`} style={{ left: `${((i.fromMs - v.fromMs!) / span) * 100}%`, width: `${Math.max(1.5, ((i.toMs - i.fromMs) / span) * 100)}%` }}><em>{i.index}</em></span>)}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
