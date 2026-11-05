# Pipeline run report - What is mixture of experts in large language models and how does expert routing work?

Generated 2026-11-05 21:58 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 8 in the file) and the database. Query id `cc81e9cc-1bfd-48d1-a3cc-ed23e8c00320`.

## 1. Summary

| | |
|---|---|
| Question | What is mixture of experts in large language models and how does expert routing work? |
| Domain anchor | (cached): 'deep learning' | context: Deep learning for NLP: 'expert' refers to a model subnetwork and 'routing' to the internal selection mechanism, not human experts or data‑network routing. |
| Started / finished | 2026-11-05 20:53:07 / 21:15:17 |
| **Total execution time** | **22m 10s** (1330 s) |
| Sub-questions / search queries | 5 / 13 (per sub-question [3, 3, 2, 2, 3]) |
| Plan source | planner |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 539 candidates -> 465 cleared the similarity floor -> 100 shortlisted |
| **Papers kept after the relevance judge** | **69** (log: 69); 31 shortlisted papers rejected |
| **Web sources** | **54** (per sub-question [14, 10, 10, 8, 12]) |
| Papers attempted for parsing | 32 (top-N per sub-question) |
| **Papers parsed to usable full text** | **25** of 32 attempted (6 from the parse cache) |
| Papers not parsed (all routes failed) | 5 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 14 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 40 (25 from full text, 0 from abstracts, 15 from web snippets) |
| Findings (verified / total) | 124 / 146 |
| Coverage sufficient | 4 of 5 sub-questions |
| Judge | 1m 42s in 6 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 108 parking events, 3537 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 20:53:07 | 20:53:36 | 30s | 2% |
| Web search (Tavily) | 20:53:36 | 20:53:49 | 12s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 20:53:49 | 20:54:37 | 48s | 4% |
| Embedding pre-filter + relevance judge | 20:54:37 | 20:56:33 | 1m 56s | 9% |
| Citation enrichment (Semantic Scholar) | 20:56:33 | 20:56:44 | 10s | 1% |
| Store papers in the database | 20:56:44 | 20:56:46 | 2s | 0% |
| PDF download + Docling parsing | 20:56:46 | 21:04:53 | 8m 07s | 37% |
| Stage 3 preparation (aspect split, chunking, embedding) | 21:04:53 | 21:09:28 | 4m 35s | 21% |
| Stage 3 digest generation (Groq) | 21:09:28 | 21:13:28 | 4m 01s | 18% |
| Stage 3 judge + coverage (per sub-question) | 21:13:28 | 21:15:16 | 1m 47s | 8% |
| **Total** | 20:53:07 | 21:15:17 | **22m 10s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is a large language model (LLM)? | 131 -> 120 -> 20 | 12 of 20 | 5 | 14 | 8 (5 / 0 / 3) | 29 / 30 | sufficient |
| 2 | What is a mixture of experts (MoE) model? | 117 -> 97 -> 20 | 11 of 20 | 6 | 10 | 8 (5 / 0 / 3) | 26 / 30 | sufficient |
| 3 | How is MoE applied to LLMs? | 102 -> 89 -> 20 | 13 of 20 | 5 | 10 | 8 (5 / 0 / 3) | 20 / 22 | sufficient |
| 4 | What is expert routing in MoE models? | 64 -> 55 -> 20 | 17 of 20 | 5 | 8 | 8 (5 / 0 / 3) | 27 / 32 | sufficient |
| 5 | How is expert routing implemented in LLMs? | 125 -> 104 -> 20 | 16 of 20 | 5 | 12 | 8 (5 / 0 / 3) | 22 / 32 | NOT sufficient |

