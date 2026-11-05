# Pipeline run report - How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance?

Generated 2026-11-05 20:44 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 4 in the file) and the database. Query id `e5fca5b6-ab05-4707-a4b2-33069bed228e`.

## 1. Summary

| | |
|---|---|
| Question | How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance? |
| Domain anchor | (cached): 'deep learning' | context: Machine learning (deep learning): transformers are neural network architectures and state space models are sequence models such as Mamba, not electrical transformers or classical control‑theory state‑space representations. |
| Started / finished | 2026-11-05 16:53:20 / 17:07:19 |
| **Total execution time** | **13m 59s** (839 s) |
| Sub-questions / search queries | 5 / 15 (per sub-question [3, 3, 3, 3, 3]) |
| Plan source | planner |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 374 candidates -> 374 cleared the similarity floor -> 100 shortlisted |
| **Papers kept after the relevance judge** | **28** (log: 28); 72 shortlisted papers rejected |
| **Web sources** | **59** (per sub-question [10, 11, 13, 14, 11]) |
| Papers attempted for parsing | 20 (top-N per sub-question) |
| **Papers parsed to usable full text** | **17** of 20 attempted (5 from the parse cache) |
| Papers not parsed (all routes failed) | 3 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 11 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 33 (17 from full text, 1 from abstracts, 15 from web snippets) |
| Findings (verified / total) | 83 / 103 |
| Coverage sufficient | 1 of 5 sub-questions |
| Judge | 1m 11s in 5 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 58 parking events, 1021 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 16:53:20 | 16:53:47 | 27s | 3% |
| Web search (Tavily) | 16:53:47 | 16:54:05 | 18s | 2% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 16:54:05 | 16:54:40 | 36s | 4% |
| Embedding pre-filter + relevance judge | 16:54:40 | 16:56:14 | 1m 34s | 11% |
| Citation enrichment (Semantic Scholar) | 16:56:15 | 16:56:26 | 11s | 1% |
| Store papers in the database | 16:56:26 | 16:56:27 | 1s | 0% |
| PDF download + Docling parsing | 16:56:27 | 17:00:58 | 4m 32s | 32% |
| Stage 3 preparation (aspect split, chunking, embedding) | 17:00:58 | 17:03:39 | 2m 40s | 19% |
| Stage 3 digest generation (Groq) | 17:03:39 | 17:06:05 | 2m 26s | 17% |
| Stage 3 judge + coverage (per sub-question) | 17:06:05 | 17:07:18 | 1m 13s | 9% |
| **Total** | 16:53:20 | 17:07:19 | **13m 59s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What are state space models and how do they work? | 69 -> 69 -> 20 | 2 of 20 | 2 | 10 | 5 (2 / 0 / 3) | 7 / 13 | NOT sufficient |
| 2 | What are transformers and how do they work? | 84 -> 84 -> 20 | 6 of 20 | 4 | 11 | 8 (4 / 1 / 3) | 25 / 25 | sufficient |
| 3 | What is Mamba and how does it relate to state space models and transformers? | 88 -> 88 -> 20 | 8 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 18 / 25 | NOT sufficient |
| 4 | How are training efficiency and long-sequence performance measured and compared? | 86 -> 86 -> 20 | 1 of 20 | 1 | 14 | 4 (1 / 0 / 3) | 6 / 9 | NOT sufficient |
| 5 | How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance? | 47 -> 47 -> 20 | 11 of 20 | 5 | 11 | 8 (5 / 0 / 3) | 27 / 31 | NOT sufficient |

