# Pipeline run report - What are the privacy risks of federated learning and how effective are the defenses against them?

Generated 2026-11-07 13:29 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 17 in the file) and the database. Query id `fb587186-7af6-4bea-be1e-dbb0a10936ee`.

## 1. Summary

| | |
|---|---|
| Question | What are the privacy risks of federated learning and how effective are the defenses against them? |
| Domain anchor | (cached): 'machine learning' | context: Machine learning: federated learning is a privacy‑preserving distributed training method, not an educational or political collaboration. |
| Started / finished | 2026-11-07 11:57:09 / 12:17:30 |
| **Total execution time** | **20m 21s** (1221 s) |
| Sub-questions / search queries | 4 / 13 (per sub-question [3, 3, 3, 3]) |
| Plan source | planner |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 475 candidates -> 466 cleared the similarity floor -> 80 shortlisted |
| **Papers kept after the relevance judge** | **73** (log: 73); 7 shortlisted papers rejected |
| **Web sources** | **54** (per sub-question [14, 12, 13, 15]) |
| Papers attempted for parsing | 21 (top-N per sub-question) |
| **Papers parsed to usable full text** | **20** of 21 attempted (6 from the parse cache) |
| Papers not parsed (all routes failed) | 1 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 16 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 32 (20 from full text, 0 from abstracts, 12 from web snippets) |
| Findings (verified / total) | 109 / 116 |
| Coverage sufficient | 2 of 4 sub-questions |
| Judge | 1m 33s in 4 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 92 parking events, 1332 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 4 sub-questions) | 11:57:09 | 11:57:34 | 25s | 2% |
| Web search (Tavily) | 11:57:34 | 11:57:47 | 13s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 11:57:47 | 11:58:26 | 39s | 3% |
| Embedding pre-filter + relevance judge | 11:58:26 | 12:01:34 | 3m 08s | 15% |
| Citation enrichment (Semantic Scholar) | 12:01:35 | 12:02:41 | 1m 06s | 5% |
| Store papers in the database | 12:02:41 | 12:02:42 | 1s | 0% |
| PDF download + Docling parsing | 12:02:42 | 12:06:13 | 3m 31s | 17% |
| Stage 3 preparation (aspect split, chunking, embedding) | 12:06:13 | 12:14:37 | 8m 24s | 41% |
| Stage 3 digest generation (Groq) | 12:14:37 | 12:15:49 | 1m 12s | 6% |
| Stage 3 judge + coverage (per sub-question) | 12:15:49 | 12:17:27 | 1m 38s | 8% |
| **Total** | 11:57:09 | 12:17:30 | **20m 21s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is federated learning and how does it work? | 131 -> 130 -> 20 | 16 of 20 | 5 | 14 | 8 (5 / 0 / 3) | 27 / 29 | sufficient |
| 2 | What are the privacy risks of federated learning? | 110 -> 108 -> 20 | 20 of 20 | 5 | 12 | 8 (5 / 0 / 3) | 29 / 30 | sufficient |
| 3 | What are the defenses against privacy risks in federated learning? | 113 -> 109 -> 20 | 20 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 21 / 24 | NOT sufficient |
| 4 | How effective are the defenses against privacy risks in federated learning? | 121 -> 119 -> 20 | 17 of 20 | 5 | 15 | 8 (5 / 0 / 3) | 32 / 33 | NOT sufficient |

- Relevance judge rejected 4 papers for [What is federated learning and how does ]. Examples: 'Supporting Managerial Decision-Making for Federated Machine ' (The paper focuses on managerial decision-making tools and technology selection rather than explaining the fundamental concepts and mechanism); 'A Detailed Survey on Federated Learning Attacks and Defenses' (The paper focuses on security attacks and defenses rather than explaining the fundamental concepts and mechanics of federated learning.); 'Revealing the Impacting Factors for the Adoption of Federate' (The paper focuses on organizational adoption factors rather than explaining the technical definition and mechanics of federated learning.)
- Relevance judge rejected 3 papers for [How effective are the defenses against p]. Examples: 'Advances and Open Problems in Federated Learning' (The paper provides a general overview of federated learning advances and open problems but does not specifically evaluate the effectiveness ); 'Evaluating Data Distribution Strategies in Federated Learnin' (The paper focuses on data distribution strategies and dataset evaluation rather than evaluating specific defenses against privacy risks.); 'Federated learning and privacy' (The title and abstract are too vague and do not mention specific defenses or effectiveness metrics required to answer the research question.)

