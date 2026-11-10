'use client'

import { useEffect, useMemo, useState } from 'react'
import { Gauge } from 'lucide-react'
import { estimateTimeLeft } from '@/lib/eta'
import { GROQ_TOOLTIP, groqLine } from '@/lib/telemetry'
import { groqTotal } from '@/lib/stream'
import type { WorkflowEvent } from '@/lib/trace-types'

/** The live tags of the run header: the estimate of the time left (from real progress; live runs only) and the Groq use so far. Nothing renders without data. */
export function RunLive({ events, running, live, factEnabled }: { events: WorkflowEvent[]; running: boolean; live: boolean; factEnabled: boolean }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return
    const t = setInterval(() => setNow(Date.now()), 5000)                      // minutes are rounded: a tick every few seconds is plenty
    return () => clearInterval(t)
  }, [running])
  const eta = useMemo(() => (running && live ? estimateTimeLeft(events, now, factEnabled) : null), [events, now, running, live, factEnabled])
  const groq = useMemo(() => groqTotal(events), [events])
  if (!eta && !groq) return null
  return (
    <>
      {eta && <span className="tag eta" title={eta.basis}><Gauge size={12} aria-hidden="true" /> {eta.text}<span className="sr-only">. Based on: {eta.basis}</span></span>}
      {groq && <span className="tag" title={GROQ_TOOLTIP}>{groqLine(groq)}<span className="sr-only">. {GROQ_TOOLTIP}</span></span>}
    </>
  )
}