- Relevance judge rejected 18 papers for [What are state space models and how do t]. Examples: 'Deep state space models for nonlinear system identification' (The paper focuses on system identification and control theory applications rather than explaining the architecture and mechanics of modern d); 'Deep state space models for time series forecasting' (The paper focuses on combining classical linear state space models with deep learning for time series forecasting, rather than explaining th); 'Latent Matters: Learning Deep State-Space Models' (The paper focuses on training dynamics and system identification for classical deep state-space models rather than explaining the architectu)
- Relevance judge rejected 14 papers for [What are transformers and how do they wo]. Examples: 'Design of efficient distribution transformer: A deep learnin' (The paper discusses electrical distribution transformers, not the neural network architecture known as transformers.); 'Hybrid Embedding and Transformer-based Text and Vision Archi' (The paper focuses on performance comparisons and hybrid architectures rather than explaining the fundamental mechanisms of how transformers ); 'Enhancing Electrical Transformer Fault Prediction with Deep ' (The paper discusses electrical power transformers, not the neural network architecture known as transformers.)
- Relevance judge rejected 12 papers for [What is Mamba and how does it relate to ]. Examples: 'Mamba as a Motion Encoder for Robotic Imitation Learning' (The paper focuses on applying Mamba to robotic imitation learning rather than explaining its theoretical relationship to state space models ); 'Latent Mamba-DQN: Improving Temporal Dependency Modeling in ' (The paper applies Mamba to reinforcement learning without explaining its theoretical relationship to state space models or transformers.); 'Enhancing spatiotemporal prediction through the integration ' (The paper focuses on a specific application of Mamba for spatiotemporal prediction rather than explaining what Mamba is or its theoretical r)
- Relevance judge rejected 19 papers for [How are training efficiency and long-seq]. Examples: 'BENCHMARKING LEARNING EFFICIENCY IN DEEP RESERVOIR COMPUTING' (The paper focuses on reservoir computing and general learning efficiency rather than specifically measuring and comparing training efficienc); 'Extra-Deep: Automated Empirical Performance Modeling for Dis' (The paper focuses on automated performance modeling for distributed training rather than measuring or comparing training efficiency and long); 'Optimization of Deep Learning Model Training through Hardwar' (The paper focuses on hardware configuration and general training speed rather than specific metrics for comparing training efficiency and lo)
- Relevance judge rejected 9 papers for [How do state space models like Mamba com]. Examples: 'Back to recurrent processing at the crossroad of transformer' (The paper provides a high-level overview of trends and does not offer specific comparative analysis of training efficiency or long-sequence ); 'State Space Models as Foundation Models: A Control Theoretic' (The paper focuses on control theory perspectives and lacks specific empirical comparisons of training efficiency between Mamba and Transform); 'A Stock Trend Prediction Method Based on the Fusion of State' (The paper focuses on a specific financial application and hybrid architecture performance rather than a general comparative analysis of trai)

### Sources behind each sub-question's digests

**1. What are state space models and how do they work?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| State space model: a magical tool for state prediction in Nonlinear systems | paper | full_text | 1 / 3 |
| Structured state-space models are deep Wiener models | paper | full_text | 0 / 4 |
| Deep Learning-based Approaches for State Space Models:A Selective Review | web | web_snippet | 1 / 1 |
| What Are State Space Models? / IBM | web | web_snippet | 5 / 5 |
| [2412.11211] Deep Learning-based Approaches for State Space Models: A Selective Review | web | web_snippet | 0 / 0 |

**2. What are transformers and how do they work?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Deep Learning in EEG-Based BCIs: A Comprehensive Review of Transformer Models, Advantages, Chal | paper | full_text | 4 / 4 |
| Deep learning model-transformer based wind power forecasting approach | paper | full_text | 5 / 5 |
| Innovative deep learning architectures for medical image diagnosis: a comprehensive review of c | paper | full_text | 5 / 5 |
| Transformer-Based Attention Mechanisms in Agricultural Deep Learning: From Self-attention to Cr | paper | full_text | 0 / 0 |
| 9  Transformers – 6.390 - Intro to Machine Learning | web | web_snippet | 5 / 5 |
| Exploring Deep Learning Approaches for News Classification with CNNs, RNNs and Transformers | paper | abstract | 1 / 1 |
| What are Transformers in Artificial Intelligence? | web | web_snippet | 4 / 4 |
| What is a Transformer Model? / IBM | web | web_snippet | 1 / 1 |

**3. What is Mamba and how does it relate to state space models and transformers?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Integration of Mamba and Transformer - MAT for Long-Short Range Time Series Forecasting with Ap | paper | full_text | 2 / 3 |
| SSAMBA: Self-Supervised Audio Representation Learning With Mamba State Space Model | paper | full_text | 4 / 5 |
| State-space models are accurate and efficient neural operators for dynamical systems | paper | full_text | 0 / 3 |
| Vision Mamba in Remote Sensing: A Comprehensive Survey of Techniques, Applications and Outlook | paper | full_text | 4 / 4 |
| Vision Mamba: Efficient Visual Representation Learning with Bidirectional State Space Model | paper | full_text | 2 / 3 |
| Enhancing spatiotemporal prediction through the integration of Mamba state space models and Dif | web | web_snippet | 2 / 2 |
| Mamba Models a possible replacement for Transformers? - SciPy Proceedings | web | web_snippet | 3 / 3 |
| What Is A Mamba Model? / IBM | web | web_snippet | 1 / 2 |

