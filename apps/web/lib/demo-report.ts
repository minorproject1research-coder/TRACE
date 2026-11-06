import type { Report } from './trace-types'

// DEMO MODE ONLY. Fictional sample data in the exact shape of GET /api/research/{id}/report.
// It exists so every UI state can be exercised without a 15-25 minute run. Nothing here comes from the TRACE backend,
// and the publications are invented, not real.

export function demoReport(id: string, question: string, createdAt: string | null): Report {
  return {
    id,
    question,
    createdAt,
    stages: { planner: 'completed', retrieval: 'completed', summarizer: 'completed', factcheck: 'not_built', report: 'not_built' },
    totals: { subQuestions: 3, subQuestionsSufficient: 1, sources: 5, findings: 8, findingsQuoteFound: 7 },
    limitations: [
      'DEMO DATA: this is a fictional sample report, not the result of a real run.',
      'Stage 4 (fact checking) is not part of the pipeline yet: findings are verified only in the sense that their quote was found in the source, and judged by an independent model against the aspect they should answer. Nothing checks that a claim is true.',
      'Stage 5 (the written report) is not built: this is the collected evidence, not an answer.',
      'Evidence is not sufficient for: How does the sample method scale to long inputs?',
      'Stage 3 did not finish for: What are the open problems of the sample method?',
    ],
    subQuestions: [
      {
        id: 'demo-sq-1',
        topic: 'What is the sample method and how does it work?',
        detailQuestions: ['How is the sample method trained?', 'What are its main advantages?'],
        coverage: {
          sufficient: true, judgeUsed: true, sourceCount: 2, fullTextSourceCount: 1, digestFailures: 0,
          aspects: [
            { index: 0, text: 'How is the sample method trained?', state: 'covered', yesVerdicts: 3, sources: 2 },
            { index: 1, text: 'What are its main advantages?', state: 'covered', yesVerdicts: 2, sources: 2 },
            { index: 2, text: 'What is the sample method and how does it work?', state: 'covered', yesVerdicts: 4, sources: 2 },
          ],
          uncoveredAspects: [], unjudgedAspects: [], fallbackReason: null,
        },
        sources: [
          {
            id: 'demo-src-1', type: 'paper', title: '[Sample] A Fictional Survey of Signal Tracing Methods', evidenceLevel: 'full_text', weight: 0.812,
            findingsTotal: 3, findingsQuoteFound: 3, url: 'https://example.org/sample-survey', authors: ['A. Example', 'B. Placeholder'], year: 2024,
            venue: 'Journal of Sample Research', doi: null, arxivId: null, citations: 120, origin: 'openalex',
            findings: [
              {
                claim: 'The sample method is trained in two phases: a broad pretraining phase and a short task-specific tuning phase.',
                quote: 'Training proceeds in two phases, a broad pretraining phase followed by a short task-specific tuning phase.',
                stance: 'supports', quoteFound: true,
                judgements: [{ aspect: 'How is the sample method trained?', verdict: 'yes', quoteSupportsClaim: 'yes', answersAspect: 'yes', reason: 'The quote states both phases and their order.' }],
              },
              {
                claim: 'It reduces annotation cost compared with fully supervised approaches.',
                quote: 'Annotation cost fell by roughly half compared with a fully supervised baseline.',
                stance: 'supports', quoteFound: true,
                judgements: [{ aspect: 'What are its main advantages?', verdict: 'yes', quoteSupportsClaim: 'yes', answersAspect: 'yes', reason: 'Direct statement of a measured advantage.' }],
              },
              {
                claim: 'Gains disappear on very small datasets.',
                quote: 'On datasets below one thousand examples the advantage was not significant.',
                stance: 'contradicts', quoteFound: true,
                judgements: [{ aspect: 'What are its main advantages?', verdict: 'partial', quoteSupportsClaim: 'yes', answersAspect: 'partial', reason: 'Qualifies the advantage rather than stating one.' }],
              },
            ],
          },
          {
            id: 'demo-src-2', type: 'web', title: '[Sample] Sample Method Explained: A Practitioner Guide', evidenceLevel: 'web_snippet', weight: 0.41,
            findingsTotal: 1, findingsQuoteFound: 1, url: 'https://example.org/sample-guide', provider: 'sample-search', publishedDate: '2025-02-11',
            findings: [
              {
                claim: 'Practitioners usually start from a public checkpoint and tune it for their task.',
                quote: 'Most teams start from a public checkpoint and tune it on their own task data.',
                stance: 'supports', quoteFound: true,
                judgements: [{ aspect: 'What is the sample method and how does it work?', verdict: 'partial', quoteSupportsClaim: 'yes', answersAspect: 'partial', reason: 'Describes usage, not the mechanism.' }],
              },
            ],
          },
        ],
      },
      {
        id: 'demo-sq-2',
        topic: 'How does the sample method scale to long inputs?',
        detailQuestions: ['What limits the input length?', 'How does cost grow with length?'],
        coverage: {
          sufficient: false, judgeUsed: true, sourceCount: 2, fullTextSourceCount: 0, digestFailures: 1,
          aspects: [
            { index: 0, text: 'What limits the input length?', state: 'covered', yesVerdicts: 2, sources: 2 },
            { index: 1, text: 'How does cost grow with length?', state: 'judged_insufficient', yesVerdicts: 1, sources: 1 },
            { index: 2, text: 'How does the sample method scale to long inputs?', state: 'no_candidates', yesVerdicts: 0, sources: 0 },
          ],
          uncoveredAspects: ['How does cost grow with length?', 'How does the sample method scale to long inputs?'], unjudgedAspects: [], fallbackReason: null,
        },
        sources: [
          {
            id: 'demo-src-3', type: 'paper', title: '[Sample] Length Limits in Fictional Sequence Models', evidenceLevel: 'abstract', weight: 0.55,
            findingsTotal: 2, findingsQuoteFound: 1, url: 'https://example.org/sample-length', authors: ['C. Fiction'], year: 2023, venue: 'Sample Proceedings',
            doi: null, arxivId: '0000.00000', citations: 12, origin: 'arxiv',
            findings: [
              {
                claim: 'Input length is limited mainly by memory use.',
                quote: 'Memory use grows with the input length and is the main practical limit.',
                stance: 'supports', quoteFound: true,
                judgements: [{ aspect: 'What limits the input length?', verdict: 'yes', quoteSupportsClaim: 'yes', answersAspect: 'yes', reason: 'The quote names memory as the main limit.' }],
              },
              {
                claim: 'Cost grows linearly with input length.',
                quote: 'Compute grows linearly in the number of tokens processed.',
                stance: 'supports', quoteFound: false,
                judgements: [{ aspect: 'How does cost grow with length?', verdict: 'no', quoteSupportsClaim: 'no', answersAspect: 'yes', reason: 'The quote could not be located in the source, so it cannot support the claim.' }],
              },
            ],
          },
          {
            id: 'demo-src-4', type: 'web', title: '[Sample] Blog: What Happens When Inputs Get Long', evidenceLevel: 'web_snippet', weight: 0.22,
            findingsTotal: 1, findingsQuoteFound: 1, url: 'https://example.org/sample-blog', provider: 'sample-search', publishedDate: null,
            findings: [
              {
                claim: 'Long inputs make the method noticeably slower.',
                quote: 'Once inputs get long, everything gets slower.',
                stance: 'neutral', quoteFound: true,
                judgements: [{ aspect: 'How does cost grow with length?', verdict: 'partial', quoteSupportsClaim: 'yes', answersAspect: 'partial', reason: 'Too vague to say how cost grows.' }],
              },
            ],
          },
        ],
      },
      {
        id: 'demo-sq-3',
        topic: 'What are the open problems of the sample method?',
        detailQuestions: ['Which problems are unsolved?'],
        coverage: null,
        sources: [
          {
            id: 'demo-src-5', type: 'paper', title: '[Sample] Open Problems in Fictional Tracing', evidenceLevel: 'abstract', weight: null,
            findingsTotal: 0, findingsQuoteFound: 0, url: null, authors: [], year: 2022, venue: null, doi: null, arxivId: null, citations: null, origin: 'scopus',
            findings: [],
          },
        ],
      },
    ],
  }
}
