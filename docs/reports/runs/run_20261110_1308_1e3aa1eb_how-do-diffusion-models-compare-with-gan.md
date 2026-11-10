# Pipeline run report - How do diffusion models compare with GANs for image generation quality and training stability?

Generated 2026-11-10 13:22 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 32 in the file) and the database. Query id `1e3aa1eb-4b63-499d-a129-a5d362cd5f90`.

## 1. Summary

| | |
|---|---|
| Question | How do diffusion models compare with GANs for image generation quality and training stability? |
| Domain anchor | (cached): 'generative modeling' | context: Computer vision/generative AI: diffusion models refer to generative neural networks, not physical diffusion phenomena. |
| Started / finished | 2026-11-10 13:08:12 / 13:22:05 |
| **Total execution time** | **13m 54s** (834 s) |
| Sub-questions / search queries | 4 / 11 (per sub-question [3, 2, 3, 3]) |
| Plan source | plan-cache (stored plan reused, PLAN_CACHE=true) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 368 candidates -> 368 cleared the similarity floor -> 80 shortlisted |
| **Papers kept after the relevance judge** | **61** (log: 59); 21 shortlisted papers rejected |
| **Web sources** | **48** (per sub-question [12, 10, 11, 12]) |
| Papers attempted for parsing | 21 (top-N per sub-question) |
| **Papers parsed to usable full text** | **20** of 21 attempted (20 from the parse cache) |
| Papers not parsed (all routes failed) | 0 download/route failures + 1 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 0 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 42 (29 from full text, 0 from abstracts, 13 from web snippets) |
| Findings (verified / total) | 121 / 129 |
| Coverage sufficient | 4 of 4 sub-questions |
| Judge | 2m 45s in 11 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 159 parking events, 2769 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 4 sub-questions) | 13:08:12 | 13:08:19 | 8s | 1% |
| Web search (Tavily) | 13:08:19 | 13:08:32 | 12s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 13:08:32 | 13:09:06 | 34s | 4% |
| Embedding pre-filter + relevance judge | 13:09:06 | 13:09:59 | 53s | 6% |
| Store papers in the database | 13:09:59 | 13:10:00 | 1s | 0% |
| PDF download + Docling parsing | 13:10:00 | 13:10:11 | 11s | 1% |
| Stage 3 preparation (aspect split, chunking, embedding) | 13:10:11 | 13:10:22 | 11s | 1% |
| Stage 3 digest generation (Groq) | 13:10:22 | 13:10:28 | 7s | 1% |
| Stage 3 judge + coverage (per sub-question) | 13:10:28 | 13:15:46 | 5m 18s | 38% |
| Stage 4 fact check (claims, NLI, judges) | 13:15:46 | 13:22:05 | 6m 19s | 45% |
| **Total** | 13:08:12 | 13:22:05 | **13m 54s** | 100% |

Loop 2 (second search for uncovered aspects) is part of the judge + coverage phase above: 4m 54s by its own step timings (35% of the run). Its searches, parses and filters are NOT counted in the retrieval figures of this report; it stored 2 new paper(s) and 3 new web page(s) with the run, so the stored counts of papers and web sources are higher than the log counts by these numbers.

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What are diffusion models and GANs? | 94 -> 94 -> 20 | 15 of 20 | 9 | 15 | 18 (14 / 0 / 4) | 42 / 45 | sufficient |
| 2 | What are the metrics or criteria for evaluating image generation quality and training stability? | 107 -> 107 -> 20 | 15 of 20 | 5 | 10 | 8 (5 / 0 / 3) | 27 / 30 | sufficient |
| 3 | How do diffusion models compare with GANs in terms of image generation quality? | 75 -> 75 -> 20 | 19 of 20 | 5 | 11 | 8 (5 / 0 / 3) | 31 / 32 | sufficient |
| 4 | How do diffusion models compare with GANs in terms of training stability? | 92 -> 92 -> 20 | 10 of 20 | 5 | 12 | 8 (5 / 0 / 3) | 21 / 22 | sufficient |