### Sources behind each sub-question's digests

**1. What is federated learning and how does it work?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Federated Learning Systems: Vision, Hype and Reality for Data Privacy and Protectio | paper | full_text | 3 / 4 |
| Advances and Open Problems in Federated Learning | paper | full_text | 3 / 3 |
| Federated Learning: A Distributed Shared Machine Learning Method | paper | full_text | 3 / 3 |
| Federated Learning: Collaborative Machine Learning without Centralized Training Data | paper | full_text | 5 / 5 |
| Reviewing Federated Learning Aggregation Algorithms; Strategies, Contributions, Limitations and | paper | full_text | 4 / 4 |
| Federated Learning: A Survey on Enabling Technologies, Protocols, and Applications | web | web_snippet | 1 / 1 |
| Federated learning: Overview, strategies, applications, tools and future directions | web | web_snippet | 3 / 4 |
| Principles and Components of Federated Learning Architectures | web | web_snippet | 5 / 5 |

**2. What are the privacy risks of federated learning?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Achieving security and privacy in federated learning systems: Survey, research challenges and f | paper | full_text | 5 / 5 |
| An overview of implementing security and privacy in federated learning | paper | full_text | 4 / 4 |
| On Safeguarding Privacy and Security in the Framework of Federated Learning | paper | full_text | 4 / 5 |
| The Federation Strikes Back: A Survey of Federated Learning Privacy Attacks, Defenses, Applicat | paper | full_text | 4 / 4 |
| Vulnerabilities in Federated Learning | paper | full_text | 3 / 3 |
| A review of secure federated learning: Privacy leakage threats, protection technologies, challe | web | web_snippet | 5 / 5 |
| Privacy Attacks in Federated Learning – CyberIR@MIT | web | web_snippet | 1 / 1 |
| Privacy attack in federated learning is not easy: an experimental study / Complex & Intelligent | web | web_snippet | 3 / 3 |

**3. What are the defenses against privacy risks in federated learning?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Detailed Survey on Federated Learning Attacks and Defenses | paper | full_text | 4 / 4 |
| A survey of security threats in federated learning | paper | full_text | 2 / 3 |
| Privacy and Robustness in Federated Learning: Attacks and Defenses | paper | full_text | 3 / 4 |
| The Federation Strikes Back: A Survey of Federated Learning Privacy Attacks, Defenses, Applicat | paper | full_text | 4 / 4 |
| Vulnerabilities in Federated Learning | paper | full_text | 1 / 2 |
| A review of secure federated learning: Privacy leakage threats, protection technologies, challe | web | web_snippet | 3 / 3 |
| Federated Learning Privacy: Attacks, Defenses, Applications, and Policy Landscape — A Survey | web | web_snippet | 2 / 2 |
| Privacy Attacks in Federated Learning / NIST | web | web_snippet | 2 / 2 |

**4. How effective are the defenses against privacy risks in federated learning?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| On Safeguarding Privacy and Security in the Framework of Federated Learning | paper | full_text | 4 / 5 |
| Privacy and Robustness in Federated Learning: Attacks and Defenses | paper | full_text | 5 / 5 |
| Privacy and Security in Federated Learning: A Survey | paper | full_text | 5 / 5 |
| The Federation Strikes Back: A Survey of Federated Learning Privacy Attacks, Defenses, Applicat | paper | full_text | 4 / 4 |
| Vulnerabilities in Federated Learning | paper | full_text | 5 / 5 |
| Advances and Open Problems in Federated Learning — MIT Media Lab | web | web_snippet | 1 / 1 |
| Belt and Braces: When Federated Learning Meets Differential Privacy | web | web_snippet | 4 / 4 |
| Toward the Tradeoffs between Privacy, Fairness and Utility in Federated Learning | web | web_snippet | 4 / 4 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is federated learning and how does it work?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 24 = yes 13, partial 7, no 4, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | benefits of federated learning | covered | 4 | 4 |
| 2 | challenges of federated learning | covered | 2 | 2 |
| 3 | main components of federated learning | covered | 3 | 3 |
| 4 | protocols of federated learning | covered | 4 | 4 |

