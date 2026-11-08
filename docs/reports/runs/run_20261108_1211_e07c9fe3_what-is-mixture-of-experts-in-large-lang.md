# Pipeline run report - What is mixture of experts in large language models and how does expert routing work?

Generated 2026-11-08 13:41 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 28 in the file) and the database. Query id `e07c9fe3-cdb5-4d45-9464-755a05fa799e`.

## 1. Summary

| | |
|---|---|
| Question | What is mixture of experts in large language models and how does expert routing work? |
| Domain anchor | (cached): 'deep learning' | context: Deep learning for NLP: 'expert' refers to a model subnetwork and 'routing' to the internal selection mechanism, not human experts or data‑network routing. |
| Started / finished | 2026-11-08 12:11:09 / 12:40:39 |
| **Total execution time** | **29m 30s** (1770 s) |
| Sub-questions / search queries | 5 / 13 (per sub-question [3, 3, 0, 2, 3]) |
| Plan source | plan-cache (stored plan reused, PLAN_CACHE=true) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 565 candidates -> 547 cleared the similarity floor -> 100 shortlisted |
| **Papers kept after the relevance judge** | **74** (log: 74); 26 shortlisted papers rejected |
| **Web sources** | **58** (per sub-question [14, 12, 11, 8, 13]) |
| Papers attempted for parsing | 28 (top-N per sub-question) |
| **Papers parsed to usable full text** | **25** of 28 attempted (25 from the parse cache) |
| Papers not parsed (all routes failed) | 1 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 0 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 44 (29 from full text, 0 from abstracts, 15 from web snippets) |
| Findings (verified / total) | 136 / 157 |
| Coverage sufficient | 5 of 5 sub-questions |
| Judge | 2m 08s in 9 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 147 parking events, 2272 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 12:11:09 | 12:11:13 | 4s | 0% |
| Web search (Tavily) | 12:11:13 | 12:11:19 | 7s | 0% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 12:11:19 | 12:12:11 | 52s | 3% |
| Embedding pre-filter + relevance judge | 12:12:11 | 12:14:11 | 2m 00s | 7% |
| Citation enrichment (Semantic Scholar) | 12:14:12 | 12:14:37 | 26s | 1% |
| Store papers in the database | 12:14:37 | 12:14:39 | 1s | 0% |
| PDF download + Docling parsing | 12:14:39 | 12:18:51 | 4m 12s | 14% |
| Stage 3 preparation (aspect split, chunking, embedding) | 12:18:51 | 12:19:32 | 41s | 2% |
| Stage 3 digest generation (Groq) | 12:19:32 | 12:21:27 | 1m 54s | 6% |
| Stage 3 judge + coverage (per sub-question) | 12:21:27 | 12:24:00 | 2m 33s | 9% |
| Stage 4 fact check (claims, NLI, judges) | 12:24:00 | 12:40:38 | 16m 38s | 56% |
| **Total** | 12:11:09 | 12:40:39 | **29m 30s** | 100% |

Loop 2 (second search for uncovered aspects) is part of the judge + coverage phase above: 38s by its own step timings (2% of the run). Its searches, parses and filters are NOT counted in the retrieval figures of this report; it stored 0 new paper(s) and 0 new web page(s) with the run, so the stored counts of papers and web sources are higher than the log counts by these numbers.

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is a large language model (LLM)? | 140 -> 136 -> 20 | 12 of 20 | 5 | 14 | 8 (5 / 0 / 3) | 22 / 25 | sufficient |
| 2 | What is a mixture of experts (MoE) model? | 111 -> 106 -> 20 | 11 of 20 | 6 | 12 | 8 (5 / 0 / 3) | 26 / 29 | sufficient |
| 3 | How is MoE applied to LLMs? | 135 -> 135 -> 20 | 18 of 20 | 6 | 11 | 8 (5 / 0 / 3) | 30 / 33 | sufficient |
| 4 | What is expert routing in MoE models? | 63 -> 58 -> 20 | 17 of 20 | 5 | 8 | 8 (5 / 0 / 3) | 20 / 28 | sufficient |
| 5 | How is expert routing implemented in LLMs? | 116 -> 112 -> 20 | 16 of 20 | 5 | 13 | 12 (9 / 0 / 3) | 38 / 42 | sufficient |

