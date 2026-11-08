# Pipeline run report - How do diffusion models compare with GANs for image generation quality and training stability?

Generated 2026-11-08 17:15 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 31 in the file) and the database. Query id `a01aea97-84e1-4ad2-8afb-79dd93968cd7`.

## 1. Summary

| | |
|---|---|
| Question | How do diffusion models compare with GANs for image generation quality and training stability? |
| Domain anchor | (cached): 'generative modeling' | context: Computer vision/generative AI: diffusion models refer to generative neural networks, not physical diffusion phenomena. |
| Started / finished | 2026-11-08 17:10:54 / 17:14:19 |
| **Total execution time** | **3m 25s** (205 s) |
| Sub-questions / search queries | 4 / 11 (per sub-question [3, 2, 3, 3]) |
| Plan source | plan-cache (stored plan reused, PLAN_CACHE=true) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 369 candidates -> 369 cleared the similarity floor -> 80 shortlisted |
| **Papers kept after the relevance judge** | **61** (log: 61); 19 shortlisted papers rejected |
| **Web sources** | **42** (per sub-question [11, 10, 9, 12]) |
| Papers attempted for parsing | 20 (top-N per sub-question) |
| **Papers parsed to usable full text** | **20** of 20 attempted (20 from the parse cache) |
| Papers not parsed (all routes failed) | 0 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 0 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 32 (20 from full text, 0 from abstracts, 12 from web snippets) |
| Findings (verified / total) | 70 / 77 |
| Coverage sufficient | 0 of 4 sub-questions |
| Judge | 1m 22s in 6 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 32 parking events, 18949 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 4 sub-questions) | 17:10:54 | 17:10:56 | 2s | 1% |
| Web search (Tavily) | 17:10:56 | 17:11:05 | 10s | 5% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 17:11:05 | 17:11:39 | 34s | 16% |
| Embedding pre-filter + relevance judge | 17:11:39 | 17:12:23 | 44s | 21% |
| Store papers in the database | 17:12:23 | 17:12:24 | 1s | 0% |
| PDF download + Docling parsing | 17:12:24 | 17:12:31 | 7s | 4% |
| Stage 3 preparation (aspect split, chunking, embedding) | 17:12:31 | 17:12:38 | 7s | 3% |
| Stage 3 digest generation (Groq) | 17:12:38 | 17:12:50 | 12s | 6% |
| Stage 3 judge + coverage (per sub-question) | 17:12:50 | 17:14:19 | 1m 29s | 43% |
| **Total** | 17:10:54 | 17:14:19 | **3m 25s** | 100% |

Loop 2 (second search for uncovered aspects) is part of the judge + coverage phase above: 16s by its own step timings (8% of the run). Its searches, parses and filters are NOT counted in the retrieval figures of this report; it stored 0 new paper(s) and 0 new web page(s) with the run, so the stored counts of papers and web sources are higher than the log counts by these numbers.

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What are diffusion models and GANs? | 95 -> 95 -> 20 | 16 of 20 | 5 | 11 | 8 (5 / 0 / 3) | 30 / 35 | NOT sufficient |
| 2 | What are the metrics or criteria for evaluating image generation quality and training stability? | 107 -> 107 -> 20 | 14 of 20 | 5 | 10 | 8 (5 / 0 / 3) | 32 / 33 | NOT sufficient |
| 3 | How do diffusion models compare with GANs in terms of image generation quality? | 74 -> 74 -> 20 | 19 of 20 | 5 | 9 | 8 (5 / 0 / 3) | 8 / 9 | NOT sufficient |
| 4 | How do diffusion models compare with GANs in terms of training stability? | 93 -> 93 -> 20 | 12 of 20 | 5 | 12 | 8 (5 / 0 / 3) | 0 / 0 | NOT sufficient |

