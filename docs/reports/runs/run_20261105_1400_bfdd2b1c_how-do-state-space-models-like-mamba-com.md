# Pipeline run report - How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance?

Generated 2026-11-05 16:00 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (last run in the file) and the database. Query id `bfdd2b1c-4de7-4656-9a3e-64486c261c57`.

## 1. Summary

| | |
|---|---|
| Question | How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance? |
| Domain anchor | not used (switch off, or no line in the log) |
| Started / finished | 2026-11-05 14:00:57 / 14:20:28 |
| **Total execution time** | **19m 31s** (1171 s) |
| Sub-questions / search queries | 5 / 15 (per sub-question [3, 3, 3, 3, 3]) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 628 candidates -> 532 cleared the similarity floor -> 100 shortlisted |
| **Papers kept after the relevance judge** | **42** (log: 42); 58 shortlisted papers rejected |
| **Web sources** | **65** (per sub-question [11, 15, 14, 13, 12]) |
| Papers attempted for parsing | 21 (top-N per sub-question) |
| **Papers parsed to usable full text** | **18** of 21 attempted (7 from the parse cache) |
| Papers not parsed (all routes failed) | 2 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 9 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 36 (18 from full text, 3 from abstracts, 15 from web snippets) |
| Findings (verified / total) | 114 / 134 |
| Coverage sufficient | 1 of 5 sub-questions |
| Judge | 1m 35s in 6 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 85 parking events, 1336 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 14:00:57 | 14:01:36 | 38s | 3% |
| Web search (Tavily) | 14:01:36 | 14:01:53 | 17s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 14:01:53 | 14:02:34 | 41s | 3% |
| Embedding pre-filter + relevance judge | 14:02:34 | 14:04:30 | 1m 57s | 10% |
| Citation enrichment (Semantic Scholar) | 14:04:30 | 14:05:41 | 1m 11s | 6% |
| Store papers in the database | 14:05:41 | 14:05:52 | 11s | 1% |
| PDF download + Docling parsing | 14:05:52 | 14:11:33 | 5m 42s | 29% |
| Stage 3 preparation (aspect split, chunking, embedding) | 14:11:33 | 14:15:05 | 3m 32s | 18% |
| Stage 3 digest generation (Groq) | 14:15:05 | 14:18:50 | 3m 45s | 19% |
| Stage 3 judge + coverage (per sub-question) | 14:18:50 | 14:20:28 | 1m 38s | 8% |
| **Total** | 14:00:57 | 14:20:28 | **19m 31s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What are state space models and how do they work? | 122 -> 99 -> 20 | 5 of 20 | 3 | 11 | 8 (3 / 2 / 3) | 24 / 30 | sufficient |
| 2 | What are transformers and how do they work? | 146 -> 111 -> 20 | 1 of 20 | 0 | 15 | 4 (0 / 1 / 3) | 10 / 10 | NOT sufficient |
| 3 | What is Mamba and how does it relate to state space models and transformers? | 128 -> 106 -> 20 | 20 of 20 | 5 | 14 | 8 (5 / 0 / 3) | 26 / 31 | NOT sufficient |
| 4 | How is training efficiency measured and compared for state space models, transformers, and Mamba? | 119 -> 110 -> 20 | 8 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 23 / 28 | NOT sufficient |
| 5 | How is long-sequence performance measured and compared for state space models, transformers, and Mamba? | 113 -> 106 -> 20 | 8 of 20 | 5 | 12 | 8 (5 / 0 / 3) | 31 / 35 | NOT sufficient |

