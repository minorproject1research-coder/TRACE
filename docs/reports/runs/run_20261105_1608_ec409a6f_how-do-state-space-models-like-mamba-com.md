# Pipeline run report - How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance?

Generated 2026-11-05 16:37 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (last run in the file) and the database. Query id `ec409a6f-c408-4679-8190-26aa343c716e`.

## 1. Summary

| | |
|---|---|
| Question | How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance? |
| Domain anchor | 'deep learning' ends 12 of 12 stored queries (the log line is missing) |
| Started / finished | 2026-11-05 16:08:51 / 16:31:27 |
| **Total execution time** | **22m 36s** (1356 s) |
| Sub-questions / search queries | 4 / 17 (per sub-question [3, 3, 3, 3]) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 451 candidates -> 415 cleared the similarity floor -> 80 shortlisted |
| **Papers kept after the relevance judge** | **40** (log: 40); 40 shortlisted papers rejected |
| **Web sources** | **44** (per sub-question [9, 12, 11, 12]) |
| Papers attempted for parsing | 22 (top-N per sub-question) |
| **Papers parsed to usable full text** | **20** of 22 attempted (11 from the parse cache) |
| Papers not parsed (all routes failed) | 2 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 9 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 32 (20 from full text, 0 from abstracts, 12 from web snippets) |
| Findings (verified / total) | 90 / 112 |
| Coverage sufficient | 2 of 4 sub-questions |
| Judge | 1m 14s in 4 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 85 parking events, 1390 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 16:08:51 | 16:11:39 | 2m 48s | 12% |
| Web search (Tavily) | 16:11:39 | 16:12:22 | 43s | 3% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 16:12:22 | 16:13:58 | 1m 36s | 7% |
| Embedding pre-filter + relevance judge | 16:13:58 | 16:15:34 | 1m 35s | 7% |
| Citation enrichment (Semantic Scholar) | 16:15:34 | 16:15:45 | 11s | 1% |
| Store papers in the database | 16:15:45 | 16:15:46 | 1s | 0% |
| PDF download + Docling parsing | 16:15:46 | 16:22:45 | 6m 58s | 31% |
| Stage 3 preparation (aspect split, chunking, embedding) | 16:22:45 | 16:26:55 | 4m 11s | 18% |
| Stage 3 digest generation (Groq) | 16:26:55 | 16:30:11 | 3m 15s | 14% |
| Stage 3 judge + coverage (per sub-question) | 16:30:11 | 16:31:26 | 1m 16s | 6% |
| **Total** | 16:08:51 | 16:31:27 | **22m 36s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What are state space models and how do they work? | 99 -> 93 -> 20 | 6 of 20 | 5 | 9 | 8 (5 / 0 / 3) | 27 / 34 | sufficient |
| 2 | What are transformers and how do they work? | 123 -> 110 -> 20 | 9 of 20 | 5 | 12 | 8 (5 / 0 / 3) | 22 / 27 | NOT sufficient |
| 3 | What is Mamba and how does it relate to state space models and transformers? | 121 -> 115 -> 20 | 16 of 20 | 5 | 11 | 8 (5 / 0 / 3) | 22 / 29 | sufficient |
| 4 | How do state space models and transformers compare in training efficiency? | 108 -> 97 -> 20 | 9 of 20 | 5 | 12 | 8 (5 / 0 / 3) | 19 / 22 | NOT sufficient |