**4. How are training efficiency and long-sequence performance measured and compared?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Resurrecting Recurrent Neural Networks for Long Sequences | paper | full_text | 3 / 4 |
| DeepSpeed: Extreme-scale model training for everyone - Microsoft Research | web | web_snippet | 0 / 1 |
| From Deep to Long Learning? · Hazy Research | web | web_snippet | 3 / 3 |
| Measuring deep learning performance - an empirical study of performance distributions across ar | web | web_snippet | 0 / 1 |

**5. How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| EFFECTIVELY MODELING TIME SERIES WITH SIMPLE DISCRETE STATE SPACES | paper | full_text | 4 / 5 |
| HMT: Hierarchical Mamba-Transformer for Efficient Long-Sequence Text Classification | paper | full_text | 0 / 0 |
| Never Train from Scratch: FAIR COMPARISON OF LONG-SEQUENCE MODELS REQUIRES DATA-DRIVEN PRIORS | paper | full_text | 5 / 5 |
| TransMamba: A Sequence-Level Hybrid Transformer-Mamba Language Model | paper | full_text | 2 / 3 |
| Vision Mamba: Efficient Visual Representation Learning with Bidirectional State Space Model | paper | full_text | 3 / 3 |
| Benchmarking the Computational and Representational Efficiency of State Space Models against Tr | web | web_snippet | 5 / 5 |
| Repeat After Me: Transformers are Better than State Space Models at Copying - Kempner Institute | web | web_snippet | 4 / 5 |
| State-Space Modeling in Long Sequence Processing: A Survey on Recurrence in the Transformer Era | web | web_snippet | 4 / 5 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What are state space models and how do they work?

Sufficient: **False**; judge used: True; sources 3 (1 full text); judge candidates 16 = yes 5, partial 2, no 9, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the key components of a state space model? | uncovered | 1 | 1 |
| 2 | What are the parameters of a state space model? | uncovered | 1 | 1 |
| 3 | advantages of state space models | covered | 3 | 2 |
| 4 | limitations of state space models | uncovered | 0 | 0 |

Uncovered details: What are the key components and parameters of a state space model?; What are the advantages and limitations of state space models?

### 2. What are transformers and how do they work?

Sufficient: **True**; judge used: True; sources 7 (3 full text); judge candidates 20 = yes 14, partial 0, no 6, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | key components of a transformer model | covered | 4 | 4 |
| 2 | key parameters of a transformer model | covered | 2 | 2 |
| 3 | advantages of transformers | covered | 5 | 2 |
| 4 | limitations of transformers | covered | 3 | 3 |

### 3. What is Mamba and how does it relate to state space models and transformers?

Sufficient: **False**; judge used: True; sources 7 (4 full text); judge candidates 12 = yes 3, partial 7, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What is the main innovation or contribution of Mamba? | covered | 2 | 2 |
| 2 | How does Mamba integrate state space models and transformers? | uncovered | 1 | 1 |

Uncovered details: How does Mamba integrate state space models and transformers?

### 4. How are training efficiency and long-sequence performance measured and compared?

Sufficient: **False**; judge used: True; sources 2 (1 full text); judge candidates 14 = yes 6, partial 0, no 8, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the metrics or indicators of training efficiency? | uncovered | 0 | 0 |
| 2 | What are the metrics or indicators of long-sequence performance? | uncovered | 1 | 1 |
| 3 | What benchmarks or datasets are used to evaluate training efficiency? | uncovered | 2 | 1 |
| 4 | What benchmarks or datasets are used to evaluate long-sequence performance? | covered | 3 | 2 |

Uncovered details: What are the metrics or indicators of training efficiency and long-sequence performance?; What are the benchmarks or datasets used for training efficiency and long-sequence performance evaluation?

### 5. How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance?

Sufficient: **False**; judge used: True; sources 7 (4 full text); judge candidates 22 = yes 6, partial 13, no 3, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the results or findings of existing studies or papers that compare state space models (e.g., Mamba) with transformers in terms of training efficiency and long‑sequence performance? | covered | 2 | 2 |
| 2 | What are the possible explanations or interpretations of the results or findings regarding how state space models like Mamba compare with transformers in training efficiency and long-sequence performance? | uncovered | 0 | 0 |
| 3 | What are the implications of the results or findings for comparing state space models like Mamba with transformers in training efficiency and long-sequence performance? | covered | 3 | 2 |
| 4 | What are the limitations of the results or findings for comparing state space models like Mamba with transformers in training efficiency and long-sequence performance? | uncovered | 1 | 1 |

