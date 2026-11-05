# Pipeline run report - How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance?

Generated 2026-11-05 12:30 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (last run in the file) and the database. Query id `d31c7e52-6a16-464c-bbcd-a881d8dd24ee`.

## 1. Summary

| | |
|---|---|
| Question | How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance? |
| Started / finished | 2026-11-05 11:32:35 / 11:51:19 |
| **Total execution time** | **18m 44s** (1124 s) |
| Sub-questions / search queries | 5 / 15 (per sub-question [3, 3, 3, 3, 3]) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 306 candidates -> 176 cleared the similarity floor -> 100 shortlisted |
| **Papers kept after the relevance judge** | **47** (log: 47); 53 shortlisted papers rejected |
| **Web sources** | **66** (per sub-question [12, 15, 13, 14, 12]) |
| Papers attempted for parsing | 25 (top-N per sub-question) |
| **Papers parsed to usable full text** | **19** of 25 attempted (1 from the parse cache) |
| Papers not parsed (all routes failed) | 5 download/route failures + 1 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 15 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 35 (19 from full text, 1 from abstracts, 15 from web snippets) |
| Findings (verified / total) | 101 / 126 |
| Coverage sufficient | 1 of 5 sub-questions |
| Judge | 1m 26s in 5 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 73 parking events, 1487 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 11:32:35 | 11:33:18 | 43s | 4% |
| Web search (Tavily) | 11:33:18 | 11:33:35 | 17s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 11:33:35 | 11:34:13 | 38s | 3% |
| Embedding pre-filter + relevance judge | 11:34:13 | 11:35:41 | 1m 28s | 8% |
| Citation enrichment (Semantic Scholar) | 11:35:42 | 11:36:49 | 1m 07s | 6% |
| Store papers in the database | 11:36:49 | 11:36:51 | 2s | 0% |
| PDF download + Docling parsing | 11:36:51 | 11:43:28 | 6m 38s | 35% |
| Stage 3 preparation (aspect split, chunking, embedding) | 11:43:28 | 11:46:38 | 3m 10s | 17% |
| Stage 3 digest generation (Groq) | 11:46:38 | 11:49:45 | 3m 07s | 17% |
| Stage 3 judge + coverage (per sub-question) | 11:49:45 | 11:51:18 | 1m 33s | 8% |
| **Total** | 11:32:35 | 11:51:19 | **18m 44s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What are state space models and how do they work? | 50 -> 24 -> 20 | 10 of 20 | 4 | 12 | 8 (4 / 1 / 3) | 22 / 31 | sufficient |
| 2 | What are transformers and how do they work? | 79 -> 37 -> 20 | 0 of 20 | 0 | 15 | 3 (0 / 0 / 3) | 8 / 8 | NOT sufficient |
| 3 | What is Mamba and how does it relate to state space models and transformers? | 44 -> 40 -> 20 | 18 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 20 / 25 | NOT sufficient |
| 4 | What are the metrics and methods for measuring training efficiency and long-sequence performance? | 76 -> 50 -> 20 | 8 of 20 | 5 | 14 | 8 (5 / 0 / 3) | 25 / 29 | NOT sufficient |
| 5 | How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance? | 57 -> 25 -> 20 | 11 of 20 | 5 | 12 | 8 (5 / 0 / 3) | 26 / 33 | NOT sufficient |

