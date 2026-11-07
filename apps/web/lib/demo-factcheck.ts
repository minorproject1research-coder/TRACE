import type { FactCheck, FactClaim, FactCounts, FactDisagreement, FactEvidence, Report } from './trace-types'

// DEMO MODE ONLY. Fictional Stage 4 (fact check across sources) data in the exact shape of GET /api/research/{id}/report, added to the sample report.
// The cases the UI must handle: Stage 4 off (null everywhere), a claim supported by two sources (one checked by the independent judge), one that is
// only unverified, one that is contradicted with a disagreement card, a contested supported claim, an empty result, a sub-question that was not
// cross-checked, and very long claim and quote texts. Nothing here comes from the TRACE backend.

export type DemoFact = 'off' | 'on' | 'failed'

/** The wording of the server when Stage 4 did not run, and when it did (apps/api/services/report_service.py). */
export const FACTCHECK_OFF_LINE = 'Stage 4 (fact checking) did not run for this report: findings are verified only in the sense that their quote was found in the source, and judged by an independent model against the aspect they should answer. Nothing checks across sources that a claim is true.'
export const FACTCHECK_ON_LINE = 'Stage 4 compared the claims across sources. "Supported" means two independent documents state the claim; "unverified" means it rests on one document, which says nothing about whether it is false; "contradicted" means a source asserts the opposite. The checks are automatic (language models), not reviewed by a person, and their thresholds have not been tuned on a large labeled set.'

const LONG_WORD = 'https://example.org/a/very/long/unbreakable/address/that/a/layout/must/not/overflow/because/of/it/0123456789012345678901234567890123456789'
const LONG_CLAIM = 'Across all evaluated configurations, including the long-context settings that were added late in the study, the sample method keeps its advantage over the baseline as long as the pretraining corpus is at least ten times larger than the task corpus, and it stops doing so otherwise (see ' + LONG_WORD + ').'
const LONG_QUOTE = 'We observe that, for every configuration in which the pretraining corpus was at least ten times larger than the task corpus, the advantage over the baseline persisted across all three random seeds and all four evaluation suites, whereas in the remaining configurations the difference was within the run-to-run noise (' + LONG_WORD + ').'

const ev = (sourceId: string, sourceTitle: string, quote: string, relation: 'supports' | 'contradicts', evidenceLevel: string, reliability: number, via: string | null = null): FactEvidence =>
  ({ sourceId, sourceTitle, quote, relation, evidenceLevel, reliability, prob: 0.9, via })

const claim = (text: string, label: string, confidence: number, support: number, contra: number, evidence: FactEvidence[], contested = false): FactClaim =>
  ({ claim: text, label, confidence, supportDocCount: support, contraDocCount: contra, contested, evidence })

const counts = (claims: FactClaim[]): FactCounts => ({
  supported: claims.filter(c => c.label === 'supported').length,
  unverified: claims.filter(c => c.label === 'unverified').length,
  contradicted: claims.filter(c => c.label === 'contradicted').length,
  contested: claims.filter(c => c.contested).length,
})

const fact = (claims: FactClaim[], disagreements: FactDisagreement[]): FactCheck => ({ counts: counts(claims), claims, disagreements })

const SRC1 = '[Sample] A Fictional Survey of Signal Tracing Methods'
const SRC2 = '[Sample] Sample Method Explained: A Practitioner Guide'

function sq1(): FactCheck {
  const contradicted = claim('The sample method improves accuracy on datasets of every size.', 'contradicted', 0.38, 1, 1, [
    ev('demo-src-2', SRC2, 'It works well regardless of how much data you have.', 'supports', 'web_snippet', 0.41),
    ev('demo-src-1', SRC1, 'On datasets below one thousand examples the advantage was not significant.', 'contradicts', 'full_text', 0.81, 'stage3_judge'),
  ])
  const supported = claim('The sample method is trained in two phases: a broad pretraining phase and a short task-specific tuning phase.', 'supported', 0.82, 2, 0, [
    ev('demo-src-1', SRC1, 'Training proceeds in two phases, a broad pretraining phase followed by a short task-specific tuning phase.', 'supports', 'full_text', 0.81, 'stage3_judge'),
    ev('demo-src-2', SRC2, 'Most teams start from a public checkpoint and tune it on their own task data.', 'supports', 'web_snippet', 0.41),
  ])
  const unverified = claim('It reduces annotation cost compared with fully supervised approaches.', 'unverified', 0.31, 1, 0, [
    ev('demo-src-1', SRC1, 'Annotation cost fell by roughly half compared with a fully supervised baseline.', 'supports', 'full_text', 0.81, 'stage3_judge'),
  ])
  const d: FactDisagreement = {
    claimA: 'The sample method improves accuracy on datasets of every size.', claimB: 'Gains disappear on very small datasets.',
    sourceATitle: SRC2, sourceBTitle: SRC1,
    quoteA: 'It works well regardless of how much data you have.', quoteB: 'On datasets below one thousand examples the advantage was not significant.',
    prob: 0.86, reason: 'The first source claims a gain at every size; the second reports no significant gain below one thousand examples.',
  }
  return fact([contradicted, supported, unverified], [d])
}

