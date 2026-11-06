'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { Plus, RefreshCw, Search } from 'lucide-react'
import { RunList } from '@/components/trace/run-list'
import { EmptyState, ErrorState, Skeleton } from '@/components/trace/states'
import { statusLabel } from '@/lib/format'
import { useMode } from '@/lib/mode'
import { radioGroupKeys } from '@/lib/radio-keys'
import type { RunStatus } from '@/lib/trace-types'
import { useRuns } from '@/lib/use-research'

const filters: ('all' | RunStatus)[] = ['all', 'running', 'completed', 'failed']

export default function HistoryPage() {
  const { mode } = useMode()
  const runs = useRuns(100)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<'all' | RunStatus>('all')

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (runs.data ?? []).filter(r => (status === 'all' || r.status === status || (status === 'running' && r.status === 'pending')) && (!q || r.question.toLowerCase().includes(q) || r.id.startsWith(q)))
  }, [runs.data, query, status])

  return (
    <>
      <section className="page-head rise">
        <div><div className="eyebrow">Research history</div><h1>Every run, ready to reopen</h1>
          <p>{mode === 'demo' ? 'Demo mode: these are fictional sample runs stored in this browser.' : 'Runs are stored in the TRACE database. A finished run can be reopened at any time, including after a server restart.'}</p></div>
        <Link className="start-button" href="/#new-research"><Plus size={15} />New research</Link>
      </section>

      <div className="toolbar rise" style={{ '--i': 1 } as React.CSSProperties}>
        <label className="search-field"><Search size={16} aria-hidden="true" /><span className="sr-only">Filter research by question or id</span>
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Filter by question or id…" /></label>
        <div className="segmented" role="radiogroup" aria-label="Filter by status" onKeyDown={radioGroupKeys}>
          {filters.map(f => <button key={f} type="button" role="radio" aria-checked={status === f} tabIndex={status === f ? 0 : -1} className={status === f ? 'gborder' : ''} onClick={() => setStatus(f)}>{f === 'all' ? 'All' : statusLabel[f]}</button>)}
        </div>
        <button className="tool-button" onClick={runs.reload} disabled={runs.loading}><RefreshCw size={14} className={runs.loading ? 'spin' : ''} /> Refresh</button>
      </div>

      <div className="rise" style={{ '--i': 2 } as React.CSSProperties}>
        {runs.loading && !runs.data && <Skeleton rows={5} label="Loading research history" />}
        {runs.error && <ErrorState title="Could not load research history" message={runs.error.message} status={runs.error.status} onRetry={runs.reload} />}
        {runs.data && runs.data.length === 0 && <EmptyState title="No research yet" message="Your runs will appear here once you start one." action={<Link className="link-button" href="/#new-research">Start your first run</Link>} />}
        {runs.data && runs.data.length > 0 && shown.length === 0 && <EmptyState title="Nothing matches" message="No run matches that filter." action={<button className="link-button" onClick={() => { setQuery(''); setStatus('all') }}>Clear filters</button>} />}
        {shown.length > 0 && <><RunList runs={shown} /><p className="list-count" aria-live="polite">Showing {shown.length} of {runs.data?.length ?? 0} runs (latest 100)</p></>}
      </div>
    </>
  )
}