- Relevance judge rejected 4 papers for [What are diffusion models and GANs?]. Examples: 'Generative adversarial networks and diffusion models in mate' (The paper compares performance in a specific application rather than defining or explaining what diffusion models and GANs are.); 'Diffusion-GAN: Training GANs with Diffusion' (The paper focuses on improving GAN training using diffusion techniques rather than explaining what diffusion models and GANs are.); 'Unifying Diffusion Models' (The paper focuses on advanced latent space formulations and specific applications like CycleDiffusion rather than providing a foundational d)
- Relevance judge rejected 6 papers for [What are the metrics or criteria for eva]. Examples: 'Creating Realities: An In-Depth Study of AI-Driven Image Gen' (The paper focuses on Generative Adversarial Networks (GANs) rather than diffusion models, which are explicitly required by the research ques); 'Comparative Analysis of GANs and Diffusion Models in Image G' (The paper discusses general model comparisons and challenges but does not provide specific metrics or criteria for evaluating quality or tra); 'Quality Prediction on Deep Generative Images' (The paper focuses on GANs rather than diffusion models and addresses image quality assessment without discussing training stability metrics.)
- Relevance judge rejected 9 papers for [How do diffusion models compare with GAN]. Examples: 'A STUDY ON SAMPLE DIVERSITY IN GENERATIVE MODELS: GANS VS. D' (The paper focuses on sample diversity and mode collapse rather than comparing overall image generation quality.); 'Comparative Analysis of Generative Models: Enhancing Image S' (The paper discusses computational resources and application selection but does not compare training stability between diffusion models and G); 'Noiseless Diffusion-GAN: Scaling-based data augmentation for' (The paper focuses on a specific GAN variant and data scaling techniques rather than a comparative analysis of training stability between dif)

### Sources behind each sub-question's digests

**1. What are diffusion models and GANs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 5 / 5 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 4 / 4 |
| Comparative Analysis of GANs and Diffusion Models in Image Generation | paper | full_text | 5 / 5 |
| Deep Generative Models for Image Synthesis: GANs, VAEs, and Diffusion Approaches | paper | full_text | 3 / 5 |
| Unifying GANs and Score-Based Diffusion as Generative Particle Models | paper | full_text | 3 / 5 |
| Advancements in Generative Modeling: A Comprehensive Survey of GANs and Diffusion Models for Te | web | web_snippet | 3 / 4 |
| Comparative Analysis of Generative Models: Enhancing Image Synthesis with VAEs, GANs, and Stabl | web | web_snippet | 3 / 3 |
| Opportunities and challenges of diffusion models for generative AI | web | web_snippet | 4 / 4 |

**2. What are the metrics or criteria for evaluating image generation quality and training stability?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | paper | full_text | 4 / 4 |
| A note on the evaluation of generative models | paper | full_text | 4 / 4 |
| Evaluation Metrics for Conditional Image Generation | paper | full_text | 5 / 5 |
| Improved Precision and Recall Metric for Assessing Generative Models | paper | full_text | 4 / 4 |
| Reliable Fidelity and Diversity Metrics for Generative Models | paper | full_text | 4 / 5 |
| A Review of the Image Quality Metrics used in Image Generative Models | web | web_snippet | 5 / 5 |
| Advancements in Generative Modeling: A Comprehensive Survey of GANs and Diffusion Models for Te | web | web_snippet | 3 / 3 |
| Evaluation metrics for generative image models | web | web_snippet | 3 / 3 |

**3. How do diffusion models compare with GANs in terms of image generation quality?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 0 / 0 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 0 / 0 |
| Beware of diffusion models for synthesizing medical images—a comparison with GANs in terms of m | paper | full_text | 0 / 0 |
| Comparative Analysis of GANs and Diffusion Models in Image Generation | paper | full_text | 0 / 0 |
| Deep Generative Models for Image Synthesis: GANs, VAEs, and Diffusion Approaches | paper | full_text | 0 / 0 |
| GANs vs. Diffusion Models: Putting AI to the test / Aurora Solar | web | web_snippet | 2 / 3 |
| Generative Adversarial Networks (GANs) vs Diffusion Models - GeeksforGeeks | web | web_snippet | 3 / 3 |
| Perceptual Evaluation of GANs and Diffusion Models for Generating X-rays | web | web_snippet | 3 / 3 |

**4. How do diffusion models compare with GANs in terms of training stability?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 0 / 0 |
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | paper | full_text | 0 / 0 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 0 / 0 |
| Diffusion-GAN: Training GANs with Diffusion | paper | full_text | 0 / 0 |
| Evaluating Text-to-Image Generation Methods: Stable Diffusion vs Generative Adversarial Network | paper | full_text | 0 / 0 |
| AI : Diffusion Models vs GANs | web | web_snippet | 0 / 0 |
| Advancements in Generative Modeling: A Comprehensive Survey of GANs and Diffusion Models for Te | web | web_snippet | 0 / 0 |
| Comparative Analysis of Generative Models: Enhancing Image Synthesis with VAEs, GANs, and Stabl | web | web_snippet | 0 / 0 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What are diffusion models and GANs?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 3, partial 8, no 7, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How do diffusion models and GANs generate images from noise or latent representations? | covered | 2 | 2 |
| 2 | What are the main differences between diffusion models and GANs? | covered | 4 | 3 |
| 3 | What are the main similarities between diffusion models and GANs? | uncovered | 0 | 0 |

