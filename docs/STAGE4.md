# Stage 4: fact checking across sources

Stage 4 reads what Stage 3 collected (verified findings with quotes) and asks one question: **does more than one source say it, and does any source say the opposite?** It does not decide what is true. It labels each claim by how much independent evidence stands behind it.

Related files: the contract for readers of the results is `docs/STAGE4_OUTPUT.md`; the API fields are in `docs/API_HANDOFF.md`; the measurements and the history are in `docs/reports/20_stage4.md` and the run reports in `docs/reports/runs/`; open problems are the rows 4.x of `docs/KNOWN_LIMITS.md`. The original design (code of 2026-11-01) is `docs/reports/TRACE Stage 4 Fact Checking, Handoff Report.md`.

## 1. Where it sits
planner -> retrieval -> Stage 3 (digests, judge, Loop 2) -> **Stage 4** -> Stage 5 (not built).
It runs once per sub-question, only when `FACTCHECK=true`, and with `STAGE4_OVERLAP` (default) a sub-question is checked while Stage 3 is still busy with the next ones (section 11). It never fails a run: a sub-question that raises an error is reported as `{"error": ...}` in the summary and skipped; the Stage 3 evidence is already stored.

## 2. Steps for one sub-question (`apps/api/graph/nodes/factcheck_node.py`)
| # | Step | Code | What happens | Model |
|---|---|---|---|---|
| 1 | claims | `fact_checker.load_claims` | Takes the digests of the newest Stage 3 run (all rows, including Loop 2 rows). Keeps findings whose quote was found in the source, that are grounded, and have a claim and a quote. The same statement of the same source counts once. Each claim gets a weight = source reliability x evidence level (full text 1.0, abstract or web snippet 0.5). | none |
| 2 | clusters | `fact_checker.build_clusters` | Greedy grouping of claims that state the same thing: embedding candidates (cosine >= 0.84, at most 3 per claim), the **same-claim judge** decides (cosine >= 0.98 merges without it; a claim is never merged with its own document). | embeddings, Groq judge |
| 3 | support | `fact_checker.verify_support` | A member counts as support when its own quote supports its own claim. Order: Stage 3's judge already said yes (free) -> NLI entailment >= 0.5 -> otherwise the **support judge** (confidence >= 0.70). | NLI (CPU), Groq judge |
| 4 | near matches | `fact_checker.find_near_matches` | For a claim that rests on ONE document: the most similar claim of another document (cosine >= 0.70) that has a supporting quote is shown to the **near-match judge**. A yes makes the claim `partially_supported`. Switch: `STAGE4_NEAR`. | embeddings, Groq judge |
| 5 | conflicts | `contradiction_detector.detect` | Quotes of other documents against each claim: topic gate (cosine >= 0.70), NLI contradiction >= 0.7 as a cheap prefilter (at most `STAGE4_MAX_PAIRS` = 80 pairs), then the **conflict judge** and a confirming second reading. A conflict needs both. | NLI (CPU), Groq judge |
| 6 | labels | `fact_checker.label_clusters` | See section 3. A claim with no supporting quote is dropped (claim drift). | none |
| 7 | store | `db_service.write_fact_claims`, `write_contradictions` | Both tables are rewritten as a whole for the run. | none |

## 3. Labels
Checked in this order:
1. `contradicted`: another document asserts the opposite and that conflict is at least as strong as the support.
2. `supported`: at least 2 distinct documents state the claim with a supporting quote, and their evidence weight is >= 1.5. (If a weaker conflict exists the claim is still `supported` with `contested = true`.)
3. `partially_supported`: ONE supporting document, plus a close variant of the claim in another document (same subject and property, same direction, not the same sentence). The last evidence row is that document's quote with `relation = near_match` and `near_claim` (its own wording). Confidence is at most 0.6.
4. `unverified`: everything else (one document, or too little weight). Confidence is at most 0.5. It says nothing about whether the claim is false.

"Distinct documents" uses the normalised title, so a paper found both as a paper and as a web page counts once.

