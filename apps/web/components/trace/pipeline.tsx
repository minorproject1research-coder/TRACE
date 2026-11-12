'use client'

import { useEffect, useState } from 'react'
import { Check, X } from 'lucide-react'
import { elapsedLabel, factProgress, failedSubQuestionsNote, judgeFailuresNote, judgeWaitsNote, OVERLAP_TAG, overlapNote, STAGE_FAILED_NOTE, TIME_HINT, type FactProgress } from '@/lib/factcheck'
import Link from 'next/link'
import { num, REPORT_NOT_RUN, stageClockLabel, stageMeta, stageStateWord } from '@/lib/format'
import { statusView } from '@/lib/written-report'
import { stageStartedAt } from '@/lib/stream'
import { stageExtras } from '@/lib/telemetry'
import { StageExtrasView } from '@/components/trace/timeline-telemetry'
import type { StageId, StageState, WorkflowEvent } from '@/lib/trace-types'

const ORDER: StageId[] = ['planner', 'retrieval', 'summarizer', 'factcheck', 'report']

/** One-line facts about a stage, taken only from events we actually received. */
function facts(stage: StageId, events: WorkflowEvent[]): string[] {
  const done = events.find(e => e.stage === stage && e.event === 'stage_completed')
  if (stage === 'planner' && done) return [`${num(done.data, 'subQuestions') ?? '?'} sub-questions`, `${num(done.data, 'queries') ?? '?'} search queries`]
  if (stage === 'retrieval') {
    const papers = events.find(e => e.event === 'branch_completed' && e.data.branch === 'papers')
    const web = events.find(e => e.event === 'branch_completed' && e.data.branch === 'web')
    return [papers ? `${num(papers.data, 'papers') ?? '?'} papers kept` : null, web ? `${num(web.data, 'webSources') ?? '?'} web sources` : null].filter((x): x is string => !!x)
  }
  if (stage === 'summarizer' && done) return [`${num(done.data, 'digests') ?? '?'} sources digested`, `${num(done.data, 'sufficientSubQuestions') ?? '?'} of ${num(done.data, 'subQuestions') ?? '?'} sub-questions sufficient`]
  if (stage === 'report' && done) {
    const status = typeof done.data.status === 'string' ? statusView(done.data.status).label : null
    const part = (k: string, w: string) => (num(done.data, k) != null ? [`${num(done.data, k)} ${w}`] : [])
    return [...(status ? [status] : []), ...part('sections', 'sections'), ...part('sentences', 'sentences'), ...part('references', 'references'), ...part('warnings', 'warnings')]
  }
  if (stage === 'factcheck') {
    const r = factProgress(events)?.result
    if (!r) return []
    const part = (v: number | null, text: (v: number) => string) => (v != null ? [text(v)] : [])
    return [...part(r.claims, v => `${v} claims checked`), ...part(r.supported, v => `${v} supported`), ...part(r.partiallySupported, v => (v > 0 ? `${v} partly supported` : '')), ...part(r.unverified, v => `${v} not yet confirmed`),
      ...part(r.contradicted, v => `${v} contradicted`), ...part(r.contested, v => (v > 0 ? `${v} contested` : '')), ...part(r.disagreements, v => (v > 0 ? `${v} disagreements` : ''))].filter(Boolean)
  }
  return []
}

/** What a stage says about itself. A stage that was switched off for this run says so; the fact check also has a text of its own when it is not built. */
function detailOf(id: StageId, state: StageState): string {
  if (id === 'factcheck' && state === 'not_run') return 'Switched off for this run, so the evidence is not cross-checked.'
  if (id === 'factcheck' && state === 'not_built') return 'Not available on this server.'
  if (id === 'report' && state === 'not_run') return REPORT_NOT_RUN
  if (id === 'report' && state === 'not_built') return 'Not available on this server.'
  if (id === 'report' && state === 'failed') return 'The written report could not be produced. The evidence report is still available.'
  return stageMeta[id].detail
}

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [active])
  return now
}

