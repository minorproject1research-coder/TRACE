import Link from 'next/link'
import { ArrowUpRight, FileText } from 'lucide-react'
import { formatDateTime, statusLabel, statusTone } from '@/lib/format'
import type { RunSummary } from '@/lib/trace-types'
import { StatusPill } from './status-pill'

export function RunList({ runs }: { runs: RunSummary[] }) {
  return (
    <div className="recent-table">
      <div className="table-head" aria-hidden="true"><span>RESEARCH THREAD</span><span>STATUS</span><span>STARTED</span><span /></div>
      {runs.map(run => (
        <Link className="research-row" key={run.id} href={`/research/${encodeURIComponent(run.id)}`}>
          <div className="thread-cell">
            <div className="thread-icon"><FileText size={17} /></div>
            <div><b>{run.question}</b><span>{run.id.slice(0, 8)}</span></div>
          </div>
          <StatusPill tone={statusTone[run.status]}>{statusLabel[run.status]}</StatusPill>
          <span className="muted-cell">{formatDateTime(run.createdAt)}</span>
          <ArrowUpRight size={16} className="row-arrow" />
        </Link>
      ))}
    </div>
  )
}
