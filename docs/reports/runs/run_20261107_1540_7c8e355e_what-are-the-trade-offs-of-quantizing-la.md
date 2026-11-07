# Pipeline run report - What are the trade-offs of quantizing large language models to 4-bit precision?

Generated 2026-11-07 15:56 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 19 in the file) and the database. Query id `7c8e355e-122b-46b6-b227-44d876e9da1c`.

## 1. Summary

| | |
|---|---|
| Question | What are the trade-offs of quantizing large language models to 4-bit precision? |
| Domain anchor | (cached): 'NLP' | context: NLP: quantizing refers to lowering model weight precision to 4 bits, not to signal or hardware quantization. |
| Started / finished | 2026-11-07 15:40:23 / 15:52:55 |
| **Total execution time** | **12m 32s** (752 s) |
| Sub-questions / search queries | 3 / 12 (per sub-question [3, 3, 3]) |
| Plan source | plan-cache (stored plan reused, PLAN_CACHE=true) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 341 candidates -> 319 cleared the similarity floor -> 60 shortlisted |
| **Papers kept after the relevance judge** | **53** (log: 47); 13 shortlisted papers rejected |
| **Web sources** | **41** (per sub-question [9, 13, 13]) |
| Papers attempted for parsing | 15 (top-N per sub-question) |
| **Papers parsed to usable full text** | **15** of 15 attempted (15 from the parse cache) |
| Papers not parsed (all routes failed) | 0 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 0 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 55 (40 from full text, 0 from abstracts, 15 from web snippets) |
| Findings (verified / total) | 195 / 214 |
| Coverage sufficient | 1 of 3 sub-questions |
| Judge | 2m 14s in 10 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 65 parking events, 1119 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 3 sub-questions) | 15:40:23 | 15:40:24 | 1s | 0% |
| Web search (Tavily) | 15:40:24 | 15:40:28 | 4s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 15:40:28 | 15:41:01 | 33s | 4% |
| Embedding pre-filter + relevance judge | 15:41:01 | 15:42:07 | 1m 06s | 9% |
| Store papers in the database | 15:42:07 | 15:42:08 | 1s | 0% |
| PDF download + Docling parsing | 15:42:08 | 15:42:16 | 8s | 1% |
| Stage 3 preparation (aspect split, chunking, embedding) | 15:42:16 | 15:42:30 | 15s | 2% |
| Stage 3 digest generation (Groq) | 15:42:30 | 15:43:43 | 1m 12s | 10% |
| Stage 3 judge + coverage (per sub-question) | 15:43:43 | 15:52:55 | 9m 13s | 73% |
| **Total** | 15:40:23 | 15:52:55 | **12m 32s** | 100% |

Loop 2 (second search for uncovered aspects) is part of the judge + coverage phase above: 8m 09s by its own step timings (65% of the run). Its searches, parses and filters are NOT counted in the retrieval figures of this report; it stored 6 new paper(s) and 6 new web page(s) with the run, so the stored counts of papers and web sources are higher than the log counts by these numbers.

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is quantization and how does it affect large language models (LLMs)? | 98 -> 98 -> 20 | 20 of 20 | 5 | 9 | 13 (10 / 0 / 3) | 47 / 49 | sufficient |
| 2 | What is 4-bit precision and how does it differ from other precisions? | 113 -> 97 -> 20 | 12 of 20 | 9 | 16 | 20 (14 / 0 / 6) | 68 / 75 | NOT sufficient |
| 3 | What are the trade-offs of quantizing LLMs to 4-bit precision? | 130 -> 124 -> 20 | 15 of 20 | 11 | 16 | 22 (16 / 0 / 6) | 80 / 90 | NOT sufficient |

