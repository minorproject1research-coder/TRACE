# Pipeline run report - What are the trade-offs of quantizing large language models to 4-bit precision?

Generated 2026-11-07 00:39 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 13 in the file) and the database. Query id `bf7055b3-a202-4ef6-b47c-9e99c7f7a118`.

## 1. Summary

| | |
|---|---|
| Question | What are the trade-offs of quantizing large language models to 4-bit precision? |
| Domain anchor | (cached): 'NLP' | context: NLP: quantizing refers to lowering model weight precision to 4 bits, not to signal or hardware quantization. |
| Started / finished | 2026-11-07 00:17:31 / 00:35:18 |
| **Total execution time** | **17m 46s** (1066 s) |
| Sub-questions / search queries | 3 / 12 (per sub-question [3, 3, 3]) |
| Plan source | planner |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 340 candidates -> 318 cleared the similarity floor -> 60 shortlisted |
| **Papers kept after the relevance judge** | **46** (log: 46); 14 shortlisted papers rejected |
| **Web sources** | **37** (per sub-question [11, 13, 13]) |
| Papers attempted for parsing | 16 (top-N per sub-question) |
| **Papers parsed to usable full text** | **15** of 16 attempted (3 from the parse cache) |
| Papers not parsed (all routes failed) | 0 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 1 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 24 (15 from full text, 0 from abstracts, 9 from web snippets) |
| Findings (verified / total) | 97 / 103 |
| Coverage sufficient | 1 of 3 sub-questions |
| Judge | 1m 02s in 3 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 63 parking events, 1001 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 3 sub-questions) | 00:17:31 | 00:18:00 | 29s | 3% |
| Web search (Tavily) | 00:18:00 | 00:18:09 | 9s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 00:18:09 | 00:18:40 | 31s | 3% |
| Embedding pre-filter + relevance judge | 00:18:40 | 00:19:46 | 1m 06s | 6% |
| Store papers in the database | 00:19:46 | 00:19:47 | 1s | 0% |
| PDF download + Docling parsing | 00:19:47 | 00:24:40 | 4m 53s | 27% |
| Stage 3 preparation (aspect split, chunking, embedding) | 00:24:40 | 00:26:35 | 1m 55s | 11% |
| Stage 3 digest generation (Groq) | 00:26:35 | 00:27:41 | 1m 06s | 6% |
| Stage 3 judge + coverage (per sub-question) | 00:27:41 | 00:28:45 | 1m 04s | 6% |
| **Total** | 00:17:31 | 00:35:18 | **17m 46s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is quantization and how does it affect large language models (LLMs)? | 98 -> 98 -> 20 | 20 of 20 | 6 | 11 | 8 (5 / 0 / 3) | 36 / 36 | sufficient |
| 2 | What is 4-bit precision and how does it differ from other precisions? | 113 -> 97 -> 20 | 11 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 31 / 33 | NOT sufficient |
| 3 | What are the trade-offs of quantizing LLMs to 4-bit precision? | 129 -> 123 -> 20 | 15 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 30 / 34 | NOT sufficient |

- Relevance judge rejected 9 papers for [What is 4-bit precision and how does it ]. Examples: 'What Matters for NVFP4 Training? A Comparative Study of Low-' (The paper focuses on training recipes and optimization techniques for 4-bit models rather than explaining the definition of 4-bit precision ); 'Half-S: Halving the Scale for Near-Lossless 4-Bit LLM Traini' (The paper focuses on training optimization techniques for 4-bit LLMs rather than explaining the definition of 4-bit precision or comparing i); 'Precision or Peril: A PoC of Python Code Quality from Quanti' (The paper focuses on code quality degradation rather than explaining the definition or differences between precision levels.)
- Relevance judge rejected 5 papers for [What are the trade-offs of quantizing LL]. Examples: 'Sub 4-bit Power-of-Two-Based Mixed-Precision Quantization fo' (The paper focuses on mixed-precision quantization and hardware co-design for edge deployment rather than analyzing the specific software tra); 'FP4 All the Way: Fully Quantized Training of LLMs' (The paper focuses on training LLMs with 4-bit precision rather than analyzing the trade-offs of quantizing already-trained models to 4-bit i); 'Achieving Binary Weight and Activation for LLMs Using Post-T' (The paper focuses on 1-bit quantization methods rather than analyzing the specific trade-offs of 4-bit quantization.)

### Sources behind each sub-question's digests

