# Pipeline run report - How do diffusion models compare with GANs for image generation quality and training stability?

Generated 2026-11-07 11:52 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 16 in the file) and the database. Query id `7d7d1b7e-3c59-4ec6-a076-39c815d4f298`.

## 1. Summary

| | |
|---|---|
| Question | How do diffusion models compare with GANs for image generation quality and training stability? |
| Domain anchor | (cached): 'generative modeling' | context: Computer vision/generative AI: diffusion models refer to generative neural networks, not physical diffusion phenomena. |
| Started / finished | 2026-11-07 11:35:36 / 11:50:47 |
| **Total execution time** | **15m 11s** (911 s) |
| Sub-questions / search queries | 4 / 11 (per sub-question [3, 2, 3, 3]) |
| Plan source | planner |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 366 candidates -> 366 cleared the similarity floor -> 80 shortlisted |
| **Papers kept after the relevance judge** | **60** (log: 60); 20 shortlisted papers rejected |
| **Web sources** | **42** (per sub-question [11, 10, 11, 10]) |
| Papers attempted for parsing | 21 (top-N per sub-question) |
| **Papers parsed to usable full text** | **20** of 21 attempted (7 from the parse cache) |
| Papers not parsed (all routes failed) | 0 download/route failures + 1 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 4 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 31 (20 from full text, 0 from abstracts, 11 from web snippets) |
| Findings (verified / total) | 96 / 111 |
| Coverage sufficient | 2 of 4 sub-questions |
| Judge | 1m 18s in 4 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 61 parking events, 1026 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 4 sub-questions) | 11:35:36 | 11:36:05 | 29s | 3% |
| Web search (Tavily) | 11:36:05 | 11:36:16 | 11s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 11:36:16 | 11:36:51 | 34s | 4% |
| Embedding pre-filter + relevance judge | 11:36:51 | 11:38:12 | 1m 22s | 9% |
| Citation enrichment (Semantic Scholar) | 11:38:13 | 11:39:21 | 1m 08s | 7% |
| Store papers in the database | 11:39:21 | 11:39:22 | 1s | 0% |
| PDF download + Docling parsing | 11:39:22 | 11:42:11 | 2m 50s | 19% |
| Stage 3 preparation (aspect split, chunking, embedding) | 11:42:11 | 11:47:35 | 5m 24s | 36% |
| Stage 3 digest generation (Groq) | 11:47:35 | 11:48:49 | 1m 14s | 8% |
| Stage 3 judge + coverage (per sub-question) | 11:48:49 | 11:50:18 | 1m 28s | 10% |
| **Total** | 11:35:36 | 11:50:47 | **15m 11s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What are diffusion models and GANs? | 94 -> 94 -> 20 | 16 of 20 | 5 | 11 | 8 (5 / 0 / 3) | 24 / 30 | sufficient |
| 2 | What are the metrics or criteria for evaluating image generation quality and training stability? | 105 -> 105 -> 20 | 14 of 20 | 5 | 10 | 8 (5 / 0 / 3) | 28 / 30 | sufficient |
| 3 | How do diffusion models compare with GANs in terms of image generation quality? | 74 -> 74 -> 20 | 18 of 20 | 5 | 11 | 8 (5 / 0 / 3) | 26 / 30 | NOT sufficient |
| 4 | How do diffusion models compare with GANs in terms of training stability? | 93 -> 93 -> 20 | 12 of 20 | 5 | 10 | 7 (5 / 0 / 2) | 18 / 21 | NOT sufficient |

- Relevance judge rejected 4 papers for [What are diffusion models and GANs?]. Examples: 'Generative adversarial networks and diffusion models in mate' (The paper compares performance in a specific application rather than defining or explaining what diffusion models and GANs are.); 'Diffusion-GAN: Training GANs with Diffusion' (The paper focuses on a specific GAN training method using diffusion noise rather than explaining what diffusion models and GANs are.); 'Unifying Diffusion Models' (The paper focuses on advanced latent space formulations and specific applications like CycleDiffusion rather than providing a foundational d)
- Relevance judge rejected 6 papers for [What are the metrics or criteria for eva]. Examples: 'Creating Realities: An In-Depth Study of AI-Driven Image Gen' (The paper focuses on Generative Adversarial Networks (GANs) rather than diffusion models, which are explicitly required by the research ques); 'Comparative Analysis of GANs and Diffusion Models in Image G' (The paper discusses general challenges like training instability but does not provide specific metrics or criteria for evaluating quality or); 'Quality Prediction on Deep Generative Images' (The paper focuses on GANs and image quality assessment, not diffusion models or training stability metrics.)
- Relevance judge rejected 10 papers for [How do diffusion models compare with GAN]. Examples: 'A STUDY ON SAMPLE DIVERSITY IN GENERATIVE MODELS: GANS VS. D' (The paper focuses on sample diversity and mode collapse rather than comparing overall image generation quality.); 'Hybrid Diffusion Models for Scalable and High-Quality Medica' (The paper evaluates a hybrid model combining both techniques rather than providing a direct comparison between standalone diffusion models a); 'Comparative Analysis of Generative Models: Enhancing Image S' (The paper discusses computational resources and application selection but does not compare training stability between diffusion models and G)