- Relevance judge rejected 8 papers for [What is 4-bit precision and how does it ]. Examples: 'What Matters for NVFP4 Training? A Comparative Study of Low-' (The paper focuses on training recipes and optimization techniques for 4-bit models rather than explaining the definition of 4-bit precision ); 'Half-S: Halving the Scale for Near-Lossless 4-Bit LLM Traini' (The paper focuses on training optimization techniques for 4-bit LLMs rather than explaining the definition of 4-bit precision or comparing i); 'Precision or Peril: A PoC of Python Code Quality from Quanti' (The paper focuses on code generation quality and deployment constraints rather than explaining the definition or differences of 4-bit precis)
- Relevance judge rejected 5 papers for [What are the trade-offs of quantizing LL]. Examples: 'Sub 4-bit Power-of-Two-Based Mixed-Precision Quantization fo' (The paper focuses on mixed-precision quantization and hardware co-design for edge deployment rather than analyzing the specific software tra); 'FP4 All the Way: Fully Quantized Training of LLMs' (The paper focuses on training LLMs with 4-bit precision rather than analyzing the trade-offs of quantizing already-trained models to 4-bit i); 'Achieving Binary Weight and Activation for LLMs Using Post-T' (The paper focuses on 1-bit quantization methods rather than analyzing the specific trade-offs of 4-bit quantization.)

### Sources behind each sub-question's digests

**1. What is quantization and how does it affect large language models (LLMs)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| An empirical study of Qwen3 quantization | paper | full_text | 5 / 5 |
| An empirical study of Qwen3 quantization | paper | full_text | 3 / 4 |
| Evaluating Quantized Large Language Models | paper | full_text | 4 / 4 |
| Evaluating Quantized Large Language Models | paper | full_text | 2 / 2 |
| LLM-QAT: Data-Free Quantization Aware Training for Large Language Models | paper | full_text | 2 / 3 |
| LLM-QAT: Data-Free Quantization Aware Training for Large Language Models | paper | full_text | 5 / 5 |
| QuIP: 2-Bit Quantization of Large Language Models With Guarantees | paper | full_text | 5 / 5 |
| QuIP: 2-Bit Quantization of Large Language Models With Guarantees | paper | full_text | 4 / 4 |
| Quantization Techniques for Efficient Inference of Large Language Models | paper | full_text | 4 / 4 |
| Quantization Techniques for Efficient Inference of Large Language Models | paper | full_text | 3 / 3 |
| A Comprehensive Study on Quantization Techniques for Large Language Models | web | web_snippet | 4 / 4 |
| Quantization; from Signal processing to NLP and Large Language Models. | web | web_snippet | 3 / 3 |
| Understanding the 'Billions' and Quantization in Large Language Models. | web | web_snippet | 3 / 3 |

**2. What is 4-bit precision and how does it differ from other precisions?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| BitMoD: Bit-serial Mixture-of-Datatype LLM Acceleration | paper | full_text | 5 / 5 |
| Enhancing Computation Efficiency in Large Language Models through Weight and Activation Quantiz | paper | full_text | 4 / 5 |
| Evaluating the Impact of Post-Training Quantization on Large Language Models for Code Generatio | paper | full_text | 3 / 3 |
| LLM-FP4: 4-Bit Floating-Point Quantized Transformers | paper | full_text | 3 / 4 |
| LLM-FP4: 4-Bit Floating-Point Quantized Transformers | paper | full_text | 1 / 1 |
| Normalized Architectures are Natively 4-Bit | paper | full_text | 4 / 4 |
| Normalized Architectures are Natively 4-Bit | paper | full_text | 4 / 5 |
| Not All Linguistic Capabilities Degrade Equally Under Quantization | paper | full_text | 3 / 4 |
| Pretraining Large Language Models with NVFP4 | paper | full_text | 4 / 5 |
| Pretraining Large Language Models with NVFP4 | paper | full_text | 5 / 5 |
| The case for 4-bit precision: k-bit Inference Scaling Laws | paper | full_text | 5 / 5 |
| The case for 4-bit precision: k-bit Inference Scaling Laws | paper | full_text | 4 / 4 |
| any4: Learned 4-bit Numeric Representation for LLMs | paper | full_text | 5 / 5 |
| any4: Learned 4-bit Numeric Representation for LLMs | paper | full_text | 2 / 4 |
| Low-Precision Training of Large Language Models: Methods, Challenges, and Opportunities | web | web_snippet | 3 / 3 |
| Mixed-Precision Quantization for Language Models: Techniques and Prospects | web | web_snippet | 3 / 3 |
| QRazor: Reliable and Effortless 4-bit LLM Quantization by Significant Data Razoring | web | web_snippet | 2 / 2 |
| Quantized Local LLMs: 4-bit vs 8-bit Performance Analysis / SitePoint | web | web_snippet | 2 / 2 |
| Sub-4-Bit LLM Quantization: Enterprise Guide to Methods & Tradeoffs | web | web_snippet | 2 / 2 |
| 🤔How much performance is lost with LLM quantization? Reportedly, very little in most cases. Qua | web | web_snippet | 4 / 4 |

