import { AlertTriangle, ChevronDown, GitCompare, Quote, ShieldCheck } from 'lucide-react'
import { evidenceLevelLabel } from '@/lib/format'
import {
  againstSources, checkedByJudge, CONTESTED_HINT, countsOf, DISAGREEMENT_TOOLTIP, EMPTY_STATE, factSummaryLine, JUDGE_BADGE, JUDGE_BADGE_TOOLTIP, labelView,
  mustShowDisagreement, NEAR_HEADING, NEAR_HINT, NOT_CROSS_CHECKED_NOTE, PANEL_INTRO, PANEL_TITLE, sourcesLine, splitEvidence, STRENGTH_TOOLTIP, strengthOf,
} from '@/lib/factcheck'
import type { FactCheck, FactClaim, FactCounts, FactDisagreement, FactEvidence, SubQuestionReport } from '@/lib/trace-types'
import { StatusPill } from './status-pill'

/** The numbers of a fact check as chips: Supported (green), Partly supported (blue), Unverified (grey), Contradicted (red) and, only when there are some, Contested (a flag). */
export function FactCountChips({ counts }: { counts: FactCounts }) {
  return (
    <span className="fc-chips" role="group" aria-label={factSummaryLine(counts)}>
      <span title={labelView('supported').hint}><StatusPill tone="mint">Supported {counts.supported}</StatusPill></span>
      <span title={labelView('partially_supported').hint}><StatusPill tone="blue">Partly supported {counts.partially_supported ?? 0}</StatusPill></span>
      <span title={labelView('unverified').hint}><StatusPill tone="neutral">Unverified {counts.unverified}</StatusPill></span>
      <span title={labelView('contradicted').hint}><StatusPill tone="coral">Contradicted {counts.contradicted}</StatusPill></span>
      {counts.contested > 0 && <span className="tag gap" title={CONTESTED_HINT}>contested {counts.contested}</span>}
    </span>
  )
}

/** The report-level summary row. Hidden (null) when Stage 4 did not run. */
export function FactTotals({ totals, className = '' }: { totals: FactCounts; className?: string }) {
  return (
    <section className={`metrics report-metrics fc-totals ${className}`} aria-label="Cross-check totals">
      <div title={labelView('supported').hint}><strong>{totals.supported}</strong><span>claims supported by 2+ sources</span></div>
      <div title={labelView('partially_supported').hint}><strong>{totals.partially_supported ?? 0}</strong><span>close variant in another source</span></div>
      <div title={labelView('unverified').hint}><strong>{totals.unverified}</strong><span>not yet confirmed by a second source</span></div>
      <div title={DISAGREEMENT_TOOLTIP}><strong>{totals.contradicted}</strong><span>contradicted by another source</span></div>
      <div title={CONTESTED_HINT}><strong>{totals.contested}</strong><span>supported but contested</span></div>
    </section>
  )
}

/** A bar and a word, never a percent: the number behind it is a ranking, not a probability. */
function Strength({ confidence }: { confidence: number | null }) {
  const s = strengthOf(confidence)
  return (
    <span className={`fc-strength ${s.level}`} title={STRENGTH_TOOLTIP}>
      <span className="fc-bar" aria-hidden="true"><i style={{ width: `${Math.round(s.fraction * 100)}%` }} /></span>
      <span>evidence strength: {s.word}</span>
      <span className="sr-only">. {STRENGTH_TOOLTIP}</span>
    </span>
  )
}

function Quoted({ quote }: { quote: string | null | undefined }) {
  return <blockquote className="quote"><Quote size={14} aria-hidden="true" /><span>{quote || '(no quote was returned)'}</span></blockquote>
}

function EvidenceItem({ e }: { e: FactEvidence }) {
  const level = e.evidenceLevel ? (evidenceLevelLabel[e.evidenceLevel as keyof typeof evidenceLevelLabel] ?? { label: e.evidenceLevel, partial: true }) : null
  const rel = (e.relation ?? '').toLowerCase()
  const near = rel === 'near_match'
  return (
    <li className={`fc-ev ${rel === 'contradicts' ? 'against' : rel === 'supports' ? 'for' : near ? 'near' : 'other'}`}>
      {near && <p className="fc-near-head" title={NEAR_HINT}>{NEAR_HEADING}</p>}
      <div className="fc-ev-head">
        <b className="fc-ev-title">{e.sourceTitle ?? 'Untitled source'}</b>
        <StatusPill tone={rel === 'supports' ? 'mint' : rel === 'contradicts' ? 'coral' : near ? 'blue' : 'neutral'}>{rel === 'supports' ? 'supports' : rel === 'contradicts' ? 'contradicts' : near ? 'close variant, not the same claim' : (e.relation || 'unclear')}</StatusPill>
        {level && <StatusPill tone={level.partial ? 'amber' : 'mint'}>{level.label}</StatusPill>}
        {checkedByJudge(e) && <span className="tag synth" title={JUDGE_BADGE_TOOLTIP}>{JUDGE_BADGE}<span className="sr-only">. {JUDGE_BADGE_TOOLTIP}</span></span>}
        {typeof e.reliability === 'number' && <span className="tag" title="How reliable the source looks (venue, citations). Not a measure of this quote.">reliability {e.reliability.toFixed(2)}</span>}
      </div>
      {near && <p className="fc-near-claim"><b>They say: </b>{e.nearClaim || '(their wording was not returned)'}</p>}
      <Quoted quote={e.quote} />
    </li>
  )
}

