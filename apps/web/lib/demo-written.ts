import { LEGEND, markers, PARTLY_LABEL, SINGLE_LABEL } from './written-report'
import type { WrittenDisagreement, WrittenReference, WrittenReport, WrittenReportResponse, WrittenSection, WrittenSentence } from './trace-types'

// DEMO MODE ONLY. Fictional written reports (Stage 5) in the exact shape of GET /api/research/{id}/written-report (docs/STAGE5_OUTPUT.md), one per status.

export type DemoWritten = 'completed' | 'warnings' | 'insufficient' | 'failed' | 'running' | 'none' | 'off'

const REFS: WrittenReference[] = [
  { number: 1, title: '[Sample] A Fictional Method for Signal Tracing', authors: ['A. Fiction', 'B. Imaginary'], year: 2024, venue: 'Journal of Sample Methods', doi: '10.0000/sample.1', url: 'https://example.org/sample-1', kind: 'paper', evidenceLevel: 'full_text', sourceIds: ['demo-src-1'], text: 'A. Fiction, B. Imaginary (2024). [Sample] A Fictional Method for Signal Tracing. Journal of Sample Methods. doi:10.0000/sample.1', markdown: '' },
  { number: 2, title: '[Sample] Scaling Fictional Tracers to Long Inputs', authors: ['C. Example'], year: 2023, venue: 'arXiv', doi: null, url: 'https://example.org/sample-2', kind: 'paper', evidenceLevel: 'full_text', sourceIds: ['demo-src-2'], text: 'C. Example (2023). [Sample] Scaling Fictional Tracers to Long Inputs. arXiv.', markdown: '' },
  { number: 3, title: '[Sample] Production Costs of Fictional Tracers', authors: ['D. Sample'], year: 2022, venue: null, doi: null, url: 'https://example.org/sample-3', kind: 'paper', evidenceLevel: 'abstract', sourceIds: ['demo-src-11'], text: 'D. Sample (2022). [Sample] Production Costs of Fictional Tracers (abstract only).', markdown: '' },
  { number: 4, title: '[Sample] Noise and Tracers: Forum Thread', authors: [], year: null, venue: 'sample-forum.example.org', doi: null, url: 'https://example.org/sample-4', kind: 'web', evidenceLevel: 'web_snippet', sourceIds: ['demo-src-12'], text: '[Sample] Noise and Tracers: Forum Thread. sample-forum.example.org. Accessed 2026-11-10.', markdown: '' },
  { number: 5, title: '[Sample] Robustness of Tracers Under Noise', authors: ['E. Test', 'F. Mock'], year: 2025, venue: 'Sample Conference', doi: '10.0000/sample.5', url: null, kind: 'paper', evidenceLevel: 'full_text', sourceIds: ['demo-src-13'], text: 'E. Test, F. Mock (2025). [Sample] Robustness of Tracers Under Noise. Sample Conference. doi:10.0000/sample.5', markdown: '' },
  { number: 6, title: '[Sample] A Practitioner Notebook', authors: [], year: 2024, venue: 'sample-notebook.example.org', doi: null, url: 'https://example.org/sample-notebook', kind: 'web', evidenceLevel: 'web_snippet', sourceIds: ['demo-src-15'], text: '[Sample] A Practitioner Notebook. sample-notebook.example.org (2024). Accessed 2026-11-10.', markdown: '' },
]

const S = (text: string, refs: number[], tier: 'supported' | 'partly' | 'single', origin: 'llm' | 'fallback' | 'template' = 'llm'): WrittenSentence => ({ text, claimIds: [`claim-${refs.join('')}-${text.length}`], refs, tier, origin })

const TOPICS = [
  'What is the sample method and how does it work?',
  'How does the sample method scale to long inputs?',
  'What are the open problems of the sample method?',
  'Which training settings does the sample method prefer?',
]

const DISAGREEMENT: WrittenDisagreement = {
  claimA: 'Noise only matters at very low signal levels.', claimB: 'Accuracy dropped sharply as soon as noise grew.', claimId: 'claim-noise',
  note: 'Both sources are shown. This report does not decide which of them is right.',
  sideA: { quote: 'Noise only matters at very low signal levels.', ref: 4, title: REFS[3].title ?? '' },
  sideB: { quote: 'Accuracy dropped sharply as soon as noise grew in our experiments.', ref: 5, title: REFS[4].title ?? '' },
}

