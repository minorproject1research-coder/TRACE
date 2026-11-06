# Pipeline run report - What is mixture of experts in large language models and how does expert routing work?

Generated 2026-11-06 23:52 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 12 in the file) and the database. Query id `156ebc90-6250-4178-9d80-94b9ecdf50df`.

## 1. Summary

| | |
|---|---|
| Question | What is mixture of experts in large language models and how does expert routing work? |
| Domain anchor | (cached): 'deep learning' | context: Deep learning for NLP: 'expert' refers to a model subnetwork and 'routing' to the internal selection mechanism, not human experts or data‑network routing. |
| Started / finished | 2026-11-06 23:29:31 / 23:45:35 |
| **Total execution time** | **16m 04s** (964 s) |
| Sub-questions / search queries | 5 / 13 (per sub-question [3, 3, 0, 2, 3]) |
| Plan source | plan-cache (stored plan reused, PLAN_CACHE=true) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 606 candidates -> 576 cleared the similarity floor -> 100 shortlisted |
| **Papers kept after the relevance judge** | **73** (log: 73); 27 shortlisted papers rejected |
| **Web sources** | **63** (per sub-question [13, 11, 18, 8, 13]) |
| Papers attempted for parsing | 28 (top-N per sub-question) |
| **Papers parsed to usable full text** | **25** of 28 attempted (24 from the parse cache) |
| Papers not parsed (all routes failed) | 1 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 0 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 40 (25 from full text, 0 from abstracts, 15 from web snippets) |
| Findings (verified / total) | 140 / 157 |
| Coverage sufficient | 3 of 5 sub-questions |
| Judge | 1m 44s in 6 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 139 parking events, 2484 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 23:29:31 | 23:29:35 | 4s | 0% |
| Web search (Tavily) | 23:29:35 | 23:29:49 | 14s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 23:29:49 | 23:30:41 | 52s | 5% |
| Embedding pre-filter + relevance judge | 23:30:41 | 23:32:38 | 1m 57s | 12% |
| Citation enrichment (Semantic Scholar) | 23:32:38 | 23:33:04 | 26s | 3% |
| Store papers in the database | 23:33:04 | 23:33:06 | 1s | 0% |
| PDF download + Docling parsing | 23:33:06 | 23:37:41 | 4m 35s | 29% |
| Stage 3 preparation (aspect split, chunking, embedding) | 23:37:41 | 23:41:43 | 4m 02s | 25% |
| Stage 3 digest generation (Groq) | 23:41:43 | 23:43:44 | 2m 01s | 13% |
| Stage 3 judge + coverage (per sub-question) | 23:43:44 | 23:45:31 | 1m 47s | 11% |
| **Total** | 23:29:31 | 23:45:35 | **16m 04s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is a large language model (LLM)? | 140 -> 136 -> 20 | 12 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 27 / 28 | sufficient |
| 2 | What is a mixture of experts (MoE) model? | 110 -> 105 -> 20 | 11 of 20 | 6 | 11 | 8 (5 / 0 / 3) | 26 / 28 | sufficient |
| 3 | How is MoE applied to LLMs? | 173 -> 164 -> 20 | 17 of 20 | 6 | 18 | 8 (5 / 0 / 3) | 32 / 34 | NOT sufficient |
| 4 | What is expert routing in MoE models? | 65 -> 59 -> 20 | 17 of 20 | 5 | 8 | 8 (5 / 0 / 3) | 20 / 31 | sufficient |
| 5 | How is expert routing implemented in LLMs? | 118 -> 112 -> 20 | 16 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 35 / 36 | NOT sufficient |

