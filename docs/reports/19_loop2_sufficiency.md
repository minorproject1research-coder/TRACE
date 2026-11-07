# Report 19: making more sub-questions sufficient with Loop 2

Date 2026-11-08. Follows report 18. Goal from the user: most sub-questions sufficient. Code: `loop2.py` (synthesis, gap rule, query rounds, candidate cap), `coverage_check.py` (`synthesis_covered`, `non_blocking`), `evidence_judge.py` (`candidates_per_aspect`), `report_service.py`, `scripts/pipeline_run_report.py`; tests in `tests/test_loop2.py` (31 tests; the full suite passes); experiment `tests/synthesis_experiment.py`.

## 1. Where the sub-questions were still failing
After Loop 2 (report 18) I classified the 13 aspects that were still uncovered in the full runs of Q3, Q2 and Q4:

| Kind | Aspects | Meaning |
|---|---|---|
| near miss: 3 or more yes/partial verdicts from 2 or more sources | **9** | The evidence is there but each claim is one measured result of a broad aspect; the rule needs two single claims that each answer the whole aspect. Example: "how does 4-bit affect representation and computation": 10 partial verdicts from 10 sources. |
| thin: 1 or 2 yes/partial verdicts | 3 | Little evidence after the whole search. |
| none | 1 | Nothing found (the planner's "security of quantized LLMs"). |

So searching more was not the main lever. The two gaps were (a) the single-claim rule on broad aspects and (b) sub-questions that stay "not sufficient" because of aspects with no evidence at all.

## 2. What was changed
1. **Synthesis of partial findings.** For an uncovered aspect with yes/partial findings from at least 2 sources, the judge gets ONE item with the claims and quotes of up to 6 sources together. If it says "yes", the aspect counts as covered, marked "by synthesis" in the evidence, the report and the API, and listed in the report's limitations as weaker evidence. It runs before any search (a near miss does not need one) and after every step.
2. **Known gaps do not block "sufficient" (item B3), as a stated rule.** An aspect that stays uncovered after the whole ladder, with thin evidence (fewer than 3 yes/partial verdicts or fewer than 2 sources), is a known gap "evidence not found". `coverage.sufficient` then means "every aspect with evidence is covered"; the old meaning is stored as `sufficientStrict` and the gaps are listed in the report. Near misses, aspects that were not searched (cap), aspects whose search was cut short (time, failed digests) and every aspect of a sub-question whose first digests failed keep blocking. `LOOP2_GAP_RULE=strict` restores the old meaning.
3. Smaller levers: `LOOP2_MAX_ASPECTS` 4 to 8, the judge sees 10 instead of 6 findings per aspect after Loop 2 added sources (`LOOP2_CANDIDATES_PER_ASPECT`), the queries step can run twice with new queries each time (`LOOP2_QUERY_ROUNDS`, default 1, not measured).

## 3. Is synthesis safe? (tests/synthesis_experiment.py)
51 aspects of the Q3, Q2 and Q4 full runs with findings from at least 2 sources. Pass rules written before the first run: (1) negative controls (the same composite built from another topic's findings put under the aspect) at most 10% "yes"; (2) the accepted composites read by hand: at least 80% truly answer the aspect; (3) the planner's invented aspects are not accepted.

| | Result |
|---|---|
| (1) controls | **0 of 51** rated yes |
| accepted among the 11 aspects uncovered at the time | **6 of 11**: representation and computation, quality of generated text, model size and memory (Q3); effect of routing on performance and efficiency, types of routing strategies (Q2); insights from using benchmarks (Q4) |
| (2) hand reading of the 6 | all 6 answer the aspect from the claims shown; two are weak (quality of generated text mixes findings that point in opposite directions; "insights" is a loose match) |
| (3) invented aspects | interoperability got "partial": not accepted |

Variant v2 (no "Taken together" framing, only findings whose quote support was already verified, `answers_aspect` decides) accepted 7 of 11 with 0 of 51 controls, but replaced one right acceptance by a wrong one ("how are benchmarks and metrics compared" accepted on two claims that compare nothing). Not adopted. The composite keeps the judge's usual stringency: five uncovered near misses stay "partial" (for example the comparison of routing methods, where the claims come from one paper).

## 4. Effect: replay on the stored Stage 3 of Q1 to Q6 (25 sub-questions)
Stored digests judged again with the current judge, then Loop 2 with the steps `reselect,pool`, synthesis and the core rule (`scripts/loop2_on_stored.py`; no writes to the stored runs).

| | Sub-questions sufficient |
|---|---|
| fresh baseline (strict rule, no Loop 2) | 10 of 25 |
| Loop 2 without synthesis and the gap rule (report 18, same replay) | about 17 of 25 (7 flips) |
| **with synthesis and the core rule** | **20 of 25 (80%)** |
| of these, sufficient under the strict rule too | 15 of 25 (60%) |

By question: Q1 4 of 5, Q2 5 of 5, Q3 2 of 3, Q4 2 of 4, Q5 4 of 4, Q6 3 of 4. Five sub-questions are sufficient only by the core rule; their known gaps are: "parameters of a transformer", "open challenges of transformers" (Q1), "main challenges of LLMs" (Q4, a background sub-question), "scaling with data size, model size and compute" (Q5, the planner's invented aspects), "how the defenses can be combined" (Q6). The five that stay insufficient all have near misses: Q1 long-sequence metrics, Q3 quality and robustness, Q4 "existing benchmarks" and "existing metrics" (list aspects), Q4 "insights ...", Q6 "assumptions of the defenses".

## 5. What this does not show
- **No full run yet with these changes.** The Groq quota was gone again (a Q3 run at 17:22 lost all its digests: 3 verified findings, 26,301 key-seconds parked) and I stopped the chain. The replay uses the stored digests plus Loop 2's own digests (cached from the earlier replays), the real judge, and only the steps `reselect` and `pool`; the queries step needs Groq and is not in these numbers. A full run will add the queries step (more coverage, more time) and different Stage 3 digests (the first Stage 3 pass is not deterministic), so expect a lower, noisier number than 20 of 25.
- The Q3 run exposed a flaw that is now fixed: with the digests failing, "no evidence found" looked like a finding and the core rule would have called the gap non-blocking. Aspects of a sub-question whose first digests failed now keep blocking (test added).
- The core rule changes what "sufficient" means. It is stored both ways and shown as "evidence not found", but a reader who sees only `sufficient: true` should be told that known gaps exist; the frontend must show `knownGapsNoEvidence` and `coveredBySynthesis` next to it (fields in `docs/API_HANDOFF.md`).
- Precision of the new coverage by synthesis rests on 6 hand-read composites; the precision of the core rule is a policy, not a measurement.

## 6. Next
Run the full pipeline for Q3, Q4, Q2, Q5, Q6 when the Groq quota is back: `PLAN_CACHE=true LOOP2=true python test_pipeline.py "<question>"` (takes 8 to 17 minutes each) and compare with the strict rule stored in `judge_stats.loop2.sufficient_strict`.