Uncovered details: What are the possible explanations or interpretations of the results or findings?; What are the implications or limitations of the results or findings?

## 5. Retrieval details

- Web search variants: [10, 11, 13, 14, 11] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 69 candidates -> 69 cleared min_similarity (0.56) -> top 20 shortlisted; 84 candidates -> 84 cleared min_similarity (0.56) -> top 20 shortlisted; 88 candidates -> 88 cleared min_similarity (0.56) -> top 20 shortlisted; 86 candidates -> 86 cleared min_similarity (0.56) -> top 20 shortlisted; 47 candidates -> 47 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'scopus': 27, 'arxiv': 1}; requests to api.openalex.org in the log: 0
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0
- Citation enrichment: Citation enrichment: 1 arXiv-only papers to enrich; took 11s in total

## 6. Parsing details

- Attempted 20 papers, usable full text 17, 28 papers saved in the database.
- PDF obtained via: Unpaywall: 5, its own link: 1, the same paper on arXiv: 3; parse cache hits: 5; Unpaywall OA links found: 5; landing-page citation_pdf_url: 1
- Individual download failures: 11 -> ValueError: 11
- Headless-browser fallback: 6 tried, 6 failed; Docling fetch-by-URL attempts: 6; HTML full-text attempts that failed: 3

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| A comprehensive survey and taxonomy of mamba: Applications, Challenges, and Future Directi | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |
| Exploring Deep Learning Approaches for News Classification with CNNs, RNNs and Transformer | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |
| Large Vision Models: How Transformer-based Models excelled over Traditional Deep Learning  | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |

## 7. Groq and judge

- Stage 3: 33 digests for 5 sub-questions, 4 worker(s), 4 Groq key(s)
- Rate-limit parking events: 58; per key (events / parked seconds): ...KJJp: 13 / 259s, ...KaRe: 16 / 294s, ...X2Oj: 13 / 213s, ...x1nP: 16 / 255s
- Judge batch latencies (s): [13.4, 16.2, 11.1, 12.5, 18.0]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 3 | All PDF URLs failed for <id>: ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 11 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 5 | Playwright fallback failed: ValueError: ValueError('<text>') |
| WARNING | 2 | Parse cache lookup failed for <id>: RemoteProtocolError: Server disconnected |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | Removed N NUL character(s) from the parsed text of paper <id> before storing it |
| WARNING | 1 | Playwright fallback failed: TimeoutError: TimeoutError('<text>') |

## 9. Checks (rule based, from the log)

- OpenAlex was not queried at all (0 requests in the log): the agent skips it silently when no OPENALEX_API_KEYS is set; kept papers by source: {'scopus': 27, 'arxiv': 1}
- Semantic Scholar search was skipped (probe returned 429).
- 3 paper(s) could not be downloaded by any route.
- Groq rate limiting: 58 parking events; digest generation took 2m 26s.
- Longest phase: PDF download + Docling parsing (4m 32s, 32% of the run).

Warnings in the log: 22; errors: 3.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand after reading the log and the database)

**Bottom line.** This run is not a fair test of the pipeline, because **OpenAlex was not used at all**: 0 requests to `api.openalex.org` in the log, and all 28 kept papers come from Scopus (27) and arXiv (1). The `.env` no longer has an active `OPENALEX_API_KEYS` line (only the commented `# OPENALEX_API_KEY=...` and the tuning variables remain), and the agent skips OpenAlex silently when it has no key. Run 3 had 41 OpenAlex requests and 32 of its 40 papers from OpenAlex. That explains why this was the fastest run (13m 59s: no OpenAlex backoffs, fewer papers to parse) and also why the result is thinner: 1 of 5 sub-questions "sufficient", 28 kept papers, and two sub-questions starved. The four fixes made after run 3 all held up.

### Comparison of the four runs of this question