- Relevance judge rejected 15 papers for [What are state space models and how do t]. Examples: 'SSpace: A Toolbox for State Space Modeling' (The paper describes a software toolbox for implementing models rather than explaining the theoretical concepts and mechanisms of state space); 'Learning a Sparse Polynomial Approximation to the Transition' (The paper focuses on a specific estimation method for sparse state-space models rather than explaining the fundamental concepts and mechanic); 'TheState Space ModelsToolbox forMATLAB' (The paper describes a software toolbox for implementing state space models rather than explaining their theoretical definitions or operation)
- Relevance judge rejected 19 papers for [What are transformers and how do they wo]. Examples: 'Transforming the transformer' (The paper discusses electrical transformers, not the Transformer neural network architecture.); 'Transformer development trend' (The paper discusses electrical power transformers and their engineering trends, not the Transformer neural network architecture.); 'History: The Transformer' (The paper discusses electrical transformers, whereas the research question asks about transformer neural networks.)
- Relevance judge rejected 12 papers for [How is training efficiency measured and ]. Examples: 'Benchmarking Feed-Forward Neural Networks: Models and Measur' (The paper focuses on feed-forward neural networks and does not address state space models, transformers, or Mamba.); 'Mechanistic evaluation of Transformers and state space model' (The paper focuses on mechanistic evaluation and architectural differences rather than measuring or comparing training efficiency.); 'BlackMamba: Mixture of Experts for State-Space Models' (The paper focuses on architectural improvements and performance benchmarks rather than defining or comparing specific training efficiency me)
- Relevance judge rejected 12 papers for [How is long-sequence performance measure]. Examples: 'Long Range Arena: A Benchmark for Efficient Transformers' (The paper only benchmarks efficient Transformers and does not include state space models or Mamba.); 'Routing Mamba: Scaling State Space Models with Mixture-of-Ex' (The paper focuses on scaling SSMs using MoE techniques rather than measuring or comparing long-sequence performance across different model a); 'Exploring the Limitations of Mamba in COPY and CoT Reasoning' (The paper focuses on specific reasoning limitations (COPY and CoT) rather than providing a general framework for measuring and comparing lon)

### Sources behind each sub-question's digests

**1. What are state space models and how do they work?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| BAYESIAN STATE SPACE MODELS IN MACROECONOMETRICS | paper | full_text | 4 / 5 |
| State‐space models for ecological time‐series data: Practical model‐fitting | paper | full_text | 2 / 5 |
| Statistical Software for State Space Methods | paper | full_text | 2 / 3 |
| Deep Learning-based Approaches for State Space Models:A Selective Review | web | web_snippet | 1 / 2 |
| Formulating State Space Models inRwith Focus on Longitudinal Regression Models | paper | abstract | 4 / 4 |
| Lecture 21 Notes - State Space Models - Stat 153 / 248 | web | web_snippet | 5 / 5 |
| Non-markovian state-space models in dependability evaluation | paper | abstract | 2 / 2 |
| What Are State Space Models? / IBM | web | web_snippet | 4 / 4 |

**2. What are transformers and how do they work?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| 9  Transformers – 6.390 - Intro to Machine Learning | web | web_snippet | 4 / 4 |
| Transformer in Image Interpretation | paper | abstract | 2 / 2 |
| Transformers Explained / Simple Explanation of Transformers | web | web_snippet | 2 / 2 |
| [2304.10557] An Introduction to Transformers | web | web_snippet | 2 / 2 |

**3. What is Mamba and how does it relate to state space models and transformers?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey of Mamba | paper | full_text | 5 / 5 |
| A hybrid model based on transformer and Mamba for enhanced sequence modeling | paper | full_text | 2 / 5 |
| Mamba in Speech: Towards an Alternative to Self-Attention | paper | full_text | 3 / 5 |
| Transformers are SSMs: Generalized Models and Efficient Algorithms Through Structured State Spa | paper | full_text | 3 / 3 |
| Vision Mamba: A Comprehensive Survey and Taxonomy | paper | full_text | 4 / 4 |
| A hybrid model based on transformer and Mamba for enhanced sequence modeling / Scientific Repor | web | web_snippet | 2 / 2 |
| Mamba-360: Survey of State Space Models as Transformer Alternative for Long Sequence Modelling: | web | web_snippet | 3 / 3 |
| What Is A Mamba Model? / IBM | web | web_snippet | 4 / 4 |

**4. How is training efficiency measured and compared for state space models, transformers, and Mamba?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| An Empirical Study of Mamba-based Language Models | paper | full_text | 4 / 5 |
| Benchmarking the Computational and Representational Efficiency of State Space Models against Tr | paper | full_text | 2 / 4 |
| MAMBA: SSM model as alternative to the transformers | paper | full_text | 4 / 5 |
| Rethinking Token Reduction for State Space Models | paper | full_text | 5 / 5 |
| Transformers are SSMs: Generalized Models and Efficient Algorithms Through Structured State Spa | paper | full_text | 5 / 5 |
| A hybrid model based on transformer and Mamba for enhanced sequence modeling / Scientific Repor | web | web_snippet | 1 / 1 |
| Mamba: New Selective State Space Model vs Transformer | web | web_snippet | 0 / 0 |
| Repeat After Me: Transformers are Better than State Space Models at Copying - Kempner Institute | web | web_snippet | 2 / 3 |