- Relevance judge rejected 10 papers for [What are state space models and how do t]. Examples: 'SSpace: A Toolbox for State Space Modeling' (The paper describes a software toolbox for implementing models rather than explaining the theoretical concepts and mechanisms of state space); 'TheState Space ModelsToolbox forMATLAB' (The paper describes a software toolbox for implementing state space models rather than explaining their theoretical definitions or operation); 'State Space Models inR' (The paper focuses on software implementation in R rather than explaining the theoretical concepts and mechanics of state space models.)
- Relevance judge rejected 17 papers for [What are transformers and how do they wo]. Examples: 'Transforming the transformer' (The paper discusses electrical transformers, not the Transformer neural network architecture.); 'History: The Transformer' (The paper discusses electrical transformers, whereas the research question asks about transformer neural networks.); 'Toroidal Transformer and Its Application' (The paper discusses a specific type of electrical transformer rather than the Transformer architecture used in deep learning.)
- Relevance judge rejected 2 papers for [What is Mamba and how does it relate to ]. Examples: 'S-Mamba: Pressure-Driven State Model' (The paper focuses on a physics-inspired pressure-driven model for recurrent states rather than explaining Mamba's relationship to state spac); 'Hidden-State�Driven Survival Modeling with Mamba' (The paper focuses on survival modeling applications rather than explaining Mamba's architecture or its relationship to state space models an)
- Relevance judge rejected 12 papers for [What are the metrics and methods for mea]. Examples: 'Learning Evaluation Models From Large Language Models for Se' (The paper focuses on developing new evaluation metrics for sequence quality rather than measuring training efficiency or long-sequence perfo); 'Sequence Level Training with Recurrent Neural Networks' (The paper focuses on improving generation quality via sequence-level training rather than defining metrics or methods for measuring training); 'Demystifying productivity and performance' (The paper focuses on defining general business terminology rather than providing specific metrics or methods for training efficiency or long)
- Relevance judge rejected 9 papers for [How do state space models like Mamba com]. Examples: 'State Space Models are Comparable to Transformers in Estimat' (The paper provides a theoretical analysis of function estimation capabilities rather than empirical evidence on training efficiency or long-); 'A Best Match Is Not a Twin: What Feature Similarity Between ' (The paper focuses on feature similarity and measurement methodology rather than comparing training efficiency or long-sequence performance.); 'The Illusion of State in State-Space Models' (The paper focuses on theoretical expressiveness limitations rather than comparing training efficiency or long-sequence performance metrics.)

### Sources behind each sub-question's digests

**1. What are state space models and how do they work?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| BAYESIAN STATE SPACE MODELS IN MACROECONOMETRICS | paper | full_text | 5 / 5 |
| SSMMATLAB: A Set ofMATLABPrograms for the Statistical Analysis of State Space Models | paper | full_text | 2 / 3 |
| State Space Representation of Dynamical Systems | paper | full_text | 2 / 5 |
| State‐space models for ecological time‐series data: Practical model‐fitting | paper | full_text | 0 / 5 |
| State Space Model - an overview | web | web_snippet | 2 / 2 |
| State Space Models as Foundation Models:A Control Theoretic Overview | web | web_snippet | 3 / 3 |
| Statistical algorithms for models in state space using SsfPack 2.2 | paper | abstract | 5 / 5 |
| What Are State Space Models? / IBM | web | web_snippet | 3 / 3 |

**2. What are transformers and how do they work?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| 9  Transformers – 6.390 - Intro to Machine Learning | web | web_snippet | 4 / 4 |
| [2304.10557] An Introduction to Transformers | web | web_snippet | 4 / 4 |
| [2510.03989] A Mathematical Explanation of Transformers | web | web_snippet | 0 / 0 |

**3. What is Mamba and how does it relate to state space models and transformers?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Visual Mamba | paper | full_text | 2 / 5 |
| Mamba: Linear-Time Sequence Modeling with Selective State Spaces | paper | full_text | 1 / 3 |
| MoE-Mamba: Efficient Selective State Space Models with Mixture of Experts | paper | full_text | 3 / 3 |
| VL-Mamba: Exploring State Space Models for Multimodal Learning | paper | full_text | 5 / 5 |
| Vision Mamba: Efficient Visual Representation Learning with Bidirectional State Space Model | paper | full_text | 3 / 3 |
| A hybrid model based on transformer and Mamba for enhanced sequence modeling / Scientific Repor | web | web_snippet | 2 / 2 |
| Repeat After Me: Transformers are Better than State Space Models at Copying - Kempner Institute | web | web_snippet | 1 / 1 |
| What Is A Mamba Model? / IBM | web | web_snippet | 3 / 3 |

