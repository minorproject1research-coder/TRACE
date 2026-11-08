# Report 21: where the time of a run goes, what was measured, what was built

Date 2026-11-08. Data: the three complete runs of that day with Loop 2 and Stage 4 on (runs 28, 29, 30; reports in `docs/reports/runs/`), the log `logs/pipeline.log`, and four profiling experiments on the stored data of run 30 (scratch scripts, results below). All times are from this laptop (16 cores, no GPU) with the model and the parsers on the Tailscale host and Groq on 7 free keys.

## 1. Time per phase of a full run (seconds, share of the run)
| Phase | Run 28: Q2, 5 sub-questions | Run 29: Q5, 3 sub-questions | Run 30: diffusion vs GAN, 4 sub-questions |
|---|---|---|---|
| Planner + web search (Tavily) | 11 (1%) | 14 (1%) | 14 (1%) |
| Paper search (OpenAlex, Scopus, arXiv ...) | 52 (3%) | 42 (3%) | 37 (3%) |
| Embedding pre-filter + relevance judge | 120 (7%) | 119 (9%) | 94 (7%) |
| Citation enrichment (Semantic Scholar) | 26 (1%) | 0 | 11 (1%) |
| PDF download + Docling parsing | 252 (14%) | 146 (11%) | 6 (0%, all 20 from the parse cache) |
| Stage 3 preparation (aspect split, chunks, embeddings) | 41 (2%) | 54 (4%) | 18 (1%) |
| Stage 3 digests (Groq) | 114 (6%) | 54 (4%) | 87 (6%) |
| Stage 3 judge + coverage (includes Loop 2) | 153 (9%) | 112 (8%) | 323 (23%; Loop 2 231 s) |
| **Stage 4 fact check** | **998 (56%)** | **835 (61%)** | **822 (58%)** |
| Total | 1,770 | 1,377 | 1,413 |

Stage 4 is more than half of every run. The next items are Loop 2 when it searches the web (up to 231 s), parsing when the papers are not cached (146 to 252 s), and the retrieval filter (about 2 min).

## 2. Inside Stage 4 (profile of run 30, judges cached so only the CPU shows)
| Step (per sub-question) | Seconds | What it is |
|---|---|---|
| claims, clusters | 2 | embeddings; merge judgements were cached in this profile |
| support (NLI on the quotes Stage 3 did not already accept) | 19 to 38 | DeBERTa-large on the CPU |
| near matches | 0.1 (cached) | judge calls in a real run |
| conflicts (NLI on the 80 most similar pairs) | 72 to 103 (1.0 to 1.2 s per pair) | DeBERTa-large on the CPU |

So the NLI model needs about 100 to 140 s per sub-question, i.e. about 6.4 of the 13.7 minutes of run 30. The rest is Groq judge calls (merge, near match, support, conflict) and the waiting on the per-minute token limit; sub-question 4 of run 30 alone took 5m 14s because the breaker tripped.

## 3. Experiments on how to make the NLI step faster (run 30 data, 4 x 80 pairs)
| Idea | Result | Verdict |
|---|---|---|
| int8 dynamic quantization of the large model | same probabilities (0.99 / 0.99, 0.75 / 0.75 ...), but 90 to 109 s instead of 72 to 85 s per 80 pairs | **slower** on this CPU: rejected |
| DeBERTa-base as a prefilter (2.9x faster: 25 to 29 s) | of the 15 pairs the large model flags (contradiction >= 0.7), base keeps only 7 at a threshold of 0.5 and 4 at 0.7; the pairs the conflict judge's first reading later called conflicts got 0.14, 0.17 and 0.00 | **loses real conflicts**: rejected |
| `STAGE4_MAX_PAIRS` 80 -> 40 | the first-reading conflicts of this run sit at ranks 17, 30 and 41 of the 80; positives reach rank 67 | would drop the rank-41 one: rejected |
| Cache the NLI answers on disk | built (`NLI_CACHE`, default on, `.cache/nli`) | see section 4 |

Nothing quality-neutral makes the first NLI computation faster on this CPU. The remaining routes are hardware (a GPU, or NLI on the host) and overlapping the NLI with other work.

