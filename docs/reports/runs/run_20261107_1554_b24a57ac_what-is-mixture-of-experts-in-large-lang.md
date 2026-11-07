# Pipeline run report - What is mixture of experts in large language models and how does expert routing work?

Generated 2026-11-07 16:16 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 20 in the file) and the database. Query id `b24a57ac-fdcf-4802-ac29-c35297bcd7de`.

## 1. Summary

| | |
|---|---|
| Question | What is mixture of experts in large language models and how does expert routing work? |
| Domain anchor | (cached): 'deep learning' | context: Deep learning for NLP: 'expert' refers to a model subnetwork and 'routing' to the internal selection mechanism, not human experts or data‑network routing. |
| Started / finished | 2026-11-07 15:54:03 / 16:11:01 |
| **Total execution time** | **16m 58s** (1018 s) |
| Sub-questions / search queries | 5 / 13 (per sub-question [3, 3, 0, 2, 3]) |
| Plan source | plan-cache (stored plan reused, PLAN_CACHE=true) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 568 candidates -> 541 cleared the similarity floor -> 100 shortlisted |
| **Papers kept after the relevance judge** | **78** (log: 72); 28 shortlisted papers rejected |
| **Web sources** | **68** (per sub-question [14, 12, 14, 8, 14]) |
| Papers attempted for parsing | 27 (top-N per sub-question) |
| **Papers parsed to usable full text** | **25** of 27 attempted (24 from the parse cache) |
| Papers not parsed (all routes failed) | 1 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 2 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 59 (41 from full text, 0 from abstracts, 18 from web snippets) |
| Findings (verified / total) | 193 / 213 |
| Coverage sufficient | 3 of 5 sub-questions |
| Judge | 2m 02s in 10 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 114 parking events, 5633 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 15:54:03 | 15:54:06 | 3s | 0% |
| Web search (Tavily) | 15:54:06 | 15:54:21 | 14s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 15:54:21 | 15:55:05 | 44s | 4% |
| Embedding pre-filter + relevance judge | 15:55:05 | 15:56:56 | 1m 51s | 11% |
| Citation enrichment (Semantic Scholar) | 15:56:56 | 15:58:03 | 1m 08s | 7% |
| Store papers in the database | 15:58:03 | 15:58:04 | 1s | 0% |
| PDF download + Docling parsing | 15:58:04 | 16:00:10 | 2m 06s | 12% |
| Stage 3 preparation (aspect split, chunking, embedding) | 16:00:10 | 16:02:08 | 1m 58s | 12% |
| Stage 3 digest generation (Groq) | 16:02:08 | 16:04:17 | 2m 09s | 13% |
| Stage 3 judge + coverage (per sub-question) | 16:04:17 | 16:11:01 | 6m 44s | 40% |
| **Total** | 15:54:03 | 16:11:01 | **16m 58s** | 100% |

Loop 2 (second search for uncovered aspects) is part of the judge + coverage phase above: 5m 11s by its own step timings (31% of the run). Its searches, parses and filters are NOT counted in the retrieval figures of this report; it stored 6 new paper(s) and 6 new web page(s) with the run, so the stored counts of papers and web sources are higher than the log counts by these numbers.

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is a large language model (LLM)? | 140 -> 136 -> 20 | 13 of 20 | 5 | 14 | 8 (5 / 0 / 3) | 26 / 27 | sufficient |
| 2 | What is a mixture of experts (MoE) model? | 110 -> 105 -> 20 | 11 of 20 | 6 | 12 | 8 (5 / 0 / 3) | 25 / 28 | sufficient |
| 3 | How is MoE applied to LLMs? | 135 -> 129 -> 20 | 15 of 20 | 5 | 14 | 8 (5 / 0 / 3) | 25 / 27 | sufficient |
| 4 | What is expert routing in MoE models? | 65 -> 59 -> 20 | 17 of 20 | 8 | 11 | 18 (13 / 0 / 5) | 70 / 76 | NOT sufficient |
| 5 | How is expert routing implemented in LLMs? | 118 -> 112 -> 20 | 16 of 20 | 9 | 17 | 17 (13 / 0 / 4) | 47 / 55 | NOT sufficient |

