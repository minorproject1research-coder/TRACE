# Pipeline run report - What are the trade-offs of quantizing large language models to 4-bit precision?

Generated 2026-11-08 14:13 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 29 in the file) and the database. Query id `a158fe7d-5105-4c72-b5a6-b4db99744c85`.

## 1. Summary

| | |
|---|---|
| Question | What are the trade-offs of quantizing large language models to 4-bit precision? |
| Domain anchor | (cached): 'NLP' | context: NLP: quantizing refers to lowering model weight precision to 4 bits, not to signal or hardware quantization. |
| Started / finished | 2026-11-08 13:43:26 / 14:06:23 |
| **Total execution time** | **22m 57s** (1377 s) |
| Sub-questions / search queries | 3 / 12 (per sub-question [3, 3, 3]) |
| Plan source | plan-cache (stored plan reused, PLAN_CACHE=true) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 337 candidates -> 317 cleared the similarity floor -> 60 shortlisted |
| **Papers kept after the relevance judge** | **49** (log: 49); 11 shortlisted papers rejected |
| **Web sources** | **35** (per sub-question [11, 12, 12]) |
| Papers attempted for parsing | 15 (top-N per sub-question) |
| **Papers parsed to usable full text** | **15** of 15 attempted (10 from the parse cache) |
| Papers not parsed (all routes failed) | 0 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 0 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 29 (20 from full text, 0 from abstracts, 9 from web snippets) |
| Findings (verified / total) | 112 / 121 |
| Coverage sufficient | 3 of 3 sub-questions |
| Judge | 1m 39s in 7 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 71 parking events, 992 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 3 sub-questions) | 13:43:26 | 13:43:30 | 4s | 0% |
| Web search (Tavily) | 13:43:30 | 13:43:40 | 10s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 13:43:40 | 13:44:22 | 42s | 3% |
| Embedding pre-filter + relevance judge | 13:44:22 | 13:46:21 | 1m 59s | 9% |
| Store papers in the database | 13:46:21 | 13:46:22 | 1s | 0% |
| PDF download + Docling parsing | 13:46:22 | 13:48:48 | 2m 26s | 11% |
| Stage 3 preparation (aspect split, chunking, embedding) | 13:48:48 | 13:49:42 | 54s | 4% |
| Stage 3 digest generation (Groq) | 13:49:42 | 13:50:35 | 54s | 4% |
| Stage 3 judge + coverage (per sub-question) | 13:50:35 | 13:52:28 | 1m 52s | 8% |
| Stage 4 fact check (claims, NLI, judges) | 13:52:28 | 14:06:23 | 13m 55s | 61% |
| **Total** | 13:43:26 | 14:06:23 | **22m 57s** | 100% |

Loop 2 (second search for uncovered aspects) is part of the judge + coverage phase above: 46s by its own step timings (3% of the run). Its searches, parses and filters are NOT counted in the retrieval figures of this report; it stored 0 new paper(s) and 0 new web page(s) with the run, so the stored counts of papers and web sources are higher than the log counts by these numbers.

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is quantization and how does it affect large language models (LLMs)? | 100 -> 100 -> 20 | 20 of 20 | 5 | 11 | 8 (5 / 0 / 3) | 34 / 37 | sufficient |
| 2 | What is 4-bit precision and how does it differ from other precisions? | 110 -> 95 -> 20 | 14 of 20 | 5 | 12 | 8 (5 / 0 / 3) | 33 / 37 | sufficient |
| 3 | What are the trade-offs of quantizing LLMs to 4-bit precision? | 127 -> 122 -> 20 | 15 of 20 | 5 | 12 | 13 (10 / 0 / 3) | 45 / 47 | sufficient |

- Relevance judge rejected 6 papers for [What is 4-bit precision and how does it ]. Examples: 'Half-S: Halving the Scale for Near-Lossless 4-Bit LLM Traini' (The paper focuses on training optimization techniques for 4-bit LLMs rather than explaining the definition of 4-bit precision or comparing i); 'Precision or Peril: A PoC of Python Code Quality from Quanti' (The paper focuses on code generation quality and deployment constraints rather than explaining the definition or differences of 4-bit precis); 'Error analysis in the hardware neural networks applications ' (The paper focuses on hardware floating-point quantization for embedded systems rather than the NLP-specific weight quantization to 4-bit int)
- Relevance judge rejected 5 papers for [What are the trade-offs of quantizing LL]. Examples: 'Sub 4-bit Power-of-Two-Based Mixed-Precision Quantization fo' (The paper focuses on mixed-precision quantization and hardware co-design rather than analyzing the specific software trade-offs of pure 4-bi); 'FP4 All the Way: Fully Quantized Training of LLMs' (The paper focuses on training LLMs with 4-bit precision, whereas the research question asks about the trade-offs of quantizing already-train); 'FlexiBit: Fully Flexible Precision Bit-parallel Accelerator ' (The paper focuses on hardware accelerator architecture design rather than analyzing the model performance trade-offs of 4-bit quantization.)