**5. How is long-sequence performance measured and compared for state space models, transformers, and Mamba?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| An Empirical Study of Mamba-based Language Models | paper | full_text | 3 / 4 |
| Efficiently Modeling Long Sequences with Structured State Spaces | paper | full_text | 5 / 5 |
| Mamba-360: Survey of State Space Models as Transformer Alternative for Long Sequence Modelling: | paper | full_text | 5 / 5 |
| Mamba: Linear-Time Sequence Modeling with Selective State Spaces | paper | full_text | 3 / 5 |
| SiMBA: Simplified Mamba-Based Architecture for Vision and Multivariate Time series | paper | full_text | 5 / 5 |
| Mamba-360: Survey of State Space Models as Transformer Alternative for Long Sequence Modelling: | web | web_snippet | 5 / 5 |
| Mamba-360: Survey of state space models as transformer alternative for long sequence modelling: | web | web_snippet | 2 / 3 |
| Repeat After Me: Transformers are Better than State Space Models at Copying - Kempner Institute | web | web_snippet | 3 / 3 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What are state space models and how do they work?

Sufficient: **True**; judge used: True; sources 8 (3 full text); judge candidates 22 = yes 12, partial 0, no 10, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | key components of a state space model | covered | 2 | 2 |
| 2 | parameters of a state space model | covered | 4 | 4 |
| 3 | advantages of state space models | covered | 4 | 4 |
| 4 | limitations of state space models | covered | 2 | 2 |

### 2. What are transformers and how do they work?

Sufficient: **False**; judge used: True; sources 4 (0 full text); judge candidates 17 = yes 6, partial 3, no 8, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the key components of a transformer model? | uncovered | 1 | 1 |
| 2 | What are the parameters of a transformer model? | uncovered | 0 | 0 |
| 3 | advantages of transformers | covered | 4 | 3 |
| 4 | limitations of transformers | uncovered | 1 | 1 |

Uncovered details: What are the key components and parameters of a transformer model?; What are the advantages and limitations of transformers?

### 3. What is Mamba and how does it relate to state space models and transformers?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 8, partial 1, no 9, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What is the main innovation or contribution of Mamba? | covered | 3 | 3 |
| 2 | How does Mamba incorporate state space models? | uncovered | 2 | 1 |
| 3 | How does Mamba incorporate transformers? | covered | 3 | 3 |

Uncovered details: How does Mamba incorporate state space models and transformers?

### 4. How is training efficiency measured and compared for state space models, transformers, and Mamba?

Sufficient: **False**; judge used: True; sources 7 (5 full text); judge candidates 39 = yes 12, partial 17, no 10, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the relevant metrics or indicators of training efficiency for state space models, transformers, and Mamba? | uncovered | 1 | 1 |
| 2 | How do state space models, transformers, and Mamba differ in training complexity? | uncovered | 0 | 0 |
| 3 | How do state space models, transformers, and Mamba differ in training speed? | covered | 3 | 3 |
| 4 | How do state space models, transformers, and Mamba differ in training resources? | uncovered | 1 | 1 |
| 5 | What are the empirical results or benchmarks of training efficiency for state space models? | covered | 3 | 3 |
| 6 | What are the empirical results or benchmarks of training efficiency for transformers? | covered | 2 | 2 |
| 7 | What are the empirical results or benchmarks of training efficiency for Mamba? | covered | 2 | 2 |

Uncovered details: What are the relevant metrics or indicators of training efficiency?; How do state space models, transformers, and Mamba differ in their training complexity, speed, and resources?

### 5. How is long-sequence performance measured and compared for state space models, transformers, and Mamba?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 1, partial 8, no 9, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the relevant metrics or indicators of long-sequence performance? | uncovered | 0 | 0 |
| 2 | How do state space models, transformers, and Mamba differ in their ability to handle long-range dependencies, attention, and context? | uncovered | 0 | 0 |
| 3 | What are the empirical results or benchmarks of long-sequence performance for state space models, transformers, and Mamba? | uncovered | 1 | 1 |

Uncovered details: What are the relevant metrics or indicators of long-sequence performance?; How do state space models, transformers, and Mamba differ in their ability to handle long-range dependencies, attention, and context?; What are the empirical results or benchmarks of long-sequence performance for state space models, transformers, and Mamba?

## 5. Retrieval details