- Relevance judge rejected 8 papers for [What is a large language model (LLM)?]. Examples: 'Large Language Model in Various Fields: Opportunities, Chall' (The paper focuses on applications and challenges of LLMs in specific domains rather than defining what an LLM is.); 'A Survey on Evaluation of Large Language Models' (The paper focuses on evaluation methods and benchmarks for LLMs rather than defining what an LLM is.); 'Large Language Models: A Structured Taxonomy and Review of C' (The paper reviews challenges and ethical issues of LLMs rather than defining what an LLM is.)
- Relevance judge rejected 9 papers for [What is a mixture of experts (MoE) model]. Examples: 'Diversifying the Mixture-of-Experts Representation for Langu' (The paper assumes the reader already understands what an MoE model is and focuses exclusively on solving the problem of homogeneous represen); 'Flexible and Effective Mixing of Large Language Models into ' (The paper discusses mixing pre-trained models into a domain expert framework rather than defining the internal architecture of a standard Mi); 'An Alternative Model for Mixtures of Experts' (The paper focuses on an alternative gating mechanism and training algorithm for MoE, not on defining or explaining what an MoE model is.)
- Relevance judge rejected 2 papers for [How is MoE applied to LLMs?]. Examples: 'Towards Understanding the Mixture-of-Experts Layer in Deep L' (The paper studies MoE in general deep learning architectures rather than specifically addressing its application to Large Language Models.); 'Flexible and Effective Mixing of Large Language Models into ' (The paper discusses mixing pre-trained models as a form of MOE rather than applying MoE architectures (expert subnetworks and routing) withi)
- Relevance judge rejected 3 papers for [What is expert routing in MoE models?]. Examples: 'Radio Frequency Machine Learning Mixture of Experts' (The paper applies MoE to radio frequency signals rather than addressing the general definition or mechanism of expert routing in NLP models.); 'Supervised Mixture-of-Experts with Deep Neural Network Routi' (The paper applies MoE routing to network intrusion detection rather than investigating the fundamental definition or mechanism of expert rou); 'Mixture-of-Experts Models in Vision: Routing, Optimization, ' (The paper studies MoE in vision tasks and focuses on generalization and efficiency rather than defining or explaining the expert routing mec)
- Relevance judge rejected 4 papers for [How is expert routing implemented in LLM]. Examples: 'A Survey on Deep Learning for the Routing Layer of Computer ' (The paper discusses routing in computer networks, not the internal expert routing mechanisms within Large Language Models.); 'Universal Model Routing for Efficient LLM Inference' (The paper discusses routing between separate external models for inference efficiency, not the internal selection mechanism between subnetwo); 'Routing Manifold Alignment Improves Generalization of Mixtur' (The paper focuses on improving router performance via manifold alignment rather than explaining how expert routing is implemented.)

### Sources behind each sub-question's digests

**1. What is a large language model (LLM)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comprehensive Overview of Large Language Models | paper | full_text | 3 / 3 |
| A Review of Current Trends, Techniques, and Challenges in Large Language Models (LLMs) | paper | full_text | 1 / 1 |
| Assessing the Strengths and Weaknesses of Large Language Models | paper | full_text | 3 / 5 |
| Natural language processing in the era of large language models | paper | full_text | 4 / 5 |
| Survey of Different Large Language Model Architectures: Trends, Benchmarks, and Challenges | paper | full_text | 5 / 5 |
| AI Demystified: Introduction to large language models / University IT | web | web_snippet | 2 / 2 |
| What Are Large Language Models (LLMs)? / IBM | web | web_snippet | 3 / 3 |
| What is a large language model (LLM)? - University of Arizona Libraries | web | web_snippet | 1 / 1 |

**2. What is a mixture of experts (MoE) model?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Mixture of Experts in Large Language Models | paper | full_text | 4 / 4 |
| Learning Factored Representations in a Deep Mixture of Experts | paper | full_text | 4 / 5 |
| Mixture of Experts in Large Language Models | paper | full_text | 5 / 5 |
| Specialization through Collaboration: Understanding Expert Interaction in Mixture-of-Expert Lar | paper | full_text | 5 / 5 |
| Towards Understanding Mixture of Experts in Deep Learning | paper | full_text | 3 / 5 |
| A Survey on Mixture of Experts in Large Language Models | web | web_snippet | 0 / 0 |
| Towards Understanding Mixture of Experts in Deep Learning | web | web_snippet | 3 / 3 |
| What is mixture of experts? / IBM | web | web_snippet | 2 / 2 |

