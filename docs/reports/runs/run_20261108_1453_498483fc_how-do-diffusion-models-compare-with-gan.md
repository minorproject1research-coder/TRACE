# Pipeline run report - How do diffusion models compare with GANs for image generation quality and training stability?

Generated 2026-11-08 15:22 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 30 in the file) and the database. Query id `498483fc-938d-4816-900f-d8b1b7d64c64`.

## 1. Summary

| | |
|---|---|
| Question | How do diffusion models compare with GANs for image generation quality and training stability? |
| Domain anchor | (cached): 'generative modeling' | context: Computer vision/generative AI: diffusion models refer to generative neural networks, not physical diffusion phenomena. |
| Started / finished | 2026-11-08 14:53:48 / 15:17:21 |
| **Total execution time** | **23m 33s** (1413 s) |
| Sub-questions / search queries | 4 / 11 (per sub-question [3, 2, 3, 3]) |
| Plan source | plan-cache (stored plan reused, PLAN_CACHE=true) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 370 candidates -> 370 cleared the similarity floor -> 80 shortlisted |
| **Papers kept after the relevance judge** | **65** (log: 62); 18 shortlisted papers rejected |
| **Web sources** | **44** (per sub-question [10, 10, 10, 11]) |
| Papers attempted for parsing | 20 (top-N per sub-question) |
| **Papers parsed to usable full text** | **20** of 20 attempted (20 from the parse cache) |
| Papers not parsed (all routes failed) | 0 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 0 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 41 (29 from full text, 0 from abstracts, 12 from web snippets) |
| Findings (verified / total) | 126 / 129 |
| Coverage sufficient | 3 of 4 sub-questions |
| Judge | 2m 34s in 14 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 112 parking events, 8746 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 4 sub-questions) | 14:53:48 | 14:53:50 | 3s | 0% |
| Web search (Tavily) | 14:53:50 | 14:54:02 | 11s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 14:54:02 | 14:54:39 | 37s | 3% |
| Embedding pre-filter + relevance judge | 14:54:39 | 14:56:13 | 1m 34s | 7% |
| Citation enrichment (Semantic Scholar) | 14:56:13 | 14:56:24 | 11s | 1% |
| Store papers in the database | 14:56:24 | 14:56:25 | 1s | 0% |
| PDF download + Docling parsing | 14:56:25 | 14:56:31 | 6s | 0% |
| Stage 3 preparation (aspect split, chunking, embedding) | 14:56:31 | 14:56:49 | 18s | 1% |
| Stage 3 digest generation (Groq) | 14:56:49 | 14:58:16 | 1m 27s | 6% |
| Stage 3 judge + coverage (per sub-question) | 14:58:16 | 15:03:40 | 5m 23s | 23% |
| Stage 4 fact check (claims, NLI, judges) | 15:03:40 | 15:17:21 | 13m 42s | 58% |
| **Total** | 14:53:48 | 15:17:21 | **23m 33s** | 100% |

Loop 2 (second search for uncovered aspects) is part of the judge + coverage phase above: 3m 51s by its own step timings (16% of the run). Its searches, parses and filters are NOT counted in the retrieval figures of this report; it stored 3 new paper(s) and 3 new web page(s) with the run, so the stored counts of papers and web sources are higher than the log counts by these numbers.

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What are diffusion models and GANs? | 95 -> 95 -> 20 | 16 of 20 | 8 | 10 | 14 (11 / 0 / 3) | 42 / 44 | sufficient |
| 2 | What are the metrics or criteria for evaluating image generation quality and training stability? | 107 -> 107 -> 20 | 15 of 20 | 5 | 10 | 8 (5 / 0 / 3) | 25 / 26 | sufficient |
| 3 | How do diffusion models compare with GANs in terms of image generation quality? | 75 -> 75 -> 20 | 19 of 20 | 5 | 10 | 8 (5 / 0 / 3) | 30 / 30 | sufficient |
| 4 | How do diffusion models compare with GANs in terms of training stability? | 93 -> 93 -> 20 | 12 of 20 | 9 | 14 | 11 (8 / 0 / 3) | 29 / 29 | NOT sufficient |