**4. What are the metrics and methods for measuring training efficiency and long-sequence performance?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Efficiently Modeling Long Sequences with Structured State Spaces | paper | full_text | 4 / 4 |
| Never Train from Scratch: Fair Comparison of Long-Sequence Models Requires Data-Driven Priors | paper | full_text | 2 / 3 |
| Simplified State Space Layers for Sequence Modeling | paper | full_text | 1 / 3 |
| Teacher Retains Full Tokens, Student Merges Efficiently: TM20K for E-Commerce Sequence Modeling | paper | full_text | 5 / 5 |
| Training Compute-Optimal Protein Language Models | paper | full_text | 4 / 5 |
| Exploring the Landscape for Generative Sequence Models for Specialized Data Synthesis | web | web_snippet | 2 / 2 |
| Introduction to Sequence Modeling with Transformers | web | web_snippet | 3 / 3 |
| Optimization of sequence modeling algorithm and long-range dependency handling based on dynamic | web | web_snippet | 4 / 4 |

**5. How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Hungry Hungry Hippos: Towards Language Modeling with State Space Models | paper | full_text | 5 / 5 |
| MoE-Mamba: Efficient Selective State Space Models with Mixture of Experts | paper | full_text | 1 / 4 |
| SiMBA: Simplified Mamba-Based Architecture for Vision and Multivariate Time series | paper | full_text | 5 / 5 |
| State space model for new generation network alternative to transformers: a survey | paper | full_text | 3 / 4 |
| Transformers are SSMs: Generalized Models and Efficient Algorithms Through Structured State Spa | paper | full_text | 3 / 5 |
| Mamba-360: Survey of state space models as transformer alternative for long sequence modelling: | web | web_snippet | 5 / 5 |
| Repeat After Me: Transformers are Better than State Space Models at Copying - Kempner Institute | web | web_snippet | 3 / 3 |
| State Space Models are Provably Comparable to Transformers in Dynamic Token Selection | web | web_snippet | 1 / 2 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What are state space models and how do they work?

Sufficient: **True**; judge used: True; sources 7 (3 full text); judge candidates 24 = yes 11, partial 2, no 11, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What is the mathematical formulation of state space models? | covered | 2 | 2 |
| 2 | What are the main components of state space models? | covered | 2 | 2 |
| 3 | advantages of state space models | covered | 4 | 3 |
| 4 | limitations of state space models | covered | 3 | 3 |

### 2. What are transformers and how do they work?

Sufficient: **False**; judge used: True; sources 2 (0 full text); judge candidates 20 = yes 6, partial 1, no 13, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What is the mathematical formulation of transformers? | uncovered | 0 | 0 |
| 2 | What are the main components of transformers? | uncovered | 1 | 1 |
| 3 | What are the parameters of transformers? | uncovered | 0 | 0 |
| 4 | advantages of transformers | covered | 4 | 2 |
| 5 | limitations of transformers | uncovered | 1 | 1 |

Uncovered details: What is the mathematical formulation of transformers?; What are the main components and parameters of transformers?; What are the advantages and limitations of transformers?

### 3. What is Mamba and how does it relate to state space models and transformers?

Sufficient: **False**; judge used: False; sources 8 (5 full text); judge candidates 26 = yes 13, partial 8, no 4, error 1; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | motivation of Mamba | covered | 3 | 3 |
| 2 | design of Mamba | covered | 6 | 4 |
| 3 | How does Mamba use state space models to achieve linear complexity? | uncovered | 1 | 1 |
| 4 | How does Mamba use state space models to achieve selective attention? | unjudged | 1 | 1 |
| 5 | How does Mamba compare to transformers in terms of architecture? | covered | 2 | 2 |

Uncovered details: How does Mamba use state space models to achieve linear complexity and selective attention?

### 4. What are the metrics and methods for measuring training efficiency and long-sequence performance?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 22 = yes 4, partial 5, no 13, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the common training objectives for sequence modeling tasks? | uncovered | 0 | 0 |
| 2 | What are the common losses for sequence modeling tasks? | uncovered | 0 | 0 |
| 3 | What are the common evaluation tasks for sequence modeling tasks? | uncovered | 1 | 1 |
| 4 | What are the common datasets for sequence modeling tasks? | uncovered | 0 | 0 |
| 5 | how training efficiency is defined and measured | covered | 2 | 2 |
| 6 | how long-sequence performance is defined and measured | uncovered | 1 | 1 |