**3. How is MoE applied to LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Mixture of Experts in Large Language Models | paper | full_text | 5 / 5 |
| Mixture of Experts in Large Language Models | paper | full_text | 4 / 4 |
| MoE-LLaVA: Mixture of Experts for Large Vision-Language Models | paper | full_text | 2 / 5 |
| OpenMoE: An Early Effort on Open Mixture-of-Experts Language Models | paper | full_text | 5 / 5 |
| Uni-MoE: Scaling Unified Multimodal LLMs With Mixture of Experts | paper | full_text | 5 / 5 |
| Mixture of Experts in Large Language Models | web | web_snippet | 4 / 4 |
| Mixture of Experts in Large Language Models | web | web_snippet | 4 / 4 |
| What is mixture of experts? / IBM | web | web_snippet | 1 / 1 |

**4. What is expert routing in MoE models?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Exploration-Driven Reinforcement Learning for Expert Routing Improvement in Mixture-of-Experts  | paper | full_text | 1 / 4 |
| Patch-level Routing in Mixture-of-Experts is Provably Sample-efficient for Convolutional Neural | paper | full_text | 2 / 4 |
| ProbMoE: Differentiable Probabilistic Routing for Mixture-of-Experts | paper | full_text | 3 / 4 |
| Task-Conditioned Routing Signatures in Sparse Mixture-of-Experts Transformers | paper | full_text | 2 / 3 |
| Towards Understanding Mixture of Experts in Deep Learning | paper | full_text | 4 / 4 |
| 91edff07232fb1b55a505a9e9f6c0ff3-Paper-Conference.pdf | web | web_snippet | 2 / 2 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 2 / 3 |
| Mixture-of-Experts with Expert Choice Routing | web | web_snippet | 4 / 4 |

**5. How is expert routing implemented in LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| MoE Routing Testbed: Studying Expert Specialization and Routing Behavior at Small Scale | paper | full_text | 5 / 5 |
| MoE Routing Testbed: Studying Expert Specialization and Routing Behavior at Small Scale | paper | full_text | 2 / 2 |
| Routing by Analogy: kNN-Augmented Expert Assignment for Mixture-of-Experts | paper | full_text | 3 / 5 |
| Routing by Analogy: kNN-Augmented Expert Assignment for Mixture-of-Experts | paper | full_text | 4 / 4 |
| ScoutRoute: Efficient Mixture-of-Experts Routing Using Internal Language Model Signals | paper | full_text | 5 / 5 |
| ScoutRoute: Efficient Mixture-of-Experts Routing Using Internal Language Model Signals | paper | full_text | 2 / 2 |
| Task-Conditioned Routing Signatures in Sparse Mixture-of-Experts Transformers | paper | full_text | 3 / 3 |
| When Are Experts Misrouted? Counterfactual Routing Analysis in Mixture-of-Experts Language Mode | paper | full_text | 5 / 5 |
| When Are Experts Misrouted? Counterfactual Routing Analysis in Mixture-of-Experts Language Mode | paper | full_text | 1 / 3 |
| Expert-guided routing: A supervised post-hoc routing framework for task-specific and multilingu | web | web_snippet | 1 / 1 |
| Mixture of Experts in Large Language Models | web | web_snippet | 2 / 2 |
| Mixture-of-Experts with Expert Choice Routing | web | web_snippet | 5 / 5 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is a large language model (LLM)?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 21 = yes 14, partial 5, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How are LLMs trained? | covered | 2 | 2 |
| 2 | How are LLMs used? | covered | 5 | 3 |
| 3 | main challenges of LLMs | covered | 4 | 2 |
| 4 | main limitations of LLMs | covered | 3 | 2 |

### 2. What is a mixture of experts (MoE) model?

Sufficient: **True**; judge used: True; sources 7 (5 full text); judge candidates 18 = yes 10, partial 4, no 4, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does a MoE model differ from a standard neural network model? | covered | 5 | 4 |
| 2 | advantages of using a MoE model | covered | 6 | 4 |
| 3 | disadvantages of using a MoE model | covered | 3 | 3 |

Loop 2 (r1 triage, steps reselect, pool, queries): searched 0 aspect(s), covered 1 (1 by synthesis of several sources), sufficient True (strict rule: True), gap rule core, 5.1 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| How does a MoE model differ from a standard neural network model? | covered | - | synthesis | synthesis | 1/4/1 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|

