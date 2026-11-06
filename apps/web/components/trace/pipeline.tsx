'use client'

import { Check, X } from 'lucide-react'
import { formatClock, num, stageMeta, stageStateLabel } from '@/lib/format'
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
  return []
}

function when(stage: StageId, events: WorkflowEvent[], kind: 'stage_started' | 'stage_completed') {
  return events.find(e => e.stage === stage && e.event === kind)?.timestamp ?? null
}

export function Pipeline({ stages, events }: { stages: Record<StageId, StageState>; events: WorkflowEvent[] }) {
  const observed = ORDER.filter(s => stages[s] === 'completed').length
  const buildable = ORDER.filter(s => stages[s] !== 'not_built').length
  return (
    <div className="workflow">
      <div className="workflow-head"><span>EXECUTION PIPELINE</span><span>{observed} / {buildable} stages done</span></div>
      <ol className="stage-list" aria-label="Pipeline stages">
        {ORDER.map((id, i) => {
          const state = stages[id] ?? 'unknown'
          const meta = stageMeta[id]
          const f = facts(id, events)
          const t = state === 'completed' ? when(id, events, 'stage_completed') : state === 'running' ? when(id, events, 'stage_started') : null
          const cls = state === 'not_built' ? 'not_built' : state
          return (
            <li key={id} className={`stage ${cls}`} aria-current={state === 'running' ? 'step' : undefined}>
              <div className="stage-row">
                <div className="stage-marker" aria-hidden="true">{state === 'completed' ? <Check size={14} /> : state === 'running' ? <span className="spinner" /> : state === 'failed' ? <X size={14} /> : <span>{i + 1}</span>}</div>
                {i < ORDER.length - 1 && <div className="stage-connector" aria-hidden="true" />}
                <div className="stage-info">
                  <div className="stage-title"><b>{meta.name}</b><span>{stageStateLabel[state]}</span></div>
                  <p>{meta.detail}</p>
                  {state === 'running' && meta.hint && <p className="hint">In progress, {meta.hint}. No progress is reported inside a stage.</p>}
                  {(f.length > 0 || t) && <div className="stage-detail">{f.map(x => <span key={x}>{x}</span>)}{t && <code>{formatClock(t)}</code>}</div>}
                </div>
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
