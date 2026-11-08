'use client'

import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Check, ChevronDown, CircleDashed, Clock, Globe, BookOpen, Brain, ListChecks, MinusCircle, ShieldCheck, X } from 'lucide-react'
import { ActivityLog } from '@/components/trace/activity-log'
import { StatusPill } from '@/components/trace/status-pill'
import { OVERLAP_TAG, STAGE_FAILED_NOTE, STAGE_SKIPPED_LABEL } from '@/lib/factcheck'
import { formatDuration } from '@/lib/format'
import { stageStartedAt, tokensLabel, tokenUsage, type TokenUsage } from '@/lib/stream'
import { buildTimeline, type FactRowView, type LaneView, type StepView, type TimelineModel } from '@/lib/timeline'
import type { PapersOverview, StageState, StreamStatus, WorkflowEvent } from '@/lib/trace-types'

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [active])
  return now
}

const ms = (iso: string | null) => (iso ? new Date(iso).getTime() : null)
const nowIso = (now: number) => new Date(now).toISOString()

const laneIcon = { papers: BookOpen, web: Globe, summarizer: Brain, factcheck: ShieldCheck } as const
const laneTone = { pending: 'neutral', running: 'blue', completed: 'mint', failed: 'coral' } as const
const laneText = { pending: 'Waiting', running: 'Running', completed: 'Done', failed: 'Failed' } as const

function StepIcon({ status }: { status: StepView['status'] }) {
  if (status === 'completed') return <span className="step-ico done" aria-hidden="true"><Check size={12} /></span>
  if (status === 'running') return <span className="step-ico live" aria-hidden="true"><span className="spinner" /></span>
  if (status === 'failed') return <span className="step-ico bad" aria-hidden="true"><X size={12} /></span>
  if (status === 'skipped' || status === 'unreported') return <span className="step-ico muted" aria-hidden="true"><MinusCircle size={12} /></span>
  return <span className="step-ico wait" aria-hidden="true"><CircleDashed size={12} /></span>
}

function FactRows({ rows }: { rows: FactRowView[] }) {
  return (
    <ol className="fact-rows" aria-label="Fact check, one row per sub-question">
      {rows.map(r => (
        <li key={r.index} className={`fact-row ${r.status}`}>
          <div className="fact-row-head"><b>{r.label}</b><span className="fact-row-state">{r.statusText}</span>{r.chips.map(c => <span className="tag" key={c}>{c}</span>)}</div>
          <ol className="fact-steps">
            {r.steps.map(st => <li key={st.id} className={`fact-step ${st.status}`}><StepIcon status={st.status} /><span>{st.label}</span><span className="sr-only">: {statusWord[st.status]}</span></li>)}
          </ol>
        </li>
      ))}
    </ol>
  )
}

const statusWord: Record<StepView['status'], string> = { pending: 'waiting', running: 'running', completed: 'done', failed: 'failed', skipped: 'skipped', unreported: 'not recorded' }

function Step({ step, now }: { step: StepView; now: number }) {
  const took = step.startedAt && step.endedAt ? formatDuration(step.startedAt, step.endedAt) : step.status === 'running' && step.startedAt ? formatDuration(step.startedAt, nowIso(now)) : null
  const pct = step.progress ? Math.round((step.progress.done / step.progress.total) * 100) : null
  return (
    <li className={`step ${step.status}`}>
      <StepIcon status={step.status} />
      <div className="step-main">
        <div className="step-line">
          <b>{step.label}</b>
          <span className="step-state"><span className="sr-only">{statusWord[step.status]}. </span>{took ?? (step.status === 'pending' ? '' : statusWord[step.status])}</span>
        </div>
        {step.chips.length > 0 && <div className="step-chips">{step.chips.map(c => <span className="tag" key={c}>{c}</span>)}</div>}
        {step.subs && step.subs.length > 0 && (
          <ul className="sq-chips" aria-label={`${step.label}: one chip per sub-question`}>
            {step.subs.map(sq => <li key={sq.key} className={`sq-chip ${sq.state} ${sq.tone}`}><b>{sq.label}</b><span>{sq.text}</span></li>)}
          </ul>
        )}
        {pct != null && <div className="step-bar" role="progressbar" aria-valuenow={step.progress!.done} aria-valuemin={0} aria-valuemax={step.progress!.total} aria-label={`${step.label}: ${step.progress!.done} of ${step.progress!.total}`}><span style={{ width: `${pct}%` }} /></div>}
        {step.message && step.status !== 'running' && step.approx && <p className="meta">{step.message}</p>}
        {step.message && step.status === 'running' && <p className="meta">{step.message}</p>}
      </div>
    </li>
  )
}

