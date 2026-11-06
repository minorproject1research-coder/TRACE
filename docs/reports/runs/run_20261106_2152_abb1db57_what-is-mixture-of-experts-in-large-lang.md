# Pipeline run report - What is mixture of experts in large language models and how does expert routing work?

Generated 2026-11-06 23:06 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 10 in the file) and the database. Query id `abb1db57-d2bd-4a76-b80f-89981ae68563`.

## 1. Summary

| | |
|---|---|
| Question | What is mixture of experts in large language models and how does expert routing work? |
| Domain anchor | (cached): 'deep learning' | context: Deep learning for NLP: 'expert' refers to a model subnetwork and 'routing' to the internal selection mechanism, not human experts or data‑network routing. |
| Started / finished | 2026-11-06 21:52:46 / 22:33:58 |
| **Total execution time** | **41m 12s** (2472 s) |
| Sub-questions / search queries | 5 / 13 (per sub-question [3, 3, 0, 2, 3]) |
| Plan source | plan-cache (stored plan reused, PLAN_CACHE=true) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 605 candidates -> 579 cleared the similarity floor -> 100 shortlisted |
| **Papers kept after the relevance judge** | **75** (log: 75); 25 shortlisted papers rejected |
| **Web sources** | **62** (per sub-question [13, 12, 17, 7, 13]) |
| Papers attempted for parsing | 30 (top-N per sub-question) |
| **Papers parsed to usable full text** | **25** of 30 attempted (20 from the parse cache) |
| Papers not parsed (all routes failed) | 1 download/route failures + 1 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 2 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 40 (25 from full text, 0 from abstracts, 15 from web snippets) |
| Findings (verified / total) | 86 / 104 |
| Coverage sufficient | 0 of 5 sub-questions |
| Judge | 1m 32s in 5 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 99 parking events, 1371 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 21:52:46 | 21:52:51 | 5s | 0% |
| Web search (Tavily) | 21:52:51 | 21:53:06 | 16s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 21:53:06 | 21:54:02 | 56s | 2% |
| Embedding pre-filter + relevance judge | 21:54:02 | 21:56:18 | 2m 16s | 5% |
| Citation enrichment (Semantic Scholar) | 21:56:19 | 21:57:27 | 1m 09s | 3% |
| Store papers in the database | 21:57:27 | 21:57:28 | 1s | 0% |
| PDF download + Docling parsing | 21:57:28 | 22:03:59 | 6m 31s | 16% |
| Stage 3 preparation (aspect split, chunking, embedding) | 22:03:59 | 22:08:53 | 4m 54s | 12% |
| Stage 3 digest generation (Groq) | 22:08:53 | 22:10:30 | 1m 38s | 4% |
| Stage 3 judge + coverage (per sub-question) | 22:10:30 | 22:12:09 | 1m 39s | 4% |
| **Total** | 21:52:46 | 22:33:58 | **41m 12s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is a large language model (LLM)? | 139 -> 135 -> 20 | 12 of 20 | 6 | 13 | 8 (5 / 0 / 3) | 12 / 12 | NOT sufficient |
| 2 | What is a mixture of experts (MoE) model? | 110 -> 105 -> 20 | 12 of 20 | 6 | 12 | 8 (5 / 0 / 3) | 19 / 20 | NOT sufficient |
| 3 | How is MoE applied to LLMs? | 173 -> 168 -> 20 | 18 of 20 | 6 | 17 | 8 (5 / 0 / 3) | 26 / 32 | NOT sufficient |
| 4 | What is expert routing in MoE models? | 65 -> 59 -> 20 | 17 of 20 | 5 | 7 | 8 (5 / 0 / 3) | 9 / 12 | NOT sufficient |
| 5 | How is expert routing implemented in LLMs? | 118 -> 112 -> 20 | 16 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 20 / 28 | NOT sufficient |