- Relevance judge rejected 8 papers for [What is a large language model (LLM)?]. Examples: 'Large Language Model in Various Fields: Opportunities, Chall' (The paper focuses on applications and challenges of LLMs in specific domains rather than defining what an LLM is.); 'Large Language Models: A Structured Taxonomy and Review of C' (The paper reviews challenges and ethical issues of LLMs rather than defining what an LLM is.); 'Integrated Method of Deep Learning and Large Language Model ' (The paper focuses on applying LLMs to speech recognition rather than defining or explaining what an LLM is.)
- Relevance judge rejected 9 papers for [What is a mixture of experts (MoE) model]. Examples: 'Diversifying the Mixture-of-Experts Representation for Langu' (The paper assumes the reader already understands what an MoE model is and focuses exclusively on solving the problem of homogeneous represen); 'Flexible and Effective Mixing of Large Language Models into ' (The paper discusses mixing pre-trained models into a domain expert framework, which is distinct from defining the internal architecture of a); 'An Alternative Model for Mixtures of Experts' (The paper focuses on an alternative gating mechanism and training algorithm for MoE, not on defining or explaining what an MoE model is.)
- Relevance judge rejected 7 papers for [How is MoE applied to LLMs?]. Examples: 'Flexible and Effective Mixing of Large Language Models into ' (The paper discusses mixing pre-trained models into a domain expert framework rather than applying MoE architectures (expert subnetworks and ); 'Efficient Edge Deployment of Mixture-of-Experts Models With ' (The paper focuses on deployment optimization and quantization rather than explaining how MoE architectures are applied to LLMs.); 'SmolLM2: When Smol Goes Big -- Data-Centric Training of a Sm' (The paper focuses on data-centric training and model scaling for small LMs without mentioning MoE architecture or routing mechanisms.)
- Relevance judge rejected 3 papers for [What is expert routing in MoE models?]. Examples: 'Radio Frequency Machine Learning Mixture of Experts' (The paper applies MoE to radio frequency signals rather than addressing the general definition or mechanism of expert routing in NLP models.); 'Supervised Mixture-of-Experts with Deep Neural Network Routi' (The paper applies MoE routing to network intrusion detection rather than investigating the fundamental mechanism of expert routing in NLP mo); 'Mixture-of-Experts Models in Vision: Routing, Optimization, ' (The paper studies MoE in vision tasks and focuses on generalization and efficiency rather than defining or explaining the expert routing mec)
- Relevance judge rejected 4 papers for [How is expert routing implemented in LLM]. Examples: 'A Survey on Deep Learning for the Routing Layer of Computer ' (The paper discusses routing in computer networks, not the internal expert routing mechanisms within Large Language Models.); 'Routing Manifold Alignment Improves Generalization of Mixtur' (The paper focuses on optimizing router performance via manifold alignment rather than explaining how expert routing is implemented.); 'LLMMR: A Large Language Model-Guided Mixture-of-Experts Fram' (The paper applies MoE routing to satellite network traffic management rather than investigating the internal implementation of expert routin)

### Sources behind each sub-question's digests

**1. What is a large language model (LLM)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comprehensive Overview of Large Language Models | paper | full_text | 3 / 3 |
| A Review of Current Trends, Techniques, and Challenges in Large Language Models (LLMs) | paper | full_text | 5 / 5 |
| Assessing the Strengths and Weaknesses of Large Language Models | paper | full_text | 4 / 5 |
| Natural language processing in the era of large language models | paper | full_text | 5 / 5 |
| Survey of Different Large Language Model Architectures: Trends, Benchmarks, and Challenges | paper | full_text | 4 / 4 |
| AI Demystified: Introduction to large language models / University IT | web | web_snippet | 4 / 4 |
| What Are Large Language Models (LLMs)? / IBM | web | web_snippet | 3 / 3 |
| What is a large language model (LLM)? - University of Arizona Libraries | web | web_snippet | 1 / 1 |

**2. What is a mixture of experts (MoE) model?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Mixture of Experts in Large Language Models | paper | full_text | 3 / 4 |
| Learning Factored Representations in a Deep Mixture of Experts | paper | full_text | 4 / 5 |
| Mixture of Experts in Large Language Models | paper | full_text | 3 / 4 |
| Specialization through Collaboration: Understanding Expert Interaction in Mixture-of-Expert Lar | paper | full_text | 3 / 3 |
| Towards Understanding Mixture of Experts in Deep Learning | paper | full_text | 4 / 5 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 4 / 4 |
| Mixture of experts | web | web_snippet | 3 / 3 |
| What is mixture of experts? / IBM | web | web_snippet | 2 / 2 |

**3. How is MoE applied to LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Mixture of Experts in Large Language Models | paper | full_text | 4 / 4 |
| Branch-Train-MiX: Mixing Expert LLMs into a Mixture-of-Experts LLM | paper | full_text | 5 / 5 |
| Mixture Compressor for Mixture-of-Experts LLMs Gains More | paper | full_text | 4 / 5 |
| Mixture of Experts in Large Language Models | paper | full_text | 3 / 3 |
| Not All Experts are Equal: Efficient Expert Pruning and Skipping for Mixture-of-Experts Large L | paper | full_text | 4 / 5 |
| AI Demystified: Introduction to large language models / University IT | web | web_snippet | 0 / 0 |
| What Are Large Language Models (LLMs)? / IBM | web | web_snippet | 0 / 0 |
| What is LLM? - Large Language Models Explained - AWS | web | web_snippet | 0 / 0 |

**4. What is expert routing in MoE models?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Exploration-Driven Reinforcement Learning for Expert Routing Improvement in Mixture-of-Experts  | paper | full_text | 5 / 5 |
| Patch-level Routing in Mixture-of-Experts is Provably Sample-efficient for Convolutional Neural | paper | full_text | 2 / 4 |
| ProbMoE: Differentiable Probabilistic Routing for Mixture-of-Experts | paper | full_text | 4 / 4 |
| Task-Conditioned Routing Signatures in Sparse Mixture-of-Experts Transformers | paper | full_text | 4 / 4 |
| Towards Understanding Mixture of Experts in Deep Learning | paper | full_text | 3 / 5 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 2 / 3 |
| Mixture of Experts | web | web_snippet | 3 / 3 |
| Mixture-of-Experts with Expert Choice Routing | web | web_snippet | 4 / 4 |

**5. How is expert routing implemented in LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Attention-aware routing in mixture of experts language models | paper | full_text | 0 / 5 |
| MoE Routing Testbed: Studying Expert Specialization and Routing Behavior at Small Scale | paper | full_text | 3 / 4 |
| ScoutRoute: Efficient Mixture-of-Experts Routing Using Internal Language Model Signals | paper | full_text | 5 / 5 |
| Task-Conditioned Routing Signatures in Sparse Mixture-of-Experts Transformers | paper | full_text | 2 / 4 |
| When Are Experts Misrouted? Counterfactual Routing Analysis in Mixture-of-Experts Language Mode | paper | full_text | 3 / 4 |
| A Comprehensive Survey of Mixture-of-Experts: Algorithms, Theory, and Applications | web | web_snippet | 1 / 2 |
| Mixture of Experts in Large Language Models | web | web_snippet | 3 / 3 |
| Mixture-of-Experts with Expert Choice Routing | web | web_snippet | 5 / 5 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is a large language model (LLM)?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 23 = yes 16, partial 5, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How are LLMs trained? | covered | 3 | 3 |
| 2 | How are LLMs used? | covered | 4 | 4 |
| 3 | main challenges of LLMs | covered | 5 | 5 |
| 4 | main limitations of LLMs | covered | 4 | 3 |

### 2. What is a mixture of experts (MoE) model?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 11, partial 4, no 3, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does a MoE model differ from a standard neural network model? | covered | 2 | 2 |
| 2 | advantages of using a MoE model | covered | 5 | 4 |
| 3 | disadvantages of using a MoE model | covered | 4 | 3 |

### 3. How is MoE applied to LLMs?

Sufficient: **True**; judge used: True; sources 5 (5 full text); judge candidates 12 = yes 5, partial 4, no 3, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the benefits of using MoE in LLMs? | covered | 2 | 2 |
| 2 | What are the challenges of using MoE in LLMs? | covered | 3 | 2 |

### 4. What is expert routing in MoE models?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 24 = yes 13, partial 2, no 9, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does expert routing work in MoE models? | covered | 4 | 4 |
| 2 | different types of expert routing strategies in MoE models | covered | 3 | 2 |
| 3 | How does expert routing affect the performance of MoE models? | covered | 3 | 3 |
| 4 | How does expert routing affect the efficiency of MoE models? | covered | 3 | 3 |

### 5. How is expert routing implemented in LLMs?

Sufficient: **False**; judge used: True; sources 7 (4 full text); judge candidates 34 = yes 17, partial 12, no 5, error 0; digest failures 2.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the existing methods for expert routing in LLMs? | covered | 2 | 2 |
| 2 | What are the existing architectures for expert routing in LLMs? | uncovered | 1 | 1 |
| 3 | accuracy comparison of expert routing implementations in LLMs | covered | 4 | 4 |
| 4 | speed comparison of expert routing implementations in LLMs | covered | 4 | 4 |
| 5 | scalability comparison of expert routing implementations in LLMs | covered | 3 | 2 |
| 6 | What are the open problems for expert routing in LLMs? | covered | 2 | 2 |
| 7 | What are the future directions for expert routing in LLMs? | uncovered | 1 | 1 |

Uncovered details: What are the existing methods and architectures for expert routing in LLMs?; What are the open problems and future directions for expert routing in LLMs?

## 5. Retrieval details

- Web search variants: [14, 10, 10, 8, 12] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 131 candidates -> 120 cleared min_similarity (0.56) -> top 20 shortlisted; 117 candidates -> 97 cleared min_similarity (0.56) -> top 20 shortlisted; 102 candidates -> 89 cleared min_similarity (0.56) -> top 20 shortlisted; 64 candidates -> 55 cleared min_similarity (0.56) -> top 20 shortlisted; 125 candidates -> 104 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'both': 3, 'scopus': 31, 'openalex': 32, 'arxiv': 3}; requests to api.openalex.org in the log: 31
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0
- Citation enrichment: Citation enrichment: 2 arXiv-only papers to enrich; took 10s in total