- Relevance judge rejected 4 papers for [What are diffusion models and GANs?]. Examples: 'Generative adversarial networks and diffusion models in mate' (The paper compares performance in a specific application rather than defining or explaining what diffusion models and GANs are.); 'Diffusion-GAN: Training GANs with Diffusion' (The paper focuses on improving GAN training using diffusion techniques rather than explaining what diffusion models and GANs are.); 'Unifying Diffusion Models' (The paper focuses on advanced latent space formulations and specific applications like CycleDiffusion rather than providing a foundational d)
- Relevance judge rejected 5 papers for [What are the metrics or criteria for eva]. Examples: 'Creating Realities: An In-Depth Study of AI-Driven Image Gen' (The paper focuses on Generative Adversarial Networks (GANs) rather than diffusion models, which are explicitly required by the research ques); 'Comparative Analysis of GANs and Diffusion Models in Image G' (The paper discusses general challenges like training instability but does not provide specific metrics or criteria for evaluating quality or); 'Quality Prediction on Deep Generative Images' (The paper focuses on GANs rather than diffusion models and addresses image quality assessment without discussing training stability metrics.)
- Relevance judge rejected 9 papers for [How do diffusion models compare with GAN]. Examples: 'A STUDY ON SAMPLE DIVERSITY IN GENERATIVE MODELS: GANS VS. D' (The paper focuses on sample diversity and mode collapse rather than comparing overall image generation quality.); 'Comparative Analysis of Generative Models: Enhancing Image S' (The paper discusses computational resources and application selection but does not compare training stability between diffusion models and G); 'Noiseless Diffusion-GAN: Scaling-based data augmentation for' (The paper focuses on a specific GAN variant and data scaling techniques rather than a comparative analysis of training stability between dif)

### Sources behind each sub-question's digests

**1. What are diffusion models and GANs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 2 / 2 |
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 5 / 5 |
| A Comprehensive Survey of Image Generation Models Based on Deep Learning | paper | full_text | 1 / 1 |
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | paper | full_text | 1 / 1 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 1 / 1 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 3 / 3 |
| Comparative Analysis of GANs and Diffusion Models in Image Generation | paper | full_text | 4 / 5 |
| Comparative Analysis of Generative Models: Enhancing Image Synthesis with VAEs, GANs, and Stabl | paper | full_text | 1 / 2 |
| Deep Generative Models for Image Synthesis: GANs, VAEs, and Diffusion Approaches | paper | full_text | 5 / 5 |
| Unifying GANs and Score-Based Diffusion as Generative Particle Models | paper | full_text | 2 / 2 |
| Unifying GANs and Score-Based Diffusion as Generative Particle Models | paper | full_text | 5 / 5 |
| Advancements in Generative Modeling: A Comprehensive Survey of GANs and Diffusion Models for Te | web | web_snippet | 4 / 4 |
| Comparative Analysis of Generative Models: Enhancing Image Synthesis with VAEs, GANs, and Stabl | web | web_snippet | 4 / 4 |
| Opportunities and challenges of diffusion models for generative AI | web | web_snippet | 4 / 4 |

**2. What are the metrics or criteria for evaluating image generation quality and training stability?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | paper | full_text | 4 / 4 |
| A note on the evaluation of generative models | paper | full_text | 4 / 4 |
| Evaluation Metrics for Conditional Image Generation | paper | full_text | 3 / 3 |
| Improved Precision and Recall Metric for Assessing Generative Models | paper | full_text | 2 / 3 |
| Reliable Fidelity and Diversity Metrics for Generative Models | paper | full_text | 2 / 2 |
| A Review of the Image Quality Metrics used in Image Generative Models | web | web_snippet | 3 / 3 |
| Advancements in Generative Modeling: A Comprehensive Survey of GANs and Diffusion Models for Te | web | web_snippet | 2 / 2 |
| Evaluation metrics for generative image models | web | web_snippet | 5 / 5 |

**3. How do diffusion models compare with GANs in terms of image generation quality?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 4 / 4 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 4 / 4 |
| Beware of diffusion models for synthesizing medical images—a comparison with GANs in terms of m | paper | full_text | 4 / 4 |
| Comparative Analysis of GANs and Diffusion Models in Image Generation | paper | full_text | 5 / 5 |
| Deep Generative Models for Image Synthesis: GANs, VAEs, and Diffusion Approaches | paper | full_text | 4 / 4 |
| GANs vs. Diffusion Models: Putting AI to the test / Aurora Solar | web | web_snippet | 3 / 3 |
| Generative Adversarial Networks (GANs) vs Diffusion Models - GeeksforGeeks | web | web_snippet | 3 / 3 |
| Perceptual Evaluation of GANs and Diffusion Models for Generating X-rays | web | web_snippet | 3 / 3 |