**3. What are the trade-offs of quantizing LLMs to 4-bit precision?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Integer or Floating Point? New Outlooks for Low-Bit Quantization on Large Language Models | paper | full_text | 3 / 3 |
| Integer or Floating Point? New Outlooks for Low-Bit Quantization on Large Language Models | paper | full_text | 5 / 5 |
| LLM-FP4: 4-Bit Floating-Point Quantized Transformers | paper | full_text | 4 / 4 |
| LLM-QAT: Data-Free Quantization Aware Training for Large Language Models | paper | full_text | 4 / 5 |
| LLM-QAT: Data-Free Quantization Aware Training for Large Language Models | paper | full_text | 5 / 5 |
| Low-Bit Quantization Favors Undertrained LLMs:Scaling Laws for Quantized LLMs with 100T Trainin | paper | full_text | 4 / 4 |
| Not All Linguistic Capabilities Degrade Equally Under Quantization | paper | full_text | 5 / 5 |
| Pretraining Large Language Models with NVFP4 | paper | full_text | 4 / 4 |
| Pretraining Large Language Models with NVFP4 | paper | full_text | 4 / 5 |
| Qrazor: Reliable and Effortless 4-bit LLM Quantization by Significant Data Razoring | paper | full_text | 0 / 5 |
| Qrazor: Reliable and Effortless 4-bit LLM Quantization by Significant Data Razoring | paper | full_text | 5 / 5 |
| The case for 4-bit precision: k-bit Inference Scaling Laws | paper | full_text | 4 / 5 |
| The case for 4-bit precision: k-bit Inference Scaling Laws | paper | full_text | 4 / 4 |
| Understanding the Impact of Post-Training Quantization on Large Language Models | paper | full_text | 5 / 5 |
| What Makes Quantization for Large Language Models Hard? An Empirical Study from the Lens of Per | paper | full_text | 4 / 5 |
| Which Quantization Should I Use? A Unified Evaluation of llama.cpp Quantization on Llama-3.1-8B | paper | full_text | 5 / 5 |
| Agile-Quant: Activation-Guided Quantization for Faster Inference of LLMs on the Edge | web | web_snippet | 4 / 4 |
| How quantization reduces LLM latency / Latitude | web | web_snippet | 2 / 2 |
| Mixed-Precision Quantization for Language Models: Techniques and Prospects | web | web_snippet | 2 / 2 |
| Performance Trade-offs of Optimizing Small Language Models for E-Commerce | web | web_snippet | 2 / 3 |
| QRazor: Reliable and Effortless 4-bit LLM Quantization by Significant Data Razoring | web | web_snippet | 4 / 4 |
| What types of quantization will improve LLM inference latency and throughput? | web | web_snippet | 1 / 1 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is quantization and how does it affect large language models (LLMs)?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 12 = yes 7, partial 3, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the benefits of quantization for LLMs? | covered | 3 | 3 |
| 2 | What are the challenges of quantization for LLMs? | covered | 4 | 3 |

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 1, 12.6 s.

| Aspect | Status | Steps tried | Covered by | Before (yes/partial/no) |
|---|---|---|---|---|
| What are the challenges of quantization for LLMs? | covered | reselect | reselect | 1/3/2 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 5 | 14 | 1 | 12.6 | sources_tried=5 |