- Relevance judge rejected 8 papers for [What is a large language model (LLM)?]. Examples: 'Large Language Model in Various Fields: Opportunities, Chall' (The paper focuses on applications and challenges of LLMs in specific domains rather than defining what an LLM is.); 'A Survey on Evaluation of Large Language Models' (The paper focuses on evaluation methods and benchmarks for LLMs rather than defining what an LLM is.); 'Large Language Models: A Structured Taxonomy and Review of C' (The paper reviews challenges and ethical issues of LLMs rather than defining what an LLM is.)
- Relevance judge rejected 9 papers for [What is a mixture of experts (MoE) model]. Examples: 'Diversifying the Mixture-of-Experts Representation for Langu' (The paper assumes the reader already understands what an MoE model is and focuses exclusively on solving specific training optimization prob); 'Flexible and Effective Mixing of Large Language Models into ' (The paper discusses mixing pre-trained models into a domain expert framework, which is distinct from defining the internal architecture of a); 'An Alternative Model for Mixtures of Experts' (The paper focuses on an alternative gating mechanism and training algorithm for MoE, not on defining or explaining what an MoE model is.)
- Relevance judge rejected 3 papers for [How is MoE applied to LLMs?]. Examples: 'Exploring the Use of Software Product Lines for the Combinat' (The paper focuses on software engineering methods for model combination rather than the technical architecture and routing mechanisms of MoE); 'SP-MoE: Expediting Mixture-of-Experts Training with Optimize' (The paper focuses on training system optimization and latency reduction rather than explaining how MoE architectures or routing mechanisms a); '3D-MoE: Accelerating Multi-Expert Activated LLMs on 3D In/Ne' (The paper focuses on hardware acceleration and system architecture for MoE models rather than explaining the application or mechanism of MoE)
- Relevance judge rejected 3 papers for [What is expert routing in MoE models?]. Examples: 'Radio Frequency Machine Learning Mixture of Experts' (The paper applies MoE to radio frequency signals rather than addressing the general definition or mechanism of expert routing in NLP models.); 'Supervised Mixture-of-Experts with Deep Neural Network Routi' (The paper applies MoE routing to network intrusion detection rather than investigating the mechanism itself within the context of NLP.); 'Mixture-of-Experts Models in Vision: Routing, Optimization, ' (The paper studies MoE in vision tasks and focuses on optimization and generalization rather than explaining the mechanism of expert routing )
- Relevance judge rejected 4 papers for [How is expert routing implemented in LLM]. Examples: 'A Survey on Deep Learning for the Routing Layer of Computer ' (The paper discusses routing in computer networks, not the internal expert routing mechanisms within Large Language Models.); 'Universal Model Routing for Efficient LLM Inference' (The paper discusses routing between separate external models for inference efficiency, not the internal selection mechanism between subnetwo); 'Routing Manifold Alignment Improves Generalization of Mixtur' (The paper focuses on improving router performance via manifold alignment rather than explaining how expert routing is implemented.)

### Sources behind each sub-question's digests

**1. What is a large language model (LLM)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comprehensive Overview of Large Language Models | paper | full_text | 3 / 3 |
| A Review of Current Trends, Techniques, and Challenges in Large Language Models (LLMs) | paper | full_text | 4 / 4 |
| Assessing the Strengths and Weaknesses of Large Language Models | paper | full_text | 5 / 5 |
| Natural language processing in the era of large language models | paper | full_text | 3 / 4 |
| Survey of Different Large Language Model Architectures: Trends, Benchmarks, and Challenges | paper | full_text | 5 / 5 |
| AI Demystified: Introduction to large language models / University IT | web | web_snippet | 4 / 4 |
| What Are Large Language Models (LLMs)? / IBM | web | web_snippet | 2 / 2 |
| What is a large language model (LLM)? - University of Arizona Libraries | web | web_snippet | 1 / 1 |

**2. What is a mixture of experts (MoE) model?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Mixture of Experts in Large Language Models | paper | full_text | 1 / 1 |
| Learning Factored Representations in a Deep Mixture of Experts | paper | full_text | 5 / 5 |
| Mixture of Experts in Large Language Models | paper | full_text | 5 / 5 |
| Specialization through Collaboration: Understanding Expert Interaction in Mixture-of-Expert Lar | paper | full_text | 5 / 5 |
| Towards Understanding Mixture of Experts in Deep Learning | paper | full_text | 3 / 5 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 4 / 4 |
| A Survey on Mixture of Experts in Large Language Models | web | web_snippet | 0 / 0 |
| What is mixture of experts? / IBM | web | web_snippet | 3 / 3 |

**3. How is MoE applied to LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| DeepSpeed-MoE: Advancing Mixture-of-Experts Inference and Training to Power Next-Generation AI  | paper | full_text | 5 / 5 |
| Mixture of Experts in Large Language Models | paper | full_text | 4 / 4 |
| MoE-LLaVA: Mixture of Experts for Large Vision-Language Models | paper | full_text | 3 / 5 |
| OpenMoE: An Early Effort on Open Mixture-of-Experts Language Models | paper | full_text | 5 / 5 |
| Uni-MoE: Scaling Unified Multimodal LLMs With Mixture of Experts | paper | full_text | 5 / 5 |
| Mixture of Experts in Large Language Models | web | web_snippet | 3 / 3 |
| Mixture of Experts in Large Language Models | web | web_snippet | 3 / 3 |
| What is mixture of experts? / IBM | web | web_snippet | 4 / 4 |

