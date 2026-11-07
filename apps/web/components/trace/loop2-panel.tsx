import { ChevronDown, Search } from 'lucide-react'
import { ladderLabel, loop2AspectView, loop2Summary, SUBSTEP_TITLE, secondsLabel } from '@/lib/loop2'
import type { Loop2 } from '@/lib/trace-types'
import { StatusPill } from './status-pill'

const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s)

/** The collapsible "Second search" panel of one sub-question: what Loop 2 did, step by step, and what became of each aspect it searched for. */
/** `label` names the sub-question: every sub-question has its own steps table, and landmark names must be unique. */
export function Loop2Panel({ loop2, label }: { loop2: Loop2; label?: string }) {
  const steps = Array.isArray(loop2.steps) ? loop2.steps : []
  const aspects = Array.isArray(loop2.aspects) ? loop2.aspects : []
  const gaps = Array.isArray(loop2.knownGaps) ? loop2.knownGaps : []
  return (
    <details className="loop2-panel">
      <summary>
        <Search size={14} aria-hidden="true" />
        <span className="loop2-title">Second search</span>
        <span className="loop2-line">{loop2Summary(loop2)}</span>
        <ChevronDown size={14} className="chev" aria-hidden="true" />
      </summary>
      <div className="loop2-body">
        <p className="meta">{SUBSTEP_TITLE}: for the aspects that stayed uncovered, TRACE tried, in this order, re-reading the papers it already had, reading more of the search results, and searching with new queries.</p>
        <div className="source-tags">
          {loop2.gapRule && <span className="tag">gap rule: {loop2.gapRule}</span>}
          {loop2.triage && <span className="tag">triage: {loop2.triage}</span>}
          {typeof loop2.coveredBySynthesis === 'number' && loop2.coveredBySynthesis > 0 && <span className="tag">{loop2.coveredBySynthesis} covered by combining sources</span>}
        </div>

        {steps.length > 0 && (
          <div className="table-wrap" tabIndex={0} role="region" aria-label={`Steps of the second search${label ? `: ${label}` : ''}`}>
            <table>
              <thead><tr><th scope="col">Step</th><th scope="col">Aspects</th><th scope="col">New sources</th><th scope="col">New verified findings</th><th scope="col">Covered</th><th scope="col">Time</th></tr></thead>
              <tbody>
                {steps.map((s, i) => (
                  <tr key={`${s.step}-${i}`}>
                    <th scope="row">{cap(ladderLabel(s.step))}</th>
                    <td>{s.aspects}</td><td>{s.newSources}</td><td>{s.newVerifiedFindings}</td><td>{s.covered}</td><td>{secondsLabel(s.seconds)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {aspects.length > 0 ? (
          <ul className="aspects loop2-aspects" aria-label="Aspects searched again">
            {aspects.map((a, i) => {
              const v = loop2AspectView(a)
              const tried = Array.isArray(a.steps) ? a.steps : []
              return (
                <li key={`${a.text}-${i}`}>
                  <span className="aspect-text">{a.text}</span>
                  <span title={v.detail}><StatusPill tone={v.tone}>{v.label}</StatusPill><span className="sr-only">. {v.detail}</span></span>
                  {a.status === 'covered' && a.coveredBy && <span className="tag">by {ladderLabel(a.coveredBy)}</span>}
                  {tried.length > 0 && <span className="tag" title="The rungs of the ladder that were tried for this aspect">tried: {tried.map(t => ladderLabel(t)).join(' → ')}</span>}
                  {v.blocksSufficient && <span className="tag warn">blocks “sufficient”</span>}
                </li>
              )
            })}
          </ul>
        ) : gaps.length > 0 ? (
          <ul className="aspects loop2-aspects" aria-label="Aspects still uncovered">
            {gaps.map((t, i) => <li key={`${i}:${t}`}><span className="aspect-text">{t}</span><StatusPill tone="amber">Not found</StatusPill></li>)}
          </ul>
        ) : null}
      </div>
    </details>
  )
}