**4. How do diffusion models compare with GANs in terms of training stability?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 5 / 5 |
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 1 / 1 |
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | paper | full_text | 5 / 5 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 3 / 3 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 1 / 1 |
| Diffusion-GAN: Training GANs with Diffusion | paper | full_text | 4 / 4 |
| Diffusion-GAN: Training GANs with Diffusion | paper | full_text | 2 / 2 |
| Evaluating Text-to-Image Generation Methods: Stable Diffusion vs Generative Adversarial Network | paper | full_text | 1 / 1 |
| AI : Diffusion Models vs GANs | web | web_snippet | 0 / 0 |
| Advancements in Generative Modeling: A Comprehensive Survey of GANs and Diffusion Models for Te | web | web_snippet | 3 / 3 |
| Comparative Analysis of Generative Models: Enhancing Image Synthesis with VAEs, GANs, and Stabl | web | web_snippet | 4 / 4 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What are diffusion models and GANs?

Sufficient: **True**; judge used: True; sources 11 (8 full text); judge candidates 30 = yes 5, partial 14, no 11, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How do diffusion models and GANs generate images from noise or latent representations? | covered | 3 | 3 |
| 2 | What are the main differences between diffusion models and GANs? | covered | 6 | 5 |
| 3 | What are the main similarities between diffusion models and GANs? | covered | 3 | 2 |

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 2 (2 by synthesis of several sources), sufficient True (strict rule: True), gap rule core, 46.8 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| What are the main differences between diffusion models and GANs? | covered | - | synthesis | synthesis | 1/3/2 | - |
| What are the main similarities between diffusion models and GANs? | covered | reselect, pool | pool | synthesis | 1/1/4 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 3 | 5 | 0 | 25.6 | digest_failed=0, sources_tried=5 |
| pool | 1 | 3 | 3 | 1 | 17.3 | parsed=3, digest_failed=0, sources_tried=3 |

### 2. What are the metrics or criteria for evaluating image generation quality and training stability?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 22 = yes 11, partial 4, no 7, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How is image quality measured in image generation evaluation? | covered | 4 | 2 |
| 2 | How is diversity measured in image generation evaluation? | covered | 5 | 3 |
| 3 | How is training stability measured in image generation models? | uncovered | 1 | 1 |
| 4 | How is convergence measured in image generation models? | covered | 3 | 2 |

Uncovered details: How are training stability and convergence measured, e.g. loss, samples per epoch, etc.?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 0 aspect(s), covered 1 (1 by synthesis of several sources), sufficient True (strict rule: False), gap rule core, 4.9 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| How is convergence measured in image generation models? | covered | - | synthesis | synthesis | 1/1/2 | - |
| How is training stability measured in image generation models? | known_gap_no_evidence | - | - | - | 1/0/5 | 1/0, 1 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|

### 3. How do diffusion models compare with GANs in terms of image generation quality?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 9, partial 6, no 3, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | advantages of diffusion models vs. GANs for image quality | covered | 6 | 6 |
| 2 | disadvantages of diffusion models vs. GANs for image quality | covered | 3 | 3 |
| 3 | How do diffusion models vs. GANs perform on different types of images, e.g. realistic, artistic, text-to-image, etc.? | covered | 5 | 5 |

Loop 2 (r1 triage, steps reselect, pool, queries): searched 0 aspect(s), covered 1 (1 by synthesis of several sources), sufficient True (strict rule: True), gap rule core, 5.6 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| How do diffusion models vs. GANs perform on different types of images, e.g. real | covered | - | synthesis | synthesis | 0/6/0 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|

### 4. How do diffusion models compare with GANs in terms of training stability?

Sufficient: **False**; judge used: True; sources 7 (5 full text); judge candidates 43 = yes 9, partial 24, no 10, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | challenges for training diffusion models vs. GANs | covered | 5 | 5 |
| 2 | solutions for training diffusion models vs. GANs | covered | 2 | 2 |
| 3 | How do diffusion models vs. GANs handle mode collapse, overconfidence, or other training issues? | covered | 7 | 6 |
| 4 | How do diffusion models vs. GANs scale with data size? | uncovered | 0 | 0 |
| 5 | How do diffusion models vs. GANs scale with model size? | uncovered | 0 | 0 |
| 6 | How do diffusion models vs. GANs scale with computational resources? | covered | 6 | 5 |