Uncovered details: What are the main differences and similarities between them?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 1 (1 by synthesis of several sources), sufficient False (strict rule: False), gap rule core, 5.7 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| What are the main differences between diffusion models and GANs? | covered | - | synthesis | synthesis | 1/2/3 | - |
| What are the main similarities between diffusion models and GANs? | known_gap | reselect | - | - | 0/3/3 | 0/3, 3 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 0 | 0 | 0 | 0.6 | digest_failed=5, sources_tried=5 |

### 2. What are the metrics or criteria for evaluating image generation quality and training stability?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 21 = yes 8, partial 6, no 7, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How is image quality measured in image generation? | covered | 4 | 4 |
| 2 | How is image diversity measured in image generation? | covered | 3 | 3 |
| 3 | How is training stability measured in image generation models? | covered | 3 | 2 |
| 4 | How is convergence measured in image generation models? | uncovered | 0 | 0 |

Uncovered details: How are training stability and convergence measured, e.g. loss, samples per epoch, etc.?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 1 (1 by synthesis of several sources), sufficient False (strict rule: False), gap rule core, 5.9 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| How is convergence measured in image generation models? | known_gap | reselect | - | - | 0/2/1 | 0/2, 2 |
| How is training stability measured in image generation models? | covered | - | synthesis | synthesis | 1/1/4 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 0 | 0 | 0 | 0.8 | digest_failed=5, sources_tried=5 |

### 3. How do diffusion models compare with GANs in terms of image generation quality?

Sufficient: **False**; judge used: True; sources 3 (0 full text); judge candidates 15 = yes 8, partial 4, no 3, error 0; digest failures 5.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | advantages of diffusion models vs. GANs for image quality | covered | 6 | 3 |
| 2 | disadvantages of diffusion models vs. GANs for image quality | covered | 2 | 2 |
| 3 | How do diffusion models compare with GANs in terms of performance on different types of images such as realistic, artistic, and text-to-image? | covered | 3 | 3 |

Loop 2 (r1 triage, steps reselect, pool, queries): searched 0 aspect(s), covered 1 (1 by synthesis of several sources), sufficient False (strict rule: False), gap rule core, 4.7 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| How do diffusion models compare with GANs in terms of performance on different t | covered | - | synthesis | synthesis | 0/3/0 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|

### 4. How do diffusion models compare with GANs in terms of training stability?

Sufficient: **False**; judge used: True; sources 0 (0 full text); judge candidates 0 = yes 0, partial 0, no 0, error 0; digest failures 8.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | challenges for training diffusion models vs. GANs | no candidates | 0 | 0 |
| 2 | solutions for training diffusion models vs. GANs | no candidates | 0 | 0 |
| 3 | How do diffusion models vs. GANs handle training issues such as mode collapse, overconfidence, and other training issues? | no candidates | 0 | 0 |
| 4 | How do diffusion models vs. GANs scale with data size? | no candidates | 0 | 0 |
| 5 | How do diffusion models vs. GANs scale with model size? | no candidates | 0 | 0 |
| 6 | How do diffusion models vs. GANs scale with computational resources? | no candidates | 0 | 0 |

Uncovered details: What are the challenges and solutions for training diffusion models vs. GANs?; How do diffusion models vs. GANs handle mode collapse, overconfidence, or other training issues?; How do diffusion models vs. GANs scale with data size, model size, or computational resources?

## 5. Retrieval details

- Web search variants: [11, 10, 9, 12] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 95 candidates -> 95 cleared min_similarity (0.56) -> top 20 shortlisted; 107 candidates -> 107 cleared min_similarity (0.56) -> top 20 shortlisted; 74 candidates -> 74 cleared min_similarity (0.56) -> top 20 shortlisted; 93 candidates -> 93 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 29, 'scopus': 28, 'both': 4}; requests to api.openalex.org in the log: 23
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0

## 6. Parsing details

- Attempted 20 papers, usable full text 20, 61 papers saved in the database.
- PDF obtained via: -; parse cache hits: 20; Unpaywall OA links found: 0; landing-page citation_pdf_url: 0
- Individual download failures: 0 -> 
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

## 7. Groq and judge