## 4. Built in this round
| Change | Effect |
|---|---|
| **NLI answers cached on disk** (`apps/api/agents/stage4_factcheck/common.py`; the model is deterministic) | measured: Stage 4 of run 30 sub-question 1 on the same claims: **124 s -> 2 s**, identical labels (3 supported, 10 partially supported, 21 unverified). A repeated test question (a rerun from the web app, `stage4_on_stored.py`) no longer pays the 6 minutes of NLI. First runs are not faster. |
| **Judge calls wait out a short Groq limit** (`STAGE4_RATE_WAIT_MAX` 300 s, `STAGE4_RATE_RETRIES` 2) instead of failing closed | fixes the 37 lost judge answers of run 30; costs wall time only when all 7 keys are parked (it waits the 124 to 171 s seen) |
| Per-judge token tags (`stage4_merge`, `stage4_support`, `stage4_near`, `stage4_conflict`) | the next run shows which judge costs what |
| **Parallel work, built by four helpers on 2026-11-08, none of it timed in a full run yet** | |
| near-match judge beside the conflict NLI in one sub-question (`STAGE4_PARALLEL_STEPS`, default on) and the NLI model preloaded at the start of the run | expected: the Groq-bound near step hides behind the CPU-bound NLI step |
| Stage 4 of a sub-question starts when Stage 3 has stored it (`STAGE4_OVERLAP`, default on, one background worker) and the Stage 3 preparation per sub-question runs in parallel (`STAGE3_PREP_WORKERS` 4) | expected: part of Stage 3's judge/Loop 2 time (1.9 to 5.4 min) is hidden behind Stage 4 |
| relevance filter for several sub-questions at once (`RELEVANCE_WORKERS`, default 2; 4 would mean 32 judge requests at once, not tested) | expected 30 to 45 s |
| judge batches in parallel (`JUDGE_PARALLEL`, default 2; measured on the host: 2 concurrent 8-item batches took 8.0 s wall against about 18 s one after another, 3 took 11.9 s against about 27 s, same verdicts, no 429; 32-item batches not measured) | expected 30 to 70 s |

## 5. Not built, with the numbers
| Idea | Expected saving per run | Risk / why not yet |
|---|---|---|
| **Start Stage 4 of a sub-question as soon as Stage 3 stored it** (overlap CPU NLI with the host judge and Loop 2) | 2 to 5 minutes (Stage 3 judge + coverage is 1.9 to 5.4 min) | digests and coverage are written for all sub-questions at the end of Stage 3, so the write must move per sub-question; more Groq calls at the same time (Loop 2 digests and Stage 4 judges) make the per-minute limit worse. A real change of the graph: needs a run to verify |
| **NLI on a GPU** (the host, if it has room: DeBERTa-large needs about 1 to 2 GB in half precision) | about 6 minutes (the NLI share) | needs a small endpoint on the host; not known whether the host CPU alone would be faster than this laptop |
| **Loop 2 without the `queries` step** (`LOOP2_STEPS=reselect,pool`) | 100 to 224 s per time the step runs (9 times in the logs; 140 s in run 30 for an aspect that stayed a gap) | it covered 4 of the 14 aspects that reached it (29%); the earlier measurement (report 18) gave 5 of 8 covered aspects at 17% of the time without it |
| A rule "skip `queries` for aspects with no yes verdict" | would have saved the 140 s of run 30 | **refuted by the data**: of 14 aspects that reached the queries step, the 4 that it covered had 0, 0, 0 and 1 yes verdicts before it; the rule would have blocked 3 of the 4 successes. Not built |
| Relevance filter for the sub-questions in parallel (now one after the other: about 17 s embeddings + 11 s host judge each) | 30 to 45 s | the embedding is CPU-bound, so only the judge wait overlaps |
| **Judge batches of Stage 3 in parallel** (was sequential, 5 to 28 s each, 14 batches in run 30) | 30 to 70 s | **built, `JUDGE_PARALLEL` (default 2; 1 = old behaviour).** Measured on the host with 8-item batches (12 requests): alone 9.4 s and 8.6 s; two at once 8.0 s wall; three at once 11.9 s wall (sequential would be about 27 s). Final verdicts identical in all 8 items of each compared batch; the free-text `reason` differs slightly even between two identical single requests. Not measured with full 32-item batches; a full run has not been timed |
| Citation enrichment: stop after the first batch that gives up | 26 to 68 s on days when Semantic Scholar answers 429 | small; also loses the counts for the papers of the later batches |
| Parsing 146 to 252 s when papers are new | not reducible here | Docling runs on the host; repeat questions already hit the parse cache |

## 6. What a repeated test run (a "try") costs now
Cached between runs: the plan (`PLAN_CACHE`), the parse of every paper, chunk embeddings, aspect splits, Stage 3 digests, Stage 3 judge verdicts, all Stage 4 judge answers and now the NLI answers. Not cached: the live searches (papers, web), the relevance filter, and Loop 2's searches. So a repeat of the same question should now spend its time on retrieval + filter (about 3 min), Stage 3 judge/Loop 2 (1 to 4 min) and a few minutes of Groq in Stage 4 instead of 14 minutes. This has been measured for Stage 4 only (section 4); a full repeat run has not been timed.