### 2. What are the privacy risks of federated learning?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 23 = yes 19, partial 1, no 3, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | sources of privacy leakage in federated learning | covered | 4 | 3 |
| 2 | types of privacy leakage in federated learning | covered | 5 | 3 |
| 3 | potential harms of privacy leakage in federated learning | covered | 6 | 4 |
| 4 | potential impacts of privacy leakage in federated learning | covered | 4 | 4 |

### 3. What are the defenses against privacy risks in federated learning?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 30 = yes 12, partial 5, no 13, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the goals of the defenses against privacy risks in federated learning? | covered | 2 | 2 |
| 2 | What are the assumptions of the defenses against privacy risks in federated learning? | uncovered | 1 | 1 |
| 3 | methods of the defenses against privacy risks in federated learning | covered | 2 | 2 |
| 4 | techniques of the defenses against privacy risks in federated learning | covered | 4 | 4 |
| 5 | How are the defenses against privacy risks in federated learning evaluated? | covered | 2 | 2 |
| 6 | How are the defenses against privacy risks in federated learning compared? | uncovered | 1 | 1 |

Uncovered details: What are the goals and assumptions of the defenses?; How are the defenses evaluated and compared?

### 4. How effective are the defenses against privacy risks in federated learning?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 30 = yes 14, partial 10, no 6, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | strengths of the defenses against privacy risks in federated learning | covered | 3 | 3 |
| 2 | limitations of the defenses against privacy risks in federated learning | covered | 3 | 2 |
| 3 | trade-offs of the defenses | covered | 3 | 3 |
| 4 | open problems of the defenses | covered | 3 | 3 |
| 5 | How can the defenses against privacy risks in federated learning be improved? | covered | 2 | 2 |
| 6 | How can the defenses against privacy risks in federated learning be combined? | uncovered | 0 | 0 |

Uncovered details: How can the defenses be improved or combined?

## 5. Retrieval details

- Web search variants: [14, 12, 13, 15] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 131 candidates -> 130 cleared min_similarity (0.56) -> top 20 shortlisted; 110 candidates -> 108 cleared min_similarity (0.56) -> top 20 shortlisted; 113 candidates -> 109 cleared min_similarity (0.56) -> top 20 shortlisted; 121 candidates -> 119 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 44, 'both': 3, 'scopus': 22, 'arxiv': 4}; requests to api.openalex.org in the log: 30
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 3
- Citation enrichment: Citation enrichment: 2 arXiv-only papers to enrich; took 1m 06s in total

## 6. Parsing details

- Attempted 21 papers, usable full text 20, 73 papers saved in the database.
- PDF obtained via: its own link: 7, the OpenAlex content API: 4, Unpaywall: 2; parse cache hits: 6; Unpaywall OA links found: 2; landing-page citation_pdf_url: 0
- Individual download failures: 16 -> HTTPStatusError: 11, ValueError: 5
- Headless-browser fallback: 2 tried, 2 failed; Docling fetch-by-URL attempts: 3; HTML full-text attempts that failed: 1

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| Federated Machine Learning: Survey, Multi-Level Classification, Desirable Criteria and Fut | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |

## 7. Groq and judge

- Stage 3: 32 digests for 4 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 92; per key (events / parked seconds): ...3mla: 12 / 154s, ...Ef4D: 9 / 148s, ...KJJp: 10 / 173s, ...KaRe: 13 / 228s, ...X2Oj: 21 / 234s, ...uNUk: 8 / 144s, ...x1nP: 19 / 251s
- Judge batch latencies (s): [21.3, 19.4, 25.9, 25.9]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 1 | All PDF URLs failed for <id>: ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 11 | Failed to download from <url> HTTPStatusError: HTTPStatusError('<text>') |
| WARNING | 5 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 3 | SN rate limited on batch, backing off Ns |
| WARNING | 2 | Playwright fallback failed: ValueError: ValueError('<text>') |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429) and citation enrichment still spent 1m 06s on 3 rate-limited batch calls.
- 1 paper(s) could not be downloaded by any route.
- Groq rate limiting: 92 parking events; digest generation took 1m 12s.
- Longest phase: Stage 3 preparation (aspect split, chunking, embedding) (8m 24s, 41% of the run).

Warnings in the log: 23; errors: 1.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand after reading the log and the database)