- Relevance judge rejected 5 papers for [What are diffusion models and GANs?]. Examples: 'Generative adversarial networks and diffusion models in mate' (The paper compares performance in a specific application rather than defining or explaining what diffusion models and GANs are.); 'Diffusion-GAN: Training GANs with Diffusion' (The paper focuses on improving GAN training using diffusion techniques rather than explaining what diffusion models and GANs are.); 'Unifying Diffusion Models' (The paper focuses on advanced latent space formulations and specific applications like CycleDiffusion rather than providing a foundational d)
- Relevance judge rejected 5 papers for [What are the metrics or criteria for eva]. Examples: 'Creating Realities: An In-Depth Study of AI-Driven Image Gen' (The paper focuses on Generative Adversarial Networks (GANs) rather than diffusion models, which are explicitly required by the research ques); 'Comparative Analysis of GANs and Diffusion Models in Image G' (The paper discusses general model comparisons and challenges but does not provide specific metrics or criteria for evaluating quality or tra); 'Quality Prediction on Deep Generative Images' (The paper focuses on GANs rather than diffusion models and does not address training stability metrics.)
- Relevance judge rejected 11 papers for [How do diffusion models compare with GAN]. Examples: 'A STUDY ON SAMPLE DIVERSITY IN GENERATIVE MODELS: GANS VS. D' (The paper focuses on sample diversity and mode collapse rather than comparing overall image generation quality.); 'Comparative Analysis of Generative Models: Enhancing Image S' (The paper discusses computational resources and application selection but does not compare training stability between diffusion models and G); 'Noiseless Diffusion-GAN: Scaling-based data augmentation for' (The paper focuses on a specific GAN variant and data scaling techniques rather than a comparative analysis of training stability between dif)

### Sources behind each sub-question's digests

**1. What are diffusion models and GANs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 1 / 3 |
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 2 / 2 |
| A Comprehensive Survey of Image Generation Models Based on Deep Learning | paper | full_text | 1 / 1 |
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | paper | full_text | 4 / 5 |
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | paper | full_text | 1 / 1 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 4 / 4 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 1 / 1 |
| Comparative Analysis of GANs and Diffusion Models in Image Generation | paper | full_text | 5 / 5 |
| Comparative Analysis of GANs and Diffusion Models in Image Generation | paper | full_text | 2 / 2 |
| Comparative Analysis of Generative Models: Enhancing Image Synthesis with VAEs, GANs, and Stabl | paper | full_text | 1 / 1 |
| GENERATOR MATCHING: GENERATIVE MODELING WITH ARBITRARY MARKOV PROCESSES | paper | full_text | 1 / 1 |
| Generative AI in depth: A survey of recent advances, model variants, and real-world application | paper | full_text | 3 / 3 |
| Unifying GANs and Score-Based Diffusion as Generative Particle Models | paper | full_text | 5 / 5 |
| Unifying GANs and Score-Based Diffusion as Generative Particle Models | paper | full_text | 1 / 1 |
| Advancements in Generative Modeling: A Comprehensive Survey of GANs and Diffusion Models for Te | web | web_snippet | 3 / 3 |
| GANs vs. Diffusion Models: Putting AI to the test / Aurora Solar | web | web_snippet | 4 / 4 |
| Improving Diffusion Models as an Alternative To GANs, Part 1 / NVIDIA Technical Blog | web | web_snippet | 2 / 2 |
| lecture_notes.pdf | web | web_snippet | 1 / 1 |

**2. What are the metrics or criteria for evaluating image generation quality and training stability?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | paper | full_text | 3 / 3 |
| A note on the evaluation of generative models | paper | full_text | 5 / 5 |
| Evaluation Metrics for Conditional Image Generation | paper | full_text | 3 / 4 |
| Improved Precision and Recall Metric for Assessing Generative Models | paper | full_text | 2 / 3 |
| Reliable Fidelity and Diversity Metrics for Generative Models | paper | full_text | 4 / 5 |
| A Brief History and Overview of Generative Models in Machine Learning | web | web_snippet | 2 / 2 |
| Advancements in Generative Modeling: A Comprehensive Survey of GANs and Diffusion Models for Te | web | web_snippet | 3 / 3 |
| Generative machine learning models for image synthesis: Advances, challenges, and future direct | web | web_snippet | 5 / 5 |

**3. How do diffusion models compare with GANs in terms of image generation quality?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 5 / 5 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 5 / 5 |
| Beware of diffusion models for synthesizing medical images—a comparison with GANs in terms of m | paper | full_text | 3 / 3 |
| Comparative Analysis of GANs and Diffusion Models in Image Generation | paper | full_text | 4 / 4 |
| Deep Generative Models for Image Synthesis: GANs, VAEs, and Diffusion Approaches | paper | full_text | 5 / 5 |
| GANs vs. Diffusion Models: Putting AI to the test / Aurora Solar | web | web_snippet | 2 / 3 |
| Generative Adversarial Networks (GANs) vs Diffusion Models | web | web_snippet | 5 / 5 |
| Synthetic Scientific Image Generation with VAE, GAN, and Diffusion Model Architectures | web | web_snippet | 2 / 2 |