### Sources behind each sub-question's digests

**1. What are diffusion models and GANs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 5 / 5 |
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | paper | full_text | 4 / 5 |
| Comparative Analysis of GANs and Diffusion Models in Image Generation | paper | full_text | 2 / 5 |
| Deep Generative Models for Image Synthesis: GANs, VAEs, and Diffusion Approaches | paper | full_text | 3 / 5 |
| Unifying GANs and Score-Based Diffusion as Generative Particle Models | paper | full_text | 4 / 4 |
| Comparative Analysis of Generative Models: Enhancing Image Synthesis with VAEs, GANs, and Stabl | web | web_snippet | 1 / 1 |
| Diffusion Models versus Generative Adversarial Networks (GANs) / AI Image Generation Models | web | web_snippet | 2 / 2 |
| Image Generation Models: A Technical History | web | web_snippet | 3 / 3 |

**2. What are the metrics or criteria for evaluating image generation quality and training stability?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | paper | full_text | 4 / 4 |
| A note on the evaluation of generative models | paper | full_text | 4 / 4 |
| Evaluation Metrics for Conditional Image Generation | paper | full_text | 4 / 4 |
| Improved Precision and Recall Metric for Assessing Generative Models | paper | full_text | 4 / 4 |
| Reliable Fidelity and Diversity Metrics for Generative Models | paper | full_text | 3 / 5 |
| A Review of the Image Quality Metrics used in Image Generative Models | web | web_snippet | 3 / 3 |
| Evaluation metrics for generative image models | web | web_snippet | 3 / 3 |
| How to Evaluate Generative Image Models | web | web_snippet | 3 / 3 |

**3. How do diffusion models compare with GANs in terms of image generation quality?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 4 / 5 |
| Beware of diffusion models for synthesizing medical images—a comparison with GANs in terms of m | paper | full_text | 4 / 5 |
| Comparative Analysis of GANs and Diffusion Models in Image Generation | paper | full_text | 3 / 5 |
| Deep Generative Models for Image Synthesis: GANs, VAEs, and Diffusion Approaches | paper | full_text | 5 / 5 |
| Evaluating Text-to-Image Generation Methods: Stable Diffusion vs Generative Adversarial Network | paper | full_text | 2 / 2 |
| Comparative Analysis of Generative Models: Enhancing Image Synthesis with VAEs, GANs, and Stabl | web | web_snippet | 4 / 4 |
| Perceptual Evaluation of GANs and Diffusion Models for Generating X-rays | web | web_snippet | 3 / 3 |
| Synthetic Scientific Image Generation with VAE, GAN, and Diffusion Model Architectures | web | web_snippet | 1 / 1 |

**4. How do diffusion models compare with GANs in terms of training stability?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparative Analysis Between GAN and Diffusion Models in Image Generation | paper | full_text | 5 / 5 |
| A Survey on Generative Models for Image Synthesis: GANs, Diffusion Models, and Beyond | paper | full_text | 3 / 4 |
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | paper | full_text | 2 / 3 |
| Diffusion-GAN: Training GANs with Diffusion | paper | full_text | 4 / 5 |
| Evaluating Text-to-Image Generation Methods: Stable Diffusion vs Generative Adversarial Network | paper | full_text | 1 / 1 |
| Comparative Analysis of Generative Models: Enhancing Image Synthesis with VAEs, GANs, and Stabl | web | web_snippet | 3 / 3 |
| Diffusion Transformer vs GAN: Which Generates Better Images? / newline | web | web_snippet | 0 / 0 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What are diffusion models and GANs?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 9, partial 7, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How do diffusion models and GANs generate images from noise or latent representations? | covered | 3 | 3 |
| 2 | differences between diffusion models and GANs | covered | 4 | 4 |
| 3 | similarities between diffusion models and GANs | covered | 2 | 2 |