## 4. The four judges (all in `apps/api/agents/stage4_factcheck/judge.py`)
Every judge **fails closed**: any error means "no conflict", "does not support", "not the same", "not near". A failed Groq call can therefore never create a conflict, a support, a merge or a near match.
| Judge | Question | Notes |
|---|---|---|
| same claim (`SAME_PROMPT`) | do two claims make the same specific assertion? | no if one has a mechanism, number, condition or scope the other lacks |
| support (`SUPPORT_PROMPT`) | does the quote support the claim? | no if the claim adds a fact the quote lacks; ignores formatting noise |
| conflict (`PROMPT` + `CONFIRM_PROMPT`) | could both statements be true together? | hedges ("can", "may"), aims versus results, different models, datasets or settings are not conflicts; a conflict needs the first reading to say yes and a second reading that tries to reconcile them (using only words that are really in the texts) to fail. On 41 labeled pairs: precision 0.71, recall 0.56 |
| near match (`NEAR_PROMPT`) | does source 2 make the main point of claim 1, more generally or more specifically? | the judge must first write the shared point in a sentence; "none" or an empty point turns a yes into a no |

Infrastructure: all judge answers are cached on disk (`.cache/stage4_judge`, a failure is never cached), so rerunning Stage 4 on the same claims costs no Groq tokens and gives the same labels; judge calls run side by side (`STAGE4_WORKERS`, default 4) with results in input order; after a "rate limited for good" answer the judge is not asked again for 5 minutes (the circuit breaker); every cap logs a warning when it bites.

## 5. Settings (`.env`, defaults in `.env.example`)
| Setting | Default | Meaning |
|---|---|---|
| `FACTCHECK` | false | switch for the whole stage |
| `STAGE4_WORKERS` | 4 | judge calls in parallel |
| `STAGE4_SQ_WORKERS` | 1 | how many sub-questions Stage 4 checks at the same time when it overlaps Stage 3 (not the judge threads, that is `STAGE4_WORKERS`). 2 shortens the queue; see section 11 |
| `STAGE4_OVERLAP` | true | (with `FACTCHECK=true`) Stage 4 of a sub-question starts as soon as Stage 3 has stored its digests and coverage, on one background worker, while Stage 3 judges the next sub-question; `false` = Stage 4 starts after the whole of Stage 3 (the old behaviour). See section 11 |
| `STAGE4_CACHE`, `STAGE4_CACHE_DIR` | true, `.cache/stage4_judge` | judge answer cache |
| `STAGE4_MAX_MERGE_JUDGE` / `STAGE4_MAX_SUPPORT_JUDGE` / `STAGE4_MAX_JUDGE` / `STAGE4_MAX_PAIRS` | 300 / 150 / 40 / 80 | caps per sub-question |
| `STAGE4_PARALLEL_STEPS` | true | inside one sub-question the near-match judge (Groq) runs while the conflict NLI (CPU) computes; they read the same clusters and write different fields. The NLI model is also loaded in the background at the start of a run that has Stage 4 on |
| `STAGE4_NEAR` | true | the `partially_supported` label |
| `STAGE4_NEAR_MIN_SIM`, `STAGE4_NEAR_CANDIDATES`, `STAGE4_MAX_NEAR_JUDGE` | 0.70, 1, 120 | near-match candidates and cap |
| `STAGE4_RATE_WAIT_MAX`, `STAGE4_RATE_RETRIES` | 300, 2 | when every Groq key is parked for at most this many seconds (the per-minute limit; seen 124 to 171 s) a judge call waits and asks again, up to this many times, instead of failing closed; a longer limit (a daily one) opens the 5-minute breaker at once |
| `NLI_CACHE`, `NLI_CACHE_DIR` | true, `.cache/nli` | NLI answers are cached on disk (the model is deterministic): a rerun on the same quotes and claims costs no CPU. Measured: 124 s -> 2 s for one sub-question |
| `NLI_MODEL` | `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli` | NLI model (1.7 GB, downloaded on first use) |

## 6. Output
Tables `fact_claims` (one row per checked claim) and `contradictions` (one row per disagreeing pair); the API report fields `factCheck` per sub-question, `totals.factChecked` and `stages.factcheck`; the progress lane `factcheck` (steps claims, clusters, support, near, conflicts, store); the run summary `fact_summary`. Exact fields: `docs/STAGE4_OUTPUT.md`.