**4. How do diffusion models compare with GANs in terms of training stability?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 5 / 5 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 2 / 3 |
| Diffusion-GAN: Training GANs with Diffusion | paper | full_text | 5 / 5 |
| Evaluating Text-to-Image Generation Methods: Stable Diffusion vs Generative Adversarial Network | paper | full_text | 1 / 1 |
| Unrolled Generative Adversarial Networks | paper | full_text | 0 / 0 |
| Advancements in Generative Modeling: A Comprehensive Survey of GANs and Diffusion Models for Te | web | web_snippet | 5 / 5 |
| GANs vs. Diffusion Models: Putting AI to the test / Aurora Solar | web | web_snippet | 1 / 1 |
| Synthetic Scientific Image Generation with VAE, GAN, and Diffusion Model Architectures | web | web_snippet | 2 / 2 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What are diffusion models and GANs?

Sufficient: **True**; judge used: True; sources 13 (9 full text); judge candidates 30 = yes 6, partial 12, no 12, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How do diffusion models and GANs generate images from noise or latent representations? | covered | 3 | 3 |
| 2 | What are the main differences between diffusion models and GANs? | covered | 3 | 2 |
| 3 | What are the main similarities between diffusion models and GANs? | covered | 2 | 2 |

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 2 (1 by synthesis of several sources), sufficient True (strict rule: True), gap rule core, 288.5 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| What are the main similarities between diffusion models and GANs? | covered | reselect, pool, queries | queries | synthesis | 1/1/4 | - |
| How do diffusion models and GANs generate images from noise or latent representa | covered | - | synthesis | single claims | 1/3/2 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 5 | 7 | 0 | 60.3 | digest_failed=0, sources_tried=5 |
| pool | 1 | 2 | 2 | 0 | 27.3 | parsed=2, digest_failed=0, sources_tried=3 |
| queries | 1 | 3 | 5 | 1 | 195.5 | queries=3, new_web_kept=3, digest_failed=0, new_web_found=11, new_papers_kept=2, new_papers_found=2, new_papers_parsed=2 |

### 2. What are the metrics or criteria for evaluating image generation quality and training stability?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 22 = yes 9, partial 0, no 13, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How is image quality measured | covered | 5 | 4 |
| 2 | How is image diversity measured | covered | 2 | 2 |
| 3 | How is training stability measured in image generation models? | uncovered | 1 | 1 |
| 4 | How is convergence measured in image generation models? | uncovered | 1 | 1 |

Uncovered details: How are training stability and convergence measured, e.g. loss, samples per epoch, etc.?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 0 aspect(s), covered 0 (0 by synthesis of several sources), sufficient True (strict rule: False), gap rule core, 0.0 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| How is convergence measured in image generation models? | known_gap_no_evidence | - | - | - | 1/0/3 | 1/0, 1 |
| How is training stability measured in image generation models? | known_gap_no_evidence | - | - | - | 1/0/5 | 1/0, 1 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|

### 3. How do diffusion models compare with GANs in terms of image generation quality?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 27 = yes 16, partial 10, no 1, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | advantages of diffusion models vs. GANs for image quality | covered | 6 | 5 |
| 2 | disadvantages of diffusion models vs. GANs for image quality | covered | 2 | 2 |
| 3 | How do diffusion models vs. GANs perform on realistic images? | covered | 3 | 3 |
| 4 | How do diffusion models vs. GANs perform on artistic images? | covered | 2 | 2 |
| 5 | How do diffusion models vs. GANs perform on text-to-image generation? | covered | 3 | 2 |

### 4. How do diffusion models compare with GANs in terms of training stability?

Sufficient: **True**; judge used: True; sources 7 (4 full text); judge candidates 32 = yes 7, partial 14, no 11, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | challenges for training diffusion models vs. GANs | covered | 4 | 4 |
| 2 | solutions for training diffusion models vs. GANs | covered | 2 | 2 |
| 3 | How do diffusion models vs. GANs handle mode collapse? | covered | 3 | 3 |
| 4 | How do diffusion models vs. GANs handle overconfidence? | uncovered | 0 | 0 |
| 5 | How do diffusion models vs. GANs handle other training issues? | covered | 4 | 3 |
| 6 | How do diffusion models vs. GANs scale with data size? | uncovered | 0 | 0 |
| 7 | How do diffusion models vs. GANs scale with model size? | uncovered | 0 | 0 |
| 8 | How do diffusion models vs. GANs scale with computational resources? | uncovered | 0 | 0 |