**4. What is expert routing in MoE models?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Exploration-Driven Reinforcement Learning for Expert Routing Improvement in Mixture-of-Experts  | paper | full_text | 2 / 4 |
| Patch-level Routing in Mixture-of-Experts is Provably Sample-efficient for Convolutional Neural | paper | full_text | 2 / 5 |
| ProbMoE: Differentiable Probabilistic Routing for Mixture-of-Experts | paper | full_text | 3 / 4 |
| Task-Conditioned Routing Signatures in Sparse Mixture-of-Experts Transformers | paper | full_text | 4 / 4 |
| Towards Understanding Mixture of Experts in Deep Learning | paper | full_text | 0 / 4 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 2 / 3 |
| Mixture of Experts | web | web_snippet | 2 / 2 |
| Mixture-of-Experts with Expert Choice Routing | web | web_snippet | 5 / 5 |

**5. How is expert routing implemented in LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Attention-aware routing in mixture of experts language models | paper | full_text | 4 / 4 |
| MoE Routing Testbed: Studying Expert Specialization and Routing Behavior at Small Scale | paper | full_text | 4 / 5 |
| ScoutRoute: Efficient Mixture-of-Experts Routing Using Internal Language Model Signals | paper | full_text | 5 / 5 |
| Task-Conditioned Routing Signatures in Sparse Mixture-of-Experts Transformers | paper | full_text | 5 / 5 |
| When Are Experts Misrouted? Counterfactual Routing Analysis in Mixture-of-Experts Language Mode | paper | full_text | 5 / 5 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 3 / 3 |
| Mixture of Experts in Large Language Models | web | web_snippet | 4 / 4 |
| Mixture-of-Experts with Expert Choice Routing | web | web_snippet | 5 / 5 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is a large language model (LLM)?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 24 = yes 17, partial 5, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How are LLMs trained? | covered | 3 | 3 |
| 2 | How are LLMs used? | covered | 5 | 4 |
| 3 | main challenges of LLMs | covered | 5 | 4 |
| 4 | main limitations of LLMs | covered | 4 | 3 |

### 2. What is a mixture of experts (MoE) model?

Sufficient: **True**; judge used: True; sources 7 (5 full text); judge candidates 18 = yes 10, partial 3, no 5, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does a MoE model differ from a standard neural network model? | covered | 3 | 2 |
| 2 | advantages of using a MoE model | covered | 4 | 3 |
| 3 | disadvantages of using a MoE model | covered | 3 | 3 |

### 3. How is MoE applied to LLMs?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 12 = yes 6, partial 4, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | benefits of using MoE in LLMs | covered | 5 | 4 |
| 2 | What are the challenges of using MoE in LLMs? | uncovered | 1 | 1 |

Uncovered details: What are the challenges of using MoE in LLMs?

### 4. What is expert routing in MoE models?

Sufficient: **True**; judge used: True; sources 7 (4 full text); judge candidates 18 = yes 9, partial 5, no 4, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does expert routing work in MoE models? | covered | 5 | 5 |
| 2 | What are the different types of expert routing strategies in MoE models? | covered | 2 | 2 |
| 3 | How does expert routing affect the performance and efficiency of MoE models? | covered | 2 | 2 |

### 5. How is expert routing implemented in LLMs?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 41 = yes 21, partial 10, no 10, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | existing methods for expert routing in LLMs | covered | 5 | 3 |
| 2 | existing architectures for expert routing in LLMs | covered | 4 | 4 |
| 3 | How does expert routing implementation in LLMs compare in terms of accuracy? | covered | 2 | 2 |
| 4 | How does expert routing implementation in LLMs compare in terms of speed? | covered | 2 | 2 |
| 5 | How does expert routing implementation in LLMs compare in terms of scalability? | uncovered | 0 | 0 |
| 6 | open problems for expert routing in LLMs | covered | 4 | 4 |
| 7 | future directions for expert routing in LLMs | covered | 4 | 4 |

Uncovered details: How do they compare in terms of accuracy, speed, and scalability?

## 5. Retrieval details

