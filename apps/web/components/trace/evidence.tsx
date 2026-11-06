import { AlertTriangle, BookOpen, Check, ExternalLink, Globe, HelpCircle, Quote } from 'lucide-react'
import { aspectStateLabel, evidenceLevelLabel } from '@/lib/format'
import type { Coverage, Finding, Report, SourceReport, SubQuestionReport } from '@/lib/trace-types'
import { StatusPill } from './status-pill'

/** Safe external link: only http(s) URLs become links, and they never get opener access. */
function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null
  try { const u = new URL(url); return u.protocol === 'http:' || u.protocol === 'https:' ? u.toString() : null } catch { return null }
}

export function StanceChip({ stance }: { stance: Finding['stance'] }) {
  const map = { supports: { t: 'mint', l: 'Supports' }, contradicts: { t: 'coral', l: 'Contradicts' }, neutral: { t: 'neutral', l: 'Neutral' } } as const
  return <StatusPill tone={map[stance].t}>{map[stance].l}</StatusPill>
}

export function FindingCard({ finding, children }: { finding: Finding; children?: React.ReactNode }) {
  const yes = finding.judgements.filter(j => j.verdict === 'yes').length
  return (
    <article className={`finding ${finding.quoteFound ? '' : 'unverified'}`}>
      <div className="finding-head">
        <StanceChip stance={finding.stance} />
        {finding.quoteFound
          ? <span className="verify ok"><Check size={13} aria-hidden="true" /> Quote found in source</span>
          : <span className="verify bad"><AlertTriangle size={13} aria-hidden="true" /> Quote not located in source: treat as unverified</span>}
      </div>
      <p className="claim">{finding.claim}</p>
      <blockquote className="quote"><Quote size={14} aria-hidden="true" /><span>{finding.quote}</span></blockquote>
      {children}
      {finding.judgements.length > 0 && (
        <details className="judgements">
          <summary>Independent judge: {yes} of {finding.judgements.length} aspect check{finding.judgements.length === 1 ? '' : 's'} answered yes</summary>
          <ul>
            {finding.judgements.map((j, i) => (
              <li key={i}>
                <b>{j.aspect ?? 'Aspect'}</b>
                <span className={`verdict ${j.verdict ?? 'none'}`}>{j.verdict ?? 'no verdict'}</span>
                {j.reason && <p>{j.reason}</p>}
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="finding-note">A finding is what the source says, not a confirmed fact. Fact checking is not built yet.</p>
    </article>
  )
}

export function SourceCard({ source, topic, open = false, headingLevel = 4 }: { source: SourceReport; topic?: string; open?: boolean; headingLevel?: 2 | 4 }) {
  const Heading = `h${headingLevel}` as 'h2' | 'h4'
  const level = evidenceLevelLabel[source.evidenceLevel] ?? { label: source.evidenceLevel, partial: true }
  const href = safeUrl(source.url)
  const meta = [source.authors?.length ? source.authors.slice(0, 3).join(', ') + (source.authors.length > 3 ? ' et al.' : '') : null, source.year, source.venue ?? source.provider, source.publishedDate].filter(Boolean).join(' · ')
  return (
    <article className="source">
      <div className="source-head">
        <span className={`source-icon ${source.type}`} aria-hidden="true">{source.type === 'paper' ? <BookOpen size={15} /> : <Globe size={15} />}</span>
        <div className="source-title">
          <Heading>{href ? <a href={href} target="_blank" rel="noopener noreferrer">{source.title ?? 'Untitled source'}<ExternalLink size={12} aria-hidden="true" /><span className="sr-only"> (opens in a new tab)</span></a> : (source.title ?? 'Untitled source')}</Heading>
          {meta && <p className="meta">{meta}</p>}
          {topic && <p className="meta topic">For: {topic}</p>}
        </div>
      </div>
      <div className="source-tags">
        <StatusPill tone={source.type === 'paper' ? 'lav' : 'blue'}>{source.type === 'paper' ? 'Paper' : 'Web'}</StatusPill>
        <StatusPill tone={level.partial ? 'amber' : 'mint'}>{level.label}</StatusPill>
        <span className="tag">{source.findingsQuoteFound}/{source.findingsTotal} quotes found</span>
        {source.weight != null && <span className="tag">weight {source.weight.toFixed(2)}</span>}
        {source.citations != null && <span className="tag">{source.citations} citations</span>}
      </div>
      {level.partial && <p className="partial-note">Only part of this source was read ({level.label.toLowerCase()}). Findings from it are weaker evidence.</p>}
      {source.findings.length > 0 && (
        <details className="source-findings" open={open}>
          <summary>{source.findings.length} finding{source.findings.length === 1 ? '' : 's'}</summary>
          <div className="finding-list">{source.findings.map((f, i) => <FindingCard key={i} finding={f} />)}</div>
        </details>
      )}
      {source.findings.length === 0 && <p className="meta">No findings were extracted from this source.</p>}
    </article>
  )
}

export function CoverageBlock({ sq }: { sq: SubQuestionReport }) {
  const c: Coverage | null = sq.coverage
  if (!c) {
    return <div className="callout-box coral" role="note"><HelpCircle size={18} aria-hidden="true" /><div><b>Not finished</b><p>Evidence judging did not finish for this sub-question. Do not read it as answered.</p></div></div>
  }
  return (
    <div className="coverage">
      <div className="coverage-head">
        <StatusPill tone={c.sufficient ? 'mint' : 'amber'}>{c.sufficient ? 'Enough independent sources' : 'Not enough evidence'}</StatusPill>
        <span className="tag">{c.sourceCount ?? '?'} sources</span>
        {c.fullTextSourceCount != null && <span className="tag">{c.fullTextSourceCount} read in full</span>}
        {c.digestFailures ? <span className="tag warn">{c.digestFailures} failed to digest</span> : null}
        {c.judgeUsed === false && <span className="tag warn">judge not used</span>}
      </div>
      {c.sufficient && <p className="meta">&ldquo;Sufficient&rdquo; means each aspect has at least two independent supporting sources. It does not mean the question is answered.</p>}
      {c.fallbackReason && <p className="meta">Note: {c.fallbackReason}</p>}
      <ul className="aspects" aria-label="Aspects checked">
        {c.aspects.map(a => (
          <li key={a.index}>
            <span className="aspect-text">{a.text ?? `Aspect ${a.index + 1} (text unavailable)`}</span>
            <StatusPill tone={aspectStateLabel[a.state].tone}>{aspectStateLabel[a.state].label}</StatusPill>
            <span className="tag">{a.yesVerdicts} yes · {a.sources} source{a.sources === 1 ? '' : 's'}</span>
          </li>
        ))}
      </ul>
      {c.uncoveredAspects.length > 0 && (
        <div className="callout-box amber" role="note"><AlertTriangle size={18} aria-hidden="true" />
          <div><b>Known gaps</b><ul>{c.uncoveredAspects.map(t => <li key={t}>{t}</li>)}</ul></div></div>
      )}
    </div>
  )
}

/** Numbers for the Verification view, all derived from the report and nothing else. */
export function verificationStats(report: Report) {
  const findings = report.subQuestions.flatMap(sq => sq.sources.flatMap(s => s.findings.map(f => ({ f, s, sq }))))
  const verdicts = { yes: 0, partial: 0, no: 0 }
  for (const { f } of findings) for (const j of f.judgements) if (j.verdict) verdicts[j.verdict]++
  return {
    findings,
    verdicts,
    contradicting: findings.filter(x => x.f.stance === 'contradicts'),
    unverified: findings.filter(x => !x.f.quoteFound),
    partialSources: report.subQuestions.flatMap(sq => sq.sources).filter(s => s.evidenceLevel !== 'full_text').length,
  }
}