Uncovered details: What are the common training objectives and losses for sequence modeling tasks?; What are the common evaluation tasks and datasets for sequence modeling tasks?; How are training efficiency and long-sequence performance defined and measured?

### 5. How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 12 = yes 2, partial 7, no 3, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the empirical results and findings from existing studies or benchmarks regarding how state space models like Mamba compare with transformers in training efficiency and long‑sequence performance? | uncovered | 1 | 1 |
| 2 | What are the open challenges for state space models and transformers? | uncovered | 1 | 1 |

Uncovered details: What are the empirical results and findings from existing studies or benchmarks?; What are the open challenges and future directions for state space models and transformers?

## 5. Retrieval details

- Web search variants: [12, 15, 13, 14, 12] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 50 candidates -> 24 cleared min_similarity (0.56) -> top 20 shortlisted; 79 candidates -> 37 cleared min_similarity (0.56) -> top 20 shortlisted; 44 candidates -> 40 cleared min_similarity (0.56) -> top 20 shortlisted; 76 candidates -> 50 cleared min_similarity (0.56) -> top 20 shortlisted; 57 candidates -> 25 cleared min_similarity (0.56) -> top 20 shortlisted
- Scopus: UNAVAILABLE - Scopus unavailable, skipping it for this run: /scopus/search returned HTTP 404: {"detail":"Not Found"}
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 3
- Citation enrichment: Citation enrichment: 10 arXiv-only papers to enrich; took 1m 07s in total

## 6. Parsing details