Uncovered details: How do diffusion models vs. GANs handle mode collapse, overconfidence, or other training issues?; How do diffusion models vs. GANs scale with data size, model size, or computational resources?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 0 aspect(s), covered 2 (2 by synthesis of several sources), sufficient True (strict rule: False), gap rule core, 5.9 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| How do diffusion models vs. GANs handle mode collapse? | covered | - | synthesis | synthesis | 0/3/2 | - |
| How do diffusion models vs. GANs scale with data size? | known_gap_no_evidence | - | - | - | 0/1/1 | 0/1, 1 |
| How do diffusion models vs. GANs handle overconfidence? | known_gap_no_evidence | - | - | - | 0/1/1 | 0/1, 1 |
| How do diffusion models vs. GANs scale with model size? | known_gap_no_evidence | - | - | - | 0/1/1 | 0/1, 1 |
| How do diffusion models vs. GANs handle other training issues? | covered | - | synthesis | synthesis | 1/5/0 | - |
| How do diffusion models vs. GANs scale with computational resources? | known_gap_no_evidence | - | - | - | 0/1/2 | 0/1, 1 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|

## 5. Retrieval details

- Web search variants: [12, 10, 11, 12] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 94 candidates -> 94 cleared min_similarity (0.56) -> top 20 shortlisted; 107 candidates -> 107 cleared min_similarity (0.56) -> top 20 shortlisted; 75 candidates -> 75 cleared min_similarity (0.56) -> top 20 shortlisted; 92 candidates -> 92 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 28, 'scopus': 28, 'both': 5}; requests to api.openalex.org in the log: 28
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0

## 6. Parsing details

- Attempted 21 papers, usable full text 20, 59 papers saved in the database.
- PDF obtained via: -; parse cache hits: 20; Unpaywall OA links found: 0; landing-page citation_pdf_url: 0
- Individual download failures: 0 -> 
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | parse/database error: 33 |

## 7. Groq and judge

- Stage 3: 32 digests for 4 sub-questions, 7 worker(s), 7 Groq key(s)
- Groq usage: 290,782 tokens (152,227 prompt + 138,555 completion, of which 107,706 reasoning) in 333 calls, 159 rate limits [digest 104,067, stage4_near 60,119, stage4_merge 59,410, stage4_support 22,462, digest_loop2 22,449, stage4_conflict 15,305, aspect_split 6,970]
- Rate-limit parking events: 159; per key (events / parked seconds): ...3mla: 25 / 395s, ...Ef4D: 18 / 336s, ...KJJp: 22 / 377s, ...KaRe: 20 / 366s, ...X2Oj: 21 / 333s, ...uNUk: 22 / 393s, ...x1nP: 31 / 569s
- Judge batch latencies (s): [25.9, 23.2, 5.4, 14.6, 12.3, 7.1, 29.5, 28.9, 5.6, 7.7, 4.5]

- Judge verdicts that came back as error: 0

## 7b. Stage 4: fact check

Claims after grouping: 89; labels {'partially_supported': 35, 'unverified': 49, 'contradicted': 1, 'supported': 4}; contradictions stored: 3; time 6m 19s.

| # | Sub-question | Digests | Claims | Clusters | Supported | Partly supported | Unverified | Contradicted |
|---|---|---|---|---|---|---|---|---|
| 1 | What are the metrics or criteria for evaluating im | 8 | 27 | 20 | 0 | 11 | 9 | 0 |
| 2 | How do diffusion models compare with GANs in terms | 8 | 31 | 20 | 4 | 4 | 12 | 0 |
| 3 | How do diffusion models compare with GANs in terms | 8 | 21 | 17 | 0 | 8 | 9 | 0 |
| 4 | What are diffusion models and GANs? | 18 | 42 | 32 | 0 | 12 | 19 | 1 |

NLI pair cap: 228 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI; 106 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI; 701 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI
- Conflict: Statement A says GANs iteratively convert noise, while Source B says GANs use a direct mapping, directly opposing the described process.
- Conflict: Both statements make opposite claims about which model type produces more realistic/detail‑rich images in the same general setting.
- Conflict: Both statements make opposite claims about which model type produces more realistic images.

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 1 | Failed to parse paper <id>: N |
| WARNING | 8 | find_cached_parse: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 3 | Stage N: N quote/claim pairs passed the topic gate; only the N most similar go to NLI |
| WARNING | 2 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 2 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 2 | find_cached_parse: database connection error (attempt N/N): RemoteProtocolError: <ConnectionTerminated error_c |
| WARNING | 1 | _upsert_parsed: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- 1 paper(s) failed at the parse/database step: A Survey on Generative Models for Image Synthesis: (33)
- Groq rate limiting: 159 parking events; digest generation took 7s.
- Longest phase: Stage 4 fact check (claims, NLI, judges) (6m 19s, 45% of the run).