- Relevance judge rejected 8 papers for [What is a large language model (LLM)?]. Examples: 'Large Language Model in Various Fields: Opportunities, Chall' (The paper focuses on applications and challenges of LLMs in specific domains rather than defining what an LLM is.); 'A Survey on Evaluation of Large Language Models' (The paper focuses on evaluation methods and benchmarks for LLMs rather than defining what an LLM is.); 'Large Language Models: A Structured Taxonomy and Review of C' (The paper reviews challenges and ethical issues of LLMs rather than defining what an LLM is.)
- Relevance judge rejected 8 papers for [What is a mixture of experts (MoE) model]. Examples: 'Diversifying the Mixture-of-Experts Representation for Langu' (The paper assumes the reader already understands what an MoE model is and focuses exclusively on solving specific training optimization prob); 'Flexible and Effective Mixing of Large Language Models into ' (The paper discusses mixing pre-trained models into a domain expert framework, which is distinct from defining the internal architecture of a); 'An Alternative Model for Mixtures of Experts' (The paper focuses on an alternative gating mechanism and training algorithm for MoE, not on defining or explaining what an MoE model is.)
- Relevance judge rejected 2 papers for [How is MoE applied to LLMs?]. Examples: 'MoE-Compression: How the Compression Error of Experts Affect' (The paper focuses on memory compression techniques for MoE inference rather than explaining how MoE architectures are applied to LLMs.); 'Challenges and Limitations of Leveraging LLMs for Anomaly De' (The paper discusses general LLM limitations in numerical data and anomaly detection without mentioning MoE architectures or routing mechanis)
- Relevance judge rejected 3 papers for [What is expert routing in MoE models?]. Examples: 'Radio Frequency Machine Learning Mixture of Experts' (The paper applies MoE to radio frequency signals rather than addressing the general definition or mechanism of expert routing in NLP models.); 'Supervised Mixture-of-Experts with Deep Neural Network Routi' (The paper applies MoE routing to network intrusion detection rather than investigating the mechanism itself within the context of NLP.); 'Mixture-of-Experts Models in Vision: Routing, Optimization, ' (The paper studies MoE in vision tasks and focuses on optimization and generalization rather than explaining the mechanism of expert routing )
- Relevance judge rejected 4 papers for [How is expert routing implemented in LLM]. Examples: 'A Survey on Deep Learning for the Routing Layer of Computer ' (The paper discusses routing in computer networks, not the internal expert routing mechanisms within Large Language Models.); 'Universal Model Routing for Efficient LLM Inference' (The paper discusses routing between separate, distinct LLMs for inference efficiency, not the internal selection mechanism between subnetwor); 'Routing Manifold Alignment Improves Generalization of Mixtur' (The paper focuses on improving router performance via manifold alignment rather than explaining how expert routing is implemented.)

### Sources behind each sub-question's digests

**1. What is a large language model (LLM)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comprehensive Overview of Large Language Models | paper | full_text | 1 / 1 |
| Assessing the Strengths and Weaknesses of Large Language Models | paper | full_text | 2 / 2 |
| Challenges and Applications of Large Language Models | paper | full_text | 3 / 3 |
| Large Language Models: A Survey | paper | full_text | 1 / 1 |
| Natural language processing in the era of large language models | paper | full_text | 2 / 2 |
| AI Demystified: Introduction to large language models / University IT | web | web_snippet | 1 / 1 |
| What Are Large Language Models (LLMs)? / IBM | web | web_snippet | 1 / 1 |
| What is a large language model (LLM)? - University of Arizona Libraries | web | web_snippet | 1 / 1 |

**2. What is a mixture of experts (MoE) model?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Mixture of Experts in Large Language Models | paper | full_text | 2 / 2 |
| Learning Factored Representations in a Deep Mixture of Experts | paper | full_text | 4 / 5 |
| Mixture of Experts in Large Language Models | paper | full_text | 4 / 4 |
| Specialization through Collaboration: Understanding Expert Interaction in Mixture-of-Expert Lar | paper | full_text | 3 / 3 |
| Towards Understanding Mixture of Experts in Deep Learning | paper | full_text | 2 / 2 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 2 / 2 |
| A Survey on Mixture of Experts in Large Language Models | web | web_snippet | 0 / 0 |
| What is mixture of experts? / IBM | web | web_snippet | 2 / 2 |