### 2. What is 4-bit precision and how does it differ from other precisions?

Sufficient: **False**; judge used: True; sources 15 (9 full text); judge candidates 18 = yes 6, partial 11, no 1, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does 4-bit precision affect the representation and computation of LLMs? | uncovered | 1 | 1 |
| 2 | How does 4-bit precision affect the accuracy of LLMs? | covered | 3 | 3 |
| 3 | How does 4-bit precision affect the performance of LLMs? | covered | 2 | 2 |

Uncovered details: How does 4-bit precision affect the representation and computation of LLMs?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 2 aspect(s), covered 1, 212.6 s.

| Aspect | Status | Steps tried | Covered by | Before (yes/partial/no) |
|---|---|---|---|---|
| How does 4-bit precision affect the performance of LLMs? | covered | reselect, pool | pool | 2/3/1 |
| How does 4-bit precision affect the representation and computation of LLMs? | known_gap | reselect, pool, queries | - | 0/5/1 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 2 | 5 | 16 | 0 | 17.3 | sources_tried=5 |
| pool | 2 | 1 | 4 | 1 | 12.7 | parsed=1, sources_tried=3 |
| queries | 1 | 6 | 19 | 0 | 182.6 | queries=4, new_web_kept=3, new_web_found=14, new_papers_kept=3, new_papers_found=7, new_papers_parsed=3 |

### 3. What are the trade-offs of quantizing LLMs to 4-bit precision?

Sufficient: **False**; judge used: True; sources 17 (11 full text); judge candidates 37 = yes 9, partial 11, no 17, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does quantizing LLMs to 4-bit precision affect the model size and memory usage? | uncovered | 1 | 1 |
| 2 | How does quantizing LLMs to 4-bit precision affect the inference speed and latency? | covered | 2 | 2 |
| 3 | How does quantizing LLMs to 4-bit precision affect the quality of generated text? | uncovered | 1 | 1 |
| 4 | How does quantizing LLMs to 4-bit precision affect the diversity of generated text? | uncovered | 0 | 0 |
| 5 | How does quantizing LLMs to 4-bit precision affect the robustness of LLMs? | covered | 2 | 2 |
| 6 | How does quantizing LLMs to 4-bit precision affect the security of LLMs? | uncovered | 0 | 0 |
| 7 | How does quantizing LLMs to 4-bit precision affect the compatibility of LLMs? | covered | 2 | 2 |
| 8 | How does quantizing LLMs to 4-bit precision affect the interoperability of LLMs? | uncovered | 1 | 1 |

Uncovered details: How does quantizing LLMs to 4-bit precision affect the model size and memory usage?; How does quantizing LLMs to 4-bit precision affect the quality and diversity of generated text?; How does quantizing LLMs to 4-bit precision affect the robustness and security of LLMs?; How does quantizing LLMs to 4-bit precision affect the compatibility and interoperability of LLMs?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 4 aspect(s), covered 3, 264.2 s.

| Aspect | Status | Steps tried | Covered by | Before (yes/partial/no) |
|---|---|---|---|---|
| How does quantizing LLMs to 4-bit precision affect the security of LLMs? | known_gap_skipped_triage | - | - | 0/0/2 |
| How does quantizing LLMs to 4-bit precision affect the robustness of LLMs? | covered | reselect, pool, queries | queries | 0/2/1 |
| How does quantizing LLMs to 4-bit precision affect the compatibility of LLMs? | covered | reselect, pool | pool | 1/2/1 |
| How does quantizing LLMs to 4-bit precision affect the interoperability of LLMs? | known_gap_skipped_cap | - | - | 1/1/1 |
| How does quantizing LLMs to 4-bit precision affect the quality of generated text | known_gap | reselect, pool, queries | - | 1/5/0 |
| How does quantizing LLMs to 4-bit precision affect the diversity of generated te | known_gap_skipped_triage | - | - | 0/0/2 |
| How does quantizing LLMs to 4-bit precision affect the inference speed and laten | covered | reselect, pool, queries | queries | 0/2/4 |
| How does quantizing LLMs to 4-bit precision affect the model size and memory usa | known_gap_skipped_triage | - | - | 0/1/5 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 4 | 5 | 23 | 0 | 23.8 | sources_tried=5 |
| pool | 4 | 3 | 13 | 1 | 19.0 | parsed=3, sources_tried=3 |
| queries | 3 | 6 | 21 | 2 | 221.4 | queries=12, new_web_kept=3, new_web_found=41, new_papers_kept=3, new_papers_found=24, new_papers_parsed=3 |