Warnings in the log: 18; errors: 1.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes

**First run after the parallelism changes (script run, not through the web app).** Same question as runs 30 and 31, started 2026-11-10 13:08, no Groq daily-limit problem (the longest key park was 37 s; the breaker never opened).

**Time: 13m 54s against 23m 33s for run 30 (-41%).** Not a clean comparison, three things were reused: the stored plan (plan cache), the parse cache (20 of 21 papers) and the judge cache (cache hits 17/30, 26/30 and 1/1 in the first batches). The digest cache did NOT help: digest tokens were 104,067 against 112,073 in run 30, because the scope change makes the first run under the new scope a miss. A rerun of this question should reuse them. So part of the saving is caches and part is the new overlap; this single run cannot split the two.

**The phase table misleads now.** "Digest generation 7 s" and "Stage 4 6m 19s" are artefacts of the overlap: digests keep running while the judge starts, and Stage 4 starts during Stage 3. Real timeline from the log:
- Stage 3 ran 13:10:22 to 13:15:46 (5m 24s). Sub-question 1 ("What are diffusion models and GANs?") was last because of Loop 2: reselect 60 s, pool 27 s, queries 195 s, 288 s in total for one aspect, which it did cover.
- Stage 4 ran 13:10:58 to 13:22:05 (about 11 min) and finished 4m 48s of work during Stage 3, then 6m 19s after it.
- Sub-questions were queued at 13:10:58, 13:12:43, 13:13:19 and 13:15:46 but finished at 13:13:54, 13:16:56, 13:19:05 and 13:22:05. That is one background worker processing a queue: each sub-question took about 2m 10s to 3m, and the queue was backed up, so the last sub-question started only at 13:19:05. **Stage 4 is now the critical path.** A second Stage 4 worker would save roughly 3 min; not built (it adds simultaneous Groq calls, so it would be a switch).

**Stage 3 judge unchanged in quality.** 4 of 4 sub-questions sufficient, 0 judge errors, 0 digest failures, 11 batches (4.5 to 29.5 s). Sub-questions 2 and 4 keep 6 aspects as known gaps with no evidence (training stability and convergence measurement, overconfidence, scaling with data, model size and compute) and Loop 2 searched 0 of them because the gap rule treats them as core-sufficient. Same gaps as run 30.

**Stage 4: 89 claims: 4 supported, 35 partially supported, 49 unverified, 1 contradicted** (run 30: 100 claims, 8 / 19 / 71 / 2). Partly supported is now 39% of claims and unverified fell from 71% to 55%; supported fell from 8 to 4 (different claim set, one run, so I would not read this as a trend). Contradictions stored: 3. I read the quotes: all three are real disagreements between sources (GANs "iteratively convert noise" against "direct mapping"; two pairs where one source says GANs excel in realism and another says diffusion is better). So 3 of 3 correct this time, against 1 of 2 in run 30; still a very small sample. Only one claim carries the contradicted label, the other two are stored as disagreements.

**Groq: 290,782 tokens in 333 calls** (run 30: 284,736 in 294). Stage 4 is now 54% of it (157k): stage4_near 60,119, stage4_merge 59,410, stage4_support 22,462, stage4_conflict 15,305. The same-claim (merge) and near-match judges cost the most; digest 104,067, digest_loop2 22,449, aspect_split 6,970. Rate limiting fell: 159 parking events and 2,769 key-seconds parked, against 112 events and 8,746 key-seconds in run 30; no breaker, no wait of more than 37 s.

**Other warnings:** Semantic Scholar probe returned 429 and was skipped for the run (as designed). Supabase "Server disconnected" ten times in the parse cache lookup; the retry recovered all but one paper ("A Survey on Generative Models for Image Synthesis...", parse/database error), which still appears in the digest sources from the cache. NLI pair cap hit in three sub-questions (228, 106 and 701 pairs passed the topic gate, 80 went to NLI).

**Not verified by this run:** the replayed progress burst and the per-sub-question UI (the run did not go through the web app); `judgeWaits` and `judgeFailures` (they are in the Stage 4 event data, which the log does not hold; the log shows no wait or breaker line); host behaviour under the 4 simultaneous judge requests (no judge error, batch latencies in line with run 30).

**Open for next time:** (1) a second Stage 4 worker or splitting the queue to shorten the Stage 4 tail; (2) Stage 4 token cost (merge + near = 41% of the run); (3) Loop 2 on one aspect costs 288 s and decides when Stage 3 ends; (4) rerun of the same question to measure the digest cache.
