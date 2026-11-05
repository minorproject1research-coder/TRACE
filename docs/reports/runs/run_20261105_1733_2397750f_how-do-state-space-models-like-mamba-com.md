# Pipeline run report - How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance?

Generated 2026-11-05 20:44 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 6 in the file) and the database. Query id `2397750f-41eb-4693-a21e-fd5a7045e9d7`.

## 1. Summary

| | |
|---|---|
| Question | How do state space models like Mamba compare with transformers in training efficiency and long-sequence performance? |
| Domain anchor | (cached): 'deep learning' | context: Machine learning (deep learning): transformers are neural network architectures and state space models are sequence models such as Mamba, not electrical transformers or classical control‑theory state‑space representations. |
| Started / finished | 2026-11-05 17:33:30 / 17:48:44 |
| **Total execution time** | **15m 14s** (914 s) |
| Sub-questions / search queries | 5 / 14 (per sub-question [3, 3, 3, 2, 3]) |
| Plan source | planner |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 479 candidates -> 439 cleared the similarity floor -> 100 shortlisted |
| **Papers kept after the relevance judge** | **48** (log: 48); 52 shortlisted papers rejected |
| **Web sources** | **52** (per sub-question [10, 12, 13, 9, 8]) |
| Papers attempted for parsing | 26 (top-N per sub-question) |
| **Papers parsed to usable full text** | **25** of 26 attempted (23 from the parse cache) |
| Papers not parsed (all routes failed) | 1 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 0 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 40 (25 from full text, 0 from abstracts, 15 from web snippets) |
| Findings (verified / total) | 122 / 150 |
| Coverage sufficient | 2 of 5 sub-questions |
| Judge | 1m 24s in 5 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 99 parking events, 1773 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 17:33:30 | 17:33:56 | 26s | 3% |
| Web search (Tavily) | 17:33:56 | 17:34:21 | 25s | 3% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 17:34:21 | 17:35:19 | 58s | 6% |
| Embedding pre-filter + relevance judge | 17:35:19 | 17:37:10 | 1m 51s | 12% |
| Store papers in the database | 17:37:10 | 17:37:12 | 1s | 0% |
| PDF download + Docling parsing | 17:37:12 | 17:37:46 | 35s | 4% |
| Stage 3 preparation (aspect split, chunking, embedding) | 17:37:46 | 17:43:16 | 5m 30s | 36% |
| Stage 3 digest generation (Groq) | 17:43:16 | 17:47:17 | 4m 01s | 26% |
| Stage 3 judge + coverage (per sub-question) | 17:47:17 | 17:48:43 | 1m 26s | 9% |
| **Total** | 17:33:30 | 17:48:44 | **15m 14s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What are state space models (SSMs) and how do they work? | 97 -> 97 -> 20 | 6 of 20 | 5 | 10 | 8 (5 / 0 / 3) | 21 / 28 | sufficient |
| 2 | What are transformers and how do they work? | 112 -> 111 -> 20 | 9 of 20 | 5 | 12 | 8 (5 / 0 / 3) | 25 / 29 | NOT sufficient |
| 3 | What is Mamba and how does it relate to SSMs? | 109 -> 104 -> 20 | 9 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 26 / 30 | sufficient |
| 4 | How are SSMs and transformers trained and evaluated? | 94 -> 77 -> 20 | 15 of 20 | 5 | 9 | 8 (5 / 0 / 3) | 23 / 27 | NOT sufficient |
| 5 | How do SSMs and transformers compare in training efficiency and long-sequence performance? | 67 -> 50 -> 20 | 9 of 20 | 5 | 8 | 8 (5 / 0 / 3) | 27 / 36 | NOT sufficient |