function Claim({ claim }: { claim: FactClaim }) {
  const v = labelView(claim.label)
  const { supports, contradicts, near, other } = splitEvidence(claim)
  const shown = mustShowDisagreement(claim)
  const all = [...supports, ...contradicts, ...other]            // the close variants are shown apart, below
  return (
    <li className={`fc-claim ${v.kind}${claim.contested ? ' contested' : ''}`}>
      <div className="fc-claim-head">
        <span title={v.hint}><StatusPill tone={v.tone}>{v.text}</StatusPill><span className="sr-only">. {v.hint}</span></span>
        {claim.contested && <span className="tag gap" title={CONTESTED_HINT}>contested<span className="sr-only">. {CONTESTED_HINT}</span></span>}
        <Strength confidence={claim.confidence} />
      </div>
      <p className="fc-claim-text">{claim.claim}</p>
      <p className="meta fc-counts"><b>{sourcesLine(claim)}</b><span aria-hidden="true"> · </span><span className={claim.contraDocCount > 0 ? 'against' : ''}>{againstSources(claim.contraDocCount)}</span></p>

      {shown && (
        <div className="fc-against" role="group" aria-label="The source that disagrees" title={DISAGREEMENT_TOOLTIP}>
          <div className="fc-against-head"><AlertTriangle size={15} aria-hidden="true" /><b>The source that disagrees</b></div>
          {contradicts.length > 0
            ? <ul className="fc-ev-list">{contradicts.map((e, i) => <EvidenceItem key={`${i}:${e.sourceId}`} e={e} />)}</ul>
            : <p className="meta">The disagreeing source was not returned for this claim, so it cannot be checked here. Do not rely on this claim.</p>}
          <p className="meta">{DISAGREEMENT_TOOLTIP}</p>
        </div>
      )}

      {all.length > 0 && (
        <details className="fc-evidence">
          <summary>Evidence ({all.length})<ChevronDown size={14} className="chev" aria-hidden="true" /></summary>
          <ul className="fc-ev-list">{all.map((e, i) => <EvidenceItem key={`${i}:${e.sourceId}`} e={e} />)}</ul>
        </details>
      )}

      {near.length > 0 && (
        <ul className="fc-ev-list fc-near" aria-label={NEAR_HEADING}>{near.map((e, i) => <EvidenceItem key={`${i}:${e.sourceId}`} e={e} />)}</ul>
      )}
    </li>
  )
}

function DisagreementCard({ d, index }: { d: FactDisagreement; index: number }) {
  return (
    <li className="fc-disagree" title={DISAGREEMENT_TOOLTIP}>
      <div className="fc-sides">
        <div className="fc-side" role="group" aria-label={`Disagreement ${index + 1}, claim A`}>
          <p className="eyebrow">Claim A</p>
          <p className="fc-claim-text">{d.claimA}</p>
          <Quoted quote={d.quoteA} />
          <p className="meta fc-source">From {d.sourceATitle ?? 'an untitled source'}</p>
        </div>
        <div className="fc-side" role="group" aria-label={`Disagreement ${index + 1}, claim B`}>
          <p className="eyebrow">Claim B</p>
          <p className="fc-claim-text">{d.claimB}</p>
          <Quoted quote={d.quoteB} />
          <p className="meta fc-source">From {d.sourceBTitle ?? 'an untitled source'}</p>
        </div>
      </div>
      <p className="fc-reason"><b>The judge's reason: </b>{d.reason || 'no reason was given'}</p>
    </li>
  )
}

/** The collapsible "Cross-check" panel of one sub-question (Stage 4). Renders nothing when Stage 4 did not run; a short note when it ran but not for this sub-question.
 *  `ran` = the report says Stage 4 ran at all (totals.factChecked is not null). */
export function FactCheckPanel({ sq, ran }: { sq: SubQuestionReport; ran: boolean }) {
  const fc: FactCheck | null | undefined = sq.factCheck
  if (!fc) {
    return ran
      ? <div className="callout-box amber fc-missing" role="note"><AlertTriangle size={18} aria-hidden="true" /><div><b>{PANEL_TITLE}</b><p>{NOT_CROSS_CHECKED_NOTE}</p></div></div>
      : null
  }
  const claims = Array.isArray(fc.claims) ? fc.claims : []
  const disagreements = Array.isArray(fc.disagreements) ? fc.disagreements : []
  const counts = countsOf(fc)
  return (
    <details className="factcheck-panel">
      <summary>
        <ShieldCheck size={14} aria-hidden="true" />
        <span className="fc-title">{PANEL_TITLE}<span className="sr-only"> of: {sq.topic}</span></span>
        <FactCountChips counts={counts} />
        <ChevronDown size={14} className="chev" aria-hidden="true" />
      </summary>
      <div className="fc-body">
        <p className="meta">{PANEL_INTRO}</p>
        {claims.length === 0
          ? <p className="meta fc-empty">{EMPTY_STATE}</p>
          : <ol className="fc-claims" aria-label={`Claims cross-checked for: ${sq.topic}`}>{claims.map((c, i) => <Claim key={`${i}:${c.claim}`} claim={c} />)}</ol>}
        {disagreements.length > 0 && (
          <div className="fc-disagreements">
            <h3 className="fc-sub"><GitCompare size={14} aria-hidden="true" /> Sources that disagree ({disagreements.length})</h3>
            <ul className="fc-disagree-list" aria-label={`Disagreements for: ${sq.topic}`}>{disagreements.map((d, i) => <DisagreementCard key={`${i}:${d.claimA}`} d={d} index={i} />)}</ul>
          </div>
        )}
      </div>
    </details>
  )
}