- Relevance judge rejected 14 papers for [What are state space models and how do t]. Examples: 'Structured Inference Networks for Nonlinear State Space Mode' (The paper focuses on learning algorithms for Gaussian state space models rather than explaining the fundamental concepts and mechanisms of m); 'Latent Matters: Learning Deep State-Space Models' (The paper focuses on training dynamics and system identification for classical deep state-space models rather than explaining the architectu); 'Deep State Space Models for Time Series Forecasting' (The paper focuses on time series forecasting applications rather than explaining the fundamental definition and mechanics of state space mod)
- Relevance judge rejected 11 papers for [What are transformers and how do they wo]. Examples: 'Design of efficient distribution transformer: A deep learnin' (The paper discusses electrical distribution transformers, not the neural network architecture known as transformers.); 'Hybrid Embedding and Transformer-based Text and Vision Archi' (The paper focuses on performance comparisons and hybrid architectures rather than explaining the fundamental mechanisms of how transformers ); 'On reading and interpreting black box deep neural networks' (The paper focuses on interpreting and critiquing Transformer models as black boxes rather than explaining their fundamental architecture and)
- Relevance judge rejected 4 papers for [What is Mamba and how does it relate to ]. Examples: 'Mamba as a Motion Encoder for Robotic Imitation Learning' (The paper focuses on applying Mamba to robotic imitation learning rather than explaining its theoretical relationship to state space models ); 'VL-Mamba: Exploring State Space Models for Multimodal Learni' (The paper focuses on applying Mamba to multimodal learning tasks rather than explaining what Mamba is or its theoretical relationship to tra); 'CMMamba: channel mixing Mamba for time series forecasting' (The paper focuses on applying Mamba to time series forecasting rather than explaining what Mamba is or its theoretical relationship to state)
- Relevance judge rejected 11 papers for [How do state space models and transforme]. Examples: 'State Space Models are Comparable to Transformers in Estimat' (The paper focuses on theoretical estimation capabilities and convergence rates rather than comparing training efficiency.); 'The Illusion of State in State-Space Models' (The paper discusses theoretical expressiveness limitations rather than comparing training efficiency between state space models and transfor); 'Repeat After Me: Transformers are Better than State Space Mo' (The paper focuses on task performance (copying) and theoretical limitations rather than comparing training efficiency.)

### Sources behind each sub-question's digests

**1. What are state space models and how do they work?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Combining Recurrent, Convolutional, and Continuous-time Models with Linear State-Space Layers | paper | full_text | 5 / 5 |
| Deep State Space Models for Nonlinear System Identification | paper | full_text | 2 / 4 |
| Effectively Modeling Time Series with Simple Discrete State Spaces | paper | full_text | 3 / 5 |
| State space model: a magical tool for state prediction in Nonlinear systems | paper | full_text | 1 / 3 |
| Vision Mamba: A Comprehensive Survey and Taxonomy | paper | full_text | 5 / 5 |
| Aman's AI Journal • Primers • State Space Models | web | web_snippet | 4 / 5 |
| Deep Learning-based Approaches for State Space Models:A Selective Review | web | web_snippet | 3 / 3 |
| What Are State Space Models? / IBM | web | web_snippet | 4 / 4 |

**2. What are transformers and how do they work?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| An Introduction to Transformers | paper | full_text | 4 / 5 |
| DeLighT: Deep and Light-weight Transformer | paper | full_text | 3 / 4 |
| Deep learning model-transformer based wind power forecasting approach | paper | full_text | 3 / 5 |
| Introduction to Transformers: an NLP Perspective | paper | full_text | 5 / 5 |
| Simplifying Transformer Blocks | paper | full_text | 5 / 5 |
| 9  Transformers – 6.390 - Intro to Machine Learning | web | web_snippet | 0 / 0 |
| Deep Learning Essentials — (10) Transformers | web | web_snippet | 1 / 1 |
| What is a Transformer Model? / IBM | web | web_snippet | 1 / 2 |

**3. What is Mamba and how does it relate to state space models and transformers?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey of Mamba | paper | full_text | 2 / 4 |
| A Survey on Visual Mamba | paper | full_text | 5 / 5 |
| A hybrid model based on transformer and Mamba for enhanced sequence modeling | paper | full_text | 2 / 4 |
| Vision Mamba in Remote Sensing: A Comprehensive Survey of Techniques, Applications and Outlook | paper | full_text | 3 / 5 |
| Vision Mamba: A Comprehensive Survey and Taxonomy | paper | full_text | 4 / 4 |
| A hybrid model based on transformer and Mamba for enhanced sequence modeling / Scientific Repor | web | web_snippet | 0 / 1 |
| What Are State Space Models? / IBM | web | web_snippet | 3 / 3 |
| What Is A Mamba Model? / IBM | web | web_snippet | 3 / 3 |