| | Run 1 (11:32) | Run 2 (14:00) | Run 3 (16:08) | **Run 4 (16:53)** |
|---|---|---|---|---|
| Domain anchor | no | no | yes | yes (cached) |
| OpenAlex | yes | yes | yes | **no key, 0 requests** |
| Total time | 18m 44s | 19m 31s | 22m 36s | **13m 59s** |
| Candidates / kept papers | 306 / 47 | 628 / 42 | 451 / 40 | **374 / 28** |
| Kept by source | OpenAlex 36, arXiv 10 | OpenAlex 18, Scopus 18, both 4, arXiv 2 | OpenAlex 26, Scopus 7, both 6, arXiv 1 | **Scopus 27, arXiv 1** |
| Papers attempted / usable full text | 25 / 19 | 21 / 18 | 22 / 20 | 20 / 17 (5 from cache) |
| Papers with no usable text | 6 | 2 | 2 | 3 (Scopus DOI-only, publisher HTML) |
| Digests full text / abstract / web | 19 / 1 / 15 | 18 / 3 / 15 | 20 / 0 / 12 | 17 / 1 / 15 |
| Findings verified / total | 101 / 126 | 114 / 134 | 90 / 112 | 83 / 103 |
| Judge pairs / failed verdicts | 104 / 1 | 114 / 0 | 92 / 0 | 84 / 0 |
| Sub-questions sufficient | 1 of 5 | 1 of 5 | 2 of 4 | 1 of 5 |
| Planning phase | 43 s | 38 s | 2m 48s | **27 s** |

### Checklist from run 3 (the fixes made afterwards)

- [x] Planning back to about 40 s: **27 s** (embedding model loaded from disk).
- [x] Anchor log line present (`Domain anchor (cached): 'deep learning' ...`, UTF-8 log file).
- [x] NUL fix exercised for the first time: "Removed 4 NUL character(s) from the parsed text of paper 773b8441... before storing it", and no database error.
- [x] No digest error, no judge error this run; the new digest failure counter and retry were not exercised (nothing failed).
- [ ] Planner merge: no merge happened, so the fix could not be tested (the planner wrote 5 sub-questions, two of them the generic "measured and compared" one and the central one).
- [ ] OpenAlex backoffs: not applicable, OpenAlex was not queried.

### What is wrong

1. **A whole source disappeared without a trace.** No warning, no log line; the only signs were the kept-paper counts. Fixed after the run: the agent now logs "OpenAlex is NOT searched: no OPENALEX_API_KEYS..." when it starts without a key, and this report prints the kept papers by source and flags 0 OpenAlex requests. **To restore it, an `OPENALEX_API_KEYS=key1,key2` line has to be active in `.env`** (I did not touch your keys).

2. **Scopus alone gives weaker evidence.** Scopus ranks by relevance but returns application papers: the transformers sub-question is "sufficient", yet its full-text sources are EEG brain-computer interfaces, wind power forecasting, medical imaging and agriculture reviews, not explanations of transformers (OpenAlex's reranked search supplied "An Introduction to Transformers", "Introduction to Transformers: an NLP Perspective", "Simplifying Transformer Blocks" in run 3). So "sufficient" there means the aspects were answered by application papers. The state-space sub-question got 2 of 20 papers through the judge (3 sources, 1 full text, only "advantages" covered) and the generic sub-question 4 got 1 of 20.

3. **Candidate pools were smaller and fully above the similarity floor** (374 of 374 cleared 0.56): without OpenAlex's broad results nothing is rejected by the floor, but the shortlist of 20 is filled by Scopus' top results.

4. **The central comparison again lacks evidence**: sub-question 5 has 6 yes, 13 partial, 3 no, and its four aspects ("results", "explanations", "implications", "limitations" of existing comparisons) are broad and mostly uncovered. The planner worded this sub-question differently from the earlier runs (it asks for "the results or findings of existing studies", not the comparison itself).

### What worked

- The arXiv title-twin route made Scopus papers readable: 3 papers whose publisher page was HTML were obtained as "the same paper on arXiv" (Never Train from Scratch, Effectively Modeling Time Series with Simple Discrete State Spaces, Resurrecting Recurrent Neural Networks for Long Sequences), plus Unpaywall 5. 17 of 20 attempted papers have full text, 16 of them Scopus papers.
- The domain anchor kept working with Scopus: no electrical transformers or statistics papers were parsed.
- Speed: planning 27 s, parsing 4m 32s, Stage 3 preparation 2m 40s (less than before), digests 2m 26s with 58 Groq parking events (85 before), judge + coverage 1m 13s.

### Next checks
- [ ] Re-run with the OpenAlex key active: expect OpenAlex requests > 0, kept papers back at 40+, the transformers sub-question on introductions and surveys again.
- [ ] Compare that run with run 3 to separate the effect of the planner's different sub-questions from the effect of the source mix.
- [ ] Planner merge and digest failure counter: still to be seen in a run where they trigger.

(To regenerate the tables above after another run: `python scripts/pipeline_run_report.py`; these notes are kept.)