### 2. What are the metrics or criteria for evaluating image generation quality and training stability?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 19 = yes 12, partial 5, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How is image quality measured in image generation evaluation? | covered | 5 | 5 |
| 2 | How is diversity measured in image generation evaluation? | covered | 3 | 3 |
| 3 | How is training stability measured in image generation models? | covered | 2 | 2 |
| 4 | How is convergence measured in image generation models? | covered | 2 | 2 |

### 3. How do diffusion models compare with GANs in terms of image generation quality?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 7, partial 7, no 4, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | advantages of diffusion models vs. GANs for image quality | covered | 5 | 4 |
| 2 | disadvantages of diffusion models vs. GANs for image quality | covered | 2 | 2 |
| 3 | How do diffusion models vs. GANs perform on different types of images, e.g. realistic, artistic, text-to-image, etc.? | uncovered | 0 | 0 |

Uncovered details: How do diffusion models vs. GANs perform on different types of images, e.g. realistic, artistic, text-to-image, etc.?

### 4. How do diffusion models compare with GANs in terms of training stability?

Sufficient: **False**; judge used: True; sources 6 (5 full text); judge candidates 26 = yes 6, partial 9, no 11, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the challenges for training diffusion models vs. GANs? | covered | 4 | 3 |
| 2 | What are the solutions for training diffusion models vs. GANs? | uncovered | 0 | 0 |
| 3 | How do diffusion models vs. GANs handle mode collapse, overconfidence, or other training issues? | covered | 2 | 2 |
| 4 | How do diffusion models vs. GANs scale with data size? | uncovered | 0 | 0 |
| 5 | How do diffusion models vs. GANs scale with model size? | uncovered | 0 | 0 |
| 6 | How do diffusion models vs. GANs scale with computational resources? | uncovered | 0 | 0 |

Uncovered details: What are the challenges and solutions for training diffusion models vs. GANs?; How do diffusion models vs. GANs scale with data size, model size, or computational resources?

## 5. Retrieval details

- Web search variants: [11, 10, 11, 10] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 94 candidates -> 94 cleared min_similarity (0.56) -> top 20 shortlisted; 105 candidates -> 105 cleared min_similarity (0.56) -> top 20 shortlisted; 74 candidates -> 74 cleared min_similarity (0.56) -> top 20 shortlisted; 93 candidates -> 93 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'scopus': 27, 'openalex': 29, 'both': 3, 'arxiv': 1}; requests to api.openalex.org in the log: 24
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 3
- Citation enrichment: Citation enrichment: 1 arXiv-only papers to enrich; took 1m 08s in total

## 6. Parsing details

- Attempted 21 papers, usable full text 20, 60 papers saved in the database.
- PDF obtained via: its own link: 11, the same paper on arXiv: 1, the OpenAlex content API: 1; parse cache hits: 7; Unpaywall OA links found: 1; landing-page citation_pdf_url: 0
- Individual download failures: 4 -> ValueError: 2, HTTPStatusError: 2
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review | parse/database error: <ConnectionTerminated error_code:9, last_stream_id:17, additional_data:None> |

## 7. Groq and judge

- Stage 3: 31 digests for 4 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 61; per key (events / parked seconds): ...3mla: 9 / 133s, ...Ef4D: 5 / 95s, ...KJJp: 13 / 168s, ...KaRe: 8 / 155s, ...X2Oj: 13 / 219s, ...uNUk: 5 / 116s, ...x1nP: 8 / 140s
- Judge batch latencies (s): [18.8, 17.9, 17.5, 24.1]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 1 | Failed to parse paper <id>: <ConnectionTerminated error_code:N, last_stream_id:N, additional_data:None> |
| WARNING | 3 | SN rate limited on batch, backing off Ns |
| WARNING | 2 | Parse cache lookup failed for <id>: RemoteProtocolError: Server disconnected |
| WARNING | 2 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 2 | Failed to download from <url> HTTPStatusError: HTTPStatusError('<text>') |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | Unpaywall route failed for '<text>': ConnectError: All connection attempts failed |
| WARNING | 1 | Parse cache lookup failed for <id>: RemoteProtocolError: <ConnectionTerminated error_code:N, last_stream_id:N, |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429) and citation enrichment still spent 1m 08s on 3 rate-limited batch calls.
- 1 paper(s) failed at the parse/database step: Artificial-Intelligence-Generated Content with Dif (<ConnectionTerminated error_code:9, last_stream_id:17, additional_data:None>)
- Groq rate limiting: 61 parking events; digest generation took 1m 14s.
- Longest phase: Stage 3 preparation (aspect split, chunking, embedding) (5m 24s, 36% of the run).