function sections(fallback: boolean): WrittenSection[] {
  const o = fallback ? 'fallback' : 'llm'
  return [
    { id: 'sec-1', title: TOPICS[0], subQuestionId: 'demo-sq-1', detailQuestions: ['What is the main goal of the method?', 'Which datasets were used?'],
      sentences: [
        S('Two sources report that the method aims to trace weak signals back to their sources.', [1, 2], 'supported'),
        S('The first paper reports that two public datasets were used, and another paper makes a related point about how they were split.', [1, 5], 'partly'),
        S('According to one paper, training used an 80/10/10 split.', [2], 'single', o),
      ],
      disagreements: [DISAGREEMENT], gaps: [], counts: { total: 5, supported: 1, partly: 1, single: 1, disputed: 1, filtered: 1 } },
    { id: 'sec-2', title: TOPICS[1], subQuestionId: 'demo-sq-2', detailQuestions: ['What limits the input length?', 'How does cost grow with length?'],
      sentences: [
        S('Two sources report that compute grows linearly with the number of tokens processed.', [2, 5], 'supported'),
        S('One study reports that production cost fell to about a tenth of the baseline, based on its abstract.', [3], 'single'),
      ],
      disagreements: [], gaps: ['No evidence was found for how the method behaves on streaming inputs.'], counts: { total: 3, supported: 1, partly: 0, single: 1, disputed: 0, filtered: 1 } },
    { id: 'sec-3', title: TOPICS[2], subQuestionId: 'demo-sq-3', detailQuestions: [], sentences: [], disagreements: [],
      gaps: ['The evidence for this sub-question was not sufficient, so nothing is written about it.'], counts: { total: 0, supported: 0, partly: 0, single: 0, disputed: 0, filtered: 0 } },
    { id: 'sec-4', title: TOPICS[3], subQuestionId: 'demo-sq-5', detailQuestions: ['Which learning rate schedules are used?'],
      sentences: [
        S('One practitioner notebook reports little extra benefit from very large batches, and a paper makes a related point.', [6, 2], 'partly'),
        S('According to one notebook, a short warm-up followed by a slow decay was used.', [6], 'single', fallback ? 'template' : 'llm'),
      ],
      disagreements: [], gaps: [], counts: { total: 2, supported: 0, partly: 1, single: 1, disputed: 0, filtered: 0 } },
  ]
}

const INTRO = ['This report answers the question from the evidence TRACE collected and checked: the papers and web pages it found, the findings taken from them, and the cross-check of those findings across sources.', 'Each sentence below says how many documents stand behind it. Read it as a summary of what the sources say, not as a verified answer.']

function build(kind: 'completed' | 'warnings' | 'insufficient' | 'failed', question: string): WrittenReport {
  if (kind === 'failed') {
    return { status: 'failed', question, generatedAt: '2026-11-10T10:20:00Z', overview: { summary: [], counts: {} }, introduction: [], sections: [], limitations: ['Stage 5 failed: RuntimeError: the writer model stayed unreachable (simulated).'], conclusion: [], references: [], stats: {}, warnings: ['RuntimeError: the writer model stayed unreachable (simulated).'] }
  }
  if (kind === 'insufficient') {
    const secs = sections(false).map(s => ({ ...s, sentences: [], disagreements: [], gaps: ['Nothing was eligible to write about: the evidence is insufficient.'], counts: { total: 0, supported: 0, partly: 0, single: 0, disputed: 0, filtered: 0 } }))
    return {
      status: 'insufficient_evidence', question, generatedAt: '2026-11-10T10:20:00Z', overview: { summary: [], counts: { sections: 4, documents: 0, claims: 0, supported: 0, partly: 0, single: 0, disputed: 0, filtered: 0, sentences: 0, disagreements: 0, references: 0 } },
      introduction: INTRO, sections: secs, limitations: ['No claim was eligible for the written report, so it has no findings.', 'Every check is automatic and none was reviewed by a person.'], conclusion: [], references: [], stats: {}, warnings: [],
    }
  }
  const warn = kind === 'warnings'
  const secs = sections(warn)
  const summary = [S('Two sources report that the method aims to trace weak signals back to their sources.', [1, 2], 'supported'), S('One study reports that production cost fell to about a tenth of the baseline, based on its abstract.', [3], 'single')]
  const conclusion = [S('The sources agree on the goal of the method, while most other findings rest on a single document and are not confirmed.', [], 'single', 'template')]
  const all: WrittenSentence[] = [...summary, ...secs.flatMap(sec => sec.sentences ?? [])]
  const n = (t: string) => all.filter(s => s.tier === t).length
  return {
    status: warn ? 'completed_with_warnings' : 'completed', question, generatedAt: '2026-11-10T10:20:00Z',
    overview: { summary, counts: { sections: 4, documents: 6, claims: 12, supported: n('supported'), partly: n('partly'), single: n('single'), disputed: 1, filtered: 2, sentences: all.length, disagreements: 1, references: 6 } },
    introduction: INTRO, sections: secs,
    limitations: [
      'This report was written by language models from the labels of the fact check and checked by rules and models. No step was reviewed by a person.',
      'The conflict check compares only the most similar pairs of claims and is automatic, not reviewed by a person.',
      'Sections without eligible evidence: ' + TOPICS[2],
      '2 claims were left out because a document already had the maximum number of single-source claims or its only quote is an unconfirmed abstract.',
      ...(warn ? ['2 sentences use the standard template wording instead of the model’s.'] : []),
    ],
    conclusion, references: REFS, stats: { sentences: { llm: warn ? 6 : 8, fallback: warn ? 1 : 0, template: warn ? 2 : 1 } },
    warnings: warn ? ['1 sentence uses the template wording because the model’s sentence failed its checks twice.', '1 sentence was dropped by the final check.'] : [],
  }
}