### 3. How is MoE applied to LLMs?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 12 = yes 9, partial 1, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the benefits of using MoE in LLMs? | covered | 5 | 4 |
| 2 | challenges of using MoE in LLMs | covered | 4 | 2 |

### 4. What is expert routing in MoE models?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 8, partial 6, no 4, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does expert routing work in MoE models? | covered | 4 | 4 |
| 2 | What are the different types of expert routing strategies in MoE models? | covered | 2 | 2 |
| 3 | How does expert routing affect the performance and efficiency of MoE models? | covered | 2 | 2 |

### 5. How is expert routing implemented in LLMs?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 51 = yes 39, partial 8, no 4, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | existing methods for expert routing in LLMs | covered | 10 | 7 |
| 2 | existing architectures for expert routing in LLMs | covered | 9 | 7 |
| 3 | How do expert routing implementations in LLMs compare in terms of accuracy? | covered | 5 | 4 |
| 4 | How do expert routing implementations in LLMs compare in terms of speed? | covered | 2 | 2 |
| 5 | How do expert routing implementations in LLMs compare in terms of scalability? | covered | 3 | 2 |
| 6 | open problems for expert routing in LLMs | covered | 7 | 5 |
| 7 | future directions for expert routing in LLMs | covered | 5 | 3 |

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 2 (1 by synthesis of several sources), sufficient True (strict rule: True), gap rule core, 33.2 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| How do expert routing implementations in LLMs compare in terms of accuracy? | covered | reselect | reselect | single claims | 1/3/1 | - |
| How do expert routing implementations in LLMs compare in terms of scalability? | covered | - | synthesis | synthesis | 1/1/1 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 4 | 9 | 1 | 27.6 | digest_failed=0, sources_tried=5 |

## 5. Retrieval details

- Web search variants: [14, 12, 11, 8, 13] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 140 candidates -> 136 cleared min_similarity (0.56) -> top 20 shortlisted; 111 candidates -> 106 cleared min_similarity (0.56) -> top 20 shortlisted; 135 candidates -> 135 cleared min_similarity (0.56) -> top 20 shortlisted; 63 candidates -> 58 cleared min_similarity (0.56) -> top 20 shortlisted; 116 candidates -> 112 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 41, 'both': 3, 'scopus': 28, 'arxiv': 2}; requests to api.openalex.org in the log: 28
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 1
- Citation enrichment: Citation enrichment: 1 arXiv-only papers to enrich; took 26s in total

## 6. Parsing details

- Attempted 28 papers, usable full text 25, 74 papers saved in the database.
- PDF obtained via: its own link: 2; parse cache hits: 25; Unpaywall OA links found: 0; landing-page citation_pdf_url: 0
- Individual download failures: 0 -> 
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| Towards Understanding the Mixture-of-Experts Layer in Deep Learning | all PDF routes failed: None: None |

## 7. Groq and judge

- Stage 3: 40 digests for 5 sub-questions, 7 worker(s), 7 Groq key(s)
- Groq usage: 186,317 tokens (92,195 prompt + 94,122 completion, of which 71,693 reasoning) in 133 calls, 147 rate limits [digest 128,034, stage4_judge 41,432, digest_loop2 8,882, aspect_split 7,626, query_expansion 343]
- Rate-limit parking events: 147; per key (events / parked seconds): ...3mla: 25 / 371s, ...Ef4D: 22 / 329s, ...KJJp: 24 / 293s, ...KaRe: 23 / 323s, ...X2Oj: 17 / 353s, ...uNUk: 20 / 311s, ...x1nP: 16 / 292s
- Judge batch latencies (s): [19.6, 17.8, 4.9, 12.3, 18.2, 26.4, 7.3, 5.4, 16.5]

- Judge verdicts that came back as error: 0

## 7b. Stage 4: fact check

Claims after grouping: 113; labels {'unverified': 109, 'supported': 4}; contradictions stored: 0; time 16m 38s.

| # | Sub-question | Digests | Claims | Clusters | Supported / unverified / contradicted |
|---|---|---|---|---|---|
| 1 | What is a large language model (LLM)? | 8 | 22 | 20 | 1 / 19 / 0 |
| 2 | What is a mixture of experts (MoE) model? | 8 | 26 | 18 | 1 / 17 / 0 |
| 3 | How is MoE applied to LLMs? | 8 | 30 | 24 | 1 / 23 / 0 |
| 4 | What is expert routing in MoE models? | 8 | 20 | 16 | 1 / 15 / 0 |
| 5 | How is expert routing implemented in LLMs? | 12 | 38 | 35 | 0 / 35 / 0 |

