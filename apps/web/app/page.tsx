'use client'

import Link from 'next/link'
import { ArrowUpRight, ShieldCheck } from 'lucide-react'
import { Composer } from '@/components/trace/composer'
import { RunList } from '@/components/trace/run-list'
import { EmptyState, ErrorState, Skeleton } from '@/components/trace/states'
import { TraceMark } from '@/components/trace/trace-mark'
import { useRuns } from '@/lib/use-research'

function Stat({ value, label, color }: { value: string; label: string; color: string }) {
  return <div className="stat"><div className="stat-value" style={{ color }}>{value}</div><div className="stat-label">{label}</div></div>
}

export default function OverviewPage() {
  const runs = useRuns(100)
  const items = runs.data ?? []
  const completed = items.filter(r => r.status === 'completed').length
  const failed = items.filter(r => r.status === 'failed').length

  return (
    <>
      <section className="welcome rise">
        <div>
          <div className="eyebrow">Research overview</div>
          <h1>Find the signal.<br /><em>Verify the evidence.</em></h1>
          <p>Research across sources, connect findings, and understand what the evidence actually supports.</p>
        </div>
        <div className="orbit" aria-hidden="true">
          <div className="orbit-ring a" /><div className="orbit-ring b" />
          <div className="orbit-core"><TraceMark size={40} /></div>
          <span className="orbit-label one">SOURCE</span><span className="orbit-label two">SIGNAL</span>
        </div>
      </section>

      <Composer />

      <section className="stats-row rise" style={{ '--i': 3 } as React.CSSProperties} aria-label="Research totals">
        <Stat value={runs.data ? String(items.length) : '–'} label="Research runs on record" color="var(--text-1)" />
        <Stat value={runs.data ? String(completed) : '–'} label="Completed" color="var(--mint)" />
        <Stat value={runs.data ? String(failed) : '–'} label="Failed or interrupted" color={failed ? 'var(--coral)' : 'var(--text-3)'} />
        <div className="stats-note"><ShieldCheck size={18} /><span>Evidence-first<br />by design</span></div>
      </section>

      <section className="recent-section rise" style={{ '--i': 5 } as React.CSSProperties} aria-labelledby="recent-title">
        <div className="section-heading">
          <div><div className="eyebrow">Your research</div><h2 id="recent-title">Recent threads</h2></div>
          <Link className="link-button" href="/history">View history <ArrowUpRight size={14} /></Link>
        </div>
        {runs.loading && <Skeleton rows={3} label="Loading recent research" />}
        {runs.error && <ErrorState title="Could not load research history" message={runs.error.message} status={runs.error.status} onRetry={runs.reload} />}
        {!runs.loading && !runs.error && items.length === 0 && <EmptyState title="No research yet" message="Ask a question above to start your first run." />}
        {!runs.loading && !runs.error && items.length > 0 && <RunList runs={items.slice(0, 5)} />}
      </section>
    </>
  )
}