**3. How is MoE applied to LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Mixture of Experts in Large Language Models | paper | full_text | 4 / 4 |
| Mixture of Experts in Large Language Models | paper | full_text | 2 / 3 |
| MoE-LLaVA: Mixture of Experts for Large Vision-Language Models | paper | full_text | 3 / 5 |
| OpenMoE: An Early Effort on Open Mixture-of-Experts Language Models | paper | full_text | 5 / 5 |
| Uni-MoE: Scaling Unified Multimodal LLMs With Mixture of Experts | paper | full_text | 4 / 5 |
| Mixture of Experts in Large Language Models | web | web_snippet | 2 / 3 |
| Mixture of Experts in Large Language Models | web | web_snippet | 3 / 3 |
| Sparse Mixture-of-Experts Transformers for Efficient Scaling of Large Language Models | web | web_snippet | 3 / 4 |

**4. What is expert routing in MoE models?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Exploration-Driven Reinforcement Learning for Expert Routing Improvement in Mixture-of-Experts  | paper | full_text | 0 / 1 |
| Patch-level Routing in Mixture-of-Experts is Provably Sample-efficient for Convolutional Neural | paper | full_text | 2 / 3 |
| ProbMoE: Differentiable Probabilistic Routing for Mixture-of-Experts | paper | full_text | 1 / 1 |
| Task-Conditioned Routing Signatures in Sparse Mixture-of-Experts Transformers | paper | full_text | 3 / 3 |
| Towards Understanding Mixture of Experts in Deep Learning | paper | full_text | 0 / 1 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 1 / 1 |
| Mixture-of-Experts with Expert Choice Routing | web | web_snippet | 1 / 1 |
| What is mixture of experts? / IBM | web | web_snippet | 1 / 1 |

**5. How is expert routing implemented in LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Attention-aware routing in mixture of experts language models | paper | full_text | 4 / 5 |
| MoE Routing Testbed: Studying Expert Specialization and Routing Behavior at Small Scale | paper | full_text | 1 / 5 |
| ScoutRoute: Efficient Mixture-of-Experts Routing Using Internal Language Model Signals | paper | full_text | 3 / 3 |
| Task-Conditioned Routing Signatures in Sparse Mixture-of-Experts Transformers | paper | full_text | 1 / 3 |
| When Are Experts Misrouted? Counterfactual Routing Analysis in Mixture-of-Experts Language Mode | paper | full_text | 1 / 2 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 1 / 1 |
| Mixture of Experts in Large Language Models | web | web_snippet | 4 / 4 |
| Mixture-of-Experts with Expert Choice Routing | web | web_snippet | 5 / 5 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is a large language model (LLM)?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 14 = yes 4, partial 3, no 7, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How are LLMs trained? | uncovered | 0 | 0 |
| 2 | How are LLMs used? | uncovered | 1 | 1 |
| 3 | main challenges of LLMs | uncovered | 0 | 0 |
| 4 | main limitations of LLMs | uncovered | 0 | 0 |
| 5 | What is a large language model (LLM)? | covered | 3 | 3 |

Uncovered details: How are LLMs trained and used?; What are the main challenges and limitations of LLMs?

### 2. What is a mixture of experts (MoE) model?

Sufficient: **False**; judge used: True; sources 7 (5 full text); judge candidates 20 = yes 11, partial 6, no 3, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does a MoE model differ from a standard neural network model? | uncovered | 1 | 1 |
| 2 | advantages of using a MoE model | covered | 4 | 3 |
| 3 | disadvantages of using a MoE model | uncovered | 2 | 1 |
| 4 | What is a mixture of experts (MoE) model? | covered | 4 | 4 |