function Lane({ lane, now, open }: { lane: LaneView; now: number; open?: boolean }) {
  const Icon = laneIcon[lane.id]
  const end = lane.endedAt ?? (lane.status === 'running' ? nowIso(now) : null)
  const took = lane.startedAt && end ? formatDuration(lane.startedAt, end) : null
  const doneSteps = lane.steps.filter(s => s.status === 'completed' || s.status === 'skipped' || s.status === 'unreported').length
  return (
    <section className={`lane ${lane.status}`} aria-label={lane.title}>
      <div className="lane-head">
        <span className={`source-icon ${lane.id === 'web' ? 'web' : 'paper'}`} aria-hidden="true"><Icon size={15} /></span>
        <div className="lane-title"><h3>{lane.title}</h3><p className="meta">{lane.subtitle}</p></div>
        <StatusPill tone={laneTone[lane.status]}>{laneText[lane.status]}{took ? ` · ${took}` : ''}</StatusPill>
      </div>
      {lane.summary && <p className="lane-summary">{lane.summary}</p>}
      {lane.note && <p className="stage-info-note" role="note"><span className="tag">{OVERLAP_TAG}</span> {lane.note}</p>}
      {lane.rows && lane.rows.length > 0 && <FactRows rows={lane.rows} />}
      {lane.steps.length > 0 && (
        <details className="lane-steps" open={open ?? lane.status === 'running'}>
          <summary><ListChecks size={14} aria-hidden="true" /> Steps <span className="count">{doneSteps}/{lane.steps.length}</span><ChevronDown size={14} className="chev" aria-hidden="true" /></summary>
          <ol className="step-list">{lane.steps.map(s => <Step key={s.id} step={s} now={now} />)}</ol>
        </details>
      )}
    </section>
  )
}

const GANTT_LABEL = { papers: 'Papers', web: 'Web', summarizer: 'Evidence', factcheck: 'Fact check' } as const

/** Lanes on one time axis: the overlap is the point (the two retrieval branches; Stage 3 and Stage 4). */
function Gantt({ lanes, from, to, intro }: { lanes: LaneView[]; from: string | null; to: string | null; intro: string }) {
  const a = ms(from)
  const b = ms(to)
  if (a == null || b == null || b <= a) return null
  const span = b - a
  return (
    <div className="gantt" role="img" aria-label={`${intro} ${lanes.map(l => `${l.title}: ${l.startedAt && l.endedAt ? formatDuration(l.startedAt, l.endedAt) : l.status}`).join('. ')}`}>
      {lanes.map(l => {
        const s = ms(l.startedAt) ?? a
        const e = ms(l.endedAt) ?? (l.status === 'running' ? b : s)
        const left = Math.max(0, Math.min(100, ((s - a) / span) * 100))
        const width = Math.max(1.5, Math.min(100 - left, ((e - s) / span) * 100))
        return (
          <div className="gantt-row" key={l.id}>
            <span className="gantt-label">{GANTT_LABEL[l.id]}</span>
            <div className="gantt-track"><span className={`gantt-bar ${l.id} ${l.status}`} style={{ left: `${left}%`, width: `${width}%` }} /></div>
          </div>
        )
      })}
      <div className="gantt-axis"><span>start</span><span>{formatDuration(from, to) ?? ''}</span></div>
    </div>
  )
}

