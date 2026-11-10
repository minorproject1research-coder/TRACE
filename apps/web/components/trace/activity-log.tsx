'use client'

import { useMemo, useState } from 'react'
import { Activity, AlertTriangle, Check, Copy, WifiOff, X } from 'lucide-react'
import { eventsJson, filterRows, logCountLabel, logOptions, NO_FILTER, searchIndex, type LogFilter } from '@/lib/event-log'
import { formatClock } from '@/lib/format'
import type { StreamStatus, WorkflowEvent } from '@/lib/trace-types'

const streamText: Record<StreamStatus, string> = { connecting: 'CONNECTING', open: 'STREAMING', reconnecting: 'RECONNECTING', closed: 'STREAM ENDED', error: 'STREAM UNAVAILABLE' }
const PAGE = 150                      // rows drawn at a time: a run has 300 events or more, and the filters work on all of them

export function ActivityLog({ events, status, detail, running, took }: { events: WorkflowEvent[]; status: StreamStatus; detail?: string; running: boolean; took?: Map<number, string> }) {
  const [filter, setFilter] = useState<LogFilter>(NO_FILTER)
  const [shown, setShown] = useState(PAGE)
  const [copied, setCopied] = useState<'' | 'done' | 'failed'>('')
  const rows = useMemo(() => searchIndex(events), [events])                  // the search text of every event, built once per list
  const options = useMemo(() => logOptions(rows), [rows])
  const filtered = useMemo(() => filterRows(rows, filter), [rows, filter])
  const list = useMemo(() => [...filtered].reverse().slice(0, shown), [filtered, shown])       // newest first
  const set = (patch: Partial<LogFilter>) => { setFilter(f => ({ ...f, ...patch })); setShown(PAGE) }
  const active = JSON.stringify(filter) !== JSON.stringify(NO_FILTER)
  const copy = async () => {
    try { await navigator.clipboard.writeText(eventsJson(filtered)); setCopied('done') } catch { setCopied('failed') }
    setTimeout(() => setCopied(''), 2500)
  }
  return (
    <>
      <div className="event-caption" role="status">
        {status === 'error' ? <WifiOff size={15} /> : <Activity size={15} />}
        <span>{running ? 'Live events from the research runner' : 'Events recorded for this run'}</span>
        <span className={`stream-state ${status}`}>{streamText[status]}</span>
      </div>
      {status === 'reconnecting' && <p className="meta" style={{ marginBottom: 14 }}>The connection dropped. The browser is reconnecting and will pick up where it left off.</p>}
      {status === 'error' && <p className="meta" style={{ marginBottom: 14 }}>{detail ?? 'The live stream is unavailable.'} The status above still refreshes every few seconds.</p>}
      {rows.length === 0 && <p className="meta">{status === 'closed' || status === 'error' ? 'No events are available for this run.' : 'Waiting for the first event…'}</p>}

      {rows.length > 0 && (
        <div className="log-filters" role="group" aria-label="Filter the events">
          <label className="select-field"><span className="sr-only">Stage</span>
            <select value={filter.stage} onChange={e => set({ stage: e.target.value })}><option value="all">All stages</option>{options.stages.map(s => <option key={s} value={s}>{s}</option>)}</select></label>
          <label className="select-field"><span className="sr-only">Lane</span>
            <select value={filter.lane} onChange={e => set({ lane: e.target.value })}><option value="all">All lanes</option>{options.lanes.map(s => <option key={s} value={s}>{s}</option>)}</select></label>
          {options.subQuestions.length > 0 && <label className="select-field"><span className="sr-only">Sub-question</span>
            <select value={filter.subQuestion} onChange={e => set({ subQuestion: e.target.value })}><option value="all">All sub-questions</option>{options.subQuestions.map(s => <option key={s} value={String(s)}>Sub-question {s}</option>)}</select></label>}
          <label className="select-field"><span className="sr-only">Event type</span>
            <select value={filter.type} onChange={e => set({ type: e.target.value })}><option value="all">All types</option>{options.types.map(s => <option key={s} value={s}>{s}</option>)}</select></label>
          <label className="search-field"><span className="sr-only">Search the events</span>
            <input value={filter.text} onChange={e => set({ text: e.target.value })} placeholder="Search the events…" /></label>
          <label className="check"><input type="checkbox" checked={filter.warningsOnly} onChange={e => set({ warningsOnly: e.target.checked })} /> Warnings only</label>
          <span className="meta" aria-live="polite">{logCountLabel(filtered.length, rows.length)}</span>
          <button type="button" className="tool-button" onClick={copy} disabled={filtered.length === 0}><Copy size={13} aria-hidden="true" /> Copy {active ? 'filtered ' : ''}events as JSON</button>
          {active && <button type="button" className="link-button" onClick={() => { setFilter(NO_FILTER); setShown(PAGE) }}>Clear filters</button>}
          <span className="meta" role="status">{copied === 'done' ? 'Copied.' : copied === 'failed' ? 'Could not copy: the browser blocked the clipboard.' : ''}</span>
        </div>
      )}
      {rows.length > 0 && filtered.length === 0 && <p className="meta">No event matches the filters.</p>}

      <ol className="activity-list">
        {list.map((r, i) => {
          const e = r.e
          const failed = e.event === 'run_failed'
          return (
            <li className="activity-item" key={e.seq}>
              {e.timestamp ? <time className="activity-time" dateTime={e.timestamp}>{formatClock(e.timestamp)}</time> : <span className="activity-time" aria-hidden="true" />}
              <div className={`activity-icon ${i === 0 && running && !active ? 'current' : ''} ${failed ? 'failed' : ''} ${r.warn && !failed ? 'warn' : ''}`} aria-hidden="true">{failed ? <X size={13} /> : r.warn ? <AlertTriangle size={13} /> : i === 0 && running && !active ? <Activity size={13} /> : <Check size={13} />}</div>
              <div><b>{e.message || e.event}</b><code>{e.event}{e.stage ? ` · ${e.stage}` : ''}{r.lane ? ` · ${r.lane}` : ''}{r.sq != null ? ` · Q${r.sq}` : ''}</code>{r.warn && <span className="sr-only"> (warning)</span>}{took?.get(e.seq) && <span className="took">took {took.get(e.seq)}</span>}</div>
            </li>
          )
        })}
      </ol>
      {filtered.length > list.length && <button type="button" className="tool-button more" onClick={() => setShown(n => n + PAGE)}>Show {Math.min(PAGE, filtered.length - list.length)} more</button>}
    </>
  )
}
