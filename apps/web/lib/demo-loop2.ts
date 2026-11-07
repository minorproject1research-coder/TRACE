import type { AspectRow, Finding, Loop2, Report, SourceReport, SubQuestionReport } from './trace-types'

// DEMO MODE ONLY. Fictional fixtures for the optional second search ("Loop 2"), in the exact shape of GET /api/research/{id}/report.
// The base demo report keeps one sub-question WITHOUT Loop 2 (loop2 null) and one that did not finish; these add:
//   demo-sq-2: Loop 2 ran, one aspect covered by the 'pool' rung, one near-miss gap that blocks "sufficient", a skipped-cap and a not-judged aspect
//   demo-sq-4: "sufficient" with gaps where no evidence was found, an aspect covered by SYNTHESIS, every ladder rung, digest failures,
//              10 aspects, very long aspect texts and an unbreakable URL (layout stress), sources found by 'reselect', 'pool' and 'queries'

const finding = (claim: string, quote: string, aspect: string, verdict: 'yes' | 'partial' | 'no', stance = 'supports'): Finding => ({
  claim, quote, stance, quoteFound: true,
  judgements: [{ aspect, verdict, quoteSupportsClaim: 'yes', answersAspect: verdict === 'no' ? 'no' : verdict, reason: verdict === 'yes' ? 'Answers the aspect directly.' : 'Answers only part of the aspect.' }],
})

const source = (id: string, type: 'paper' | 'web', title: string, level: SourceReport['evidenceLevel'], weight: number, findings: Finding[], extra: Partial<SourceReport> = {}): SourceReport => ({
  id, type, title, evidenceLevel: level, weight, findingsTotal: findings.length, findingsQuoteFound: findings.filter(f => f.quoteFound).length, findings,
  url: `https://example.org/${id}`, ...extra,
})

const LONG_TOPIC = 'Which open questions remain after the second search, and how long can an unusually long sub-question title get before the layout has to wrap it onto several lines without breaking anything around it?'
const LONG_LINK = 'https://example.org/a-very-long-link-without-any-spaces-that-must-wrap-or-scroll-instead-of-breaking-the-layout-0123456789-0123456789-0123456789'

const A = {
  goal: 'What is the main goal of the method?',
  data: 'Which datasets were used in the evaluation reported by the authors, and how were they split into training, validation and test sets, and why were those splits chosen over the usual ones?',
  noise: 'How robust is it to noise?',
  cost: 'What does it cost to run in production?',
  licence: 'Is the licence compatible with commercial use?',
  ethics: 'What are the ethical considerations that the authors discuss in the section on broader impact of the work, if any?',
  baseline: `How does it compare with the 2019 baseline ${LONG_LINK}`,
  distil: 'Can it be distilled?',
  hardware: 'Which hardware was used?',
  energy: 'What is the energy use?',
}

const row = (index: number, text: string, state: AspectRow['state'], yes: number, sources: number, coveredBy: AspectRow['coveredBy'] = null): AspectRow =>
  ({ index, text, state, coveredBy, yesVerdicts: yes, sources })

const SQ4_LOOP2: Loop2 = {
  searched: 7, covered: 4, seconds: 412.7, triage: 'r1', gapRule: 'core', sufficientStrict: false, coveredBySynthesis: 1,
  knownGapsNoEvidence: [A.licence, A.ethics],
  steps: [
    { step: 'reselect', aspects: 7, newSources: 3, newVerifiedFindings: 11, covered: 1, seconds: 38.9 },
    { step: 'pool', aspects: 6, newSources: 2, newVerifiedFindings: 6, covered: 1, seconds: 71.5 },
    { step: 'queries', aspects: 5, newSources: 4, newVerifiedFindings: 13, covered: 2, seconds: 302.3 },
  ],
  aspects: [
    { text: A.noise, status: 'covered', coveredBy: 'synthesis', how: 'synthesis', nearMiss: null, steps: ['reselect', 'pool', 'queries'] },
    { text: A.licence, status: 'known_gap_no_evidence', coveredBy: null, how: null, nearMiss: false, steps: ['reselect', 'pool', 'queries'] },
    { text: A.ethics, status: 'known_gap_no_evidence', coveredBy: null, how: null, nearMiss: false, steps: ['reselect', 'pool', 'queries'] },
    { text: A.baseline, status: 'covered', coveredBy: 'reselect', how: 'single claims', nearMiss: null, steps: ['reselect'] },
    { text: A.cost, status: 'covered', coveredBy: 'queries', how: 'single claims', nearMiss: null, steps: ['reselect', 'pool', 'queries'] },
    { text: A.hardware, status: 'known_gap_skipped_triage', coveredBy: null, how: null, nearMiss: null, steps: [] },
    { text: A.distil, status: 'known_gap', coveredBy: null, how: null, nearMiss: false, steps: ['reselect', 'pool', 'queries'] },
    { text: A.energy, status: 'covered', coveredBy: 'pool', how: 'single claims', nearMiss: null, steps: ['reselect', 'pool'] },
  ],
  knownGaps: [A.licence, A.ethics, A.distil, A.hardware],
}