function sq4(): FactCheck {
  const contested = claim(LONG_CLAIM, 'supported', 0.9, 3, 1, [
    ev('demo-src-10', '[Sample] A Study With A Deliberately Long Title That Keeps Going To Check That The Evidence List Wraps Instead Of Overflowing The Panel', LONG_QUOTE, 'supports', 'full_text', 0.77, 'stage3_judge'),
    ev('demo-src-11', '[Sample] Second Study', 'The advantage persisted in every configuration with a large pretraining corpus.', 'supports', 'full_text', 0.6),
    ev('demo-src-12', '[Sample] Noise and Tracers: Forum Thread', 'Some of us could not reproduce the advantage.', 'contradicts', 'web_snippet', 0.2),
    ev('demo-src-13', '[Sample] Robustness of Tracers Under Noise', 'The advantage held in our runs too.', 'supports', 'abstract', 0.55),
  ], true)
  const unverified = claim('Noise only matters at very low signal levels. ' + LONG_WORD, 'unverified', 0.22, 1, 0, [
    ev('demo-src-12', '[Sample] Noise and Tracers: Forum Thread', 'Noise only matters at very low signal levels. ' + LONG_WORD, 'supports', 'web_snippet', 0.2),
  ])
  const d: FactDisagreement = {
    claimA: LONG_CLAIM, claimB: 'The advantage over the baseline could not be reproduced outside the original setting.',
    sourceATitle: '[Sample] A Study With A Deliberately Long Title That Keeps Going To Check That The Cards Wrap Instead Of Overflowing', sourceBTitle: '[Sample] Noise and Tracers: Forum Thread',
    quoteA: LONG_QUOTE, quoteB: 'Some of us could not reproduce the advantage. ' + LONG_WORD, prob: 0.7,
    reason: 'One source reports the advantage in every large-corpus configuration, the other reports a failed reproduction; the judge could not tell which setting the second source used. ' + LONG_WORD,
  }
  return fact([contested, unverified], [d])
}

/** What Stage 4 found per sub-question of the sample report. sq-3 has no Stage 3 result, so it was not cross-checked (null); sq-2 had nothing to cross-check ([]). */
export function demoFactChecks(): Record<string, FactCheck | null> {
  return { 'demo-sq-1': sq1(), 'demo-sq-2': fact([], []), 'demo-sq-3': null, 'demo-sq-4': sq4() }
}

/** The totals of the fixtures, so the simulated stage_completed event and the report agree. */
export function demoFactTotals(): FactCounts {
  const all = Object.values(demoFactChecks()).filter((x): x is FactCheck => !!x)
  return all.reduce((t, f) => ({ supported: t.supported + f.counts.supported, unverified: t.unverified + f.counts.unverified, contradicted: t.contradicted + f.counts.contradicted, contested: t.contested + f.counts.contested }),
    { supported: 0, unverified: 0, contradicted: 0, contested: 0 })
}
export const demoFactDisagreements = (): number => Object.values(demoFactChecks()).reduce((n, f) => n + (f?.disagreements.length ?? 0), 0)

/** Adds Stage 4 to the sample report. 'off' and 'failed' both give a report without it (a failed stage stores nothing), like the server. */
export function withFactcheckFixtures(base: Report, mode: DemoFact): Report {
  const r: Report = JSON.parse(JSON.stringify(base))
  const rest = r.limitations.filter(l => !l.startsWith('Stage 4 '))
  if (mode !== 'on') {
    r.stages.factcheck = 'not_run'
    r.totals.factChecked = null
    for (const sq of r.subQuestions) sq.factCheck = null
    r.limitations = [rest[0], FACTCHECK_OFF_LINE, ...rest.slice(1)]
    return r
  }
  const checks = demoFactChecks()
  r.stages.factcheck = 'completed'
  for (const sq of r.subQuestions) sq.factCheck = checks[sq.id] ?? null
  r.totals.factChecked = demoFactTotals()
  const disagree = r.subQuestions.flatMap(sq => (sq.factCheck?.disagreements ?? []).map(d => `Sources disagree (${sq.topic}): "${d.claimA}" versus "${d.claimB}"`))
  r.limitations = [rest[0], FACTCHECK_ON_LINE, ...rest.slice(1), ...disagree]
  return r
}