Uncovered details: How does a MoE model differ from a standard neural network model?; What are the advantages and disadvantages of using a MoE model?

### 3. How is MoE applied to LLMs?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 8, partial 6, no 4, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the benefits of using MoE in LLMs? | covered | 4 | 4 |
| 2 | challenges of using MoE in LLMs | covered | 3 | 2 |
| 3 | How is MoE applied to LLMs? | uncovered | 1 | 1 |

Uncovered details: How is MoE applied to LLMs?

### 4. What is expert routing in MoE models?

Sufficient: **False**; judge used: False; sources 6 (3 full text); judge candidates 20 = yes 11, partial 4, no 4, error 1; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does expert routing work in MoE models? | covered | 6 | 6 |
| 2 | What are the different types of expert routing strategies? | uncovered | 0 | 0 |
| 3 | How does expert routing affect the performance of MoE models? | unjudged | 0 | 0 |
| 4 | How does expert routing affect the efficiency of MoE models? | uncovered | 0 | 0 |
| 5 | What is expert routing in MoE models? | covered | 5 | 5 |

Uncovered details: What are the different types of expert routing strategies?; How does expert routing affect the performance and efficiency of MoE models?

### 5. How is expert routing implemented in LLMs?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 27 = yes 10, partial 12, no 5, error 0; digest failures 1.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the existing methods for expert routing in LLMs? | uncovered | 1 | 1 |
| 2 | What are the existing architectures for expert routing in LLMs? | uncovered | 1 | 1 |
| 3 | How do expert routing implementations in LLMs compare in terms of accuracy, speed, and scalability? | uncovered | 0 | 0 |
| 4 | open problems for expert routing in LLMs | covered | 2 | 2 |
| 5 | future directions for expert routing in LLMs | covered | 2 | 2 |
| 6 | How is expert routing implemented in LLMs? | covered | 4 | 4 |

Uncovered details: What are the existing methods and architectures for expert routing in LLMs?; How do they compare in terms of accuracy, speed, and scalability?

## 5. Retrieval details

- Web search variants: [13, 12, 17, 7, 13] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 139 candidates -> 135 cleared min_similarity (0.56) -> top 20 shortlisted; 110 candidates -> 105 cleared min_similarity (0.56) -> top 20 shortlisted; 173 candidates -> 168 cleared min_similarity (0.56) -> top 20 shortlisted; 65 candidates -> 59 cleared min_similarity (0.56) -> top 20 shortlisted; 118 candidates -> 112 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 43, 'arxiv': 2, 'both': 3, 'scopus': 27}; requests to api.openalex.org in the log: 31
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 3
- Citation enrichment: Citation enrichment: 1 arXiv-only papers to enrich; took 1m 09s in total

## 6. Parsing details

- Attempted 30 papers, usable full text 25, 75 papers saved in the database.
- PDF obtained via: its own link: 7, Unpaywall: 1; parse cache hits: 20; Unpaywall OA links found: 1; landing-page citation_pdf_url: 0
- Individual download failures: 2 -> ValueError: 2
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| Towards Understanding the Mixture-of-Experts Layer in Deep Learning | all PDF routes failed: None: None |
| A Review of Current Trends, Techniques, and Challenges in Large Language Models (LLMs) | parse/database error: Server disconnected |

## 7. Groq and judge

- Stage 3: 40 digests for 5 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 99; per key (events / parked seconds): ...3mla: 14 / 182s, ...Ef4D: 18 / 227s, ...KJJp: 12 / 165s, ...KaRe: 15 / 171s, ...X2Oj: 13 / 208s, ...uNUk: 17 / 268s, ...x1nP: 10 / 150s
- Judge batch latencies (s): [14.2, 18.7, 17.1, 18.4, 23.7]