- Relevance judge rejected 7 papers for [What is a large language model (LLM)?]. Examples: 'Large Language Model in Various Fields: Opportunities, Chall' (The paper focuses on applications and challenges of LLMs in specific domains rather than defining what an LLM is.); 'A Survey on Evaluation of Large Language Models' (The paper focuses on evaluation methods and benchmarks for LLMs rather than defining what an LLM is.); 'Integrated Method of Deep Learning and Large Language Model ' (The paper focuses on applying LLMs to speech recognition rather than defining what an LLM is.)
- Relevance judge rejected 9 papers for [What is a mixture of experts (MoE) model]. Examples: 'Diversifying the Mixture-of-Experts Representation for Langu' (The paper assumes the reader already understands what an MoE model is and focuses exclusively on solving the problem of homogeneous represen); 'Flexible and Effective Mixing of Large Language Models into ' (The paper discusses mixing pre-trained models into a domain expert framework rather than defining the internal architecture of a standard Mi); 'An Alternative Model for Mixtures of Experts' (The paper focuses on an alternative gating mechanism and training algorithm for MoE, not on defining or explaining what an MoE model is.)
- Relevance judge rejected 5 papers for [How is MoE applied to LLMs?]. Examples: 'MoE-Compression: How the Compression Error of Experts Affect' (The paper focuses on memory compression techniques for MoE inference rather than explaining how MoE architectures are applied to LLMs.); 'Challenges and Applications of Large Language Models' (The paper provides a general overview of LLM challenges and applications without mentioning MoE, experts, or routing mechanisms.); 'Challenges and Limitations of Leveraging LLMs for Anomaly De' (The paper discusses general LLM limitations in numerical data and anomaly detection without mentioning MoE architectures or routing mechanis)
- Relevance judge rejected 3 papers for [What is expert routing in MoE models?]. Examples: 'Radio Frequency Machine Learning Mixture of Experts' (The paper applies MoE to radio frequency signals rather than addressing the general definition or mechanism of expert routing in NLP models.); 'Supervised Mixture-of-Experts with Deep Neural Network Routi' (The paper applies MoE routing to network intrusion detection rather than investigating the mechanism itself within the context of NLP.); 'Mixture-of-Experts Models in Vision: Routing, Optimization, ' (The paper studies MoE in vision tasks and focuses on optimization and generalization rather than explaining the mechanism of expert routing )
- Relevance judge rejected 4 papers for [How is expert routing implemented in LLM]. Examples: 'A Survey on Deep Learning for the Routing Layer of Computer ' (The paper discusses routing in computer networks, not the internal expert routing mechanisms within Large Language Models.); 'Universal Model Routing for Efficient LLM Inference' (The paper discusses routing between separate external models for inference efficiency, not the internal selection of subnetworks within a si); 'Routing Manifold Alignment Improves Generalization of Mixtur' (The paper focuses on optimizing router performance via manifold alignment rather than explaining the implementation mechanics of expert rout)

### Sources behind each sub-question's digests

**1. What is a large language model (LLM)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comprehensive Overview of Large Language Models | paper | full_text | 3 / 3 |
| A Review of Current Trends, Techniques, and Challenges in Large Language Models (LLMs) | paper | full_text | 5 / 5 |
| Large Language Models: A Structured Taxonomy and Review of Challenges, Limitations, Solutions,  | paper | full_text | 3 / 3 |
| Natural language processing in the era of large language models | paper | full_text | 4 / 5 |
| Survey of Different Large Language Model Architectures: Trends, Benchmarks, and Challenges | paper | full_text | 4 / 4 |
| AI Demystified: Introduction to large language models / University IT | web | web_snippet | 4 / 4 |
| What Are Large Language Models (LLMs)? / IBM | web | web_snippet | 2 / 2 |
| What is a large language model (LLM)? - University of Arizona Libraries | web | web_snippet | 1 / 1 |