- Stage 3: 32 digests for 4 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 32; per key (events / parked seconds): ...3mla: 1 / 747s, ...Ef4D: 6 / 5255s, ...KJJp: 8 / 5084s, ...KaRe: 6 / 5437s, ...X2Oj: 5 / 960s, ...uNUk: 5 / 350s, ...x1nP: 1 / 1116s
- Judge batch latencies (s): [25.8, 27.4, 5.0, 5.0, 13.7, 4.6]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 46 | Digest generation failed: all N Groq key(s) are rate limited for Ns |
| WARNING | 3 | _upsert_parsed: database connection error (attempt N/N): WriteError: EOF occurred in violation of protocol (_s |
| WARNING | 2 | _upsert_parsed: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | OpenAlex N on key ...CHgt for '<text>' (backoff N/N), pausing that key N.Ns |
| WARNING | 1 | find_cached_parse: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 1 | Loop N [What are diffusion models and GANs?]: every digest of the reselect step failed (rate limit?); stopping |
| WARNING | 1 | Loop N [What are the metrics or criteria for eva]: every digest of the reselect step failed (rate limit?); sto |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- Sub-question 'How do diffusion models compare with GANs in terms of image generation quality?': 5 digest JSON failure(s).
- Sub-question 'How do diffusion models compare with GANs in terms of training stability?': 8 digest JSON failure(s).
- Groq rate limiting: 32 parking events; digest generation took 12s.
- Longest phase: Stage 3 judge + coverage (per sub-question) (1m 29s, 43% of the run).

Warnings in the log: 11; errors: 46.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes

**This run was stopped by hand 3m 25s in. It is NOT a valid result** (the report script lists it as "complete" because the log ended after Stage 3's judge; no digest-quality figure below can be trusted). First attempt with the new parallel code (`STAGE4_OVERLAP`, `STAGE3_PIPELINE`, `STAGE3_SQ_WORKERS=2`, `JUDGE_PARALLEL=2`, `RELEVANCE_WORKERS=2`, `STAGE3_PREP_WORKERS=4`, near match beside the conflict NLI, NLI preload), same question as run 30.

**Why it was stopped:** the Groq keys were at their daily token limit. Digest calls failed with "all 7 Groq key(s) are rate limited for 210 to 246 s" (46 failed digest calls), and the retry-after values of the 429 answers in `logs/groq_usage.jsonl` were 772 to 2,023 s: that is the daily limit, not the per-minute one. One sub-question ended with 0 verified findings and 0 of 4 sub-questions were sufficient. Continuing would only have burned the rest of the budget on garbage. By our own meter the busiest keys were at 76 to 77% of 200,000 tokens, so Groq's own count of the day is higher than ours (other uses of the same accounts, or a calendar-day window).
Cost of the attempt: 30 Groq calls, 76,617 tokens (21 digest calls, 9 aspect-split calls) before it was stopped.

**What can be read from it (one sample, not a benchmark):**
- Relevance filter + embedding pre-filter: **44 s** against 94 s in run 30 and 120 s in run 28 (`RELEVANCE_WORKERS=2`; the parse cache and the retrieval were comparable).
- Stage 3 preparation (aspect split from the cache, chunking, embeddings): 7 s against 18 s in run 30 (`STAGE3_PREP_WORKERS=4`; the aspect cache hit 9 times).
- Paper search 34 s, web search 10 s, planner 2 s, parsing 7 s (all 20 papers from the parse cache): as before.
- Stage 3 judge on the host: 6 batches in 1m 22s, the judge events came after the digest step's end (the gate works in a real run).
- Stage 4 was queued early for 3 sub-questions while Stage 3 was still working ("Stage 4 queued ... while Stage 3 goes on" appears at 17:13:23 for sub-question 1 and at 17:14:19 for the last). The Stage 4 judge waited out a 246 s Groq limit ("waiting and asking again (1 of 2)") instead of failing closed, as designed. Stage 4 itself did not finish.

**Found because of this run:** the digest cache had **0 hits** (21 digest calls), although the question and the plan were the same as in run 30. Its scope was (sub-question database id, paper database id), and both are new on every run (the plan cache keeps the plan, not the ids), so every run paid the whole digest cost (88k to 112k tokens) again. Fixed after the run: the scope now comes from the content (sub-question text and the paper's arXiv id, DOI or title; web pages by URL), `DIGEST_CACHE_SCOPE=id` restores the old behaviour. A rerun of a question on the same sources now reuses its digests (tested offline).
Also: I stopped the processes with a filter that was too broad and also ended a few of my own shell helpers; the run's python processes were the target and are gone.

**Left in the database:** the query `a01aea97-84e1-4ad2-8afb-79dd93968cd7` with digests and coverage of the aborted Stage 3 (no Stage 4 result). It will show in the web app's history as a finished-looking run with 0 of 4 sufficient. It can be ignored or deleted.