- Relevance judge rejected 14 papers for [What are state space models (SSMs) and h]. Examples: 'Deep State Space Models for Nonlinear System Identification' (The paper focuses on system identification and control theory applications rather than explaining the architecture and mechanics of modern d); 'FROM LAYERS TO STATES: A STATE SPACE MODEL PERSPECTIVE TO DE' (The paper uses SSMs as a tool to improve layer aggregation in existing networks rather than explaining what SSMs are or how they fundamental); 'FPGA-Based Parallel Acceleration of State Space Models for D' (The paper focuses on hardware acceleration and FPGA implementation rather than explaining the theoretical foundations or mechanisms of State)
- Relevance judge rejected 11 papers for [What are transformers and how do they wo]. Examples: 'Design of efficient distribution transformer: A deep learnin' (The paper discusses electrical distribution transformers, not the neural network architecture known as transformers.); 'Hybrid Embedding and Transformer-based Text and Vision Archi' (The paper focuses on performance comparisons and hybrid architectures rather than explaining the fundamental mechanisms of how transformers ); 'On reading and interpreting black box deep neural networks' (The paper focuses on interpreting and critiquing Transformer models as black boxes rather than explaining their fundamental architecture and)
- Relevance judge rejected 11 papers for [What is Mamba and how does it relate to ]. Examples: 'Mamba-Based Deep Learning Methods in Medical Image Analysis:' (The paper focuses on medical imaging applications rather than explaining the theoretical definition of Mamba or its relationship to SSMs.); 'A local enhanced mamba network for hyperspectral image class' (The paper applies Mamba to a specific hyperspectral image classification task rather than explaining what Mamba is or its relationship to SS); 'An Empirical Study of Mamba-based Language Models' (The paper focuses on empirical performance comparisons and scaling laws rather than explaining the theoretical definition of Mamba or its re)
- Relevance judge rejected 5 papers for [How are SSMs and transformers trained an]. Examples: 'State Space Models are Comparable to Transformers in Estimat' (The paper focuses on theoretical convergence rates and function estimation capabilities rather than describing the practical training and ev); 'The Illusion of State in State-Space Models' (The paper discusses theoretical limitations and experimental results regarding state tracking capabilities, but does not describe the traini); 'Evaluation of Time-Series Training Dataset through Lens of S' (The paper focuses on evaluating dataset quality using spectral metrics rather than explaining the training and evaluation methodologies of S)
- Relevance judge rejected 11 papers for [How do SSMs and transformers compare in ]. Examples: 'State Space Models are Comparable to Transformers in Estimat' (The paper focuses on theoretical convergence rates and function estimation capabilities rather than empirical comparisons of training effici); 'The Illusion of State in State-Space Models' (The paper focuses on theoretical expressiveness limitations rather than comparing training efficiency or long-sequence performance.); 'INFLUENCE OF LEARNING RATE PARAMETER IN DIFFERENT TRANSFORME' (The paper only studies transformer models and does not include any comparison with state space models (SSMs).)

### Sources behind each sub-question's digests

**1. What are state space models (SSMs) and how do they work?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Combining Recurrent, Convolutional, and Continuous-time Models with Linear State-Space Layers | paper | full_text | 2 / 4 |
| Effectively Modeling Time Series with Simple Discrete State Spaces | paper | full_text | 4 / 5 |
| Simplified State Space Layers for Sequence Modeling | paper | full_text | 1 / 1 |
| Structured state-space models are deep Wiener models | paper | full_text | 5 / 5 |
| Vision Mamba: A Comprehensive Survey and Taxonomy | paper | full_text | 2 / 4 |
| Deep Learning-based Approaches for State Space Models:A Selective Review | web | web_snippet | 1 / 2 |
| Deep Learning-based Approaches for State Space Models:A Selective Review | web | web_snippet | 4 / 5 |
| What Are State Space Models? / IBM | web | web_snippet | 2 / 2 |