Warnings in the log: 13; errors: 1.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand after reading the log and the database)

**Bottom line.** A clean run on a non-NLP topic (15m 11s, no judge error, no digest failure) and the first one where the **core aspects of the question are covered while the sub-questions still fail**: 2 of 4 sub-questions sufficient. The planner split the question properly (what the two models are, how quality and stability are measured, the quality comparison, the stability comparison) and the evidence for the comparisons exists (quality: "advantages of diffusion models versus GANs" 5 yes from 4 sources, "disadvantages" 2 from 2; stability: "challenges of training" 4 from 3, "mode collapse and other training issues" 2 from 2). What fails are the dimensions the planner added next to them: "performance on different types of images", "solutions for training" and **three scaling aspects** (data size, model size, compute) that nobody asked about. So the Stage 3 test question about a non-NLP domain gives a clear answer: nothing in the pipeline is tuned to LLM wording; the anchor, retrieval, digests and judge behave the same on image generation. This is the opposite pattern to Q3 and Q4, where the aspects that are the question failed.

### Numbers

| | |
|---|---|
| Plan | 4 sub-questions, 11 queries [3, 2, 3, 3], fresh plan (29 s), anchor 'generative modeling' ("diffusion models refer to generative neural networks, not physical diffusion phenomena") |
| Retrieval | 366 candidates, 80 shortlisted, **60 kept** (OpenAlex 29, Scopus 27, both 3, arXiv 1), 42 web sources; judge passed 16, 14, 18 and 12 of 20 |
| Parsing | 20 of 21 usable (7 from the parse cache, 11 own link, 1 arXiv twin, 1 OpenAlex content API); 2m 50s; 4 download failures recovered by other routes; **1 on-topic survey lost to a database error** (below) |
| Stage 3 | 31 digests (20 full text, 11 web) in 1m 14s on 7 keys; 111 findings, 96 verified (86%); 81 judge pairs (18 + 19 + 18 + 26), 0 errors |
| Groq | 61 parking events, 1026 key-seconds (longest single park 37 s) |
| Coverage | aspects covered 11 of 16: sub-question 1: 3 of 3; 2: 4 of 4; 3: 2 of 3; 4: 2 of 6 |

### The two sub-questions that fail, aspect by aspect

| Sub-question | Aspect | Verdicts | Reading |
|---|---|---|---|
| Quality | advantages of diffusion models vs. GANs for image quality | 5 yes, 1 partial | covered |
| Quality | disadvantages of diffusion models vs. GANs for image quality | 2 yes, 4 no | covered, barely |
| Quality | performance on different types of images (realistic, artistic, text-to-image) | 6 partial, 0 yes | near miss: the evidence is on topic but each claim names one image type |
| Stability | challenges of training diffusion models vs. GANs | 4 yes, 1 no, 1 partial | covered |
| Stability | solutions for training | 4 no, 2 partial | not covered; the claims describe the models, not remedies |
| Stability | mode collapse, overconfidence, other training issues | 2 yes, 4 partial | covered |
| Stability | scaling with data size / model size / computational resources | data 2 no; model 2 no; compute 2 partial and 2 no | planner invention: only 2 to 4 candidates each, none answers it |