**2. What is a mixture of experts (MoE) model?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Mixture of Experts in Large Language Models | paper | full_text | 3 / 3 |
| Learning Factored Representations in a Deep Mixture of Experts | paper | full_text | 5 / 5 |
| Mixture of Experts in Large Language Models | paper | full_text | 5 / 5 |
| Specialization through Collaboration: Understanding Expert Interaction in Mixture-of-Expert Lar | paper | full_text | 5 / 5 |
| Towards Understanding Mixture of Experts in Deep Learning | paper | full_text | 4 / 5 |
| A Survey on Mixture of Experts in Large Language Models | web | web_snippet | 0 / 0 |
| What is Mixture of Experts (MoE)? | web | web_snippet | 0 / 2 |
| What is mixture of experts? / IBM | web | web_snippet | 3 / 3 |

**3. How is MoE applied to LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Mixture of Experts in Large Language Models | paper | full_text | 5 / 5 |
| DeepSpeed-MoE: Advancing Mixture-of-Experts Inference and Training to Power Next-Generation AI  | paper | full_text | 1 / 3 |
| Mixture of Experts in Large Language Models | paper | full_text | 4 / 4 |
| MoE-LLaVA: Mixture of Experts for Large Vision-Language Models | paper | full_text | 4 / 4 |
| OpenMoE: An Early Effort on Open Mixture-of-Experts Language Models | paper | full_text | 5 / 5 |
| Mixture of Experts for Low-Resource LLMs | web | web_snippet | 2 / 2 |
| Mixture of Experts in Large Language Models | web | web_snippet | 3 / 3 |
| What is mixture of experts? / IBM | web | web_snippet | 1 / 1 |

**4. What is expert routing in MoE models?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Exploration-Driven Reinforcement Learning for Expert Routing Improvement in Mixture-of-Experts  | paper | full_text | 3 / 5 |
| Exploration-Driven Reinforcement Learning for Expert Routing Improvement in Mixture-of-Experts  | paper | full_text | 4 / 5 |
| MoE Lens -- An Expert Is All You Need | paper | full_text | 5 / 5 |
| Patch-level Routing in Mixture-of-Experts is Provably Sample-efficient for Convolutional Neural | paper | full_text | 5 / 5 |
| Patch-level Routing in Mixture-of-Experts is Provably Sample-efficient for Convolutional Neural | paper | full_text | 5 / 5 |
| ProbMoE: Differentiable Probabilistic Routing for Mixture-of-Experts | paper | full_text | 3 / 4 |
| ProbMoE: Differentiable Probabilistic Routing for Mixture-of-Experts | paper | full_text | 5 / 5 |
| Self-Routing: Parameter-Free Expert Routing from Hidden States | paper | full_text | 5 / 5 |
| Task-Conditioned Routing Signatures in Sparse Mixture-of-Experts Transformers | paper | full_text | 3 / 4 |
| Task-Conditioned Routing Signatures in Sparse Mixture-of-Experts Transformers | paper | full_text | 4 / 4 |
| Towards Understanding Mixture of Experts in Deep Learning | paper | full_text | 5 / 5 |
| Towards Understanding Mixture of Experts in Deep Learning | paper | full_text | 4 / 4 |
| Towards an empirical understanding of MoE design choices | paper | full_text | 5 / 5 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 3 / 3 |
| Auto Routing Benchmark: Cost Ladders / liteLLM | web | web_snippet | 2 / 2 |
| Daily Papers - Hugging Face | web | web_snippet | 3 / 4 |
| Mixture of Experts | web | web_snippet | 1 / 1 |
| Mixture-of-Experts with Expert Choice Routing | web | web_snippet | 5 / 5 |