**2. What are transformers and how do they work?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Practical Survey on Faster and Lighter Transformers | paper | full_text | 4 / 4 |
| An Introduction to Transformers | paper | full_text | 2 / 4 |
| Deep learning model-transformer based wind power forecasting approach | paper | full_text | 2 / 4 |
| Introduction to Transformers: an NLP Perspective | paper | full_text | 3 / 3 |
| Understanding Transformers: A Comprehensive Review | paper | full_text | 5 / 5 |
| 9  Transformers – 6.390 - Intro to Machine Learning | web | web_snippet | 1 / 1 |
| Deep Learning: Transformers | web | web_snippet | 5 / 5 |
| Transformers in Machine Learning - GeeksforGeeks | web | web_snippet | 3 / 3 |

**3. What is Mamba and how does it relate to SSMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey of Mamba | paper | full_text | 1 / 3 |
| A Survey on Visual Mamba | paper | full_text | 4 / 4 |
| Vision Mamba in Remote Sensing: A Comprehensive Survey of Techniques, Applications and Outlook | paper | full_text | 3 / 5 |
| Vision Mamba: A Comprehensive Survey and Taxonomy | paper | full_text | 5 / 5 |
| Vision Mamba: Efficient Visual Representation Learning with Bidirectional State Space Model | paper | full_text | 4 / 4 |
| A Survey of Mamba | web | web_snippet | 2 / 2 |
| A hybrid model based on transformer and Mamba for enhanced sequence modeling / Scientific Repor | web | web_snippet | 3 / 3 |
| What Is A Mamba Model? / IBM | web | web_snippet | 4 / 4 |

**4. How are SSMs and transformers trained and evaluated?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| An Empirical Study of Mamba-based Language Models | paper | full_text | 4 / 4 |
| Reducing Activation Recomputation in Large Transformer Models | paper | full_text | 5 / 5 |
| SiMBA: Simplified Mamba-Based Architecture for Vision and Multivariate Time series | paper | full_text | 2 / 4 |
| State space model for new generation network alternative to transformers: a survey | paper | full_text | 2 / 2 |
| Transformers are SSMs: Generalized Models and Efficient Algorithms Through Structured State Spa | paper | full_text | 2 / 3 |
| Benchmarking State Space Models, Transformers, and Recurrent Networks for US Grid Forecasting | web | web_snippet | 3 / 3 |
| Characterizing State Space Model (SSM) and SSM-Transformer Hybrid Language Model Performance wi | web | web_snippet | 3 / 3 |
| Repeat After Me: Transformers are Better than State Space Models at Copying - Kempner Institute | web | web_snippet | 2 / 3 |

**5. How do SSMs and transformers compare in training efficiency and long-sequence performance?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| An Empirical Study of Mamba-based Language Models | paper | full_text | 5 / 5 |
| SiMBA: Simplified Mamba-Based Architecture for Vision and Multivariate Time series | paper | full_text | 2 / 5 |
| State space model for new generation network alternative to transformers: a survey | paper | full_text | 3 / 5 |
| Transformers are SSMs: Generalized Models and Efficient Algorithms Through Structured State Spa | paper | full_text | 4 / 5 |
| Zamba: A Compact 7B SSM Hybrid Model | paper | full_text | 2 / 5 |
| Characterizing State Space Model (SSM) and SSM-Transformer Hybrid Language Model Performance wi | web | web_snippet | 2 / 2 |
| Repeat After Me: Transformers are Better than State Space Models at Copying - Kempner Institute | web | web_snippet | 5 / 5 |
| When recalling in-context, Transformers are not SSMs | web | web_snippet | 4 / 4 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What are state space models (SSMs) and how do they work?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 24 = yes 15, partial 1, no 8, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | key components of an SSM | covered | 4 | 3 |
| 2 | parameters of an SSM | covered | 3 | 3 |
| 3 | advantages of an SSM | covered | 4 | 2 |
| 4 | limitations of an SSM | covered | 4 | 4 |

### 2. What are transformers and how do they work?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 21 = yes 11, partial 4, no 6, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the key components of a transformer? | covered | 2 | 2 |
| 2 | What are the parameters of a transformer? | uncovered | 1 | 1 |
| 3 | What are the advantages of transformers? | covered | 6 | 5 |
| 4 | What are the limitations of transformers? | uncovered | 2 | 1 |