### Sources behind each sub-question's digests

**1. What is quantization and how does it affect large language models (LLMs)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Evaluating Quantized Large Language Models | paper | full_text | 5 / 5 |
| LLM-QAT: Data-Free Quantization Aware Training for Large Language Models | paper | full_text | 4 / 5 |
| QuIP: 2-Bit Quantization of Large Language Models With Guarantees | paper | full_text | 4 / 5 |
| Quantization Techniques for Efficient Inference of Large Language Models | paper | full_text | 4 / 4 |
| WKVQuant: Quantizing Weight and Key/Value Cache for Large Language Models Gains More | paper | full_text | 4 / 5 |
| A Comprehensive Study on Quantization Techniques for Large Language Models | web | web_snippet | 5 / 5 |
| What is Quantization? Quantizing LLMs / Exxact Blog | web | web_snippet | 5 / 5 |
| What is Quantization? / IBM | web | web_snippet | 3 / 3 |

**2. What is 4-bit precision and how does it differ from other precisions?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Any-Precision LLM: Low-Cost Deployment of Multiple, Different-Sized LLMs | paper | full_text | 5 / 5 |
| Pretraining Large Language Models with NVFP4 | paper | full_text | 1 / 5 |
| Spectra: Surprising Effectiveness of Pretraining Ternary Language Models at Scale | paper | full_text | 4 / 4 |
| TetraJet-v2: Accurate NVFP4 Training for Large Language Models with Oscillation Suppression and | paper | full_text | 5 / 5 |
| The case for 4-bit precision: k-bit Inference Scaling Laws | paper | full_text | 5 / 5 |
| A Comprehensive Evaluation of Quantization Strategiesfor Large Language Models | web | web_snippet | 5 / 5 |
| Low-Precision Training of Large Language Models: Methods, Challenges, and Opportunities | web | web_snippet | 5 / 5 |
| Mixed-Precision Quantization for Language Models: Techniques and Prospects | web | web_snippet | 3 / 3 |

**3. What are the trade-offs of quantizing LLMs to 4-bit precision?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Four Over Six: More Accurate NVFP4 Quantization with Adaptive Block Scaling | paper | full_text | 5 / 5 |
| Four Over Six: More Accurate NVFP4 Quantization with Adaptive Block Scaling | paper | full_text | 4 / 4 |
| LLM-QAT: Data-Free Quantization Aware Training for Large Language Models | paper | full_text | 3 / 4 |
| LLM-QAT: Data-Free Quantization Aware Training for Large Language Models | paper | full_text | 2 / 2 |
| Pretraining Large Language Models with NVFP4 | paper | full_text | 4 / 4 |
| Pretraining Large Language Models with NVFP4 | paper | full_text | 5 / 5 |
| TetraJet-v2: Accurate NVFP4 Training for Large Language Models with Oscillation Suppression and | paper | full_text | 5 / 5 |
| TetraJet-v2: Accurate NVFP4 Training for Large Language Models with Oscillation Suppression and | paper | full_text | 2 / 2 |
| The case for 4-bit precision: k-bit Inference Scaling Laws | paper | full_text | 4 / 5 |
| The case for 4-bit precision: k-bit Inference Scaling Laws | paper | full_text | 2 / 2 |
| Norm Tweaking: High-Performance Low-Bit Quantization of ... | web | web_snippet | 2 / 2 |
| Performance Trade-offs of Optimizing Small Language Models for E-Commerce | web | web_snippet | 5 / 5 |
| QRazor: Reliable and Effortless 4-bit LLM Quantization by Significant Data Razoring | web | web_snippet | 2 / 2 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is quantization and how does it affect large language models (LLMs)?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 12 = yes 8, partial 1, no 3, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | benefits of quantization for LLMs | covered | 5 | 4 |
| 2 | What are the challenges of quantization for LLMs? | covered | 3 | 3 |

### 2. What is 4-bit precision and how does it differ from other precisions?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 24 = yes 5, partial 14, no 5, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does 4-bit precision affect the representation of LLMs? | covered | 4 | 3 |
| 2 | How does 4-bit precision affect the computation of LLMs? | covered | 4 | 3 |
| 3 | How does 4-bit precision affect the accuracy of LLMs? | covered | 2 | 2 |
| 4 | How does 4-bit precision affect the performance of LLMs? | covered | 5 | 4 |