**Bottom line.** The longest run of the six (20m 21s) and the cleanest in terms of errors: no database error, no judge error (107 pairs), no digest failure, 20 of 21 papers with full text, 109 of 116 findings verified (94%). **2 of 4 sub-questions sufficient, and both halves of the user's question are answered**: the privacy risks (sub-question 2: 4 of 4 aspects, 19 "yes" in 23 pairs) and the effectiveness of defenses (sub-question 4: strengths 3, limitations 3, trade-offs 3, open problems 3 "yes"). The two sub-questions that fail fail on three aspects the planner added: "assumptions of the defenses" (1 yes), "how the defenses are compared" (1 yes) and "how the defenses can be combined" (0 yes). This is the Q5 pattern again (core covered, peripheral aspects fail) and the opposite of Q3 and Q4 (the core fails).

### Numbers

| | |
|---|---|
| Plan | 4 sub-questions, 13 queries [3, 3, 3, 3], fresh plan (25 s), anchor 'machine learning' from the anchor cache ("federated learning is a privacy-preserving distributed training method, not an educational or political collaboration") |
| Retrieval | 475 candidates, 80 shortlisted, **73 kept** (OpenAlex 44, Scopus 22, both 3, arXiv 4), 54 web sources; judge passed 16, 20, 20 and 17 of 20 |
| Parsing | 20 of 21 usable (6 from the parse cache; 7 own link, 4 OpenAlex content API, 2 Unpaywall); 3m 31s; 16 failed download attempts, 1 paper lost (a DOI link that returned an HTML page) |
| Stage 3 | 32 digests (20 full text, 12 web) in 1m 12s on 7 keys; 116 findings, 109 verified (94%), 3.6 per digest; 107 judge pairs (24 + 23 + 30 + 30), 0 errors; judge and coverage 1m 38s |
| Groq | 92 parking events, 1332 key-seconds (per key 144 to 251 s) |
| Coverage | aspects covered 17 of 20: sub-question 1: 4 of 4; 2: 4 of 4; 3: 4 of 6; 4: 5 of 6 |

### The three uncovered aspects (all in the two sub-questions about defenses)

| Sub-question | Aspect | Verdicts (yes / partial / no) | Reading |
|---|---|---|---|
| Defenses | assumptions of the defenses | 1 / 1 / 3 | the closest to a near miss: 5 candidates, one source with a "yes" |
| Defenses | how the defenses are compared | 1 / 0 / 1 | only 2 candidates; one "yes" |
| Effectiveness | how the defenses can be combined | 0 / 0 / 2 | only 2 candidates, both "no": nothing in the 5 papers and 3 web pages read |

All three come from details of the form "X and Y": "goals and assumptions", "evaluated and compared", "improved or combined". The splitter makes one aspect of each half, and the planner's detail questions are the generic families again (limits 1.8 and 3.12). The user asked for risks and effectiveness; assumptions and combinations are not what was asked. Note the bar: the "improved" half of the last detail got 2 "yes" from 2 sources and counts as covered, so the same detail question is half covered, half not.

For the planned triage rule (A1, "search again only for aspects with at least 2 partial or yes verdicts"): "assumptions" (1 yes + 1 partial = 2) would be sent to Loop 2, "compared" (1) and "combined" (0) would not. That is plausible for all three, but it is three aspects in one run, not a test.

### Observations (one run each, to be tested)
- **Sub-questions 3 and 4 are almost the same literature.** "Defenses against privacy risks" and "how effective are the defenses" retrieved the same papers: 4 of the 5 full-text papers of sub-question 4 had already been digested for sub-question 2 or 3 (3 shared with each). Result: **32 digests from only 25 different sources; 7 digests are repeats** ("Vulnerabilities in Federated Learning" and "The Federation Strikes Back" 3 times each, three more sources twice). In Q5 no paper was digested twice. This is known limit 3.9 biting for the first time on a large scale: 22% of the Groq digest calls, though each repeat is digested with another aspect list, so it is not pure waste.
- **Sub-question 1 is the background question again** ("What is federated learning and how does it work?"): 5 parsed papers and 8 digests, 4 of 4 aspects covered by generic aspects (benefits, challenges, components, protocols). It is sufficient, so it hides nothing, but it spends a quarter of the budget on background (Q2, Q4 and Q6 have one).
- **Stage 3 preparation took 8m 24s (41%)**, the second worst after Q4 (9m 22s). The log shows the time per sub-question: 3m 57s, 2m 21s, 1m 00s and 0m 59s. The text to chunk and embed per sub-question fell from 874,000 to 631,000, 573,000 and 492,000 characters (the first holds the 466,000-character "Advances and Open Problems in Federated Learning"), i.e. by 44%, while the time fell by 75%. Length explains part of it; the rest is not explained (a cache does not exist in `chunk_selector.py`; the later sub-questions share papers with sub-question 2, but nothing is reused). The earlier guess for Q4, other work on the machine, is neither confirmed nor excluded. The pre-filter was also slow again (3m 08s, as in Q4 with 3m 10s; 1m 06s to 2m 16s in the other runs). The chunk-embedding cache (B5) would remove the repeated work whatever the cause.
- **Recall check of the relevance judge**: it rejected "A Detailed Survey on Federated Learning Attacks and Defenses" for sub-question 1 (background) and "Advances and Open Problems in Federated Learning" for sub-question 4; both were kept and used for another sub-question. That is the per-sub-question judging working as intended, not an error.