- Web search variants: [13, 11, 18, 8, 13] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 140 candidates -> 136 cleared min_similarity (0.56) -> top 20 shortlisted; 110 candidates -> 105 cleared min_similarity (0.56) -> top 20 shortlisted; 173 candidates -> 164 cleared min_similarity (0.56) -> top 20 shortlisted; 65 candidates -> 59 cleared min_similarity (0.56) -> top 20 shortlisted; 118 candidates -> 112 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 39, 'scopus': 29, 'both': 3, 'arxiv': 2}; requests to api.openalex.org in the log: 30
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 1
- Citation enrichment: Citation enrichment: 1 arXiv-only papers to enrich; took 26s in total

## 6. Parsing details

- Attempted 28 papers, usable full text 25, 73 papers saved in the database.
- PDF obtained via: its own link: 3; parse cache hits: 24; Unpaywall OA links found: 0; landing-page citation_pdf_url: 0
- Individual download failures: 0 -> 
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| Towards Understanding the Mixture-of-Experts Layer in Deep Learning | all PDF routes failed: None: None |

## 7. Groq and judge

- Stage 3: 40 digests for 5 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 139; per key (events / parked seconds): ...3mla: 22 / 335s, ...Ef4D: 23 / 367s, ...KJJp: 28 / 377s, ...KaRe: 21 / 404s, ...X2Oj: 16 / 305s, ...uNUk: 14 / 347s, ...x1nP: 15 / 349s
- Judge batch latencies (s): [19.1, 16.8, 12.0, 17.1, 28.5, 10.8]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 1 | All PDF URLs failed for <id>: None: None |
| WARNING | 2 | Dropped query '<text>' for sub-question '<text>' (similarity N.N < N.N); it fits '<text>' better (N.N) |
| WARNING | 2 | Docling unavailable, using basic metadata: Server error '<text>' for url '<url> |
| WARNING | 2 | database read failed (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | SN rate limited on batch, backing off Ns |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429) and citation enrichment still spent 26s on 1 rate-limited batch calls.
- 1 paper(s) could not be downloaded by any route.
- Groq rate limiting: 139 parking events; digest generation took 2m 01s.
- Longest phase: PDF download + Docling parsing (4m 35s, 29% of the run).

Warnings in the log: 9; errors: 1.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand after reading the log and the database)

**Bottom line.** This is the repeat of the mixture-of-experts question with `TOPIC_ASPECT=false` that the first API run called for, with the same plan (plan cache), the query gate and the tolerant quote verifier active, and **7 Groq keys**. It confirms the diagnosis: the digests are back (**157 findings, 3.92 per digest**, against 104 and 2.60 with the topic aspect on), the verified share rose to **89%**, and **3 of 5 sub-questions are sufficient** (0 of 5 with the topic aspect, 4 of 5 on 5 November). The run took **16m 04s**, the fastest complete run of this question, mostly because the 24 of 28 parsed papers came from the parse cache and the digests ran on 7 keys (2m 01s instead of 4m 01s). The remaining difference from 5 November (3 aspects flipped at the 2-"yes" boundary, see below) is the size of change that re-running Groq digests produces on its own; it is not evidence of another regression.

### The three runs of this question

| | Run 8 (5 Nov) | Run 10 (6 Nov, topic aspect ON) | **Run 12 (6 Nov, topic aspect OFF)** |
|---|---|---|---|
| Plan source | planner | plan-cache | plan-cache (same plan) |
| Quote verifier | old | new | new |
| Groq keys / workers | 4 / 4 | 4 / 4 | **7 / 7** |
| Total time | 22m 10s | about 19m (report says 41m) | **16m 04s** |
| Kept papers / web sources | 69 / 54 | 75 / 62 | 73 / 63 |
| Papers parsed (from the parse cache) | 25 of 32 (6) | 25 of 30 (20) | 25 of 28 (24) |
| Findings (verified / total) | 124 / 146 | 86 / 104 | **140 / 157** |
| Findings per digest (40 digests each) | 3.65 | 2.60 | **3.92** |
| Verified share | 85% | 83% | **89%** |
| Same 22 sources: findings per digest | 3.74 | 2.35 | **3.92** |
| Same 22 sources: verified per digest | 3.06 | 1.86 | **3.40** |
| Sub-questions sufficient | 4 of 5 | 0 of 5 | **3 of 5** |
| Aspects covered / judged | 19 of 20 | not comparable (topic aspect added) | 17 of 19 |
| Judge pairs / errors | 111 / 0 | 99 / 1 | **113 / 0** |
| Stage 3 digest phase | 4m 01s | 1m 38s | **2m 01s** |
| Groq parking events (parked key-seconds) | 108 (3537) | 99 (1371) | 139 (2484) |