Uncovered details: How do diffusion models vs. GANs scale with data size, model size, or computational resources?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 2 (2 by synthesis of several sources), sufficient False (strict rule: False), gap rule core, 174.1 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| How do diffusion models vs. GANs scale with data size? | known_gap | reselect, pool, queries | - | - | 0/2/2 | 0/3, 3 |
| How do diffusion models vs. GANs scale with model size? | known_gap_no_evidence | - | - | - | 0/1/2 | 0/1, 1 |
| How do diffusion models vs. GANs scale with computational resources? | covered | - | synthesis | synthesis | 1/3/2 | - |
| How do diffusion models vs. GANs handle mode collapse, overconfidence, or other  | covered | - | synthesis | synthesis | 0/6/0 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 3 | 4 | 0 | 26.1 | digest_failed=0, sources_tried=5 |
| pool | 1 | 0 | 0 | 0 | 3.0 | parsed=2, digest_failed=0, sources_tried=3 |
| queries | 1 | 0 | 0 | 0 | 139.6 | queries=4, new_web_kept=3, digest_failed=0, new_web_found=18, new_papers_kept=3, new_papers_found=4, new_papers_parsed=2 |

## 5. Retrieval details

- Web search variants: [10, 10, 10, 11] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 95 candidates -> 95 cleared min_similarity (0.56) -> top 20 shortlisted; 107 candidates -> 107 cleared min_similarity (0.56) -> top 20 shortlisted; 75 candidates -> 75 cleared min_similarity (0.56) -> top 20 shortlisted; 93 candidates -> 93 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 30, 'scopus': 31, 'both': 3, 'arxiv': 1}; requests to api.openalex.org in the log: 31
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0
- Citation enrichment: Citation enrichment: 1 arXiv-only papers to enrich; took 11s in total

## 6. Parsing details

- Attempted 20 papers, usable full text 20, 62 papers saved in the database.
- PDF obtained via: -; parse cache hits: 20; Unpaywall OA links found: 0; landing-page citation_pdf_url: 0
- Individual download failures: 0 -> 
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

## 7. Groq and judge

- Stage 3: 32 digests for 4 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 112; per key (events / parked seconds): ...3mla: 21 / 1809s, ...Ef4D: 16 / 1180s, ...KJJp: 15 / 1349s, ...KaRe: 13 / 1088s, ...X2Oj: 14 / 723s, ...uNUk: 12 / 758s, ...x1nP: 21 / 1839s
- Judge batch latencies (s): [17.9, 3.8, 13.4, 5.7, 6.7, 4.2, 20.6, 4.9, 17.3, 5.5, 28.3, 5.3, 14.8, 5.7]

- Judge verdicts that came back as error: 0

## 7b. Stage 4: fact check

Claims after grouping: 100; labels {'unverified': 71, 'partially_supported': 19, 'supported': 8, 'contradicted': 2}; contradictions stored: 2; time 13m 42s.

| # | Sub-question | Digests | Claims | Clusters | Supported | Partly supported | Unverified | Contradicted |
|---|---|---|---|---|---|---|---|---|
| 1 | What are diffusion models and GANs? | 14 | 42 | 34 | 3 | 10 | 21 | 0 |
| 2 | What are the metrics or criteria for evaluating im | 8 | 25 | 19 | 2 | 1 | 15 | 1 |
| 3 | How do diffusion models compare with GANs in terms | 8 | 30 | 24 | 2 | 8 | 13 | 1 |
| 4 | How do diffusion models compare with GANs in terms | 11 | 29 | 23 | 1 | 0 | 22 | 0 |