function sq4(): SubQuestionReport {
  return {
    id: 'demo-sq-4',
    topic: LONG_TOPIC,
    detailQuestions: [A.goal, A.data],
    coverage: {
      sufficient: true, judgeUsed: true, sourceCount: 6, fullTextSourceCount: 3, digestFailures: 2,
      aspects: [
        row(0, A.goal, 'covered', 3, 3, 'single_claims'),
        row(1, A.data, 'covered', 2, 2, 'single_claims'),
        row(2, A.noise, 'covered', 3, 3, 'synthesis'),
        row(3, A.cost, 'covered', 2, 2, 'single_claims'),
        row(4, A.licence, 'no_candidates', 0, 0),
        row(5, A.ethics, 'judged_insufficient', 0, 0),
        row(6, A.baseline, 'covered', 2, 2, 'single_claims'),
        row(7, A.distil, 'judged_insufficient', 1, 1),
        row(8, A.hardware, 'judged_insufficient', 1, 1),
        row(9, A.energy, 'covered', 2, 2, 'single_claims'),
      ],
      uncoveredAspects: [A.licence, A.ethics, A.distil, A.hardware], unjudgedAspects: [], fallbackReason: null,
      loop2: SQ4_LOOP2,
    },
    sources: [
      source('demo-src-8', 'paper', '[Sample] A Fictional Method for Signal Tracing, Its Training, Costs and Limits', 'full_text', 0.78, [
        finding('The method aims to trace weak signals to their sources.', 'We aim to trace weak signals back to their sources.', A.goal, 'yes'),
        finding('Two public datasets were used, split 80/10/10.', 'Two public datasets were used, each split 80/10/10 for training, validation and test.', A.data, 'yes'),
      ]),
      source('demo-src-9', 'paper', '[Sample] Re-reading Pays Off: Cost Notes on Fictional Tracers', 'full_text', 0.64, [
        finding('A 2019 baseline needed twice the memory.', 'The 2019 baseline needed twice the memory for the same accuracy.', A.baseline, 'yes'),
      ], { foundByLoop2Step: 'reselect' }),
      source('demo-src-10', 'web', '[Sample] Energy Use of Sample Tracers: A Blog Post', 'web_snippet', 0.31, [
        finding('Energy use is about 40 W on one accelerator.', 'Typical energy use is about 40 W on a single accelerator.', A.energy, 'yes'),
      ], { foundByLoop2Step: 'pool' }),
      source('demo-src-11', 'paper', '[Sample] Production Costs of Fictional Tracers (abstract only)', 'abstract', 0.47, [
        finding('Running it in production costs about a tenth of the baseline.', 'Production cost fell to about a tenth of the baseline.', A.cost, 'yes'),
      ], { foundByLoop2Step: 'queries' }),
      source('demo-src-12', 'web', '[Sample] Noise and Tracers: Forum Thread', 'web_snippet', 0.2, [
        finding('Noise hurts only at very low signal levels.', 'Noise only matters at very low signal levels.', A.noise, 'partial'),
      ]),
      source('demo-src-13', 'paper', '[Sample] Robustness of Tracers Under Noise', 'full_text', 0.55, [
        finding('Accuracy drops gently when noise grows.', 'Accuracy dropped gently as noise grew.', A.noise, 'partial'),
        finding('Training with noise helps a little.', 'Training with noisy traces helped a little.', A.noise, 'partial', 'challenges'),
      ], { foundByLoop2Step: 'queries' }),
    ],
  }
}