**4. How do state space models and transformers compare in training efficiency?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| An Empirical Study of Mamba-based Language Models | paper | full_text | 2 / 2 |
| Hungry Hungry Hippos: Towards Language Modeling with State Space Models | paper | full_text | 1 / 1 |
| Mamba: Linear-Time Sequence Modeling with Selective State Spaces | paper | full_text | 5 / 5 |
| State space model for new generation network alternative to transformers: a survey | paper | full_text | 2 / 5 |
| Transformers are SSMs: Generalized Models and Efficient Algorithms Through Structured State Spa | paper | full_text | 5 / 5 |
| Mamba neural operator: Who wins? transformers vs. state-space models for PDEs | web | web_snippet | 1 / 1 |
| Repeat After Me: Transformers are Better than State Space Models at Copying - Kempner Institute | web | web_snippet | 1 / 1 |
| Repeat After Me: Transformers are Better than State Space Models at CopyingTransformers are Bet | web | web_snippet | 2 / 2 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What are state space models and how do they work?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 23 = yes 16, partial 0, no 7, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | key components of a state space model | covered | 4 | 4 |
| 2 | parameters of a state space model | covered | 5 | 5 |
| 3 | advantages of state space models | covered | 4 | 3 |
| 4 | limitations of state space models | covered | 3 | 3 |

### 2. What are transformers and how do they work?

Sufficient: **False**; judge used: True; sources 7 (5 full text); judge candidates 23 = yes 11, partial 3, no 9, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the key components of a transformer model? | covered | 2 | 2 |
| 2 | What are the parameters of a transformer model? | uncovered | 1 | 1 |
| 3 | advantages of transformers | covered | 5 | 4 |
| 4 | limitations of transformers | covered | 3 | 3 |

Uncovered details: What are the key components and parameters of a transformer model?

### 3. What is Mamba and how does it relate to state space models and transformers?

Sufficient: **True**; judge used: True; sources 7 (5 full text); judge candidates 23 = yes 12, partial 5, no 6, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What is the main innovation of Mamba? | covered | 4 | 4 |
| 2 | How does Mamba improve upon state space models? | covered | 3 | 3 |
| 3 | How does Mamba integrate with transformers? | covered | 3 | 3 |
| 4 | How does Mamba replace transformers? | covered | 2 | 2 |

### 4. How do state space models and transformers compare in training efficiency?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 23 = yes 5, partial 11, no 7, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | factors that affect the training efficiency of state space models and transformers | uncovered | 0 | 0 |
| 2 | How do state space models and transformers perform on different types of tasks and datasets (e.g., natural language processing, computer vision)? | uncovered | 0 | 0 |
| 3 | How does Mamba compare to state space models in training efficiency? | covered | 3 | 3 |
| 4 | How does Mamba compare to transformers in training efficiency? | covered | 2 | 2 |
| 5 | What are the challenges for measuring long-sequence performance when comparing state space models and transformers in training efficiency? | uncovered | 0 | 0 |
| 6 | What are the metrics for measuring long-sequence performance when comparing state space models and transformers in training efficiency? | uncovered | 0 | 0 |

Uncovered details: What are the factors that affect the training efficiency of state space models and transformers, e.g. computational complexity, memory usage, convergence speed, etc.?; How do state space models and transformers perform on different types of tasks and datasets, e.g. natural language processing, computer vision, etc.?; What are the challenges and metrics for measuring long-sequence performance, e.g. context length, retention, generalization, etc.?

## 5. Retrieval details

- Web search variants: [9, 12, 11, 12] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 99 candidates -> 93 cleared min_similarity (0.56) -> top 20 shortlisted; 123 candidates -> 110 cleared min_similarity (0.56) -> top 20 shortlisted; 121 candidates -> 115 cleared min_similarity (0.56) -> top 20 shortlisted; 108 candidates -> 97 cleared min_similarity (0.56) -> top 20 shortlisted
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0
- Citation enrichment: Citation enrichment: 1 arXiv-only papers to enrich; took 11s in total

## 6. Parsing details

- Attempted 22 papers, usable full text 20, 40 papers saved in the database.
- PDF obtained via: its own link: 5, Unpaywall: 2; parse cache hits: 11; Unpaywall OA links found: 3; landing-page citation_pdf_url: 0
- Individual download failures: 9 -> HTTPStatusError: 5, ValueError: 4
- Headless-browser fallback: 4 tried, 4 failed; Docling fetch-by-URL attempts: 5; HTML full-text attempts that failed: 3

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| A Historical Survey of Advances in Transformer Architectures | all PDF routes failed: HTTPStatusError: HTTPStatusError('403 Forbidden') |
| TransforLearn: Interactive Visual Tutorial for the Transformer Model | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |

## 7. Groq and judge

- Stage 3: 32 digests for 4 sub-questions, 4 worker(s), 4 Groq key(s)
- Rate-limit parking events: 85; per key (events / parked seconds): ...KJJp: 29 / 398s, ...KaRe: 18 / 315s, ...X2Oj: 16 / 291s, ...x1nP: 22 / 386s
- Judge batch latencies (s): [17.9, 17.8, 19.4, 19.0]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 1 | All PDF URLs failed for <id>: HTTPStatusError: HTTPStatusError('<text>') |
| ERROR | 1 | All PDF URLs failed for <id>: ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| ERROR | 1 | Digest generation failed: Expecting property name enclosed in double quotes: line N column N (char N) |
| WARNING | 8 | OpenAlex N on key ...CHgt for '<text>' (backoff N/N), pausing that key N.Ns |
| WARNING | 5 | OpenAlex N on key ...FsNG for '<text>' (backoff N/N), pausing that key N.Ns |
| WARNING | 5 | Failed to download from <url> HTTPStatusError: HTTPStatusError('<text>') |
| WARNING | 4 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 4 | Playwright fallback failed: ValueError: ValueError('<text>') |
| WARNING | 2 | OpenAlex gave up on '<text>' after N backoffs (last status N) |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | Unpaywall route failed for '<text>': ValueError: Non-PDF response (content-type: application/pdf) for <url> |
| WARNING | 1 | the OpenAlex content API route timed out after N s for '<text>' |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- 2 paper(s) could not be downloaded by any route.
- Groq rate limiting: 85 parking events; digest generation took 3m 15s.
- Longest phase: PDF download + Docling parsing (6m 58s, 31% of the run).

Warnings in the log: 32; errors: 3.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand after reading the log and the database)

**Bottom line.** The domain anchor did what it was built for. Sub-question 2 (transformers) went from 0-1 judge-passed papers to 9 of 20 with 5 full-text transformer papers, sub-question 1 now rests on Linear State-Space Layers, Simple Discrete State Spaces and the Vision Mamba survey instead of econometrics and ecology, and no statistics paper was parsed (so no parse failure from them). 2 of 4 sub-questions are "sufficient" (run 1 and 2: 1 of 5), and for the first time the central comparison has some covered aspects. The run was the slowest so far (22m 36s), for reasons that are not the anchor (below), and the central comparison is still only partly covered because the planner merge dropped the long-sequence dimension.

### Comparison of the three runs of this question

| | Run 1 (11:32) | Run 2 (14:00) | **Run 3 (16:08, anchor on)** |
|---|---|---|---|
| Total time | 18m 44s | 19m 31s | **22m 36s** |
| Sub-questions | 5 | 5 | 4 (one merged away) |
| Candidates / kept papers | 306 / 47 | 628 / 42 | 451 / 40 |
| Papers attempted / usable full text | 25 / 19 | 21 / 18 | 22 / 20 (11 from the parse cache) |
| Papers with no usable text | 6 | 2 | 2 (both transformer papers: publisher 403 / HTML page) |
| Digests full text / abstract / web | 19 / 1 / 15 | 18 / 3 / 15 | 20 / 0 / 12 |
| Findings verified / total | 101 / 126 | 114 / 134 | 90 / 112 |
| Judge pairs / failed verdicts | 104 / 1 | 114 / 0 | 92 / 0 |
| Judge passed: SSM sub-question | 10 (all statistics / ecology) | 5 | 6 (deep-learning state-space papers) |
| Judge passed: transformers sub-question | 0 | 1 | 9 |
| Sub-questions sufficient | 1 of 5 | 1 of 5 | 2 of 4 |
| Groq parking events | 73 | 85 | 85 |

### Checklist from run 2