Uncovered details: What are the key components and parameters of a transformer?; What are the advantages and limitations of a transformer?

### 3. What is Mamba and how does it relate to SSMs?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 13, partial 3, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does Mamba improve upon previous SSMs? | covered | 5 | 4 |
| 2 | What are the main features of Mamba? | covered | 5 | 5 |
| 3 | What are the innovations of Mamba? | covered | 3 | 3 |

### 4. How are SSMs and transformers trained and evaluated?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 1, partial 7, no 10, error 0; digest failures 1.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the common metrics and benchmarks for measuring training efficiency of SSMs and transformers? | uncovered | 0 | 0 |
| 2 | What are the common metrics and benchmarks for measuring long-sequence performance of SSMs and transformers? | uncovered | 1 | 1 |
| 3 | What are the computational and memory requirements for training and inference of SSMs and transformers? | uncovered | 0 | 0 |

Uncovered details: What are the common metrics and benchmarks for measuring training efficiency and long-sequence performance?; What are the computational and memory requirements for training and inference of SSMs and transformers?

### 5. How do SSMs and transformers compare in training efficiency and long-sequence performance?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 21 = yes 12, partial 3, no 6, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the empirical results and findings from existing studies or papers that compare SSMs and transformers? | covered | 4 | 3 |
| 2 | What are the theoretical explanations or hypotheses for the observed differences or similarities between SSMs and transformers? | covered | 3 | 3 |
| 3 | open challenges or limitations for SSMs | covered | 4 | 3 |
| 4 | open challenges or limitations for transformers | uncovered | 1 | 1 |

Uncovered details: What are the open challenges or limitations for both SSMs and transformers?

## 5. Retrieval details

- Web search variants: [10, 12, 13, 9, 8] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 97 candidates -> 97 cleared min_similarity (0.56) -> top 20 shortlisted; 112 candidates -> 111 cleared min_similarity (0.56) -> top 20 shortlisted; 109 candidates -> 104 cleared min_similarity (0.56) -> top 20 shortlisted; 94 candidates -> 77 cleared min_similarity (0.56) -> top 20 shortlisted; 67 candidates -> 50 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 34, 'scopus': 13, 'both': 1}; requests to api.openalex.org in the log: 36
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0

## 6. Parsing details

- Attempted 26 papers, usable full text 25, 48 papers saved in the database.
- PDF obtained via: its own link: 2; parse cache hits: 23; Unpaywall OA links found: 0; landing-page citation_pdf_url: 0
- Individual download failures: 0 -> 
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| Deep State Space Models for Time Series Forecasting | all PDF routes failed: None: None |

## 7. Groq and judge

- Stage 3: 40 digests for 5 sub-questions, 4 worker(s), 4 Groq key(s)
- Rate-limit parking events: 99; per key (events / parked seconds): ...KJJp: 27 / 445s, ...KaRe: 22 / 432s, ...X2Oj: 24 / 444s, ...x1nP: 26 / 452s
- Judge batch latencies (s): [18.4, 17.1, 15.3, 16.0, 17.3]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 1 | All PDF URLs failed for <id>: None: None |
| ERROR | 1 | Digest generation failed: Expecting property name enclosed in double quotes: line N column N (char N) |
| WARNING | 5 | OpenAlex N on key ...CHgt for '<text>' (backoff N/N), pausing that key N.Ns |
| WARNING | 3 | OpenAlex N on key ...FsNG for '<text>' (backoff N/N), pausing that key N.Ns |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | OpenAlex gave up on '<text>' after N backoffs (last status N) |
| WARNING | 1 | Digest JSON parse failed (attempt N/N): Expecting property name enclosed in double quotes: line N column N (ch |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- Sub-question 'How are SSMs and transformers trained and evaluated?': 1 digest JSON failure(s).
- 1 paper(s) could not be downloaded by any route.
- Groq rate limiting: 99 parking events; digest generation took 4m 01s.
- Longest phase: Stage 3 preparation (aspect split, chunking, embedding) (5m 30s, 36% of the run).

Warnings in the log: 12; errors: 2.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand after reading the log and the database)

