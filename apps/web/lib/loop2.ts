import type { PillTone } from '@/components/trace/status-pill'
import type { Coverage, Loop2, Loop2Aspect } from './trace-types'

// Pure helpers for Loop 2 (the optional second search). No React here, so they are unit-tested (tests/loop2.test.mts).
// Everything tolerates null and unknown values: the server's Loop 2 data has changed between runs, and unknown words must never break a page.

/** What each rung of the ladder does, in words a reader understands. */
export const LADDER_LABEL: Record<string, string> = {
  reselect: 're-reading papers we already have',
  pool: 'reading more papers from the search results',
  queries: 'searching with new queries',
  synthesis: 'combining the findings of several sources',
}

export const ladderLabel = (step: string | null | undefined): string => (step ? (LADDER_LABEL[step] ?? step) : 'an unknown step')

export const SYNTHESIS_BADGE = 'combined from several sources'
export const SYNTHESIS_TOOLTIP = 'No single source answered this fully; the judge accepted the findings of several sources together. Weaker evidence than two sources that each answer it.'
export const SECOND_SEARCH_BADGE = 'found by second search'
export const SUBSTEP_TITLE = 'Searching again for missing evidence'

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** 18.5 -> "19 s", 178.7 -> "2 min 59 s", 600 -> "10 min". */
export function secondsLabel(sec: number | null | undefined): string {
  if (typeof sec !== 'number' || !Number.isFinite(sec) || sec < 0) return 'unknown time'
  if (sec < 1) return 'under a second'
  if (sec < 60) return `${Math.round(sec)} s`
  const total = Math.round(sec)
  const m = Math.floor(total / 60)
  const s = total % 60
  return m >= 10 || s === 0 ? `${m} min` : `${m} min ${s} s`
}

export type AspectStatusView = { label: string; tone: PillTone; detail: string; blocksSufficient: boolean }

/** How one aspect of the second search is shown. The status is an open string: unknown words get a neutral label of their own. */
export function loop2AspectView(a: Pick<Loop2Aspect, 'status' | 'coveredBy' | 'nearMiss'>): AspectStatusView {
  switch (a.status) {
    case 'covered':
      return { label: 'Covered', tone: 'mint', detail: a.coveredBy ? `Covered by ${ladderLabel(a.coveredBy)}.` : 'Covered by the second search.', blocksSufficient: false }
    case 'known_gap_no_evidence':
      return { label: 'Evidence not found', tone: 'neutral', detail: 'Searched again and nothing usable was found. This does not block “sufficient”.', blocksSufficient: false }
    case 'known_gap':
      return a.nearMiss === true
        ? { label: 'Partly answered', tone: 'amber', detail: 'Evidence exists, but no source answered it completely. This blocks “sufficient”.', blocksSufficient: true }
        : { label: 'Not found', tone: 'amber', detail: 'Searched again and still not answered.', blocksSufficient: false }
    case 'known_gap_skipped_triage':
      return { label: 'Not searched', tone: 'neutral', detail: 'Judged not worth searching again.', blocksSufficient: false }
    case 'known_gap_skipped_cap':
      return { label: 'Not searched', tone: 'neutral', detail: 'The search limit was reached before this aspect. This blocks “sufficient”.', blocksSufficient: true }
    case 'unjudged_not_searched':
      return { label: 'Not judged', tone: 'neutral', detail: 'A judge call failed, so this aspect was neither counted as covered nor searched.', blocksSufficient: false }
    default: {
      const raw = (a.status ?? '').replace(/_/g, ' ').trim()
      return { label: raw ? raw[0].toUpperCase() + raw.slice(1) : 'Unknown', tone: 'neutral', detail: 'A status this version of TRACE does not know.', blocksSufficient: false }
    }
  }
}

/** "searched 4 aspects, found evidence for 3, 2 min" */
export function loop2Summary(l: Pick<Loop2, 'searched' | 'covered' | 'seconds'>): string {
  const searched = Number.isFinite(l.searched) ? l.searched : 0
  const covered = Number.isFinite(l.covered) ? l.covered : 0
  return `searched ${plural(searched, 'aspect', 'aspects')}, found evidence for ${covered}, ${secondsLabel(l.seconds)}`
}

/** The aspects where the second search found nothing usable. Shown right next to the sufficient badge: a green badge must never hide them. */
export function noEvidenceGaps(c: Pick<Coverage, 'loop2'> | null | undefined): string[] {
  const g = c?.loop2?.knownGapsNoEvidence
  return Array.isArray(g) ? g.filter(x => typeof x === 'string' && x) : []
}

/** Sufficient under the server's rule but not under the strict one: say so. null when there is nothing to add (also when Loop 2 did not run). */
export function sufficiencyNote(c: Pick<Coverage, 'sufficient' | 'loop2'> | null | undefined): string | null {
  return c && c.sufficient && c.loop2 && c.loop2.sufficientStrict === false ? 'Sufficient, with gaps where no evidence was found.' : null
}

/** The sentence that explains what "sufficient" means. Unchanged when Loop 2 did not run. */
export function sufficiencyMeaning(c: Pick<Coverage, 'loop2'>): string {
  return c.loop2 && c.loop2.gapRule === 'core'
    ? '“Sufficient” means every aspect that has evidence is covered; aspects where no evidence was found are listed here and do not block it. It does not mean the question is answered.'
    : '“Sufficient” means each aspect has at least two independent supporting sources. It does not mean the question is answered.'
}

/** Some sources could not be read (usually an LLM rate limit): "no evidence" may then be wrong. */
export function digestWarning(c: Pick<Coverage, 'digestFailures'> | null | undefined): string | null {
  const n = c?.digestFailures
  return typeof n === 'number' && n > 0
    ? `${plural(n, 'source', 'sources')} could not be read (usually an LLM rate limit), so “no evidence” may be wrong for this sub-question.`
    : null
}

/** Tooltips for the aspect states the judge can leave an aspect in (AspectRow.state). They only explain the existing words. */
export function aspectStateHint(state: string): string | undefined {
  switch (state) {
    case 'judged_insufficient': return 'The judge looked at the candidate findings, and too few of them answered this aspect.'
    case 'no_candidates': return 'There was nothing to judge for this aspect.'
    case 'unjudged': return 'A judge call failed for this aspect, so it is not counted as covered.'
    default: return undefined
  }
}

export const hasLoop2 = (c: Pick<Coverage, 'loop2'> | null | undefined): boolean => !!c?.loop2

/** Does any aspect of this coverage rest on findings of several sources combined? */
export const synthesisAspects = (c: Pick<Coverage, 'aspects'> | null | undefined): number => (c?.aspects ?? []).filter(a => a.coveredBy === 'synthesis').length