- Web search variants: [11, 15, 14, 13, 12] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 122 candidates -> 99 cleared min_similarity (0.56) -> top 20 shortlisted; 146 candidates -> 111 cleared min_similarity (0.56) -> top 20 shortlisted; 128 candidates -> 106 cleared min_similarity (0.56) -> top 20 shortlisted; 119 candidates -> 110 cleared min_similarity (0.56) -> top 20 shortlisted; 113 candidates -> 106 cleared min_similarity (0.56) -> top 20 shortlisted
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 3
- Citation enrichment: Citation enrichment: 2 arXiv-only papers to enrich; took 1m 11s in total

## 6. Parsing details

- Attempted 21 papers, usable full text 18, 42 papers saved in the database.
- PDF obtained via: its own link: 6, Unpaywall: 4; parse cache hits: 7; Unpaywall OA links found: 4; landing-page citation_pdf_url: 0
- Individual download failures: 9 -> ValueError: 6, HTTPStatusError: 3
- Headless-browser fallback: 2 tried, 2 failed; Docling fetch-by-URL attempts: 2; HTML full-text attempts that failed: 2

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| Non-markovian state-space models in dependability evaluation | all PDF routes failed: HTTPStatusError: HTTPStatusError('403 Forbidden') |
| Transformer in Image Interpretation | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |

## 7. Groq and judge

- Stage 3: 36 digests for 5 sub-questions, 4 worker(s), 4 Groq key(s)
- Rate-limit parking events: 85; per key (events / parked seconds): ...KJJp: 24 / 301s, ...KaRe: 22 / 362s, ...X2Oj: 16 / 335s, ...x1nP: 23 / 338s
- Judge batch latencies (s): [18.0, 12.4, 15.6, 25.4, 6.7, 16.7]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 1 | All PDF URLs failed for <id>: HTTPStatusError: HTTPStatusError('<text>') |
| ERROR | 1 | All PDF URLs failed for <id>: ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| ERROR | 1 | Aspect split failed for '<text>': Expecting value: line N column N (char N) |
| WARNING | 6 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 3 | SN rate limited on batch, backing off Ns |
| WARNING | 3 | Failed to download from <url> HTTPStatusError: HTTPStatusError('<text>') |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | OpenAlex N on key ...CHgt for '<text>' (backoff N/N), pausing that key N.Ns |
| WARNING | 1 | PDFFigures parsing failed:  |
| WARNING | 1 | Playwright fallback failed: ValueError: ValueError('<text>') |
| WARNING | 1 | Playwright fallback failed: TimeoutError: TimeoutError('<text>') |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429) and citation enrichment still spent 1m 11s on 3 rate-limited batch calls.
- Sub-question 'What are transformers and how do they work?': no full-text digest (evidence is abstracts / web snippets only).
- 2 paper(s) could not be downloaded by any route.
- Groq rate limiting: 85 parking events; digest generation took 3m 45s.
- Longest phase: PDF download + Docling parsing (5m 42s, 29% of the run).

Warnings in the log: 18; errors: 3.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand after reading the log and the database)

**Bottom line.** Same result as run 1 in the numbers that matter: 1 of 5 sub-questions "sufficient", and that one is again the one built on the wrong evidence. The infrastructure fixes worked (Scopus is back, no database error, no judge error); the problems that remain are in what gets searched (Stage 1), what the relevance judge lets through (Stage 2), and how strictly V2 judges comparison aspects (Stage 3).

### Comparison with run 1 (same question, 11:32)

| | Run 1 | Run 2 |
|---|---|---|
| Total time | 18m 44s | 19m 31s |
| Paper candidates / kept | 306 / 47 | 628 / 42 (Scopus 18, OpenAlex 18, both 4, arXiv 2) |
| Web sources | 66 | 65 |
| Papers attempted for parsing / usable full text | 25 / 19 | 21 / 18 (7 from the parse cache) |
| Papers with no usable text | 6 (5 download failures + 1 database error) | 2 |
| Digests (full text / abstract / web) | 35 (19 / 1 / 15) | 36 (18 / 3 / 15) |
| Findings verified / total | 101 / 126 | 114 / 134 |
| Judge pairs / failed verdicts | 104 / 1 | 114 / 0 |
| Sub-questions sufficient | 1 of 5 | 1 of 5 |
| Groq parking events | 73 | 85 |
| Parsing / Stage 3 prep / digests / judge+coverage | 6m 38 / 3m 10 / 3m 07 / 1m 33 | 5m 42 / 3m 32 / 3m 45 / 1m 38 |

