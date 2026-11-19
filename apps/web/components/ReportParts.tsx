'use client'

import Link from 'next/link'
import { createContext, Fragment, useContext } from 'react'
import { ShieldAlert } from 'lucide-react'
import { Fold } from '@/components/Fold'
import type { DisagreementView, EvidenceView, MarkerView, SentenceView, SideView } from '@/lib/written-report'

// The pieces shared by the report page and the Answer card. The rules (lib/written-report.ts): every sentence shows its markers from `refs` before the final full stop;
// "partly supported" and "one source, not confirmed" are always written out wherever a sentence is shown (also inside the Evidence bar); disagreements show both sides.

/** What the page lets a part do: open the References bar and go to a reference, open a section's bar and go to a block in it, remember that the paper page was reached from here. */
export type ReportActions = { openReference: (n: number) => void; openSection: (sectionId: string, targetId?: string) => void; rememberBack: () => void }
const noop: ReportActions = { openReference: () => {}, openSection: () => {}, rememberBack: () => {} }
export const ReportActionsContext = createContext<ReportActions>(noop)
export const useReportActions = (): ReportActions => useContext(ReportActionsContext)

/** The marker "3": the parsed paper at the quote (same tab), the web page of a web source (new tab), or the reference in the list (the anchor, which opens the References bar). */
export function Marker({ l }: { l: MarkerView }) {
  const act = useReportActions()
  if (!l.found || l.kind === 'plain') return <span title="This reference is not in the list">{l.n}</span>
  const tip = l.tooltip ?? undefined
  if (l.kind === 'paper') return <Link href={l.href} prefetch={false} title={tip} aria-label={l.label} onClick={act.rememberBack}>{l.n}</Link>
  if (l.kind === 'web') return <a href={l.href} target="_blank" rel="noopener noreferrer" title={tip} aria-label={l.label}>{l.n}</a>
  return <a href={l.href} title={tip} aria-label={l.label} onClick={e => { e.preventDefault(); act.openReference(l.n) }}>{l.n}</a>
}

export function Markers({ v }: { v: SentenceView }) {
  if (v.links.length === 0) return null
  return (
    <span className="wr-markers">
      {' ['}
      {v.links.map((l, i) => <Fragment key={`${l.n}-${i}`}>{i > 0 && ', '}<Marker l={l} /></Fragment>)}
      {']'}
    </span>
  )
}

/** "[4]" that goes to a reference in the list (used by the disagreements and the disputes of the Answer). */
export function RefAnchor({ l }: { l: MarkerView }) {
  const act = useReportActions()
  if (!l.found) return <>[{l.n}]</>
  return <a href={l.href} title={l.title ?? undefined} aria-label={l.label} onClick={e => { e.preventDefault(); act.openReference(l.n) }}>[{l.n}]</a>
}

function EvidenceRef({ e }: { e: EvidenceView }) {
  const act = useReportActions()
  return (
    <div className="wr-ev-ref" role="group" aria-label={`Reference ${e.ref}${e.title ? `: ${e.title}` : ''}`}>
      <p className="wr-ev-head">
        <b>[{e.ref}]</b> {e.found ? e.title ?? `Reference ${e.ref}` : 'This reference is not in the list'}
        {e.hint && <span className="tag warn" title="Only part of this source was read"> {e.hint}</span>}
      </p>
      {e.quotes.map((q, i) => (
        <figure className="wr-quote" key={i}>
          <blockquote>{q.text}</blockquote>
          <figcaption>
            <span className={`tag wr-rel ${q.relation}`}>{q.relationLabel}</span>
            {q.hint && <span className="tag warn" title="Only part of this source was read">{q.hint}</span>}
            {q.open && (q.open.external
              ? <a href={q.open.href} target="_blank" rel="noopener noreferrer">{q.open.label}<span className="sr-only"> (opens in a new tab)</span></a>
              : <Link href={q.open.href} prefetch={false} onClick={act.rememberBack}>{q.open.label}</Link>)}
          </figcaption>
        </figure>
      ))}
    </div>
  )
}

/** The bar under a sentence: "Evidence (n)", collapsed. Opened: the verbatim quotes per reference. A sentence that is not a confirmed one keeps its label inside the bar too. */
function EvidenceBar({ v }: { v: SentenceView }) {
  return (
    <Fold small title={`Evidence (${v.evidenceCount})`} className="wr-evidence">
      {v.tier.label && <p className="meta wr-ev-for">Evidence for the sentence above <span className={`wr-tier ${v.tier.kind}`} title={v.tier.hint}>({v.tier.label})</span></p>}
      {v.evidence.map(e => <EvidenceRef key={e.ref} e={e} />)}
    </Fold>
  )
}

/** One sentence: the text, the markers, the final stop, the label of its tier (always written out for a partly supported and a one-source sentence), and the Evidence bar when it has quotes.
 *  A note (tier "note", a template sentence such as the open questions of the answer) is a plain muted line: no chip, no "plain wording" hint, no markers, no bar. */
export function Sentence({ v, id, className = '' }: { v: SentenceView; id?: string; className?: string }) {
  return (
    <div className={`wr-sent ${className}`.trim()} id={id}>
      <p className={`wr-sentence ${v.tier.kind === 'note' ? 'wr-plain-note' : v.tier.kind}`}>
        {v.body}<Markers v={v} />{v.stop}
        {v.tier.label && <> <span className={`wr-tier ${v.tier.kind}`} title={v.tier.hint}>({v.tier.label})</span></>}
        {v.plainWording && <small className="wr-plain" title="Written from the claim’s own wording by a standard template, not by the model.">plain wording</small>}
      </p>
      {v.evidenceCount > 0 && <EvidenceBar v={v} />}
    </div>
  )
}

function Side({ label, s }: { label: string; s: SideView }) {
  return (
    <div className="wr-side" role="group" aria-label={label}>
      <p className="wr-side-title">{label}{s.title ? `: ${s.title}` : ''}</p>
      {s.quote ? <blockquote>{s.quote}</blockquote> : <p className="meta">No quote was stored for this side.</p>}
      {s.marker && <p className="meta">Reference <RefAnchor l={s.marker} /></p>}
    </div>
  )
}

/** "Sources disagree": both claims, both quotes, each with its reference. It never says that one side is false. Never collapsed. */
export function Disagreement({ d, index, id }: { d: DisagreementView; index: number; id?: string }) {
  return (
    <div className="wr-disagree" id={id} tabIndex={-1} role="group" aria-label={`Sources disagree (${index + 1})`}>
      <h4><ShieldAlert size={15} aria-hidden="true" /> Sources disagree</h4>
      {(d.claimA || d.claimB) && <ul className="wr-claims">{d.claimA && <li>{d.claimA}</li>}{d.claimB && <li>{d.claimB}</li>}</ul>}
      <div className="wr-sides"><Side label="One source says" s={d.sideA} /><Side label="Another source says" s={d.sideB} /></div>
      {d.note && <p className="meta">{d.note}</p>}
    </div>
  )
}