NLI pair cap: 691 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI; 295 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI; 270 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI
- Conflict: A claims FID resolves IS's diversity issue, while B says FID (and IS) still need precision/recall to measure diversity, directly opposing the claim.
- Conflict: Both statements address realism of generated images, but one claims diffusion models are more realistic while the other claims GANs excel in realism, directly opposing each other.

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 1 | All PDF URLs failed for <id>: ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 22 | Near-match judge failed: the judge model is rate limited; not asked again for a few minutes |
| WARNING | 7 | Same-claim judge failed: the judge model is rate limited; not asked again for a few minutes |
| WARNING | 4 | Support judge failed: the judge model is rate limited; not asked again for a few minutes |
| WARNING | 3 | find_cached_parse: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 3 | Stage N: N quote/claim pairs passed the topic gate; only the N most similar go to NLI |
| WARNING | 2 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 2 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 2 | _upsert_parsed: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 2 | Stage N: the judge model is rate limited (all N Groq key(s) are rate limited for Ns); judge calls fail closed  |
| WARNING | 2 | Same-claim judge failed: all N Groq key(s) are rate limited for Ns |
| WARNING | 2 | Conflict judge failed: the judge model is rate limited; not asked again for a few minutes |
| WARNING | 1 | database read failed (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 1 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 1 | Playwright fallback failed: ValueError: ValueError('<text>') |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- Groq rate limiting: 112 parking events; digest generation took 1m 27s.
- Longest phase: Stage 4 fact check (claims, NLI, judges) (13m 42s, 58% of the run).

Warnings in the log: 54; errors: 1.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes

Third full run with `LOOP2=true` and `FACTCHECK=true`, started from the web app (live mode, plan cache on), and the **first run with the `partially_supported` label and with conflicts in the data**. Query id `498483fc-938d-4816-900f-d8b1b7d64c64`.

**Retrieval and parsing: fine.** 370 candidates -> 62 papers kept by the log (65 in the database: Loop 2 stored 3 more), 44 web sources, 20 of 20 attempted papers parsed (all from the parse cache), Semantic Scholar skipped again (probe 429). One PDF failure (a Loop 2 paper: the URL returned HTML), several `Server disconnected` database errors that the retry wrapper absorbed.

**Stage 3: 3 of 4 sub-questions sufficient, 0 judge errors, 0 digest failures.**
- Sub-question 1 (what are diffusion models and GANs): sufficient; Loop 2 searched 1 aspect and covered 2 (synthesis), 46.8 s.
- Sub-question 2 (metrics): sufficient only under the core rule. "How is training stability measured" ended `known_gap_no_evidence` (1 yes, 1 source; strict rule says not sufficient), the convergence aspect was covered by synthesis (4.9 s).
- Sub-question 3 (quality): sufficient, strict rule too; 1 aspect by synthesis (5.6 s).
- **Sub-question 4 (training stability): NOT sufficient, and Loop 2 spent 174 s on it for nothing.** Aspects 4 and 5 ("scale with data size", "scale with model size") are an aspect split that drifted away from the question (stability) into scaling. Data size: `known_gap` after all three steps (reselect +3 sources/4 findings, pool +0, queries: 4 queries, 18 web pages found, 3 kept, 4 papers found, 3 kept, 2 parsed, 0 covered; it ended with 3 partial verdicts from 3 sources, a near miss). Model size: `known_gap_no_evidence`. Loop 2 cost 3m 51s in total (16% of the run) and 34,501 Groq tokens (12%), almost all of it on this one sub-question. Compare Q5: 46 s.
- So the fixed point is the same as in Q5: when the aspect split invents aspects the literature does not answer, Loop 2 can only burn time. A rule such as "stop after the reselect and pool steps fail for an aspect that had no yes verdict at all" would have saved about 140 s here; not built.

**Groq usage:** 284,736 tokens in 294 calls, the largest run so far: `stage4_judge` 131,766 (46%), digest 112,073 (39%), digest_loop2 34,501 (12%), aspect_split 6,396. 112 rate-limit answers (per-minute limit). The Stage 4 judge share keeps growing: 8.3k tokens per sub-question in Q2, 22.6k in Q5, 33k here (the near-match judge is now part of it, about 700 tokens per call; it was not tagged separately in this run, so the split is unknown. **Fixed afterwards:** the judges now log their own purposes `stage4_merge`, `stage4_support`, `stage4_near`, `stage4_conflict`).
**Daily budget:** the project's last 24 hours are 880,244 tokens = 63% of the combined free limit, but the five busiest keys are at 73 to 74% of 200,000 each. Another full run of this size (about 40k tokens per key) would reach the daily limit on those keys; see the advice at the end.

**Stage 4: the labels have content now.** 100 claims: **8 supported, 19 partially supported, 71 unverified, 2 contradicted**, 0 contested, 2 disagreements stored. Time 13m 42s (58% of the run): 3m 25s, 1m 56s, 3m 06s and 5m 14s for the four sub-questions.
- **Supported (8): all 8 read and correct.** They are plain facts that two papers both state ("GANs suffer from training instability and mode collapse", "diffusion models generate images more slowly than GANs because they need many denoising steps", Precision/Recall definitions, and so on). 8 of 100 is more than the 1 of 100 of the earlier runs because this question is a broad comparison where surveys repeat each other.
- **Partially supported (19): about 10 of the 12 pairs I read were fair corroboration, 2 loose.** Examples of fair: "both are mainstream approaches" with "both are major categories of generative modelling"; the generator/discriminator descriptions of GANs; "Inception Score evaluates quality by low-entropy predictions" with "IS quality is low when scores are widely distributed". Loose: "Diffusion models are employed for image generation among other tasks" matched with "Diffusion models generate images by adding and removing noise". Several pairs appear twice, once from each side (A's near match is B and B's is A), so the 19 labels stand for fewer than 19 independent matches. Some pairs are near-copies ("GANs generate images by training a generator that creates visuals from latent vectors..." in two papers) that the same-claim judge did not merge; some of that is the breaker (next paragraph), the rest is the strict same-claim prompt.
- **Conflicts (2): one false, one arguable.**
  - *False:* "FID solves the diversity problem of the Inception Score" (quote: "FID on the other hand solves the diversity problem of the IS but is less suitable for fidelity") against "Precision and Recall are used to assess coverage and diversity" (quote: "Precision and Recall complement FID and IS by measuring coverage and diversity"). The second source says P&R *complement* FID; it does not say FID fails at diversity. Both can be true; the claim was labeled `contradicted`, which is wrong. The first reading said conflict and the confirming second reading also failed to reconcile them, so the double reading did not catch this one. I added the pair to the labeled conflict set (`reports/stage4_eval_set.json`, now 41 pairs, negative) so the next evaluation covers it; I did not change the prompt without being able to evaluate it (Groq budget).
  - *Arguable:* "Diffusion models generate more visually realistic images overall, while GANs achieve higher accuracy for certain conditions" (X-ray paper) against "the diffusion model is superior in stability and controllability, while GAN excels in realism" (general image generation). The two papers do disagree about which family is more realistic, but one is a medical X-ray study, so the setting differs, which the judge prompt says is not a conflict. A reader should see this as "sources disagree, with different settings", not as a refuted claim. Also note that the same second paper's sentence "diffusion ... provides higher image quality and greater stability" is one of the 8 supported claims; one paper pulls both ways.
  - Real data now shows 2 stored conflicts of which at least 1 is false: the precision of the conflict step is at best 0.5 on this run. KNOWN_LIMITS 4.12 is updated.
- **Rate-limit breaker hit in sub-question 4 (15:15:36).** All 7 keys were parked at the same moment for 124 to 171 s (the per-minute limit, not the daily one), the breaker tripped for 300 s, and 37 judge calls failed closed (35 at 15:15, 2 at 15:17): 22 near-match, 9 same-claim, 4 support, 2 conflict. They all fall into sub-question 4's Stage 4, which finished with 1 supported, **0 partially supported**, 22 unverified, so its labels are probably under-counted (sub-questions 1 and 3 have 10 and 8 partial claims, sub-question 2 only 1, so 0 is not proof of a loss, but the failures make it unknowable). Sub-questions 1 to 3 had no judge failures. Fail-closed worked as designed (nothing false was created) but the result of sub-question 4 is incomplete, and the run summary's `judgeFailures` for it is non-zero, which the frontend should show.

**What the web app should have shown (checklist for the frontend test):**
1. Stage 4 lane with 4 sub-questions; final counts 8 supported, 19 partially supported, 71 not yet confirmed, 2 contradicted.
2. Two disagreement cards (FID/P&R, realism), each with both source titles and quotes and the judge's reason; both claims in the `contradicted` group at the top.
3. Partially supported claims with the "close variant in another source" row (`nearClaim` and its quote) and no "2 sources" wording; supported claims with two sources.
4. Sub-question 4 marked as not sufficient with its known gaps (data size: `known_gap`; model size: `known_gap_no_evidence`); sub-questions 2 shown as sufficient with one known gap (`knownGapsNoEvidence`).
5. A non-zero judge-failure indication on sub-question 4's fact check.
6. Loop 2 panels: sub-question 4 with the three failed steps and their timings; coveredBy synthesis on the aspects that synthesis covered.

**Fixes made after this run:** Stage 4 judge calls are tagged per judge in the token meter; the false FID/P&R conflict is in the labeled set.
**Open:** (1) conflict precision on real data (one false in two) and the hardened prompt still unevaluated; (2) judge failures after the per-minute limit: the breaker waits 300 s and fails closed for the rest of the sub-question; a wait-and-retry for the last sub-question (or lowering `STAGE4_WORKERS`) would avoid the under-labeled result; (3) Loop 2 time on aspects with no yes verdict; (4) aspect split drifting away from the question (stability -> scaling); (5) Stage 4 token cost.
**Advice for the next run:** the hot keys are at about 74% of their daily token limit. A run of this size may hit the daily limit on those keys in Stage 3 or Stage 4. Wait for the daily window to reset or run a smaller question first.