## 6. Parsing details

- Attempted 32 papers, usable full text 25, 69 papers saved in the database.
- PDF obtained via: its own link: 16, Unpaywall: 3, the OpenAlex content API: 1; parse cache hits: 6; Unpaywall OA links found: 4; landing-page citation_pdf_url: 0
- Individual download failures: 14 -> HTTPStatusError: 7, ValueError: 7
- Headless-browser fallback: 4 tried, 4 failed; Docling fetch-by-URL attempts: 8; HTML full-text attempts that failed: 8

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| From Large Language Models to Large Multimodal Models: A Literature Review | all PDF routes failed: HTTPStatusError: HTTPStatusError('403 Forbidden') |
| Exploring the frontiers of deep learning and natural language processing: A comprehensive  | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |
| The Evolution of Mixture of Experts: A Survey from Basics to Breakthroughs | all PDF routes failed: HTTPStatusError: HTTPStatusError('403 Forbidden') |
| Scaling Laws for Mixture-of-Experts: Emergence of Specialization and Routing Efficiency in | all PDF routes failed: HTTPStatusError: HTTPStatusError("Client error '410 GONE' for url 'https://zenodo.org/reco |
| Towards Understanding the Mixture-of-Experts Layer in Deep Learning | all PDF routes failed: None: None |

## 7. Groq and judge

- Stage 3: 40 digests for 5 sub-questions, 4 worker(s), 4 Groq key(s)
- Rate-limit parking events: 108; per key (events / parked seconds): ...KJJp: 31 / 2382s, ...KaRe: 27 / 438s, ...X2Oj: 24 / 333s, ...x1nP: 26 / 384s
- Judge batch latencies (s): [19.4, 17.2, 13.4, 20.4, 26.5, 4.7]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 2 | All PDF URLs failed for <id>: HTTPStatusError: HTTPStatusError('<text>') |
| ERROR | 2 | Digest generation failed: Expecting value: line N column N (char N) |
| ERROR | 1 | All PDF URLs failed for <id>: ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| ERROR | 1 | All PDF URLs failed for <id>: HTTPStatusError: HTTPStatusError("Client error 'N GONE' for url '<url> more info |
| ERROR | 1 | All PDF URLs failed for <id>: None: None |
| WARNING | 6 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 5 | Failed to download from <url> HTTPStatusError: HTTPStatusError('<text>') |
| WARNING | 4 | Playwright fallback failed: ValueError: ValueError('<text>') |
| WARNING | 2 | Failed to download from <url> HTTPStatusError: HTTPStatusError("Client error 'N GONE' for url '<url> more info |
| WARNING | 2 | Digest JSON parse failed (attempt N/N): Expecting value: line N column N (char N) |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | Docling unavailable, using basic metadata: Server error '<text>' for url '<url> |
| WARNING | 1 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: application/pdf) for <ur |
| WARNING | 1 | Unpaywall route failed for '<text>': ValueError: Non-PDF response (content-type: text/html) for <url> |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- Sub-question 'How is expert routing implemented in LLMs?': 2 digest JSON failure(s).
- 5 paper(s) could not be downloaded by any route.
- Groq rate limiting: 108 parking events; digest generation took 4m 01s.
- Longest phase: PDF download + Docling parsing (8m 07s, 37% of the run).

Warnings in the log: 24; errors: 7.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand after reading the log and the database)

**Bottom line.** A complete, clean run (22m 10s, no crash, no judge error), and the best-looking coverage so far (4 of 5 sub-questions "sufficient"), but that number flatters the evidence. The planner spent one of its five sub-questions on a background topic the user did not ask about ("What is a large language model?"), two sub-questions were handed the wrong search queries, and the aspects that decide "sufficient" are mostly generic ("advantages", "disadvantages", "challenges", "limitations") instead of the content of the question (what an expert is, what a router computes). The two things that go wrong in Stage 3 are small: 2 empty Groq replies (retried and recovered) and one paper whose 5 quotes could not be verified.

An earlier start of this question at 20:49:47 was stopped after about 40 seconds (the log ends during web-source scoring); it is not part of this report. The report is for the run that started at 20:53:07.

### Compared with the last Mamba run (Q1, run at 17:33)

| | Q1 (17:33) | **Q2 (20:53)** |
|---|---|---|
| Total time | 15m 14s | **22m 10s** |
| Candidates / kept papers | 479 / 48 | **539 / 69** |
| Kept by source | OpenAlex 34, Scopus 13, both 1 | **OpenAlex 32, Scopus 31, both 3, arXiv 3** |
| Papers attempted / usable full text | 26 / 25 (23 from the parse cache) | **32 / 25 (6 from the cache)** |
| PDF + parsing phase | 35 s | **8m 07s (37% of the run)** |
| Stage 3 preparation | 5m 30s | 4m 35s |
| Digests (full text / web) | 25 / 15 | 25 / 15 |
| Findings verified / total | 122 / 150 | 124 / 146 |
| Judge pairs / errors | 102 / 0 | **111 / 0** |
| Sub-questions sufficient | 2 of 5 | **4 of 5** |
| Groq parking events | 99 | 108 |

The time difference is almost entirely parsing: Q1's 35 s was a cache effect, Q2 is a new topic, so 26 papers were downloaded and parsed from scratch (about 19 s per paper, 8m 07s in total). This is the realistic cost of a new question.

### What is wrong, in order of impact

1. **Search queries were given to the wrong sub-questions.** The planner's flat query list is spread over the sub-questions by similarity with an even share, and that forced two bad hand-outs:
   - "What is a large language model (LLM)?" received "expert routing in large language models comparison and evaluation deep learning".
   - "How is MoE applied to LLMs?" received "large language model training and usage deep learning" (a general LLM query) next to one MoE query.
   The effect is visible in the web results of sub-question 3: its three web sources are generic LLM pages (a university IT page, IBM "What Are Large Language Models", AWS "What is LLM?"), and all three digests have **0 findings** (0 / 0). Sub-question 3 is "sufficient" on its 5 full-text papers alone.

2. **A background sub-question took 20% of the budget.** Sub-question 1 ("What is a large language model?") was not asked by the user, yet it got 20 shortlisted papers, 5 parsed papers, 8 digests and 4 aspects: "How are LLMs trained?", "How are LLMs used?", "main challenges of LLMs", "main limitations of LLMs". Its "sufficient" says nothing about mixture of experts. The same pattern as "What are SSMs?" in Q1.

3. **"Sufficient" rests on generic aspects.** In both questions the aspect splitter produces the same families for almost every sub-question: advantages, disadvantages, challenges, limitations, benefits. Sub-question 2 ("What is a mixture of experts model?") has three aspects: "differs from a standard neural network", "advantages", "disadvantages". There is no aspect for what an expert is or what the gating network does, so the sub-question is "sufficient" without the definition being asked of the evidence. Sub-question 3 ("How is MoE applied to LLMs?") has only "benefits" and "challenges". These are easy to cover; it inflates 4 of 5.

4. **Sub-question 5 is the only one not sufficient, for two aspects with 1 yes each**: "What are the existing architectures for expert routing in LLMs?" and "What are the future directions for expert routing in LLMs?". It is also the sub-question with the largest judge load (34 candidates: 17 yes, 12 partial, 5 no) and both digest failures. Its two detail questions are two-part ("methods and architectures", "open problems and future directions"); the splitter made one aspect per half, and in each pair one half is covered and the other is not.

5. **Paper downloads failed more than in Q1.** 14 individual download failures (7 HTTP errors, 7 "Non-PDF response" HTML pages), the headless-browser fallback tried 4 times and failed 4 times, and 8 Docling fetch-by-URL attempts failed. 5 papers ended with no text: two `403 Forbidden` (including "The Evolution of Mixture of Experts: A Survey from Basics to Breakthroughs", a survey exactly on the topic, and "From Large Language Models to Large Multimodal Models"), one DOI page returning HTML, one Zenodo `410 GONE` ("Scaling Laws for Mixture-of-Experts"), one with no reason logged. PDFs came from the paper's own link (16), Unpaywall (3) and the OpenAlex content API (1).

6. **One paper had 0 of 5 findings verified, and the cause is the digest model, not the verifier.** "Attention-aware routing in mixture of experts language models" (a diploma thesis, partly in Greek) was digested into 5 findings whose content is in the paper, but the quotes are edited: citation markers like "[4]" are dropped, clauses are spliced ("... (K = 1), while GShard, Mixtral ..." joins two sentences), so none of them is a contiguous passage. I tested the effect of removing "[n]" markers and the extra spaces Docling puts inside parentheses ("( K = 1 )"): only 1 of the 5 quotes then verifies (fuzzy scores 51 to 86 against a threshold of 92 for the other four). So the verifier is right to reject them, and the source is lost for coverage. Overall 22 of 146 findings (15%) are unverified.

7. **Groq: one key was out for most of the run.** Key `...KJJp` was parked once for 1908 s (about 32 minutes), 2382 s in total, while the other three keys parked 333 to 438 s each; so the digests ran on three keys. This looks like a long-window limit on that key, not the usual per-minute 429s (this was the 8th pipeline start of the day, plus aspect splits). Digest time was still 4m 01s. **The next runs (Q3 to Q6) may be starved if more keys hit the same limit.**

### What worked

- The domain anchor kept the field right: "deep learning" with the context that "expert" is a model subnetwork. The judge rejected "A Survey on Deep Learning for the Routing Layer of Computer Networks" and "Radio Frequency Machine Learning Mixture of Experts", and no human-expert or network-routing papers were digested.
- OpenAlex and Scopus both contributed (31 requests to OpenAlex; kept papers: OpenAlex 35 and Scopus 34, 3 of them found by both); Semantic Scholar was skipped (probe 429) as usual.
- 2 digest failures ("Expecting value: line 1 column 1", an empty Groq reply) were retried and recovered: the counter shows `digest_failures = 2` for sub-question 5, with no "failed after 2 attempts" line. All 8 digests of that sub-question exist.
- Sources are on topic: surveys of MoE in LLMs, Branch-Train-MiX, Mixture Compressor, expert pruning, routing papers (ProbMoE, Task-Conditioned Routing Signatures, ScoutRoute), IBM and survey pages as web sources.

### For Loop 2
- The two uncovered aspects of sub-question 5 (existing architectures, future directions) are the first real candidates from a non-Mamba question. Both already have 1 yes, so cheaper ladder steps (re-select chunks, the next-ranked papers) should come before new queries.
- Run `gap_queries.generate` on "What are the future directions for expert routing in LLMs?" with the 3 tried queries of sub-question 5 to see whether it finds new angles (not done yet).

### Next checks
- [ ] Q3 to Q6: check Groq keys before starting (one key was parked for 32 minutes in this run).
- [ ] Look for the same query hand-out problem (a sub-question given a query that belongs to another one) in the other runs.
- [ ] Count how many aspects across runs are the generic "advantages / disadvantages / challenges / limitations" family.

(To regenerate the tables above after another run: `python scripts/pipeline_run_report.py --run 8`; these notes are kept.)