**1. What is quantization and how does it affect large language models (LLMs)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Evaluating Quantized Large Language Models | paper | full_text | 5 / 5 |
| LLM-QAT: Data-Free Quantization Aware Training for Large Language Models | paper | full_text | 5 / 5 |
| Optimizing Large Language Models through Quantization: A Comparative Analysis of PTQ and QAT Te | paper | full_text | 4 / 4 |
| QuIP: 2-Bit Quantization of Large Language Models With Guarantees | paper | full_text | 5 / 5 |
| Quantization Techniques for Efficient Inference of Large Language Models | paper | full_text | 4 / 4 |
| A Comprehensive Study on Quantization Techniques for Large Language Models | web | web_snippet | 5 / 5 |
| What is Quantization? Quantizing LLMs / Exxact Blog | web | web_snippet | 5 / 5 |
| What is Quantization? / IBM | web | web_snippet | 3 / 3 |

**2. What is 4-bit precision and how does it differ from other precisions?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| LLM-FP4: 4-Bit Floating-Point Quantized Transformers | paper | full_text | 5 / 5 |
| Normalized Architectures are Natively 4-Bit | paper | full_text | 3 / 4 |
| Pretraining Large Language Models with NVFP4 | paper | full_text | 4 / 4 |
| The case for 4-bit precision: k-bit Inference Scaling Laws | paper | full_text | 5 / 5 |
| any4: Learned 4-bit Numeric Representation for LLMs | paper | full_text | 4 / 5 |
| Low-Precision Training of Large Language Models: Methods, Challenges, and Opportunities | web | web_snippet | 5 / 5 |
| Mixed-Precision Quantization for Language Models: Techniques and Prospects | web | web_snippet | 3 / 3 |
| QRazor: Reliable and Effortless 4-bit LLM Quantization by Significant Data Razoring | web | web_snippet | 2 / 2 |

**3. What are the trade-offs of quantizing LLMs to 4-bit precision?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Integer or Floating Point? New Outlooks for Low-Bit Quantization on Large Language Models | paper | full_text | 4 / 5 |
| LLM-QAT: Data-Free Quantization Aware Training for Large Language Models | paper | full_text | 3 / 5 |
| Pretraining Large Language Models with NVFP4 | paper | full_text | 3 / 3 |
| Qrazor: Reliable and Effortless 4-bit LLM Quantization by Significant Data Razoring | paper | full_text | 5 / 5 |
| The case for 4-bit precision: k-bit Inference Scaling Laws | paper | full_text | 4 / 5 |
| A Comprehensive Evaluation of Quantization Strategiesfor Large Language Models | web | web_snippet | 5 / 5 |
| Performance Trade-offs of Optimizing Small Language Models for E-Commerce | web | web_snippet | 3 / 3 |
| QRazor: Reliable and Effortless 4-bit LLM Quantization by Significant Data Razoring | web | web_snippet | 3 / 3 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is quantization and how does it affect large language models (LLMs)?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 12 = yes 8, partial 1, no 3, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | benefits of quantization for LLMs | covered | 6 | 2 |
| 2 | What are the challenges of quantization for LLMs? | covered | 2 | 2 |

### 2. What is 4-bit precision and how does it differ from other precisions?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 24 = yes 7, partial 11, no 6, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does 4-bit precision affect the representation of LLMs? | covered | 2 | 2 |
| 2 | How does 4-bit precision affect the computation of LLMs? | uncovered | 1 | 1 |
| 3 | How does 4-bit precision affect the accuracy of LLMs? | covered | 2 | 2 |
| 4 | How does 4-bit precision affect the performance of LLMs? | uncovered | 2 | 1 |

Uncovered details: How does 4-bit precision affect the representation and computation of LLMs?; How does 4-bit precision affect the accuracy and performance of LLMs?

### 3. What are the trade-offs of quantizing LLMs to 4-bit precision?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 30 = yes 2, partial 14, no 14, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does quantizing LLMs to 4-bit precision affect the model size and memory usage? | uncovered | 1 | 1 |
| 2 | How does quantizing LLMs to 4-bit precision affect inference speed and latency? | uncovered | 0 | 0 |
| 3 | How does quantizing LLMs to 4-bit precision affect the quality of generated text? | uncovered | 0 | 0 |
| 4 | How does quantizing LLMs to 4-bit precision affect the diversity of generated text? | uncovered | 0 | 0 |
| 5 | How does quantizing LLMs to 4-bit precision affect the robustness of LLMs? | uncovered | 1 | 1 |
| 6 | How does quantizing LLMs to 4-bit precision affect the security of LLMs? | uncovered | 0 | 0 |
| 7 | How does quantizing LLMs to 4-bit precision affect the compatibility of LLMs? | uncovered | 0 | 0 |
| 8 | How does quantizing LLMs to 4-bit precision affect the interoperability of LLMs? | uncovered | 0 | 0 |