/** What the finished run asked of the model, by purpose. Labels for the purposes this page knows; an unknown purpose is shown as its own key. */
function TokenUsageTile({ usage }: { usage: TokenUsage }) {
  return (
    <section className="lane token-usage" aria-label="Language-model usage">
      <div className="lane-head">
        <span className="source-icon paper" aria-hidden="true"><Brain size={15} /></span>
        <div className="lane-title"><h3>Language-model usage</h3><p className="meta">Groq tokens this run used, by purpose</p></div>
        {usage.total != null && <StatusPill tone="neutral">{tokensLabel(usage.total)} tokens{usage.calls != null ? ` · ${usage.calls} calls` : ''}</StatusPill>}
      </div>
      {usage.rows.length > 0 && (
        <ul className="usage-list">
          {usage.rows.map(r => (
            <li key={r.key}>
              <span className="usage-name" title={r.label === r.key ? undefined : r.key}>{r.label}</span>
              <span className="usage-bar" aria-hidden="true"><i style={{ width: `${Math.max(2, Math.round(r.share * 100))}%` }} /></span>
              <span className="usage-n">{tokensLabel(r.tokens)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function Timeline(props: { events: WorkflowEvent[]; overview: PapersOverview | null; streamStatus: StreamStatus; streamDetail?: string; running: boolean; factcheckState?: StageState }) {
  const { events, overview, streamStatus, streamDetail, running, factcheckState } = props
  const model: TimelineModel = useMemo(() => buildTimeline(events, overview), [events, overview])
  const now = useNow(running)
  const [papers, web] = model.retrieval.lanes
  const fact = model.factcheck
  const anyRunning = papers.status === 'running' || web.status === 'running' || model.summarizer.status === 'running' || model.planner.status === 'running' || fact?.status === 'running'
  const axisEnd = model.retrieval.endedAt ?? (papers.status === 'running' || web.status === 'running' ? nowIso(now) : [papers.endedAt, web.endedAt].filter(Boolean).sort().pop() ?? null)
  // Stage 3 and Stage 4 overlap when the fact check's real start (its earliest step) is before the evidence stage ended
  const overlap = useMemo(() => {
    const f = model.factcheck
    const a = ms(f?.startedAt ?? null), sumEnd = ms(model.summarizer.endedAt), sumStart = ms(model.summarizer.startedAt)
    if (!f || a == null || sumEnd == null || a >= sumEnd) return null
    const ends = [sumEnd, ms(f.endedAt) ?? (f.status === 'running' ? now : a)]
    return { from: new Date(Math.min(a, sumStart ?? a)).toISOString(), to: new Date(Math.max(...ends)).toISOString() }
  }, [model, now])
  const usage = useMemo(() => tokenUsage(events), [events])
  const plannerTook = model.planner.startedAt && model.planner.endedAt ? formatDuration(model.planner.startedAt, model.planner.endedAt) : null
  const took = useMemo(() => {
    const m = new Map<number, string>()
    for (const e of events) {
      if (e.event !== 'stage_completed' || !e.stage) continue
      // the fact check began before its stage_started (its first sub-questions ran during Stage 3): its time runs from its earliest step
      const start = stageStartedAt(events, e.stage)
      const d = start ? formatDuration(start, e.timestamp) : null
      if (d) m.set(e.seq, d)
    }
    return m
  }, [events])

  return (
    <div className="timeline">
      <h2 className="sr-only">Timeline</h2>
      {model.source === 'reconstructed' && (
        <div className="callout-box lav" role="note"><Clock size={18} aria-hidden="true" />
          <div><b>Reconstructed from the database</b><p>This run finished before step-by-step progress was recorded. Each step shows when its result was saved, so durations are approximate and some steps (search, judge calls) were not recorded. New runs show every step live.</p></div></div>
      )}
      {model.source === 'none' && !running && <p className="meta">No step-by-step data is available for this run.</p>}

      <section className={`tl-planner ${model.planner.status}`} aria-label="Planner">
        <div className="lane-head">
          <span className="source-icon paper" aria-hidden="true"><ListChecks size={15} /></span>
          <div className="lane-title"><h3>Planner</h3><p className="meta">Breaks the question into sub-questions and search queries</p></div>
          <StatusPill tone={laneTone[model.planner.status]}>{laneText[model.planner.status]}{plannerTook ? ` · ${plannerTook}` : ''}</StatusPill>
        </div>
        {(model.planner.subQuestions != null || model.planner.topics.length > 0) && (
          <details className="lane-steps">
            <summary><ListChecks size={14} aria-hidden="true" /> {model.planner.subQuestions ?? model.planner.topics.length} sub-questions{model.planner.queries != null ? ` · ${model.planner.queries} queries` : ''}<ChevronDown size={14} className="chev" aria-hidden="true" /></summary>
            {model.planner.anchor && <p className="meta" style={{ marginTop: 8 }}>Field of the question: <b>{model.planner.anchor}</b></p>}
            <ol className="plain-list numbered">{model.planner.topics.map(t => <li key={t}>{t}</li>)}</ol>
          </details>
        )}
      </section>

      <div className="tl-parallel" role="group" aria-label="Retrieval: two branches running at the same time">
        <div className="tl-parallel-head"><b>Retrieval</b><span className="tag">runs in parallel</span><span className="meta">{model.retrieval.startedAt && model.retrieval.endedAt ? `${formatDuration(model.retrieval.startedAt, model.retrieval.endedAt)} in total, both branches together` : 'both branches start together'}</span></div>
        <Gantt lanes={[papers, web]} from={model.retrieval.startedAt ?? papers.startedAt ?? web.startedAt} to={axisEnd} intro="Paper retrieval and web search ran at the same time." />
        <div className="lanes"><Lane lane={papers} now={now} /><Lane lane={web} now={now} /></div>
      </div>

      {overlap && (
        <div className="tl-parallel" role="group" aria-label="Evidence stage and fact check: two stages that overlapped">
          <div className="tl-parallel-head"><b>Evidence stage and fact check</b><span className="tag">{OVERLAP_TAG}</span><span className="meta">the fact check started on each sub-question as soon as its evidence was saved</span></div>
          <Gantt lanes={[model.summarizer, fact!]} from={overlap.from} to={overlap.to} intro="The evidence stage and the fact check overlapped in time." />
        </div>
      )}
      <div className="tl-after"><Lane lane={model.summarizer} now={now} />{fact && <Lane lane={fact} now={now} />}</div>
      {fact?.status === 'failed' && <div className="callout-box amber" role="note"><AlertTriangle size={18} aria-hidden="true" /><div><b>{STAGE_FAILED_NOTE}</b><p>The run itself finished. Only the cross-check is missing.</p></div></div>}

      {fact
        ? <section className="tl-notbuilt" aria-label="Not built yet"><span className="tag">not built yet</span> The written report (Stage 5) is not part of the pipeline.</section>
        : factcheckState === 'not_run'
          ? <section className="tl-notbuilt" aria-label="Not run or not built"><span className="tag">{STAGE_SKIPPED_LABEL}</span> Fact check (Stage 4) was switched off for this run. The written report (Stage 5) is not part of the pipeline.</section>
          : <section className="tl-notbuilt" aria-label="Not built yet"><span className="tag">not built yet</span> Fact check (Stage 4) and the written report (Stage 5) are not part of the pipeline.</section>}

      {model.planner.status === 'failed' || papers.status === 'failed' || web.status === 'failed' || model.summarizer.status === 'failed'
        ? <div className="callout-box coral" role="note"><AlertTriangle size={18} aria-hidden="true" /><div><b>The run stopped</b><p>The step that was running when it failed is marked above. The error is shown at the top of the page.</p></div></div> : null}

      {usage && <TokenUsageTile usage={usage} />}

      <details className="lane-steps event-log">
        <summary><Clock size={14} aria-hidden="true" /> All events <span className="count">{events.length}</span>{anyRunning ? <span className="tag">live</span> : null}<ChevronDown size={14} className="chev" aria-hidden="true" /></summary>
        <ActivityLog events={events} status={streamStatus} detail={streamDetail} running={running} took={took} />
      </details>
    </div>
  )
}