The planner is not deterministic: sub-questions 1-3 are the same as in run 1, but sub-questions 4 and 5 are different ("How is training efficiency measured and compared..." and "How is long-sequence performance measured and compared..."; the planner split the two dimensions of the question itself). So the two runs are not an exact A/B.

### Checklist from run 1

- [x] Scopus router answers: used, 18 of the 42 kept papers come from Scopus (628 candidates against 306).
- [x] No `\u0000` database error. Caveat: the paper that had the NUL characters was not in this shortlist, so the fix was not exercised.
- [x] No judge verdict error (0 of 114). The new per-item logging was therefore not exercised either.
- [ ] Sub-question 2 (transformers) gets papers: NO. 1 of 20 passed ("Transformer in Image Interpretation", abstract only, download failed); 19 were rejected, the examples are again electrical-power transformers.
- [ ] Sub-question 1 papers are about Mamba / S4: NO. Its sources are again macroeconometrics, ecology, "Statistical Software for State Space Methods", "State Space Models in R" and a dependability paper; two web snippets help. It is "sufficient" on that evidence.
- [ ] A central aspect one paper can answer: NO, see below.
- [ ] No 429 retries in enrichment: still 1m 11s for 2 papers (3 retries). Left as is by decision.

### What is still wrong

1. **Stage 1 does not disambiguate "state space models" and "transformers"** (unchanged from run 1, now confirmed on a second run). Sub-question 1 is covered by statistics / econometrics / ecology papers, sub-question 2 has web snippets only. Fix direction: put the domain from the original question into the planner's sub-questions and queries.

2. **V2 makes the central comparison sub-questions uncoverable** (the biggest new finding). Sub-question 5 (long-sequence performance): 18 candidates, 1 "yes", 8 "partial"; sub-question 4: 12 yes, 17 partial. The judge's reasons show one pattern: the aspect names three entities ("state space models, transformers, and Mamba") and a claim about one of them is "partial" ("the claim only addresses Mamba rather than the general aspect", "fails to cover the 'state space models' part", "only provides a specific result for one model"). This is the V2 clause "the right kind of answer but about a variant, a specific system or a special case when the aspect asks about the topic in general" applied to an aspect that lists the systems. One verdict also contradicts itself: SiMBA, "the claim directly answers the aspect by listing the specific metrics used" is recorded as partial. Same V2 behaviour as in the held-out test (specific result for a broad aspect = partial), now with real consequences. A V2.1 would have to limit that clause to variants of one subject and treat a multi-entity aspect as answered by a claim about any of the entities; it needs fresh rows to test on.

3. **More candidates did not mean more full text.** Scopus doubled the candidates (628) but only 1 of the 18 Scopus papers has parsed text (abstract-only evidence), and the top-20 shortlist now holds only 2 arXiv-only papers (10 in run 1), so the number of full-text papers did not grow (18 against 19). The 3 abstract digests are the visible trace.

4. **One aspect split failed** ("empirical results or benchmarks of long-sequence ...", the model returned invalid JSON twice); it fell back to the unsplit detail, which is the intended fallback, but it left an aspect with the wording of the whole detail.

### What worked

- Aspect merge fix: the sub-questions now have 4, 4, 3, 7 and 3 aspects with no detail question missing; sub-question 4 has seven because its details were split by dimension.
- 0 database errors, 0 judge errors, only 2 papers without text (both abstract fallbacks), parse cache saved about one minute (7 hits).
- Judge V2 ran 6 batches in 7-25 s each (114 pairs), the coverage rows were written with `aspect_merge` recorded in `judge_stats`.

### Where the time went (19m 31s)

PDF download + Docling parsing 5m 42s (29%), digest generation 3m 45s (19%, 85 Groq parking events), Stage 3 preparation 3m 32s (18%), pre-filter + relevance judge 1m 57s (10%; 628 candidates to embed instead of 306), judge + coverage 1m 38s (8%), citation enrichment 1m 11s (6%).

### Next checks

- [ ] Stage 1 queries carry the deep-learning context; sub-questions 1 and 2 retrieve Mamba / S4 / Transformer papers.
- [ ] A multi-entity comparison aspect gets at least 2 "yes" (V2.1 test or a different aspect wording).
- [ ] Fraction of Scopus papers with full text (here 1 of 18).

(Regenerate the tables with `python scripts/pipeline_run_report.py`; these notes are kept.)
