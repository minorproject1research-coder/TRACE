'use client'

import { AlertTriangle, ChevronDown, FileText, Info, ListChecks } from 'lucide-react'
import { StatusPill } from '@/components/trace/status-pill'
import { msLabel } from '@/lib/swimlanes'
import { FACT_GROQ_FOOTNOTE, GROQ_TOOLTIP, noteView, percentLabel, slowerHint, TYPICAL_NOTE, type StageExtras, type TimeShare } from '@/lib/telemetry'
import type { Note, PaperParseModel } from '@/lib/stream'

// The measurements of the Timeline (T4, T7, T8, T9, T10). The numbers come from lib/telemetry.ts and lib/stream.ts.

const SEG_CLASS = { planner: 'planner', search: 'search', parsing: 'parsing', evidence: 'evidence', stage4After: 'stage4' } as const

/** T4: the whole run as one stacked bar. Stage 4 work that ran during the evidence stage is hatched inside the evidence segment. */
export function TimeShareBar({ t }: { t: TimeShare }) {
  const summary = t.segs.map(s => `${s.label} ${percentLabel(s.share)}`).join(', ')
  return (
    <section className="lane tl-share" aria-label="Where the time went">
      <div className="lane-head"><div className="lane-title"><h3>Where the time went</h3><p className="meta">{msLabel(t.totalMs)} in all, split by phase{t.segs.some(s => s.running) ? ' (so far)' : ''}.</p></div></div>
      <div className="share-bar" role="img" aria-label={`${summary}${t.overlap ? `. The fact check overlapped the evidence stage for ${percentLabel(t.overlap.shareOfRun)} of the run` : ''}`}>
        {t.segs.map(s => (
          <span key={s.id} className={`share-seg ${SEG_CLASS[s.id]} ${s.running ? 'open' : ''}`} style={{ width: `${s.share * 100}%` }} title={`${s.label}: ${msLabel(s.ms)} (${percentLabel(s.share)})`}>
            {s.id === 'evidence' && t.overlap && <i className="share-overlap" style={{ width: `${t.overlap.shareOfEvidence * 100}%` }} />}
            {s.share >= 0.08 && <em>{percentLabel(s.share)}</em>}
          </span>
        ))}
      </div>
      <ul className="share-legend">
        {t.segs.map(s => <li key={s.id}><i className={`share-dot ${SEG_CLASS[s.id]}`} aria-hidden="true" />{s.label} <b>{percentLabel(s.share)}</b> <span className="meta">{msLabel(s.ms)}</span></li>)}
        {t.overlap && <li><i className="share-dot overlap" aria-hidden="true" />Fact check during the evidence stage <b>{percentLabel(t.overlap.shareOfRun)}</b> of the run <span className="meta">{msLabel(t.overlap.ms)}, hatched</span></li>}
      </ul>
      <ul className="share-hints">
        {t.phases.map(p => { const h = slowerHint(p); return <li key={p.id} className={h ? 'slow' : ''}><b>{p.label}</b> {msLabel(p.ms)}{p.running ? ' so far' : ''}{h ? <> · <span>{h}</span></> : <span className="meta"> · typical {p.typical}, {TYPICAL_NOTE}</span>}</li> })}
      </ul>
    </section>
  )
}

const OUTCOME: Record<string, { label: string; tone: 'mint' | 'amber' | 'coral' | 'neutral' }> = {
  parsed: { label: 'parsed', tone: 'mint' }, abstract_only: { label: 'abstract only', tone: 'amber' }, failed: { label: 'failed', tone: 'neutral' },
}

/** T7: one line per paper that reached an end of its parsing, with the counts. */
export function PapersParsing({ m, note }: { m: PaperParseModel; note: string | null }) {
  if (m.papers.length === 0) return null
  return (
    <details className="lane-steps papers-parse">
      <summary><FileText size={14} aria-hidden="true" /> Papers <span className="count">{m.done}</span>{note ? <span className="tag">{note}</span> : null}<ChevronDown size={14} className="chev" aria-hidden="true" /></summary>
      <div className="step-chips">
        <span className="tag good">{m.parsed} parsed</span><span className="tag">{m.abstractOnly} abstract only</span><span className="tag">{m.failed} failed</span>
        {m.other > 0 && <span className="tag">{m.other} other</span>}
        {m.reasons.map(([r, n]) => <span className="tag" key={r} title="Why a paper stayed without its full text">{r}: {n}</span>)}
        {m.routes.map(([r, n]) => <span className="tag" key={`route-${r}`} title="Where the paper's text came from">{r}: {n}</span>)}
      </div>
      <ol className="paper-parse-list">
        {m.papers.map((p, i) => {
          const o = OUTCOME[p.outcome] ?? { label: p.outcome.replace(/_/g, ' '), tone: 'neutral' as const }
          return (
            <li key={`${p.paperId ?? 'seq'}-${i}`}>
              <span className="pp-title">{p.title ?? p.paperId ?? 'Untitled paper'}</span>
              <span className="source-tags">
                <StatusPill tone={o.tone}>{o.label}</StatusPill>
                {p.route && <span className="tag">{p.route}</span>}
                {p.chars != null && <span className="tag">{p.chars.toLocaleString()} characters</span>}
                {p.reason && <span className="tag warn">{p.reason}</span>}
              </span>
            </li>
          )
        })}
      </ol>
    </details>
  )
}

/** T10: the notes of the run. Warnings are amber and calm; a code this page does not know shows its own message. */
export function NotesSection({ notes }: { notes: Note[] }) {
  if (notes.length === 0) return null
  return (
    <section className="lane tl-notes" aria-label="Notes">
      <div className="lane-head"><div className="lane-title"><h3>Notes <span className="count">{notes.length}</span></h3><p className="meta">Things the pipeline wants you to know about this run.</p></div></div>
      <ul className="notes-list">
        {notes.map(n => {
          const v = noteView(n)
          return (
            <li key={`${n.code}#${n.subQuestionIndex ?? 0}`} className={`note ${n.level}`}>
              {n.level === 'warn' ? <AlertTriangle size={15} aria-hidden="true" /> : <Info size={15} aria-hidden="true" />}
              <div><b>{v.title}</b>{v.detail && <p className="meta">{v.detail}</p>}</div>
              <span className="tag">{n.stage ?? 'run'}</span>
              <span className="sr-only">{n.level === 'warn' ? 'Warning' : 'Information'}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/** T8, T9 and T10 on a stage card: cache chips, the Groq line of the stage, and how many notes it has. */
export function StageExtrasView({ x, stage }: { x: StageExtras; stage: string }) {
  if (x.chips.length === 0 && !x.groq && x.notes.count === 0) return null
  return (
    <div className="stage-extras">
      {x.chips.length > 0 && <div className="stage-chips">{x.chips.map(c => <span className="tag" key={c}>{c}</span>)}</div>}
      {x.groq && <p className="stage-groq" title={GROQ_TOOLTIP}>{x.groq}<span className="sr-only">. {GROQ_TOOLTIP}</span>{stage === 'factcheck' && <span className="meta"> · {FACT_GROQ_FOOTNOTE}</span>}</p>}
      {x.notes.count > 0 && <span className={`tag ${x.notes.warn > 0 ? 'warn' : ''}`}><ListChecks size={11} aria-hidden="true" /> {x.notes.count} {x.notes.count === 1 ? 'note' : 'notes'}{x.notes.warn > 0 ? `, ${x.notes.warn} to look at` : ''}</span>}
    </div>
  )
}