**5. How is expert routing implemented in LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Attention-aware routing in mixture of experts language models | paper | full_text | 0 / 1 |
| Attention-aware routing in mixture of experts language models | paper | full_text | 3 / 4 |
| Deep Mixture of Experts via Shallow Embedding | paper | full_text | 2 / 2 |
| MoE Routing Testbed: Studying Expert Specialization and Routing Behavior at Small Scale | paper | full_text | 2 / 3 |
| MoE Routing Testbed: Studying Expert Specialization and Routing Behavior at Small Scale | paper | full_text | 2 / 2 |
| Routing by Analogy: kNN-Augmented Expert Assignment for Mixture-of-Experts | paper | full_text | 5 / 5 |
| ScoutRoute: Efficient Mixture-of-Experts Routing Using Internal Language Model Signals | paper | full_text | 1 / 1 |
| ScoutRoute: Efficient Mixture-of-Experts Routing Using Internal Language Model Signals | paper | full_text | 4 / 4 |
| Soft Merging of Experts with Adaptive Routing | paper | full_text | 5 / 5 |
| Task-Conditioned Routing Signatures in Sparse Mixture-of-Experts Transformers | paper | full_text | 1 / 3 |
| The Evolution of Mixture-of-Experts Architectures in Large Language Models: Routing, Topology,  | paper | full_text | 3 / 5 |
| When Are Experts Misrouted? Counterfactual Routing Analysis in Mixture-of-Experts Language Mode | paper | full_text | 5 / 5 |
| When Are Experts Misrouted? Counterfactual Routing Analysis in Mixture-of-Experts Language Mode | paper | full_text | 2 / 2 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 4 / 4 |
| Mixture of Experts in Large Language Models | web | web_snippet | 3 / 4 |
| Mixture-of-Experts with Expert Choice Routing | web | web_snippet | 4 / 4 |
| MoE Routing in Deep Learning | web | web_snippet | 1 / 1 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is a large language model (LLM)?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 23 = yes 17, partial 4, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How are LLMs trained | covered | 3 | 3 |
| 2 | How are LLMs used | covered | 5 | 3 |
| 3 | main challenges of LLMs | covered | 4 | 3 |
| 4 | main limitations of LLMs | covered | 5 | 3 |

### 2. What is a mixture of experts (MoE) model?

Sufficient: **True**; judge used: True; sources 6 (5 full text); judge candidates 18 = yes 11, partial 5, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does a MoE model differ from a standard neural network model? | covered | 2 | 2 |
| 2 | advantages of using a MoE model | covered | 5 | 4 |
| 3 | disadvantages of using a MoE model | covered | 4 | 4 |

### 3. How is MoE applied to LLMs?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 12 = yes 6, partial 2, no 4, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the benefits of using MoE in LLMs? | covered | 2 | 2 |
| 2 | What are the challenges of using MoE in LLMs? | covered | 4 | 3 |

### 4. What is expert routing in MoE models?

Sufficient: **False**; judge used: True; sources 13 (8 full text); judge candidates 18 = yes 6, partial 5, no 7, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does expert routing work in MoE models? | covered | 4 | 4 |
| 2 | What are the different types of expert routing strategies? | uncovered | 1 | 1 |
| 3 | How does expert routing affect the performance and efficiency of MoE models? | uncovered | 1 | 1 |

Uncovered details: What are the different types of expert routing strategies?; How does expert routing affect the performance and efficiency of MoE models?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 2 aspect(s), covered 0, 159.1 s.

| Aspect | Status | Steps tried | Covered by | Before (yes/partial/no) |
|---|---|---|---|---|
| What are the different types of expert routing strategies? | known_gap | reselect, pool, queries | - | 1/3/2 |
| How does expert routing affect the performance and efficiency of MoE models? | known_gap | reselect, pool, queries | - | 1/5/0 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 2 | 5 | 22 | 0 | 13.3 | sources_tried=5 |
| pool | 2 | 0 | 0 | 0 | 1.6 | parsed=0, sources_tried=3 |
| queries | 2 | 5 | 20 | 0 | 144.1 | queries=8, new_web_kept=3, new_web_found=24, new_papers_kept=3, new_papers_found=16, new_papers_parsed=3 |

### 5. How is expert routing implemented in LLMs?