## 7. What it costs (measured, full run of Q2, 2026-11-08, run 28)
- **Time:** 16m 38s of a 29m 30s run (56%). The machine has no GPU, so the NLI model runs on the CPU at about 1.2 to 1.7 s per pair.
- **Groq tokens:** the `stage4_judge` purpose used 41,432 of the run's 186,317 tokens (22%) before the near-match judge existed. Later runs: 67,745 of 175,435 (Q5, 3 sub-questions) and 131,766 of 284,736 (diffusion vs GAN, 4 sub-questions, with near matches). Since 2026-11-08 the judges are tagged separately in the token meter: `stage4_merge`, `stage4_support`, `stage4_near`, `stage4_conflict`. A near-match call costs about 700 tokens (measured: 360 calls = 252,259 tokens in one experiment); with one candidate per claim expect roughly 100 extra calls (about 70,000 tokens) per run.
- **Result of that run:** 136 claims -> 113 checked claims: 4 `supported`, 109 `unverified`, 0 `contradicted`, 0 false conflicts, 0 judge failures. The 4 supported claims were read and are correct.

## 8. Near-match label: how it was tested
On the stored digests of that run (no NLI, every member counted as supported by its own quote, real judges):
- First prompt: 45 of 132 claims became `partially_supported` (34%). Reading the pairs, about 7 in 10 were real corroboration (for example "MoE keeps computational cost low by activating only a subset of experts" with "MoE models can be made large while remaining computationally efficient because they process only a subset of experts"), the rest were different properties that share a topic ("specialization is hard to observe" with "expert imbalance early in training").
- Prompt tightened (the shared point must be named): sub-question 2 went from 14 to 12 and sub-question 3 stayed at 9. Reading these 21 pairs again, roughly 15 were fair and 6 loose (for example a LoRA-MoE parameter-efficiency claim matched with a general MoE efficiency claim). These judgements are mine, not human labels, and no precision figure is claimed. This is why the label is called *partially* supported and why readers must not show it as a fact.

## 9. Limits (details and fixes in `docs/KNOWN_LIMITS.md`)
- **Slow on the CPU** (4.10, measured in `docs/reports/21_timings.md`): int8 quantization is slower, the smaller NLI model misses the real conflicts and a cap of 40 pairs drops one; only a GPU or NLI on the host would help a first run (a repeated run is cached). Moving NLI to the host needs an endpoint there; the 80-pair cap means a true conflict outside the 80 most similar pairs is never looked at.
- **Little corroboration** (4.11): `supported` needs the same specific claim in two documents (about 3.5% of claims in the Q2 run); `partially_supported` is the answer to that, with the precision limit above.
- **No real conflict between sources has been found yet** (4.12); the conflict judge on the 41-pair labeled set has precision 0.71 and recall 0.56 (see 4.12), and one of the two conflicts of run 30 was false.
- The labeled sets (30 merge, 16 support, 40 conflict pairs) were written by an LLM, not by people.
- `needs_replan` is only recorded; the replan loop (Loop 3) is not built.

## 10. Running and testing
- Whole pipeline: `FACTCHECK=true venv/Scripts/python.exe test_pipeline.py "question"`.
- Stage 4 alone on a stored run (no new retrieval): `venv/Scripts/python.exe scripts/stage4_on_stored.py --query-id <uuid> [--sq 1 3] [--write]`.
- Evaluation of the judges on the labeled sets: `venv/Scripts/python.exe tests/stage4_eval.py [--nli]` (uses Groq).
- Tests: `venv/Scripts/python.exe -m pytest tests/test_factcheck_stage4.py` (offline, fake judges).
- Report of a run: `venv/Scripts/python.exe scripts/pipeline_run_report.py --run N` (section 7b is Stage 4).