/** Adds the Loop 2 cases to the base demo report: sq-2 gets a second search, sq-4 is new; totals and limitations are recomputed. */
export function withLoop2Fixtures(base: Report): Report {
  const r: Report = JSON.parse(JSON.stringify(base))
  const sq2 = r.subQuestions.find(s => s.id === 'demo-sq-2')
  if (sq2?.coverage) {
    sq2.coverage.aspects = [
      row(0, 'What limits the input length?', 'covered', 2, 2, 'single_claims'),
      row(1, 'How does cost grow with length?', 'covered', 2, 2, 'single_claims'),                     // covered by the second search
      row(2, 'How does the sample method scale to long inputs?', 'judged_insufficient', 3, 2),         // near miss: blocks "sufficient"
      row(3, 'How does it behave on streaming inputs?', 'judged_insufficient', 0, 0),
      row(4, 'Which memory layout is used for long inputs?', 'unjudged', 0, 0),
    ]
    sq2.coverage.uncoveredAspects = ['How does the sample method scale to long inputs?', 'How does it behave on streaming inputs?']
    sq2.coverage.unjudgedAspects = ['Which memory layout is used for long inputs?']
    sq2.coverage.loop2 = {
      searched: 2, covered: 1, seconds: 231.4, triage: 'r1', gapRule: 'core', sufficientStrict: false, coveredBySynthesis: 0, knownGapsNoEvidence: [],
      steps: [
        { step: 'reselect', aspects: 2, newSources: 1, newVerifiedFindings: 3, covered: 0, seconds: 14.2 },
        { step: 'pool', aspects: 2, newSources: 1, newVerifiedFindings: 2, covered: 1, seconds: 41.8 },
        { step: 'queries', aspects: 1, newSources: 0, newVerifiedFindings: 0, covered: 0, seconds: 175.4 },
      ],
      aspects: [
        { text: 'How does cost grow with length?', status: 'covered', coveredBy: 'pool', how: 'single claims', nearMiss: null, steps: ['reselect', 'pool'] },
        { text: 'How does the sample method scale to long inputs?', status: 'known_gap', coveredBy: null, how: null, nearMiss: true, steps: ['reselect', 'pool', 'queries'] },
        { text: 'How does it behave on streaming inputs?', status: 'known_gap_skipped_cap', coveredBy: null, how: null, nearMiss: null, steps: [] },
        { text: 'Which memory layout is used for long inputs?', status: 'unjudged_not_searched', coveredBy: null, how: null, nearMiss: null, steps: [] },
      ],
      knownGaps: ['How does the sample method scale to long inputs?', 'How does it behave on streaming inputs?'],
    }
    sq2.sources.push(source('demo-src-6', 'paper', '[Sample] Cost Growth in Fictional Sequence Models', 'full_text', 0.6, [
      finding('Cost grows linearly with the number of tokens.', 'Compute grows linearly in the number of tokens processed.', 'How does cost grow with length?', 'yes'),
    ], { foundByLoop2Step: 'pool' }))
  }

  r.subQuestions.push(sq4())

  const gapLines = (sq: SubQuestionReport) => (sq.coverage?.loop2?.knownGapsNoEvidence ?? []).map(t => `Evidence not found for: ${t} (searched again; part of: ${sq.topic})`)
  const synth = (sq: SubQuestionReport) => (sq.coverage?.aspects ?? []).filter(a => a.coveredBy === 'synthesis' && a.text).map(a => `${a.text} (part of: ${sq.topic})`)
  const synthAll = r.subQuestions.flatMap(synth)
  r.limitations = [
    ...r.limitations,
    ...r.subQuestions.flatMap(gapLines),
    ...(synthAll.length ? [`Covered by combining findings of several sources, not by one source: ${synthAll.join('; ')}`] : []),
  ]

  const all = r.subQuestions.flatMap(sq => sq.sources)
  r.totals = {
    subQuestions: r.subQuestions.length,
    subQuestionsSufficient: r.subQuestions.filter(sq => sq.coverage?.sufficient).length,
    sources: all.length,
    findings: all.reduce((n, s) => n + s.findings.length, 0),
    findingsQuoteFound: all.reduce((n, s) => n + s.findings.filter(f => f.quoteFound).length, 0),
  }
  return r
}