Sufficient: **False**; judge used: True; sources 13 (9 full text); judge candidates 30 = yes 22, partial 6, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | existing methods for expert routing in LLMs | covered | 6 | 4 |
| 2 | existing architectures for expert routing in LLMs | covered | 5 | 5 |
| 3 | How do expert routing methods compare in terms of accuracy, speed, and scalability? | uncovered | 0 | 0 |
| 4 | open problems for expert routing in LLMs | covered | 5 | 4 |
| 5 | future directions for expert routing in LLMs | covered | 6 | 3 |

Uncovered details: How do they compare in terms of accuracy, speed, and scalability?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 0, 151.7 s.

| Aspect | Status | Steps tried | Covered by | Before (yes/partial/no) |
|---|---|---|---|---|
| How do expert routing methods compare in terms of accuracy, speed, and scalabili | known_gap | reselect, pool, queries | - | 0/2/2 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 4 | 5 | 0 | 10.4 | sources_tried=5 |
| pool | 1 | 2 | 8 | 0 | 14.3 | parsed=2, sources_tried=3 |
| queries | 1 | 3 | 8 | 0 | 127.0 | queries=4, new_web_kept=3, new_web_found=14, new_papers_kept=3, new_papers_found=3, new_papers_parsed=2 |

## 5. Retrieval details

- Web search variants: [14, 12, 14, 8, 14] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 140 candidates -> 136 cleared min_similarity (0.56) -> top 20 shortlisted; 110 candidates -> 105 cleared min_similarity (0.56) -> top 20 shortlisted; 135 candidates -> 129 cleared min_similarity (0.56) -> top 20 shortlisted; 65 candidates -> 59 cleared min_similarity (0.56) -> top 20 shortlisted; 118 candidates -> 112 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'both': 3, 'scopus': 28, 'openalex': 44, 'arxiv': 3}; requests to api.openalex.org in the log: 55
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 3
- Citation enrichment: Citation enrichment: 2 arXiv-only papers to enrich; took 1m 08s in total

## 6. Parsing details

- Attempted 27 papers, usable full text 25, 72 papers saved in the database.
- PDF obtained via: its own link: 1, the OpenAlex content API: 1; parse cache hits: 24; Unpaywall OA links found: 0; landing-page citation_pdf_url: 0
- Individual download failures: 2 -> HTTPStatusError: 2
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| Towards Understanding the Mixture-of-Experts Layer in Deep Learning | all PDF routes failed: None: None |

## 7. Groq and judge

- Stage 3: 40 digests for 5 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 114; per key (events / parked seconds): ...3mla: 1 / 422s, ...Ef4D: 21 / 346s, ...KJJp: 26 / 393s, ...KaRe: 21 / 394s, ...X2Oj: 15 / 341s, ...uNUk: 25 / 411s, ...x1nP: 5 / 3326s
- Judge batch latencies (s): [19.8, 17.1, 12.0, 17.2, 6.7, 6.9, 24.6, 6.1, 5.8, 6.1]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 2 | All PDF URLs failed for <id>: None: None |
| ERROR | 1 | All PDF URLs failed for <id>: ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 4 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 4 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 3 | SN rate limited on batch, backing off Ns |
| WARNING | 2 | Dropped query '<text>' for sub-question '<text>' (similarity N.N < N.N); it fits '<text>' better (N.N) |
| WARNING | 2 | Failed to download from <url> HTTPStatusError: HTTPStatusError('<text>') |
| WARNING | 1 | OpenAlex N on key ...CHgt for '<text>' (backoff N/N), pausing that key N.Ns |
| WARNING | 1 | Docling unavailable, using basic metadata: Server error '<text>' for url '<url> |
| WARNING | 1 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 1 | Playwright fallback failed: ValueError: ValueError('<text>') |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429) and citation enrichment still spent 1m 08s on 3 rate-limited batch calls.
- 1 paper(s) could not be downloaded by any route.
- Groq rate limiting: 114 parking events; digest generation took 2m 09s.
- Longest phase: Stage 3 judge + coverage (per sub-question) (6m 44s, 40% of the run).

Warnings in the log: 19; errors: 3.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes

(write your reading of this run here)