### What went wrong
1. **Longest run so far (20m 21s)**: Stage 3 preparation (8m 24s) and the pre-filter (3m 08s) are 56% of it; the network phases were normal.
2. **Peripheral aspects fail the sub-questions** (above): 2 of 4 sub-questions "not sufficient" because of three aspects that nobody asked.
3. **Citation enrichment spent 1m 06s on two arXiv-only papers** (three rate-limited Semantic Scholar batches; the search itself was skipped after the probe returned 429).
4. **16 failed download attempts** (11 HTTP errors, 5 HTML pages instead of PDF); all but one paper were recovered through another route. The one lost, "Federated Machine Learning: Survey, Multi-Level Classification, Desirable Criteria and Future Directions", is a survey of the topic; this is a download problem, not the database problem of Q2, Q4 and Q5.

### What worked
- No database error in this run (the first since Q3), no judge error, 94% verified findings.
- The question is answered by the evidence in the two parts that matter, and the reading of the judge was consistent: "yes" for claims that answer the aspect on their own, as in Q5 (risks: "sources", "types", "harms", "impacts" all covered with 3 to 4 sources each).
- Anchor from the cache and a fresh plan: the plan is on topic, no sub-question about something else (compare Q4's "improve reasoning").
- 7 Groq keys: digests 1m 12s.

### At a glance: the six questions (latest complete run of each)

| | Q1 Mamba (17:33) | Q2 MoE (23:29) | Q3 quantization | Q4 benchmarks | Q5 diffusion vs GANs | Q6 federated learning |
|---|---|---|---|---|---|---|
| Total time | 15m 14s | 16m 04s | 17m 46s | 19m 44s | 15m 11s | 20m 21s |
| Papers kept / usable full text | 48 / 25 of 26 | 73 / 25 of 28 | 46 / 15 of 16 | 61 / 20 of 22 | 60 / 20 of 21 | 73 / 20 of 21 |
| Findings verified | 81% | 89% | 94% | 92% | 86% | 94% |
| Sub-questions sufficient | 2 of 5 | 3 of 5 | 1 of 3 | 0 of 4 | 2 of 4 | 2 of 4 |
| Core question answered | partly | partly | no | no (list aspects) | yes | yes |
| Where it fails | transformers (parameters, limitations), trained and evaluated, transformer challenges in the comparison | one challenges and one scalability aspect | the core question: 8 aspects, 2 yes in 30 pairs | the list aspects (benchmarks, metrics) and an off-question sub-question | peripheral aspects (image types, solutions, scaling x3) | peripheral aspects (assumptions, compared, combined) |

Reading of the six runs for the Stage 3 plan: the aspects that a single claim can answer ("risks of X", "advantages of X versus Y", "limitations of X") are covered in every run; the ones that need several claims (list aspects in Q4, broad "how does X affect Y" in Q3) or that nobody can answer (planner-added aspects in Q3, Q5 and Q6) are not. Two kinds of fix follow, as already planned: wording of aspects (B1) and treating unanswerable aspects differently from near misses (A1, B3).

### Next checks
- [ ] A1 and B1 on the stored runs of Q1 to Q6 (verdict statistics per aspect type; label the pairs).
- [ ] B9 (end time of runs started through the API) and B8 (database retry): no database loss in this run, so B8 stays at four papers in three runs.
- [ ] B5: chunk-embedding cache; measure Stage 3 preparation per sub-question on an otherwise idle machine.
- [ ] B7: the 7 repeated digests of this run are the first strong case for reusing a digest across sub-questions.

(To regenerate the tables above after another run: `python scripts/pipeline_run_report.py --run N`; these notes are kept.)
