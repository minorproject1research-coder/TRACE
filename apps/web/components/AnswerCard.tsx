'use client'

import { Fragment } from 'react'
import { FileText, Info, ShieldAlert } from 'lucide-react'
import { Fold } from '@/components/Fold'
import { RefAnchor, Sentence, useReportActions } from '@/components/ReportParts'
import { ANSWER_TITLE, type AnswerView, type ReportModel, type SentenceView } from '@/lib/written-report'

// The Answer of the written report (overview.answer), the main block of the page: the headline (the verdict), one block per part of the question, how well it rests on the
// evidence (the server's own line and its numbers), the key figures, and what is still open. It is never collapsed. It must look important, not more certain than it is:
// a partly supported or one-source sentence keeps its dashed border and its label here too, nothing says "reliable" or "strong", and the server's line is shown as written.

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

function StrengthStrip({ a }: { a: NonNullable<AnswerView['strength']> }) {
  return (
    <div className="wr-strength" role="group" aria-label="How well the answer rests on the evidence">
      <h3>How well it rests on the evidence</h3>
      {a.line && <p className="wr-strength-line">{a.line}</p>}
      <dl className="wr-nums">
        {a.documents != null && <div><dd>{a.documents}</dd><dt>documents behind the answer{a.fullTextDocuments != null ? ` (${a.fullTextDocuments} read in full text)` : ''}</dt></div>}
        {a.partsCovered != null && a.sections != null && <div><dd>{a.partsCovered} <span>of {a.sections}</span></dd><dt>parts covered</dt></div>}
        {a.tiers.map(t => <div key={t.key}><dd>{t.value}</dd><dt><i className={`wr-sw ${t.key}`} aria-hidden="true" />{t.label}</dt></div>)}
      </dl>
      {a.total > 0 && (
        <div className="wr-tierbar" role="img" aria-label={`The statements of the answer by strength: ${a.barLabel}`}>
          {a.tiers.filter(t => t.value > 0).map(t => <span key={t.key} className={t.key} style={{ width: `${t.pct}%` }} />)}
        </div>
      )}
    </div>
  )
}

export function AnswerCard({ m }: { m: ReportModel }) {
  const act = useReportActions()
  const a = m.answer
  const empty = m.summary.length === 0 && !a
  return (
    <>
      <section className="wr-answer" aria-labelledby="wr-overview-h">
        <h2 id="wr-overview-h"><FileText size={18} aria-hidden="true" /> {ANSWER_TITLE}</h2>
        {!a && m.summary.map((v: SentenceView, i) => <Sentence key={i} v={v} id={`wr-sum-${i}`} />)}
        {empty && <p className="meta">{m.rawStatus === 'insufficient_evidence' ? 'The evidence is insufficient for a written answer.' : 'There is no written answer.'}</p>}
        {a && (
          <>
            {a.headline && <div className="wr-headline"><Sentence v={a.headline.view} id={a.headline.id} /></div>}
            {a.parts.length > 0 && (
              <div className="wr-parts">
                {a.parts.map(p => (
                  <div className="wr-part" key={`${p.index}-${p.sectionId ?? ''}`}>
                    {p.title && <h3 className="wr-part-title">{p.title}</h3>}
                    {p.sentence ? <Sentence v={p.sentence} id={p.id} /> : <p className="meta">The statement above comes from this part.</p>}
                    {p.supporting.length > 0 && (
                      <Fold small title="More on this part" meta={plural(p.supporting.length, 'more finding', 'more findings')} className="wr-more">
                        {p.supporting.map((v, i) => <Sentence key={i} v={v} />)}
                      </Fold>
                    )}
                  </div>
                ))}
              </div>
            )}
            {a.others.map(o => <Sentence key={o.index} v={o.view} id={o.id} />)}
            {a.notes.map(o => <Sentence key={o.index} v={o.view} />)}
            {!a.headline && a.parts.length === 0 && a.others.length === 0 && <p className="meta">There is no written answer.</p>}

            {a.strength && <StrengthStrip a={a.strength} />}

            {a.figures.length > 0 && (
              <div className="wr-keyfigs">
                <h3>Key figures</h3>
                <ul>
                  {a.figures.map((f, i) => (
                    <li key={`${f.value}-${i}`}>
                      {f.anchor
                        ? <a className="wr-fig" href={`#${f.anchor}`} aria-label={`Figure ${f.value}: go to its sentence`}>{f.value}</a>
                        : <span className="wr-fig">{f.value}</span>}
                      {f.tierLabel && <span className={`wr-tier ${f.tierKind ?? 'other'}`}> ({f.tierLabel})</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {(a.openQuestions.length > 0 || a.disputes.count > 0) && (
              <div className="wr-open">
                {a.openQuestions.length > 0 && (
                  <div>
                    <h3><Info size={15} aria-hidden="true" /> The evidence does not settle</h3>
                    <ul>{a.openQuestions.map((q, i) => <li key={`${i}:${q}`}>{q}</li>)}</ul>
                  </div>
                )}
                {a.disputes.count > 0 && (
                  <div className="wr-disputes">
                    <h3><ShieldAlert size={15} aria-hidden="true" /> {plural(a.disputes.count, 'disagreement', 'disagreements')} between sources</h3>
                    {a.disputes.items.length > 0 && (
                      <ul>
                        {a.disputes.items.map((d, i) => (
                          <li key={i}>
                            {d.title && <b>{d.title}</b>}
                            <span className="wr-dispute-claims">{d.claimA}<span className="wr-vs"> / </span>{d.claimB}</span>
                            {d.refs.length > 0 && <span className="meta"> {d.refs.map((r, j) => <Fragment key={r.n}>{j > 0 && ' '}<RefAnchor l={r} /></Fragment>)}</span>}
                            {d.anchor && <> <a href={`#${d.anchor}`} onClick={e => { e.preventDefault(); act.openSection(d.sectionId, d.anchor ?? undefined) }}>See both sides in the section</a></>}
                          </li>
                        ))}
                      </ul>
                    )}
                    <p className="meta">Both sides are shown in their section. This report does not decide which of them is right.</p>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </section>
      {m.counts.length > 0 && <dl className="wr-counts" aria-label="Overview of the evidence">{m.counts.map(c => <div key={c.key}><dd>{c.value}</dd><dt>{c.label}</dt></div>)}</dl>}
    </>
  )
}