## 11. Overlap with Stage 3 (`STAGE4_OVERLAP`)
- **What happens:** `summarizer_node` stores the digests and the coverage of each sub-question as soon as it is finished (judge, coverage, Loop 2) and hands the sub-question to `factcheck_node.start_in_background`. One process-wide worker thread runs `_check_sub_question` for the queued sub-questions in order, while Stage 3 goes on with the next sub-question. `factcheck_node` then only waits (`collect`), checks any sub-question that was not started early (for example when the queueing failed), and writes `fact_claims` and `contradictions` exactly as before. The result and the summary have the same shape and the same order.
- **Database:** `digests` and `coverage_results` are append-only, so a per-sub-question write does not touch the rows of the others; `get_digests_for_stage4` picks the newest 180 s window per sub-question, and one sub-question is written in one call, so it is read correctly. A rerun of Stage 3 for the same query writes newer rows and the older ones are ignored, as before. With the switch off, both tables are written once at the end of Stage 3.
- **Workers (`STAGE4_SQ_WORKERS`, default 1):** with one, sub-questions are checked one after the other. Run 32 showed why that can be the slowest part: the four sub-questions took 2 to 3 minutes each and were queued faster than they finished, so about 6 minutes of Stage 4 were left when Stage 3 ended. With 2, two sub-questions are checked at once. The NLI model uses all CPU cores, so two NLI steps take turns on the model lock and do not speed each other up; what overlaps is the Groq judges (same-claim, support, near match) of one sub-question with the NLI of the other. The cost is twice as many simultaneous Groq calls (each worker has up to `STAGE4_WORKERS` judge threads) and so more per-minute rate-limit waiting. The judge counters of a sub-question (`judge_calls`, `judge_waits`, `judge_failures`) are counted per job (`judge.track`, a context variable that the judge threads inherit), so they stay exact with any number of workers. The code default is 1, but `.env` has set it to 2 since 2026-11-10, after run 33: its Stage 4 jobs were queued one behind the other (sub-questions 3 and 2 were ready at 16:38 and started at 16:41), only 9 Groq rate limits (42 key-seconds) happened in the tail, and the arithmetic of the recorded step times gives about 4 minutes saved. Measure it on the next run against 8m 10s of Stage 4 after Stage 3.
- Checked before any real run: on the stored claims of run 32 with the real models and an invalid Groq key (0 tokens), 1 and 2 workers gave the same 89 labels as stored, and the per-sub-question cache-hit counts (131, 38, 76, 35) added up to the process total (280).
- **Progress:** steps that Stage 4 reports while Stage 3 still runs are held back and released, in order, when the `factcheck` node starts (after the `branch` event). The UI therefore still sees `stage_started factcheck`, then the steps, then `stage_completed` once.
- **Groq:** Loop 2 digests of the next sub-question and the Stage 4 judges now run at the same time and share the per-minute token limit. The pool and the judge wait (`STAGE4_RATE_WAIT_MAX`) handle a 429; a heavier overlap can mean more waiting, not wrong answers (a judge call still fails closed).
- **Failure:** a Stage 4 error never reaches Stage 3. If Stage 3 itself fails, the queued sub-questions that have not started are cancelled.
- Stage 3 preparation also runs the sub-questions side by side (`STAGE3_PREP_WORKERS`, default 4; 1 = one after the other); the embedding model is shared and its `encode` is serialised.

Safeguards added after an independent review of the parallel code (2026-11-08):
- Early Stage 4 jobs are only queued for a run of the graph: the planner announces the run (`factcheck_node.expect`). A direct call of `summarizer_node` (`run_stage3_judge.py`, the audit scripts) queues nothing, so it cannot spend Groq calls on jobs that nobody collects.
- If Stage 3 fails, queued jobs are cancelled and a running job stops at its next step boundary (claims, clusters, support, near, conflicts) instead of finishing all its judge calls.
- Known, not changed: two sub-questions that keep the same paper may embed its chunks twice in the parallel preparation (only time, same result); Stage 4 and Loop 2 share the CPU and the Groq limit, so for a budget-critical run `STAGE4_OVERLAP=false` gives the old order.
- Dry run before the first real run (real bge and DeBERTa models, an invalid Groq key so nothing was spent, stored digests of run 30): sub-questions 1 to 3 gave exactly the stored labels, sub-question 4 differed in 1 claim (it is the one whose judge calls failed in run 30), 0 Groq tokens, no thread errors in 852 concurrent embedder calls, the registry was empty afterwards.
