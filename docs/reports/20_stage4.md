# Report 20: Stage 4 (fact checking) wired in, measured, and what is still open

Date 2026-11-08. Starting point: `docs/reports/TRACE Stage 4 Fact Checking, Handoff Report.md` (code of 2026-11-01, not part of the pipeline). Contract for readers of the results: `docs/STAGE4_OUTPUT.md`.

## 1. What Stage 4 is
For every sub-question: the verified findings of Stage 3 are grouped into claims that state the same thing, each member's quote is checked against its claim, sources that assert the opposite are looked for, and each claim gets a label: `supported` (two independent documents), `unverified` (one document), `contradicted`. Cheap filters first (embeddings, NLI), the LLM judge last, and every judge call fails closed.

## 2. What I changed
| Change | Why |
|---|---|
| **In the graph** after the summarizer, behind `FACTCHECK=true` (off by default); state fields, progress lane `factcheck` (steps claims, clusters, support, conflicts, store), run-manager stage `factcheck` (`not_run` when off), a failed Stage 4 fails the stage, never the run | it was not part of the pipeline |
| **API report**: per sub-question `factCheck` (counts, claims, disagreements), `totals.factChecked`, `stages.factcheck`, limitation lines; `docs/API_HANDOFF.md`, `docs/STAGE4_OUTPUT.md` (task 8: the contract for Stage 5) | the web app and Stage 5 need it |
| **Digests are read as the newest Stage 3 run, all rows of it** (was: the newest row per source) | with Loop 2 a source can have a second digest row with other passages; the old read dropped the original findings |
| **Quote support is taken from Stage 3's judge when it already said "yes, the quote supports the claim"** (judge-v2 on the host, no Groq, no NLI); NLI and the Stage 4 support judge only for the rest | the first real run needed 180 s and hundreds of Groq calls for this check; now 1.4 s. On my 16 labeled pairs NLI had precision 0.83 and recall 0.62, so it was the weakest checker |
| **Judge calls run side by side (4 workers), in input order**, so the result does not depend on thread timing; merge candidates of one claim are judged together and then looked at in order, budgets are charged as the sequential version would | task 4 |
| **Judge answers cached on disk** (`.cache/stage4_judge`), failures never cached | a rerun on the same claims costs no LLM calls and gives the same labels |
| **Circuit breaker**: after a "rate limited for good" answer the judge is not asked again for 5 minutes (it fails closed at once) | the first real run waited 17 minutes on a daily Groq limit and then labeled nothing `supported` |
| **Every cap logs a warning when it bites**, per-sub-question counters (`judge_calls`, `judge_cache_hits`, `judge_failures`, `support_from_stage3`) in the summary | issue 4 of the handoff |
| **Conflict judge**: the prompt now says that hedged statements ("can", "potentially"), an aim versus a result, and different settings are not conflicts, and a conflict needs a **second reading** that tries to reconcile the statements and fails | the first real run produced two false "contradicted" labels from single lenient answers (see section 4) |
| Thresholds from the labeled set: `CLUSTER_AUTO_SIM` 0.95 to 0.98, `CLUSTER_CAND_SIM` 0.80 to 0.84, `STAGE4_MAX_PAIRS` 200 to 80 (section 3) | task 5 |
| Idempotent writers retry on a dropped connection; `contradictions` is stored without `reason` if that column is missing; migration `015` records the column that already exists | handoff issue 7 |
| 44 offline tests (`tests/test_factcheck_stage4.py`), plus API tests; the whole suite passes | task 3 |

## 3. Evaluation on a labeled set (`reports/stage4_eval_set.json`, `tests/stage4_eval.py`)
Labels were written by me (an LLM) from claims of the Q3 and Q2 runs, with a few constructed pairs where the real data has no positive case; they are not human labels. Strict tests as in the handoff.