Loop 2 (r1 triage, steps reselect, pool, queries): searched 0 aspect(s), covered 3 (3 by synthesis of several sources), sufficient True (strict rule: True), gap rule core, 6.0 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| How does 4-bit precision affect the computation of LLMs? | covered | - | synthesis | synthesis | 1/4/1 | - |
| How does 4-bit precision affect the performance of LLMs? | covered | - | synthesis | synthesis | 1/5/0 | - |
| How does 4-bit precision affect the representation of LLMs? | covered | - | synthesis | synthesis | 1/3/2 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|

### 3. What are the trade-offs of quantizing LLMs to 4-bit precision?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 47 = yes 8, partial 21, no 18, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does quantizing LLMs to 4-bit precision affect the model size and memory usage? | covered | 4 | 4 |
| 2 | How does quantizing LLMs to 4-bit precision affect the inference speed and latency? | covered | 5 | 4 |
| 3 | How does quantizing LLMs to 4-bit precision affect the quality of generated text? | covered | 2 | 2 |
| 4 | How does quantizing LLMs to 4-bit precision affect the diversity of generated text? | uncovered | 0 | 0 |
| 5 | How does quantizing LLMs to 4-bit precision affect the robustness of LLMs? | covered | 4 | 3 |
| 6 | How does quantizing LLMs to 4-bit precision affect the security of LLMs? | uncovered | 1 | 1 |
| 7 | How does quantizing LLMs to 4-bit precision affect the compatibility of LLMs? | uncovered | 0 | 0 |
| 8 | How does quantizing LLMs to 4-bit precision affect the interoperability of LLMs? | uncovered | 0 | 0 |

Uncovered details: How does quantizing LLMs to 4-bit precision affect the quality and diversity of generated text?; How does quantizing LLMs to 4-bit precision affect the robustness and security of LLMs?; How does quantizing LLMs to 4-bit precision affect the compatibility and interoperability of LLMs?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 4 (2 by synthesis of several sources), sufficient True (strict rule: False), gap rule core, 40.4 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| How does quantizing LLMs to 4-bit precision affect the security of LLMs? | known_gap_no_evidence | - | - | - | 0/0/2 | 1/0, 1 |
| How does quantizing LLMs to 4-bit precision affect the robustness of LLMs? | covered | reselect | reselect | single claims | 0/2/2 | - |
| How does quantizing LLMs to 4-bit precision affect the compatibility of LLMs? | known_gap_no_evidence | - | - | - | 0/1/2 | 0/1, 1 |
| How does quantizing LLMs to 4-bit precision affect the interoperability of LLMs? | known_gap_no_evidence | - | - | - | 0/1/2 | 0/2, 2 |
| How does quantizing LLMs to 4-bit precision affect the quality of generated text | covered | - | synthesis | single claims | 1/2/3 | - |
| How does quantizing LLMs to 4-bit precision affect the diversity of generated te | known_gap_no_evidence | - | - | - | 0/0/2 | 0/0, 0 |
| How does quantizing LLMs to 4-bit precision affect the inference speed and laten | covered | - | synthesis | synthesis | 1/2/3 | - |
| How does quantizing LLMs to 4-bit precision affect the model size and memory usa | covered | - | synthesis | synthesis | 0/3/3 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 5 | 15 | 1 | 34.4 | digest_failed=0, sources_tried=5 |

## 5. Retrieval details

- Web search variants: [11, 12, 12] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 100 candidates -> 100 cleared min_similarity (0.56) -> top 20 shortlisted; 110 candidates -> 95 cleared min_similarity (0.56) -> top 20 shortlisted; 127 candidates -> 122 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 17, 'scopus': 26, 'both': 6}; requests to api.openalex.org in the log: 18
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0

## 6. Parsing details

- Attempted 15 papers, usable full text 15, 49 papers saved in the database.
- PDF obtained via: its own link: 5; parse cache hits: 10; Unpaywall OA links found: 0; landing-page citation_pdf_url: 0
- Individual download failures: 0 -> 
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

## 7. Groq and judge

- Stage 3: 24 digests for 3 sub-questions, 7 worker(s), 7 Groq key(s)
- Groq usage: 175,435 tokens (87,904 prompt + 87,531 completion, of which 65,778 reasoning) in 151 calls, 71 rate limits [digest 88,161, stage4_judge 67,745, digest_loop2 13,255, aspect_split 6,274]
- Rate-limit parking events: 71; per key (events / parked seconds): ...3mla: 10 / 119s, ...Ef4D: 8 / 144s, ...KJJp: 8 / 156s, ...KaRe: 9 / 126s, ...X2Oj: 12 / 118s, ...uNUk: 11 / 139s, ...x1nP: 13 / 190s
- Judge batch latencies (s): [12.8, 20.9, 5.9, 27.7, 6.0, 20.5, 5.5]

- Judge verdicts that came back as error: 0

## 7b. Stage 4: fact check

Claims after grouping: 88; labels {'unverified': 87, 'supported': 1}; contradictions stored: 0; time 13m 55s.