The three scaling aspects come from one detail question ("scale with data size, model size, or computational resources") that the splitter turned into three aspects; they have nothing to do with training STABILITY, which is what the sub-question is about. They are the second clear example of limit 1.8 (after Q3's diversity, security and interoperability): 4 of the 6 aspects of this sub-question have no answer in the literature that was read, so it cannot be sufficient however good the retrieval is.

### Observations for the Stage 3 plan (one run each, to be tested)
- **Aspect wording seems to decide whether the judge says "yes".** Comparison aspects worded as "advantages of X vs. Y" got 5 yes from single claims such as a better FID for diffusion models. In Q3 the broad "how does X affect Y" aspects got "partial" for the same kind of specific result, and in Q4 the "existing benchmarks / metrics" list aspects got "partial" because each claim names one item. The aspects a claim can answer ON ITS OWN are covered; the ones that need several claims are not. This supports planned item B1 (remedies by aspect type) but is three runs, not a test.
- **Near miss versus unanswerable (planned item A1), first data from this run:** "types of images" (6 partial, 0 no) is a near miss and the scaling aspects (2 to 4 candidates, mostly no) are not, which fits the idea. But "solutions for training" (4 no, 2 partial) and "computational resources" (2 partial, 2 no) have partial verdicts too, so a simple "at least 2 partial" rule would send them to Loop 2. The rule needs a better test than this; the stored runs of Q1 to Q6 are the data for it.
- No paper was digested twice (31 digests from 31 different sources), although 60 paper rows hold only 37 different titles: the same paper is kept under several sub-questions but the top five of each sub-question were different. Known limit 3.9 did not bite here.

### What went wrong
1. **A relevant survey was lost to a database error again.** "Artificial-Intelligence-Generated Content with Diffusion Models: A Literature Review" failed at the parse/store step with `ConnectionTerminated error_code:9`, and two parse-cache lookups failed with `RemoteProtocolError: Server disconnected`. In the whole log file there are 10 "Failed to parse paper" lines (6 "Server disconnected", 2 SSL EOF, 1 ConnectionTerminated, 1 old unicode error) and 9 failed parse-cache lookups; since the API went live the pipeline has lost on-topic papers this way in the first MoE API run (1), Q4 (2) and now Q5 (1). The planned retry of the pipeline's own database calls (B8) is now the item with the most repeated evidence.
2. **Stage 3 preparation took 5m 24s (36%)** for 20 full-text papers; Q3 needed 1m 55s for 15, Q4 9m 22s for 20, the MoE repeat 4m 02s for 25. The same amount of work has taken between 2 and 9 minutes. The chunk-embedding cache (B5) would remove the cost, and the spread suggests it depends on what else the machine is doing.
3. **Citation enrichment spent 1m 08s on one arXiv-only paper** (three rate-limited Semantic Scholar batches; by decision it is not tied to the search breaker).
4. **Verified share 86%**, lower than Q3 (94%) and Q4 (92%): the lowest digest is the stability sub-question (18 of 21). Not investigated.

### What worked
- A non-NLP topic: the anchor kept physical diffusion out, the relevance judge rejected the mismatches ("a study on sample diversity ...", application-specific comparisons), and the shortlists were on topic.
- All four sub-questions are on topic: no background-only sub-question and no drift to a question that was not asked (compare Q2 and Q4).
- 7 Groq keys: digests 1m 14s, 61 parking events.
- The judge accepted specific comparison results for comparison-style aspects (above).

### Tooling
- **A bug in the report script made the first version of this report wrong.** The log names a sub-question by its first 40 characters, and the quality and stability sub-questions begin alike, so their pre-filter and judge figures overwrote each other (the first version said "60 kept (log: 42)", "60 shortlisted" and wrong figures for sub-question 3). The script now matches the log lines to the sub-questions by order. The Q4 report was regenerated with the same result (no sub-question names collide there); reports of other runs whose sub-questions start alike (the 14:00 Mamba run, for example) may carry the same error and can be regenerated to check.
- The sub-questions in the report are now listed in plan order.

### At a glance: the five questions (latest complete run of each)

| | Q1 Mamba (17:33) | Q2 MoE (23:29) | Q3 quantization | Q4 benchmarks | Q5 diffusion vs GANs |
|---|---|---|---|---|---|
| Total time | 15m 14s | 16m 04s | 17m 46s | 19m 44s | 15m 11s |
| Papers kept / usable full text | 48 / 25 of 26 | 73 / 25 of 28 | 46 / 15 of 16 | 61 / 20 of 22 | 60 / 20 of 21 |
| Findings verified | 81% | 89% | 94% | 92% | 86% |
| Sub-questions sufficient | 2 of 5 | 3 of 5 | 1 of 3 | 0 of 4 | 2 of 4 |
| Where it fails | transformers (parameters, limitations), trained and evaluated, transformer challenges in the comparison | one challenges and one scalability aspect | the core question: 8 aspects, 2 yes in 30 pairs | the list aspects (benchmarks, metrics) and an off-question sub-question | peripheral aspects (image types, solutions, scaling x3) |

### Next checks
- [ ] Run Q6, then do planned items A1 and B1 on the stored runs of all six questions (verdict statistics by aspect type; label the pairs).
- [ ] B8: retry the pipeline's database calls (four on-topic papers lost in three runs).
- [ ] B5: chunk-embedding cache.

(To regenerate the tables above after another run: `python scripts/pipeline_run_report.py --run N`; these notes are kept.)