## 5. Retrieval details

- Web search variants: [9, 13, 13] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 98 candidates -> 98 cleared min_similarity (0.56) -> top 20 shortlisted; 113 candidates -> 97 cleared min_similarity (0.56) -> top 20 shortlisted; 130 candidates -> 124 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 17, 'scopus': 30, 'both': 6}; requests to api.openalex.org in the log: 65
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0

## 6. Parsing details

- Attempted 15 papers, usable full text 15, 47 papers saved in the database.
- PDF obtained via: -; parse cache hits: 15; Unpaywall OA links found: 0; landing-page citation_pdf_url: 0
- Individual download failures: 0 -> 
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

## 7. Groq and judge

- Stage 3: 24 digests for 3 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 65; per key (events / parked seconds): ...3mla: 8 / 173s, ...Ef4D: 10 / 180s, ...KJJp: 10 / 116s, ...KaRe: 8 / 138s, ...X2Oj: 5 / 151s, ...uNUk: 10 / 131s, ...x1nP: 14 / 230s
- Judge batch latencies (s): [12.3, 7.1, 18.1, 9.5, 5.3, 13.5, 29.7, 15.1, 11.8, 11.8]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| WARNING | 10 | OpenAlex N on key ...CHgt for '<text>' (backoff N/N), pausing that key N.Ns |
| WARNING | 5 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 5 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 5 | OpenAlex N on key ...FsNG for '<text>' (backoff N/N), pausing that key N.Ns |
| WARNING | 3 | find_cached_parse: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 3 | _upsert_parsed: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 1 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 1 | Failed to download from <url> HTTPStatusError: HTTPStatusError('<text>') |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- Groq rate limiting: 65 parking events; digest generation took 1m 12s.
- Longest phase: Stage 3 judge + coverage (per sub-question) (9m 13s, 73% of the run).

Warnings in the log: 33; errors: 0.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand)

First full run with Loop 2 on (`LOOP2=true`, `PLAN_CACHE=true`, all steps, triage r1). Same question and plan as the baseline Q3 run (11m 13s, 1 of 3 sufficient). The stored plan, the parse cache and the chunk-embedding cache made the Stage 1 to Stage 3 start fast (Stage 3 preparation 15 s), so the 12m 32s total is mostly Loop 2: **8m 09s inside the judge phase**.

- Loop 2 searched 7 aspects and covered 5: "challenges of quantization" (reselect), "performance" (pool, weak: one of its two claims is about memory), "compatibility" (pool, weak), **"robustness" and "inference speed and latency" (queries)**. Memory, quality, diversity, security and interoperability stayed uncovered; diversity and security were skipped by the triage (0 yes, 0 partial), interoperability by the cap of 4 aspects.
- Sub-question 1 became sufficient through Loop 2; sub-questions 2 and 3 did not (aspects "representation and computation", "quality", "memory", and the invented ones).
- The queries step found on-topic papers that the first retrieval did not: "Which Quantization Should I Use?", "What Makes Quantization for LLMs Hard?", "Not All Linguistic Capabilities Degrade Equally Under Quantization". It took 183 s and 221 s.
- The first attempt of this question (run 18) failed in Loop 2 on a bug (a data key `step` clashed with the progress event's own argument); Loop 2 fell back to the Stage 3 result as designed. Details and all results of Loop 2: `docs/reports/18_loop2.md`.