- [x] Domain anchor applied: "deep learning" ends 12 of 12 stored queries.
- [x] Sub-question 2 has several judge-passed papers: 9 of 20 (rejected: electrical distribution transformers, e.g. "Design of efficient distribution transformer: A deep learning approach"). Full-text sources: An Introduction to Transformers, Introduction to Transformers: an NLP Perspective, Simplifying Transformer Blocks, DeLighT, and one application paper (wind power forecasting).
- [x] Sub-question 1 sources are deep-learning state-space papers: Linear State-Space Layers, Simple Discrete State Spaces, Vision Mamba survey; two borderline (Deep State Space Models for Nonlinear System Identification, "State space model: a magical tool for state prediction in Nonlinear systems", both control / identification flavored).
- [x] No parse failures from statistics or ecology papers.
- [ ] Multi-system comparison aspects: the aspects are now pairwise ("How does Mamba compare to transformers in training efficiency?" covered by 2 yes from 2 sources; "...compare to state space models..." covered by 3 yes from 3 sources). The four other aspects of the sub-question are not covered (see below).

### What is still wrong

1. **The planner merged the long-sequence dimension away.** The log says: "Merged near-duplicate sub-question 'How do state space models and transformers compare in long-sequence pe...' into '... compare in training efficie...' (similarity 0.93)". Run 2's planner kept them as two sub-questions. The merge rule (`SUBQUESTION_MERGE_SIMILARITY`, default 0.92, comment says "the most similar pair of genuinely different sub-questions seen so far scores 0.84") is the same embedding-similarity merge that wrongly merged aspects: two questions that differ in the one word that matters ("training efficiency" versus "long-sequence performance") share all the other words. The result: sub-question 4 now carries both dimensions and its aspects 5 and 6 are garbled ("challenges / metrics for measuring long-sequence performance when comparing ... in training efficiency"), 4 of its 6 aspects have 0 "yes", and the judge gave 5 yes, 11 partial, 7 no. Long-sequence performance, half of the user's question, has no sub-question of its own.

2. **One digest failed and was not counted.** `Digest generation failed: Expecting property name enclosed in double quotes` for the web snippet "9 Transformers - 6.390 - Intro to Machine Learning" (0 / 0 findings), but the coverage row says 0 digest failures: the digest function swallowed the error, so the summarizer's counter and its retry never saw it. Fixed after the run (see below).

3. **The log line for the anchor was lost, and so could any other message with a non-ASCII character.** The anchor text contained a non-breaking hyphen (U+2011); `test_pipeline.py` opened `pipeline.log` with the Windows default encoding (cp1252), so the logging module raised an encoding error and dropped the line without a trace. Fixed after the run.

4. **Planning took 2m 48s (43 s before)**: the planner server answered after 34 s; the rest was loading the embedding model, which asks `huggingface.co` about files that are already on disk, and the network was slow (about 2 minutes of metadata checks). Fixed after the run (local copy first).

5. **OpenAlex rate limiting**: 13 backoff warnings on the two keys, 2 papers given up on, one content-API route timed out. Parsing took 6m 58s (35% longer than the previous run's 5m 42s) although 11 of 22 papers came from the parse cache.

6. **Stage 3 preparation is growing**: 4m 11s (3m 10s, 3m 32s before), now the second-largest phase; the chunk-embedding cache idea is still open. Groq: 85 parking events again, digest generation 3m 15s.

7. Residual noise: one application paper (wind power forecasting) in the transformers sub-question; the pre-filter still lets 3 power-transformer-with-deep-learning papers into the transformers shortlist (the judge rejected them).

### Fixed after this run (not yet exercised by a full run)
- Digest failures are raised to the summarizer (`strict=True`), retried and counted in `digest_failures`.
- The embedding model is loaded from disk first; the Hub is only contacted if the model is missing (load measured at 8 s including imports).
- Anchor text is normalized to plain ASCII punctuation, `test_pipeline.py` log files are UTF-8, and this report reads the anchor from the stored queries when the log line is missing.

### Next checks
- [x] Planner merge FIXED 2026-11-05 after this run: `SUBQUESTION_MERGE=exact` (default) merges only sub-questions with the same content words; 4 of the 5 merges in the logs were wrong, see `tests/test_subquestion_merge.py`. To be confirmed in the next run: the long-sequence dimension keeps its own sub-question (if the planner writes one).
- [ ] `digest_failures` shows the real count in the next run.
- [ ] Planning phase back to about 40 s.
- [ ] OpenAlex backoff warnings (13 here) and the parsing time.

(To regenerate the tables above after another run: `python scripts/pipeline_run_report.py`; these notes are kept.)