**Bottom line.** The first run with OpenAlex back since the key was lost (36 requests, 34 of the 48 kept papers) and the best result so far on the "what is X" sub-questions, but still 2 of 5 sub-questions sufficient, and the planner wrote a different set of sub-questions than in runs 1 to 4, so the result cannot be compared one to one with run 3. Things that are better: SSM and Mamba definitions are fully covered, the central comparison now has strong sources (An Empirical Study of Mamba-based Language Models, Transformers are SSMs, Zamba), and the new digest failure counter registered a real failure (retried and recovered). Things that are not: the "trained and evaluated" sub-question got 1 yes of 18 candidates, and the transformers sub-question again misses "parameters" and "limitations".

The log file also contains a run started at 17:16 that stopped during Stage 3 preparation (last line 17:25, no end); this report is about the complete run that started at 17:33.

### Comparison of the five runs of this question

| | Run 1 (11:32) | Run 2 (14:00) | Run 3 (16:08) | Run 4 (16:53) | **Run 5 (17:33)** |
|---|---|---|---|---|---|
| Domain anchor | no | no | yes | yes | yes (cached) |
| OpenAlex | yes | yes | yes | no key | **yes, 36 requests, 8 x 429, 1 query given up** |
| Total time | 18m 44s | 19m 31s | 22m 36s | 13m 59s | **15m 14s** |
| Candidates / kept papers | 306 / 47 | 628 / 42 | 451 / 40 | 374 / 28 | **479 / 48** |
| Kept by source | OpenAlex 36, arXiv 10 | OpenAlex 18, Scopus 18, both 4, arXiv 2 | OpenAlex 26, Scopus 7, both 6, arXiv 1 | Scopus 27, arXiv 1 | **OpenAlex 34, Scopus 13, both 1** |
| Papers attempted / usable full text | 25 / 19 | 21 / 18 | 22 / 20 | 20 / 17 | **26 / 25 (23 from the parse cache)** |
| Digests full text / abstract / web | 19 / 1 / 15 | 18 / 3 / 15 | 20 / 0 / 12 | 17 / 1 / 15 | **25 / 0 / 15** |
| Findings verified / total | 101 / 126 | 114 / 134 | 90 / 112 | 83 / 103 | **122 / 150** |
| Judge pairs / failed verdicts | 104 / 1 | 114 / 0 | 92 / 0 | 84 / 0 | **102 / 0** |
| Sub-questions sufficient | 1 of 5 | 1 of 5 | 2 of 4 | 1 of 5 | **2 of 5** |
| Planning phase | 43 s | 38 s | 2m 48s | 27 s | **26 s** |

Caveats for reading the table: 23 of the 25 parsed papers came from the parse cache, so the 35 s parsing phase says nothing about parsing speed; and the sub-questions differ from run to run (this run: three definitional ones, one "trained and evaluated", one comparison), so "sufficient" counts are not like for like.

### Sub-questions this run