| # | Sub-question | Digests | Claims | Clusters | Supported | Partly supported | Unverified | Contradicted |
|---|---|---|---|---|---|---|---|---|
| 1 | What is quantization and how does it affect large  | 8 | 34 | 28 | 0 | 0 | 28 | 0 |
| 2 | What is 4-bit precision and how does it differ fro | 8 | 33 | 27 | 1 | 0 | 26 | 0 |
| 3 | What are the trade-offs of quantizing LLMs to 4-bi | 13 | 45 | 33 | 0 | 0 | 33 | 0 |

NLI pair cap: 225 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI; 216 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI; 239 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| WARNING | 3 | Stage N: N quote/claim pairs passed the topic gate; only the N most similar go to NLI |
| WARNING | 2 | _upsert_parsed: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | get_retrieved_paper: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- Groq rate limiting: 71 parking events; digest generation took 54s.
- Longest phase: Stage 4 fact check (claims, NLI, judges) (13m 55s, 61% of the run).

Warnings in the log: 8; errors: 0.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes

Second complete run with `LOOP2=true` and `FACTCHECK=true` (plan cache on). It ran with the Stage 4 code of before the `partially_supported` label, so Stage 4 has no partial labels here.

**Retrieval and parsing: fine.** 337 candidates -> 49 papers kept, 15 of 15 attempted papers parsed (10 from the parse cache), 0 PDF failures, 35 web sources. Semantic Scholar was skipped again (probe answered 429), as in every recent run. Two database connection drops (`Server disconnected`) were retried by `retry_transient` and did not matter.

**Stage 3: 3 of 3 sub-questions sufficient, 0 judge errors, 0 digest failures. But the sufficiency of sub-question 3 is the weakest kind.**
- Sub-question 1: sufficient without Loop 2 (2 of 2 aspects, 8 yes verdicts).
- Sub-question 2: 3 of 4 aspects were near misses (1 yes + 3 to 5 partial verdicts each); synthesis covered all 3 in 6 s, no search.
- Sub-question 3: the aspect split produced **8 aspects**. 4 were covered (size and memory, speed, quality, robustness) and 4 ended as `known_gap_no_evidence`: diversity of generated text, security, compatibility, interoperability. It counts as sufficient only under the core rule (`LOOP2_GAP_RULE=core`); the strict rule says **not** sufficient. So half of its aspects have no evidence at all, and a reader who sees only `sufficient: true` is told more than the evidence shows. This is KNOWN_LIMITS 4.9 in a real run, and the frontend must show `knownGapsNoEvidence` next to it.
- Cause of those gaps: the aspect split invents side aspects (compatibility, interoperability, diversity) that the retrieved papers do not discuss; the papers cover size, speed, accuracy and robustness. Loop 2 tried the aspect it could (robustness: `reselect`, 5 new sources, 15 new verified findings, 34 s, covered) and correctly gave up on the rest instead of searching for evidence that does not exist.
- Covered-by count over the run: 6 aspects by synthesis of several sources, 1 by `reselect`. (In my chat summary I first said 5 and 2; this table is the right count.)
- Loop 2 in total: 46 s (3% of the run), 13,255 Groq tokens.

**Groq usage:** 175,435 tokens in 151 calls: digest 88,161 (50%), stage4_judge 67,745 (39%), digest_loop2 13,255, aspect_split 6,274. 71 rate-limit answers (per-minute limit), 992 key-seconds parked; digest generation still took only 54 s. For comparison the 5-sub-question Q2 run used 186,317 tokens with a Stage 4 share of 22%: here Stage 4 used 2.7 times as many judge tokens per sub-question (22.6k against 8.3k). I did not find out why; likely candidates are more merge-judge pairs because quantization claims are very similar to each other, but that is not checked.

**Stage 4: no errors, no false conflicts, almost nothing corroborated.**
- 88 claims: 1 supported, 87 unverified, 0 contradicted, 0 disagreements. Same pattern as Q2 (4 of 113) and Q3: the stage works but papers rarely repeat the same specific claim. The new `partially_supported` label is meant for exactly this; it will show up in the next run.
- 13m 55s for 3 sub-questions (4.6 min each, against 3.3 min each in Q2), 61% of the whole run. 216 to 239 pairs passed the topic gate in each sub-question and only the 80 most similar were checked by NLI. Stage 4 time is now the main thing to bring down (KNOWN_LIMITS 4.10).

**Fixes after this run:** none to the pipeline. Report script: no change needed (its Stage 4 table already worked for this run).

**Open:** (1) show known gaps next to `sufficient` in the frontend (4.9); (2) aspect split inventing aspects the sources never cover, worth a look at the split prompt (a "must be answerable from papers about the topic" rule) or accepting it as the cost of broad questions; (3) Stage 4 speed (4.10); (4) the Stage 4 judge token cost per sub-question.