/** The Markdown of a report, as the server writes it: the legend as the first block quote, the markers before the final full stop, the tier labels in italics. */
export function demoMarkdown(r: WrittenReport): string {
  const line = (s: WrittenSentence) => {
    const m = markers(s.refs)
    const text = /[.!?]$/.test(s.text) ? `${s.text.slice(0, -1)}${m ? ` ${m}` : ''}${s.text.slice(-1)}` : `${s.text}${m ? ` ${m}` : ''}`
    return `${text}${s.tier === 'partly' ? ` *(${PARTLY_LABEL})*` : s.tier === 'single' ? ` *(${SINGLE_LABEL})*` : ''}`
  }
  const out: string[] = [`# ${r.question ?? 'Written report'}`, '', `> ${LEGEND}`, '']
  if (r.overview?.summary?.length) out.push('## Research Overview and Executive Summary', '', ...r.overview.summary.map(line), '')
  if (r.introduction?.length) out.push('## Introduction', '', ...r.introduction, '')
  for (const s of r.sections ?? []) {
    out.push(`## ${s.title}`, '')
    out.push(...(s.sentences ?? []).map(line), '')
    for (const d of s.disagreements ?? []) out.push(`**Sources disagree.** ${d.claimA} [${d.sideA?.ref ?? ''}] / ${d.claimB} [${d.sideB?.ref ?? ''}]. ${d.note ?? ''}`, '')
    for (const g of s.gaps ?? []) out.push(`*Evidence gap:* ${g}`, '')
  }
  out.push('## Limitations and Evidence Gaps', '', ...(r.limitations ?? []).map(l => `- ${l}`), '')
  if (r.conclusion?.length) out.push('## Conclusion', '', ...r.conclusion.map(line), '')
  if (r.references?.length) out.push('## References', '', ...r.references.map(x => `${x.number}. ${x.text}`), '')
  return out.join('\n')
}

export function demoWrittenResponse(kind: 'completed' | 'warnings' | 'insufficient' | 'failed', question = 'How does the sample method compare with the baseline?'): WrittenReportResponse {
  const report = build(kind, question)
  const markdown = demoMarkdown(report)
  report.references = (report.references ?? []).map(x => ({ ...x, markdown: `${x.number}. ${x.text}` }))
  return { status: report.status ?? kind, report, markdown, stats: report.stats, model: 'demo-writer', templateVersion: 's5-v1', generatedAt: report.generatedAt }
}

/** The status the written report of a kind has (and so the data of the report stage's stage_completed event). */
export const demoWrittenStatus = (kind: DemoWritten): string => (kind === 'warnings' ? 'completed_with_warnings' : kind === 'insufficient' ? 'insufficient_evidence' : kind === 'failed' ? 'failed' : 'completed')