| # | Sub-question | Result | Reading |
|---|---|---|---|
| 1 | What are SSMs and how do they work? | sufficient (4/4 aspects) | Papers: S4-family, Linear State-Space Layers, Structured SSMs are deep Wiener models, plus IBM and a survey as web sources. The anchor kept control-theory papers out (rejected "Deep State Space Models for Nonlinear System Identification"). |
| 2 | What are transformers and how do they work? | NOT sufficient (2/4) | Good sources (An Introduction to Transformers, Understanding Transformers, Introduction to Transformers: an NLP Perspective) but only 1 source has a yes for "parameters" and 1 for "limitations"; one source is still a wind power forecasting paper. The judge rejected "Design of efficient distribution transformer" (electrical), so the anchor works. |
| 3 | What is Mamba and how does it relate to SSMs? | sufficient (3/3) | Surveys of Mamba, Vision Mamba surveys. |
| 4 | How are SSMs and transformers trained and evaluated? | NOT sufficient (0/3) | 1 yes of 18 candidates (10 no). The aspects ask for metrics, benchmarks and memory requirements, which the retrieved papers describe only in passing; **1 digest also failed** (see below). |
| 5 | How do SSMs and transformers compare in training efficiency and long-sequence performance? | NOT sufficient (3/4) | Results, explanations and SSM limitations are covered; "open challenges for transformers" has 1 yes from 1 source. |

### Checklist from run 4

- [x] OpenAlex back: 36 requests, 34 kept papers, introductions and surveys for transformers again. The warning added after run 4 did not fire, so the key is active.
- [x] Digest failure counter: first real failure counted. "Digest JSON parse failed (attempt 1/2): Expecting property name enclosed in double quotes: line 7 column 7", logged as an error, `digest_failures = 1` for sub-question 4, no crash, the retry worked. This is the same Groq JSON glitch as in the 16:27 log of run 3, which was invisible then.
- [x] No judge error: 102 pairs, 0 errors.
- [ ] Planner merge: no merge happened.
- [x] Digest retry: attempt 2 followed attempt 1 and no "failed after 2 attempts" line follows it in this run, so the digest was recovered; `digest_failures = 1` counts failed attempts, not lost digests.

### What is wrong

1. **Stage 3 preparation is again the longest phase: 5m 30s (36%)**, twice the 2m 40s of run 4 (17 versus 25 papers with full text). Chunk embeddings are not cached between runs, so every parsed paper is chunked and embedded again each time. This is the cheapest speed-up left.
2. **OpenAlex rate limiting is back**: 8 x 429 on two keys, and one query ("transformers components and parameters deep learning") given up after 4 backoffs. The search phase still took only 58 s, so it costs little, but the transformers sub-question may have lost its best query this way.
3. **Semantic Scholar probe failed with 429** and the search was skipped (known; citation enrichment is unaffected).
4. **Groq rate limiting: 99 parking events (1773 key-seconds)**, digests 4m 01s, longer than in run 4 (2m 26s) because there were 40 digests of which 25 from full text.
5. **"Trained and evaluated" and "limitations/parameters" aspects stay uncovered** with the evidence pool: this is the case Loop 2 is meant for (aspects 1 and 3 of sub-question 4 have 0 yes verdicts, "no candidates" or judged insufficient).

### Wrapper check (the updated `/decompose`)

Tested with the question "How does retrieval-augmented generation constrain the creativity and diversity of large language models?":

- Default call (no new fields): works as before, reply has `raw_output` plus the new `raw_outputs` (1 item). ~23 s.
- `temperature=0.8, n=3`: 3 plans returned, all 3 valid JSON, `raw_output` equals the first item, ~26 s (so the 3 samples cost about the same as 1). The three query lists overlap strongly (all start with "retrieval-augmented generation definition ..."), so temperature 0.8 gives paraphrases rather than new angles. Loop 2 will get its variety mostly from the aspect-as-question input.
- `n=99` is capped at 4 as intended.
- **`seed=7` twice gave different outputs at temperature 0.8.** Either the host does not forward `seed` to vLLM, or vLLM is not deterministic across calls here. To check on the host: print the body sent to `/v1/completions`. Until that is clear, do not rely on `seed` for reproducible plans.

### Next checks
- [ ] Chunk-embedding cache for Stage 3 preparation.
- [ ] Loop 2 query step using `n=3` (offline test first, on the RAG-creativity aspect).
- [ ] Planner determinism: fix `seed` on the host, then Stage 1 can be reproducible.

(To regenerate the tables above after another run: `python scripts/pipeline_run_report.py`; these notes are kept.)