Uncovered details: How does quantizing LLMs to 4-bit precision affect the model size and memory usage?; How does quantizing LLMs to 4-bit precision affect the inference speed and latency?; How does quantizing LLMs to 4-bit precision affect the quality and diversity of generated text?; How does quantizing LLMs to 4-bit precision affect the robustness and security of LLMs?; How does quantizing LLMs to 4-bit precision affect the compatibility and interoperability of LLMs?

## 5. Retrieval details

- Web search variants: [11, 13, 13] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 98 candidates -> 98 cleared min_similarity (0.56) -> top 20 shortlisted; 113 candidates -> 97 cleared min_similarity (0.56) -> top 20 shortlisted; 129 candidates -> 123 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 14, 'scopus': 26, 'both': 6}; requests to api.openalex.org in the log: 18
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0

## 6. Parsing details

- Attempted 16 papers, usable full text 15, 46 papers saved in the database.
- PDF obtained via: its own link: 12, Unpaywall: 1; parse cache hits: 3; Unpaywall OA links found: 1; landing-page citation_pdf_url: 0
- Individual download failures: 1 -> ValueError: 1
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

## 7. Groq and judge

- Stage 3: 24 digests for 3 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 63; per key (events / parked seconds): ...3mla: 11 / 121s, ...Ef4D: 7 / 127s, ...KJJp: 8 / 149s, ...KaRe: 10 / 209s, ...X2Oj: 7 / 111s, ...uNUk: 8 / 93s, ...x1nP: 12 / 191s
- Judge batch latencies (s): [13.0, 21.9, 26.7]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | Docling unavailable, using basic metadata: Server error '<text>' for url '<url> |
| WARNING | 1 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- Groq rate limiting: 63 parking events; digest generation took 1m 06s.
- Longest phase: PDF download + Docling parsing (4m 53s, 27% of the run).

Warnings in the log: 4; errors: 0.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand after reading the log and the database)

**Bottom line.** A clean, fast run (17m 46s, no error, no judge error, no digest failure) with the best retrieval and extraction numbers so far: 46 papers kept, 15 of 16 attempted papers with full text, **97 of 103 findings verified (94%)**, 4.3 findings per digest. But **only 1 of 3 sub-questions is sufficient, and the one that fails is the question the user asked**: "What are the trade-offs of quantizing LLMs to 4-bit precision?" has **2 "yes" verdicts in 30 judged pairs and not one covered aspect**. Reading the verdicts, this is not a retrieval failure. It is two other things: the planner wrote aspects that no literature answers, and the judge rates specific measured results "partial" for broad "how does it affect X" aspects. Both are known limits (1.3, 3.1), and this run is the clearest example of them so far.

### Numbers

| | |
|---|---|
| Plan | 3 sub-questions, 12 queries [3, 3, 3], planner 29 s; no query dropped by the gate |
| Domain anchor | 'NLP', context "quantizing refers to lowering model weight precision to 4 bits, not to signal or hardware quantization" (a genuine ambiguity here: signal quantization) |
| Retrieval | 340 candidates, 46 kept (OpenAlex 14, Scopus 26, both 6), 37 web sources; relevance judge passed 20 of 20, 11 of 20 and 15 of 20 |
| Parsing | 15 of 16 usable (3 from the cache), 4m 53s; the one failure was an HTML page instead of a PDF |
| Stage 3 | 24 digests (15 full text, 9 web), 1m 06s on 7 keys; preparation 1m 55s; judge and coverage 1m 04s; 103 findings, 97 verified |
| Groq | 63 parking events, 1001 key-seconds in total (93 to 209 s per key) |
| Judge | 3 batches, 0 errors, 66 pairs |
| Coverage | sub-question 1 sufficient; 2 and 3 not sufficient |

### Why the core sub-question fails