- Attempted 25 papers, usable full text 19, 47 papers saved in the database.
- PDF obtained via: its own link: 15, Unpaywall: 3; parse cache hits: 1; Unpaywall OA links found: 5; landing-page citation_pdf_url: 2
- Individual download failures: 15 -> HTTPStatusError: 11, ValueError: 4
- Headless-browser fallback: 5 tried, 5 failed; Docling fetch-by-URL attempts: 7; HTML full-text attempts that failed: 3

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| Statistical algorithms for models in state space using SsfPack 2.2 | all PDF routes failed: HTTPStatusError: HTTPStatusError('403 Forbidden') |
| Formulating State Space Models inRwith Focus on Longitudinal Regression Models | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |
| State Space Modeling in an Open Source, Modular, Structural Equation Modeling Environment | all PDF routes failed: HTTPStatusError: HTTPStatusError('403 Forbidden') |
| Improved state‐space models for inference about spatial and temporal variation in abundanc | all PDF routes failed: HTTPStatusError: HTTPStatusError('403 Forbidden') |
| Exact Score for Time Series Models in State Space Form | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |
| A guide to state–space modeling of ecological time series | parse/database error: {'message': 'unsupported Unicode escape sequence', 'code': '22P05', 'hint': None, 'details': '\\u0000 cannot b |

## 7. Groq and judge

- Stage 3: 35 digests for 5 sub-questions, 4 worker(s), 4 Groq key(s)
- Rate-limit parking events: 73; per key (events / parked seconds): ...KJJp: 19 / 411s, ...KaRe: 16 / 349s, ...X2Oj: 18 / 375s, ...x1nP: 20 / 352s
- Judge batch latencies (s): [19.0, 16.4, 21.2, 18.0, 11.7]

- Judge verdicts that came back as error: 1 -> aspect 4 of 'Mamba: Linear-Time Sequence Modeling wit': 

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 3 | All PDF URLs failed for <id>: HTTPStatusError: HTTPStatusError('<text>') |
| ERROR | 2 | All PDF URLs failed for <id>: ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| ERROR | 1 | Failed to parse paper <id>: {'message': '<text>', 'code': 'NPN', 'hint': None, 'details': '<text>'} |
| WARNING | 11 | Failed to download from <url> HTTPStatusError: HTTPStatusError('<text>') |
| WARNING | 5 | Playwright fallback failed: ValueError: ValueError('<text>') |
| WARNING | 4 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 3 | SN rate limited on batch, backing off Ns |
| WARNING | 1 | Scopus unavailable, skipping it for this run: /scopus/search returned HTTP N: {"detail":"Not Found"} |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | Unpaywall route failed for '<text>': ValueError: Non-PDF response (content-type: text/html) for <url> |

## 9. Checks (rule based, from the log)

- Scopus was unavailable (host returned 404 for /scopus/search): no Scopus papers in this run.
- Semantic Scholar search was skipped (probe returned 429) and citation enrichment still spent 1m 07s on 3 rate-limited batch calls.
- Sub-question [What are transformers and how do they wo]: 0 of 20 shortlisted papers passed the relevance judge; it has web sources only.
- Sub-question 'What are transformers and how do they work?': no full-text digest (evidence is abstracts / web snippets only).
- Sub-question 'What is Mamba and how does it relate to state space models and transformers?': 1 unjudged aspect(s) (a judge verdict failed): ['How does Mamba use state space models to achieve selective attention?']
- 1 paper(s) failed at the parse/database step: A guide to state–space modeling of ecological time ({'message': 'unsupported Unicode escape sequence', 'code': '22P05', 'hint': None)
- 5 paper(s) could not be downloaded by any route.
- Groq rate limiting: 73 parking events; digest generation took 3m 07s.
- Longest phase: PDF download + Docling parsing (6m 38s, 35% of the run).

Warnings in the log: 27; errors: 6.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand after reading the log and the database)

**Bottom line.** The pipeline ran end to end in 18m 44s with no crash, but the result is weaker than the numbers suggest: 1 of 5 sub-questions is "sufficient", and that one rests on the wrong kind of evidence. Most problems are in Stage 1 and Stage 2 (what gets searched and kept), not in Stage 3. Stage 3 itself behaved as designed: the judge ran on all 5 sub-questions (104 pairs, 1 failed verdict), the correct passage reached it, and the coverage rows were written.

### What went wrong, in order of impact

1. **"State space models" and "transformers" were ambiguous, and Stage 1 did not disambiguate.**
   - Sub-question 2 ("What are transformers and how do they work?"): the queries "transformers overview" and "transformers mathematical formulation" returned electrical-power-transformer papers. The relevance judge rejected all 20 shortlisted papers (correctly: "discusses electrical transformers, not the Transformer neural network"). The sub-question therefore has web snippets only (3 digests, 0 full text) and 4 of its 5 aspects are uncovered.
   - Sub-question 1 ("What are state space models..."): 10 of 20 papers passed, and all 10 that were attempted for parsing are statistical, econometric, ecological or control-theory papers (SsfPack, SSMMATLAB, State Space Models in R, ecological time series, macroeconometrics, Structural Equation Modeling), none about S4 or Mamba. They produced all 6 parse/download failures and part of the 6m 38s parsing time. The sub-question is marked "sufficient" on that evidence (plus 3 web snippets), which does not answer the user's question about Mamba. One of its full-text digests (ecological time series) has 0 of 5 verified findings.
   - The same happened in a milder form in sub-question 4: "Training Compute-Optimal Protein Language Models" and "TM20K for E-Commerce Sequence Modeling" were parsed and digested as evidence for "metrics for training efficiency and long-sequence performance". Its aspects on objectives, losses, tasks and datasets are all uncovered because the sub-question is about generic "sequence modeling".
   - Fix direction: the planner's queries need the domain from the original question ("deep learning", "neural", "Mamba", "S4"); the relevance judge could also be given the original question, not only the sub-question.

2. **The central comparison question (sub-question 5) cannot be covered as its aspects were built.** (Merge part FIXED 2026-11-05: aspects are no longer merged by embedding similarity, see `ASPECT_MERGE`; the two-part wording of the first aspect is still open.)
   - The aspect merge (cosine >= 0.92) collapsed three detail questions (empirical results, theoretical explanations, insights) into one long aspect, leaving 2 aspects: one that asks for results on BOTH training efficiency AND long-sequence performance, and one on open challenges.
   - V2 judged 7 of 12 candidate claims "partial", and the reasons say the same thing: the claim covers one half (only training efficiency, or only long-sequence tracking) or "one specific aspect rather than comprehensive". This is the V2 behaviour seen in the held-out test (a single concrete result is judged partial for a broad aspect), made worse by the merged two-part aspect.
   - 5 full-text sources (Hungry Hungry Hippos, MoE-Mamba, SiMBA, the survey, Transformers are SSMs) and 3 web snippets back this sub-question, so the evidence exists; the coverage rule does not credit it. This is the sub-question that matters most for the user's question and it ends up "not sufficient" with 1 yes per aspect.

3. **Scopus was unavailable** (`/scopus/search` returned 404 on the host). Most likely the host rebuild for the judge prompt dropped the Scopus router that was deployed earlier (not verified). No Scopus papers in this run; earlier runs got about 45% of their papers from Scopus.

4. **Semantic Scholar:** the probe failed with 429, so the search was skipped, but citation enrichment still made three batch calls with 5 s, 10 s and 20 s back-offs and got nothing: 1m 07s (6% of the run) for 10 arXiv-only papers that stayed unenriched. Decision (2026-11-05): leave enrichment as it is. It usually succeeds in other runs and the citation counts for the arXiv papers are needed, so it should not be switched off by the search breaker; this run's 1m 07s was a bad moment on the Semantic Scholar side.

5. **One paper lost to a database error:** `\u0000 cannot be converted to text` (Postgres 22P05) while storing "A guide to state-space modeling of ecological time series". The parsed text contained NUL characters; they should be stripped before the insert. FIXED 2026-11-05: `db_service.strip_nul` now removes NUL characters from every text write (parsed papers, retrieved papers, web sources, digests, coverage) and logs how many were removed from a parsed paper.

6. **One judge verdict failed** (sub-question 3, aspect 4 "selective attention", on the Mamba paper), so that aspect is "unjudged", `judge_used` is False and the sub-question is not sufficient. The reason for the failure was not recorded (the stored reason is empty). The judge call has no per-item error logging; FIXED 2026-11-05: each failed judge verdict is now logged with aspect, source, claim and reason (including the raw output), the stored reason is never empty, a batch summary line is logged, and a short server answer no longer drops items silently.

7. **Groq rate limiting** dominated Stage 3: 73 parking events across the 4 keys (about 350-410 s parked per key), digest generation took 3m 07s for 35 digests. The 4 keys sit at similar limits, which suggests the limit is per organization or per model rather than per key (the earlier note about keys from the same account). Run 7 had 9 digests in 40 s; here the load was 4 times higher.

### What worked

- Planner: 5 sub-questions, 15 queries ([3, 3, 3, 3, 3]), 43 s.
- Parsing recovered papers through other routes: of 25 attempted, 19 usable (15 through their own link, 3 through Unpaywall, 1 from the parse cache); 2 papers found through the landing page's citation_pdf_url. The 6 failures were all non-deep-learning papers, so they cost time but not evidence you needed.
- Stage 3 pipeline mechanics: the digest cache, the passage fix, the judge on V2 (batches of 12-21 s), the coverage rows with `judge_stats`, `aspect_evidence` and `uncovered_reasons` were all written.
- Deep-learning SSM evidence is good where it was retrieved: the Mamba sub-question has 5 full-text Mamba papers; sub-question 4 has S4, S5 and "Never Train from Scratch".

### Where the time went (18m 44s)

PDF download + Docling parsing 6m 38s (35%), Stage 3 preparation 3m 10s (17%), digest generation 3m 07s (17%), judge + coverage 1m 33s (8%), pre-filter + relevance judge 1m 28s (8%), citation enrichment 1m 07s (6%), the rest under 1m each. The two avoidable items in this run: parsing off-topic statistics papers (about 10 of the 25 attempts) and the 1m 07s of Semantic Scholar enrichment.

### Checklist for the next run of this question

- [ ] Scopus router answers on the host (`/scopus/status`).
- [ ] Sub-question 2 gets papers (neural-network context in its queries).
- [ ] Sub-question 1 papers are about Mamba / S4 / deep SSMs, not econometrics.
- [ ] Sub-question 5 has aspects that one paper can answer (not "efficiency AND long-sequence").
- [ ] No `\u0000` error; no judge verdict error; no 429 retries in enrichment.
- [ ] Compare: total time (18m 44s), papers kept (47), full texts (19 of 25), sufficient sub-questions (1 of 5), Groq parking events (73).

(To regenerate the tables above after another run: `python scripts/pipeline_run_report.py`; these notes are kept.)