/** The live line, the time it has taken so far, and the warnings of the fact-check stage. Nothing here for a stage that did not run. */
function FactcheckStatus({ state, progress }: { state: StageState; progress: FactProgress | null }) {
  const now = useNow(state === 'running')
  const judge = judgeFailuresNote(progress)
  const waits = judgeWaitsNote(progress)
  const partial = failedSubQuestionsNote(progress)
  const overlap = overlapNote(progress?.overlapped ?? 0, progress?.total ?? null)
  const took = state === 'running' ? elapsedLabel(progress?.startedAt ?? null, now) : null
  return (
    <>
      {state === 'running' && (
        <div className="live-line" role="status">
          <p><b>{progress?.line ?? 'Checking claims across sources'}</b></p>
          {took && <p className="elapsed">Running for {took}</p>}
          <p className="elapsed">{TIME_HINT}</p>
        </div>
      )}
      {state === 'failed' && <p className="stage-note bad" role="alert"><b>{STAGE_FAILED_NOTE}</b>{progress?.error ? <> <code>{progress.error}</code></> : null}</p>}
      {overlap && state !== 'failed' && <p className="stage-info-note" role="note"><span className="tag">{OVERLAP_TAG}</span> {overlap}</p>}
      {state === 'completed' && waits && <p className="stage-info-note" role="note">{waits}</p>}
      {state === 'completed' && judge && <p className="stage-note" role="note">{judge}</p>}
      {state === 'completed' && partial && <p className="stage-note" role="note">{partial}</p>}
    </>
  )
}

function when(stage: StageId, events: WorkflowEvent[], kind: 'stage_started' | 'stage_completed') {
  // The fact check began earlier than its stage_started: its first sub-questions were checked during Stage 3 and replayed when the stage started.
  if (kind === 'stage_started') return stageStartedAt(events, stage)
  return events.find(e => e.stage === stage && e.event === kind)?.timestamp ?? null
}

export function Pipeline({ stages, events, runId }: { stages: Record<StageId, StageState>; events: WorkflowEvent[]; runId?: string }) {
  const observed = ORDER.filter(s => stages[s] === 'completed').length
  const buildable = ORDER.filter(s => stages[s] !== 'not_built' && stages[s] !== 'not_run').length          // a stage that is switched off is not counted
  return (
    <div className="workflow" role="region" aria-label="Execution pipeline" tabIndex={0}>
      <div className="workflow-head"><span>EXECUTION PIPELINE</span><span>{observed} / {buildable} stages done</span></div>
      <ol className="stage-list" aria-label="Pipeline stages">
        {ORDER.map((id, i) => {
          const state = stages[id] ?? 'unknown'
          const meta = stageMeta[id]
          const f = facts(id, events)
          const t = state === 'completed' ? when(id, events, 'stage_completed') : state === 'running' ? when(id, events, 'stage_started') : null
          const cls = state
          const clock = stageClockLabel(state, t)                    // "started 16:29:10" while it runs, "finished 16:35:16" when it is done
          const fact = id === 'factcheck' ? factProgress(events) : null
          return (
            <li key={id} className={`stage ${cls}`} aria-current={state === 'running' ? 'step' : undefined}>
              <div className="stage-row">
                <div className="stage-marker" aria-hidden="true">{state === 'completed' ? <Check size={14} /> : state === 'running' ? <span className="spinner" /> : state === 'failed' ? <X size={14} /> : <span>{i + 1}</span>}</div>
                {i < ORDER.length - 1 && <div className="stage-connector" aria-hidden="true" />}
                <div className="stage-info">
                  <div className="stage-title"><b>{meta.name}</b><span>{stageStateWord(id, state)}</span></div>
                  <p>{detailOf(id, state)}</p>
                  {id === 'factcheck' && <FactcheckStatus state={state} progress={fact} />}
                  <StageExtrasView stage={id} x={stageExtras(events, id)} />
                  {id === 'report' && state === 'completed' && runId && <p className="stage-info-note"><Link href={`/research/${encodeURIComponent(runId)}/written-report`} className="link-button strong">Open the written report</Link></p>}
                  {state === 'running' && id !== 'factcheck' && meta.hint && <p className="hint">In progress, {meta.hint}. The Timeline tab shows its steps.</p>}
                  {(f.length > 0 || clock) && <div className="stage-detail">{f.map(x => <span key={x}>{x}</span>)}{clock && <code>{clock}</code>}</div>}
                </div>
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
