import { Activity, Check, WifiOff, X } from 'lucide-react'
import { formatClock } from '@/lib/format'
import type { StreamStatus, WorkflowEvent } from '@/lib/trace-types'

const streamText: Record<StreamStatus, string> = { connecting: 'CONNECTING', open: 'STREAMING', reconnecting: 'RECONNECTING', closed: 'STREAM ENDED', error: 'STREAM UNAVAILABLE' }

export function ActivityLog({ events, status, detail, running, took }: { events: WorkflowEvent[]; status: StreamStatus; detail?: string; running: boolean; took?: Map<number, string> }) {
  const shown = [...events].reverse()
  return (
    <>
      <div className="event-caption" role="status">
        {status === 'error' ? <WifiOff size={15} /> : <Activity size={15} />}
        <span>{running ? 'Live events from the research runner' : 'Events recorded for this run'}</span>
        <span className={`stream-state ${status}`}>{streamText[status]}</span>
      </div>
      {status === 'reconnecting' && <p className="meta" style={{ marginBottom: 14 }}>The connection dropped. The browser is reconnecting and will pick up where it left off.</p>}
      {status === 'error' && <p className="meta" style={{ marginBottom: 14 }}>{detail ?? 'The live stream is unavailable.'} The status above still refreshes every few seconds.</p>}
      {shown.length === 0 && <p className="meta">{status === 'closed' || status === 'error' ? 'No events are available for this run.' : 'Waiting for the first event…'}</p>}
      <ol className="activity-list">
        {shown.map((e, i) => {
          const failed = e.event === 'run_failed'
          return (
            <li className="activity-item" key={e.seq}>
              {e.timestamp ? <time className="activity-time" dateTime={e.timestamp}>{formatClock(e.timestamp)}</time> : <span className="activity-time" aria-hidden="true" />}
              <div className={`activity-icon ${i === 0 && running ? 'current' : ''} ${failed ? 'failed' : ''}`} aria-hidden="true">{failed ? <X size={13} /> : i === 0 && running ? <Activity size={13} /> : <Check size={13} />}</div>
              <div><b>{e.message || e.event}</b><code>{e.event}{e.stage ? ` · ${e.stage}` : ''}</code>{took?.get(e.seq) && <span className="took">took {took.get(e.seq)}</span>}</div>
            </li>
          )
        })}
      </ol>
    </>
  )
}