| Decision | Pairs | Result |
|---|---|---|
| **Merge** (same claim?), judge | 30 (9 same) | precision 0.88, recall 0.78 (7 tp, 1 fp, 2 fn). The two misses are loose paraphrases; the false merge is a general definition versus a more specific one |
| Similarity as a merge rule | same-claim pairs have cosine 0.86 to 0.97; one pair of DIFFERENT claims scored 0.957 | auto-merge at 0.95 merged a wrong pair; no auto-merge below 0.98, candidates from 0.84 (nothing same-claim is below 0.86) |
| **Support** (quote supports claim?), judge | 16 (8 yes) | precision 1.00, recall 0.75 |
| Support, NLI (entailment >= 0.5) | same 16 | precision 0.83, recall 0.62 |
| **Conflict**, judge, first prompt | 34 (8 constructed conflicts, 26 negatives, 22 of them real) | precision 1.00, recall 1.00 |
| Conflict, judge, first prompt, after adding the 2 real false conflicts of section 4 and 4 hedging cases | 40 (9 conflicts) | precision 0.90, recall 1.00 (the false conflict "can hurt accuracy" versus "little impact" came back) |
| Conflict, NLI contradiction >= 0.7 as a prefilter | same | all 9 constructed conflicts at 0.98 or more; 3 of 31 negatives above 0.7: a good, cheap filter |
| Conflict, topic gate (quote versus claim cosine >= 0.70) | same | passes 7 of 9 conflicts and 26 of 31 negatives: it filters almost nothing (1,045 pairs passed it in one real sub-question); the cap of 80 pairs is the real limit |

The hardened conflict judge (hedging rules plus a second reading) is unit-tested but **its evaluation was cut short by the Groq rate limit** (19 of 40 calls failed), so its precision is not measured yet. Rerun `python tests/stage4_eval.py --nli` when the quota is back; answers already received are cached.

## 4. First real runs (Q3 run 7c8e355e, sub-question "trade-offs of 4-bit", 22 digests, 80 claims)
- **Run 1 (Groq quota gone):** 17 minutes; every support re-check failed closed, so 0 `supported`, 25 claims kept; two `contradicted` labels. Reading them: "Quantizing transformers reduces sampling latency with little impact on performance" versus "reduces latency but can hurt task accuracy" (a hedge, not a conflict) and "low-bit quantization aims to preserve task performance" versus "4-bit can cause degradation" (an aim versus a result). The judge had answered "conflict" at confidence 0.95 and 0.90. This is why the second reading was added.
- **Run 2 (after the changes, judge answers partly cached): 3 minutes.** 80 claims became 57 checked claims: 1 `supported` (two papers state "4-bit reduces model size and inference cost, which speeds up inference"), 55 `unverified`, 1 `contradicted` (the hedge case again, from the old prompt), 1 contested. Support step 1.4 s, conflicts step 95 s (80 NLI pairs on the CPU at about 1.7 s each). Most claims stay `unverified` because papers rarely word a result alike: `supported` needs two documents that state the same specific claim.
- No real conflict between sources appeared in the data tried so far: 22 real pairs of similar opposite-sounding claims were read and none contradicts under the strict test. Positive conflict cases in the evaluation set are constructed.

## 5. Cost and speed
- NLI (DeBERTa-large) runs on the CPU at about **1.5 to 1.8 s per pair** on this laptop (16 cores; fewer threads is slower). The smaller DeBERTa-base is 2.9 times faster (0.61 s) but disagrees with the large model on 9% of labels and flags different pairs, so I did not switch. Expect about 3 minutes of CPU per sub-question, 10 to 15 minutes per run, until NLI runs on the GPU host or fewer pairs are checked.
- Groq: after the Stage 3 reuse, the calls left are merge judgements for candidate pairs, conflict judgements for NLI survivors and a few support re-checks. The counters are in the summary; a full-run figure is not measured yet.

## 6. Not done / open (also in `docs/KNOWN_LIMITS.md`)
1. A **full pipeline run with `FACTCHECK=true`** (the wiring is tested with a fake graph and the node was run on stored data, but not inside a real run).
2. The evaluation of the **hardened conflict judge**, and a larger labeled set (30 merge pairs, 16 support pairs, 40 conflict pairs, all LLM-labeled).
3. **Recall of the merge step** (0.78, and the strict prompt will leave true paraphrases unmerged), and the cost of NLI.
4. `needs_replan` (task 7) is unchanged and still only a flag; Stage 5 is not built.
5. The frontend does not show Stage 4 yet (fields: `docs/API_HANDOFF.md`, `docs/STAGE4_OUTPUT.md`).