- Judge verdicts that came back as error: 1 -> aspect 3 of 'ProbMoE: Differentiable Probabilistic Ro': the judge returned no verdict and gave no error text | raw output: {"quote_supports_claim": "yes", "answers_aspect": "no

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 1 | Failed to parse paper <id>: Server disconnected |
| ERROR | 1 | All PDF URLs failed for <id>: None: None |
| ERROR | 1 | Digest generation failed: Expecting value: line N column N (char N) |
| WARNING | 3 | SN rate limited on batch, backing off Ns |
| WARNING | 3 | Docling unavailable, using basic metadata: Server error '<text>' for url '<url> |
| WARNING | 2 | Dropped query '<text>' for sub-question '<text>' (similarity N.N < N.N); it fits '<text>' better (N.N) |
| WARNING | 2 | Parse cache lookup failed for <id>: RemoteProtocolError: Server disconnected |
| WARNING | 2 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | OpenAlex N on key ...CHgt for '<text>' (backoff N/N), pausing that key N.Ns |
| WARNING | 1 | Digest JSON parse failed (attempt N/N): Expecting value: line N column N (char N) |
| WARNING | 1 | Judge verdict failed: aspect N, source NbfNeN-bN, claim '<text>': the judge returned no verdict and gave no er |
| WARNING | 1 | Judge: N of N item(s) in this batch failed |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429) and citation enrichment still spent 1m 09s on 3 rate-limited batch calls.
- Sub-question 'What is expert routing in MoE models?': 1 unjudged aspect(s) (a judge verdict failed): ['How does expert routing affect the performance of MoE models?']
- Sub-question 'How is expert routing implemented in LLMs?': 1 digest JSON failure(s).
- 1 paper(s) failed at the parse/database step: A Review of Current Trends, Techniques, and Challe (Server disconnected)
- 1 paper(s) could not be downloaded by any route.
- Groq rate limiting: 99 parking events; digest generation took 1m 38s.
- Longest phase: PDF download + Docling parsing (6m 31s, 16% of the run).

Warnings in the log: 18; errors: 3.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand)

**Bottom line.** The first complete run started through the API (the web app's request), same question as the 2026-11-05 Q2 run. It ran end to end (planner, retrieval, Stage 3) but **0 of 5 sub-questions are sufficient (4 of 5 before)**, and most of the drop is explained by one change of mine: the topic aspect (`TOPIC_ASPECT`, then on by default) made the digest model return 65% fewer findings. Controlled test: `tests/topic_aspect_digest_experiment.py` (4.25 -> 1.50 findings per digest on the same 6 sources). `TOPIC_ASPECT` is now off by default; this run should be repeated with it off (the plan cache makes the sub-questions identical) before comparing it with 2026-11-05.

- **Real length is about 19m 23s (21:52:46 to 22:12:09), not 41m 12s.** The report tool ends an API run at the start of the next run, and the log between 22:12 and 22:33 holds HTTP request lines of the web app. For runs started through the API, read the end of the run from the last Stage 3 line.
- Plan source `plan-cache` (PLAN_CACHE=true): the planner took 5 s. The query gate dropped both queries of "How is MoE applied to LLMs?" (0 planner queries, expanded by the LLM; 17 web sources, none of them off topic this time).
- Findings per digest 2.60 (was 3.65); verified 86 of 104 (83%, was 85%): the verifier change did not raise the verified share in a real run (its estimate of about +5 points came from stored digests).
- Errors: one judge verdict failed (sub-question 4 has an unjudged aspect and `judge_used` False), one digest JSON failure (recovered), one paper lost to "Server disconnected" while parsing, two parse-cache lookups failed with the same error. The database connection drops under load; the API now retries reads once (commit 97cca63), the pipeline's own database calls do not.
- Judge and Groq: 99 parking events, digest generation 1m 38s (many digests had few findings to write).
- Citation enrichment still spent 1m 09s on Semantic Scholar 429s.

**To do:** repeat with `TOPIC_ASPECT=false`; make the pipeline's database reads retry on connection errors; end API runs correctly in `pipeline_run_report.py`.