1. **The planner's detail questions contain dimensions with no literature.** The five detail questions of the core sub-question became 8 aspects: memory, speed, quality, **diversity**, robustness, **security**, **compatibility**, **interoperability**. For "diversity", "security" and "interoperability" the 5 papers and 3 web pages read contain nothing that answers them (their 2 or 3 judged candidates are all "no" or "partial"). The realistic trade-off dimensions are accuracy, memory, speed, hardware support and energy; the last two are not in the plan at all. As long as every aspect must be covered, this sub-question cannot become sufficient however good the retrieval is.
2. **Broad aspects get "partial" for specific results.** The speed aspect ("How does quantizing LLMs to 4-bit precision affect inference speed and latency?") has 6 candidates and 0 "yes" (3 partial, 3 no). I read five of them: "FP4 halves memory and gives a 2 to 3 times arithmetic speedup versus FP8" is partial ("too specific to FP8"); "on hardware without native 4-bit support, 4-bit causes large slowdowns and higher energy per token" is partial ("only the negative trade-off"); "a significant speedup only for the 72B model" is partial ("only that model"). Taken together these answer the aspect well, but no single one answers it in general, and coverage needs two "yes" from two sources. The quality aspect behaves the same way (14 of the 30 verdicts are "partial", more than the "no" count of 14). One "no" also shows the rule that "yes" needs both the quote supporting the claim and the claim answering the aspect: a correct claim about memory with a quote about performance is "no".
3. **Sub-question 2 never asks what it says.** "What is 4-bit precision and how does it differ from other precisions?" has aspects about the effect of 4-bit on representation, computation, accuracy and performance, not about how it differs from other precisions (INT4 versus FP4 versus INT8), which is half of the question. Two aspects are near misses: "performance" has 2 "yes" from only 1 source, "computation" 1 and 1.
4. **Sub-question 1 is sufficient on two generic aspects** ("benefits" and "challenges of quantization for LLMs"); "what is quantization" is not an aspect, so the definition is never checked (known limit 3.12).

### What this means for Loop 2 (new, from this run)
Uncovered aspects are not all the same kind. Looking at the judged verdicts of an uncovered aspect separates them:
- **Near misses** (several "partial" and some "yes"; here speed, quality, memory, computation, performance): evidence on the topic exists and more or better-targeted sources, or a second look at the same chunks, could turn them into "yes". These are the Loop 2 candidates.
- **Unanswerable aspects** (only "no" among a handful of candidates; here diversity, security, interoperability): more searching will not help and the aspect is probably the planner's invention. Loop 2 should record them as known gaps without spending queries.
A rule like "search again only if the aspect has at least 2 partial or yes verdicts" costs nothing (the verdicts are already in `aspect_evidence` and `digests.findings[].judge`) and is not tested; it should be checked on the stored runs before use.

### What worked
- The 7 Groq keys: digests 1m 06s for 24 sources, 63 parking events (139 in the last run, 99 and 108 earlier), no long park.
- The tolerant quote verifier and a topic where the digest model quotes cleanly: 94% verified, only 6 findings lost.
- Retrieval found on-topic papers for all three sub-questions (LLM-FP4, QRazor, NVFP4 pretraining, "The case for 4-bit precision", LLM-QAT, "Integer or Floating Point?"); the domain anchor kept signal-processing quantization out.
- No sub-question merge or gate drop was needed; the shortlist judge passed 20 of 20 on the first sub-question, so its shortlist was already on topic.

### What I did not check
- Whether the judge is too strict here. I read 15 of the 30 verdicts of the core sub-question and agree with most of the "partial" labels as written (the claims are narrower than the aspect), but I did not label all 30 against a rule, so I cannot give precision or recall. The honest reading is: the V2 judge is conservative on broad aspects (known limit 3.1), and the planner's aspects make broad ones unavoidable.
- Whether the sufficiency rule (two "yes" from two sources for every aspect) is the right bar for a "trade-offs" question; it makes the bar depend on how many dimensions the planner invented.

### Tooling
- The planner row in the phase table was hard-coded to "5 sub-questions"; it now uses the real count (fixed in `scripts/pipeline_run_report.py`).
- The report script's own database reads are not retried: regenerating this report once failed with `RemoteProtocolError: Server disconnected` and worked on the next try.

### Next checks
- [ ] Label the 30 judged pairs of the core sub-question against a written rule (answers the aspect in general, in part, or not) to measure the judge on broad aspects.
- [ ] Test "search again only for aspects with at least 2 partial or yes verdicts" on the stored runs (Q1, Q2, Q3) before building Loop 2.
- [ ] Run Q4 to Q6.

(To regenerate the tables above after another run: `python scripts/pipeline_run_report.py --run N`; these notes are kept.)