NLI pair cap: 128 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI; 165 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI; 107 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 1 | All PDF URLs failed for <id>: None: None |
| WARNING | 3 | Stage N: N quote/claim pairs passed the topic gate; only the N most similar go to NLI |
| WARNING | 2 | Dropped query '<text>' for sub-question '<text>' (similarity N.N < N.N); it fits '<text>' better (N.N) |
| WARNING | 2 | Docling unavailable, using basic metadata: Server error '<text>' for url '<url> |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | SN rate limited on batch, backing off Ns |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429) and citation enrichment still spent 26s on 1 rate-limited batch calls.
- 1 paper(s) could not be downloaded by any route.
- Groq rate limiting: 147 parking events; digest generation took 1m 54s.
- Longest phase: Stage 4 fact check (claims, NLI, judges) (16m 38s, 56% of the run).

Warnings in the log: 10; errors: 1.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes

First complete run with `LOOP2=true` and `FACTCHECK=true` together (plan cache on, Tailscale host for the judge and Docling).

**Stage 3 and Loop 2: good.** 5 of 5 sub-questions sufficient, 0 judge errors, 0 digest failures.
- Sub-question 2 (MoE vs a standard network) had 1 yes / 4 partial / 1 no for one aspect; the synthesis of two partial findings covered it in 5 s, with no search.
- Sub-question 5: the accuracy aspect was covered by the `reselect` step (4 new sources, 9 new verified findings, 28 s); the scalability aspect was covered by synthesis. Neither needed new papers or web pages (0 stored).
- Loop 2 cost 38 s in total (2% of the run) and 8,882 Groq tokens (5% of the run's tokens). The previous run of this question with Loop 2 on (run 26 report, `run_20261107_1554_b24a57ac`) ended with 3 of 5 sufficient, so this is 5 of 5 after the Loop 2 sufficiency changes.

**Groq usage (first full run with the token meter):** 186,317 tokens in 133 calls: digest 128,034 (69%), stage4_judge 41,432 (22%), digest_loop2 8,882, aspect_split 7,626, query_expansion 343. Reasoning tokens are 38% of the total (71,693). That is 13% of the combined free daily budget of the 7 accounts (7 x 200,000), so about 7 runs per day of this size by tokens alone. The 147 rate-limit answers (429) were the per-minute token limit (8,000 per key), not the daily limit; they cost 1m 54s of digest time, which is acceptable.

**Stage 4: works, but slow and with little corroboration.**
- No false conflicts (0 stored, 0 disagreements), no judge failures, no breaker. The hardened conflict judge and the confirming second reading did their job here.
- It took 16m 38s, 56% of the whole run. There is no GPU, so the DeBERTa-large NLI model runs on the CPU (about 1.2 to 1.7 s per pair); the conflict step alone runs up to 80 pairs per sub-question (capped; 107 to 165 pairs passed the topic gate in 4 of the 5 sub-questions) and the support check adds more NLI pairs. I did not time the NLI share separately; the log only shows 12:24:00 (Stage 3 done) to 12:40:38.
- 113 claims after grouping: 4 supported (3.5%), 109 unverified, 0 contradicted. "Supported" needs two different documents in one cluster. 136 claims became 113 clusters, so only 23 merges happened and only 4 of them joined two different documents. Papers on the same topic rarely state the same sentence-level claim, so most claims keep a single source. Same picture as the Q3 run (1 supported per sub-question), so this is a property of the rule and not of this run.
- The 4 supported claims are all correct (checked the quotes: LLM tasks, MoE capacity without matching compute, MoE layers alternated with dense layers, learnable router sends each input to a subset of experts). Their first pieces of evidence mostly came through `stage3_judge` reuse (no NLI, no Groq call); one used NLI (probability 0.98).

**Fixes done in this session:** the run report script now has the Stage 4 phase in the time table, a section 7b (labels per sub-question, NLI cap warnings, conflicts) and the Groq usage line. No pipeline code needed a fix after this run.

**Open (see KNOWN_LIMITS 4.9, 4.10, 4.11):** Stage 4 time on the CPU; a third "partly corroborated" level for claims with a near-match in another document.