### What changed against 5 November (same plan, same sub-questions)
- **How is MoE applied to LLMs?** became NOT sufficient: "challenges of using MoE in LLMs" has 1 "yes" from 1 source (3 from 2 before). The sub-question again received no planner query after the gate (both its queries were dropped and the LLM expansion supplied the searches; 18 web sources, 17 of 20 papers passed the judge, against 13 of 20 on 5 November with the two misplaced generic LLM queries). A single boundary flip, so the gate cannot be blamed or cleared from this data: both API runs have this sub-question insufficient, run 10 for the topic-aspect reason, run 12 on a 1-versus-2 count.
- **How is expert routing implemented in LLMs?** is NOT sufficient only because "scalability comparison" has 0 "yes" (3 from 2 sources before). Its other six aspects are covered, including "existing architectures" and "future directions", which were uncovered on 5 November. So the same sub-question swapped one uncovered aspect for another.
- The other three sub-questions are sufficient. "What is expert routing in MoE models?" lost one aspect through the split (3 aspects instead of 4, the split is regenerated each run).
- Net: 2 aspects uncovered of 19 (1 of 20 on 5 November). These flips are the kind described in report 10 (about a sixth of the judge's pairs change between runs with no change in the total).

### What this run confirms
1. **The topic aspect was the cause of the 0 of 5.** Same sources, same code, only the setting differs: 2.35 findings per digest with it, 3.92 without (and 3.74 on 5 November). `TOPIC_ASPECT=false` stays the default.
2. **The tolerant quote verifier helps in a real run.** Verified share 89% against 85% on 5 November, and the same 22 sources give 3.40 verified findings per digest against 3.06 (the first API run could not show this because its digests were damaged). Part of the difference is run-to-run variation in what the digest model writes, but the direction matches the estimate on stored digests (+5 points).
3. **7 keys roughly halve the digest phase** (2m 01s against 4m 01s on 4 keys) with the same 40 digests. Parking is not gone: 139 events, but spread over 7 keys at 305 to 404 s each (14 to 28 events per key), against 3537 s on 4 keys. No key was parked for a long time this run (the longest single park was 36 s, against 1908 s on 5 November). Total parked key-seconds fell by 30%.
4. **The API retry absorbed two dropped connections.** Two "database read failed (attempt 1/2): RemoteProtocolError: Server disconnected" warnings and no failed request in the log (before the retry these were a 500 or a wrong 404).
5. **Judge: 0 errors in 113 pairs**; no digest failure; the one paper without text is the Scopus title variant of the arXiv paper already parsed ("Towards Understanding the Mixture-of-Experts Layer in Deep Learning", known, report 15 section 5).

### What is still wrong
- **Sub-question 4 has 11 of 31 findings unverified (65%)**, and the two worst digests are the same arXiv paper, "Towards Understanding Mixture of Experts in Deep Learning" (0 of 4 and 3 of 5), a theory paper full of formulas; "Patch-level Routing in Mixture-of-Experts is Provably Sample-efficient" (2 of 5) is similar. This is the math-heavy case from known limits 3.13: the digest model edits quotes of formula text and the verifier rightly rejects them. The tolerant verifier does not help there.
- **Stage 3 preparation is the longest Stage 3 phase again: 4m 02s** (aspect split, chunking, embeddings), now twice the digest phase. The chunk-embedding cache is the cheapest speed-up left.
- **Generic aspects remain**: "advantages", "disadvantages", "benefits", "main challenges and limitations of LLMs" are the aspects of three sub-questions, and the background sub-question "What is a large language model?" still receives 20 shortlisted papers, 5 parsed papers and 8 digests (known limits 1.3, 3.12).
- **The same two sub-questions are the Loop 2 candidates in every run**: "challenges of using MoE in LLMs" and "scalability comparison of expert routing implementations" (and, in the earlier run, "existing architectures" and "future directions"). Evidence for them exists in the literature; the retrieval does not reach it often enough to pass the 2-source rule every time.
- Citation enrichment: 26 s on one Semantic Scholar 429 batch (probe 429 again).

### Decisions this run supports
- Keep `TOPIC_ASPECT=false` (done). A judge-only topic aspect is still open (candidates must come from similarity).
- Keep 7 workers (the default of one per key). The digest phase is no longer the bottleneck; parsing (new topics) and Stage 3 preparation are.
- Q3 to Q6 can be run now; the pipeline state is as good as it was on 5 November.

(To regenerate the tables above after another run: `python scripts/pipeline_run_report.py --run N`; these notes are kept.)
