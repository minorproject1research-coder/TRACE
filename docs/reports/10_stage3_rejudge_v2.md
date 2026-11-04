# Report 10 - Re-judging the stored Stage 3 runs with judge V2 (effect on coverage)

**Question.** What does judge V2 change in real Stage 3 coverage, compared with the stored runs (judged by V1, with another paper's passage - see below)?
**Method.** `tests/rejudge_stage3.py`. For the newest run of each of the 11 sub-questions of the 3 audit queries it takes exactly the 239 (finding, aspect) pairs the stored run judged and judges them again with the deployed judge (`JUDGE_MODEL_ID=judge-v2`): `ctx` = with the correct surrounding passage rebuilt from the same source, `noctx` = no passage. Coverage uses the normal rule (2 "yes" from 2 sources per aspect). Real judge calls, no database writes. Results: `reports/rejudge_stage3_v2.json`.
**Why the passage matters.** The stored runs were judged with a passage taken from the wrong paper (chunk ids repeat in every source; fixed 2026-11-04). So "stored versus ctx" is the combined effect of the new prompt and of the fix; "ctx versus noctx" isolates the passage.

## Result

| | stored (V1, wrong passage) | V2 + correct passage | V2, no passage | V2 + correct passage + one-finding rule (margin 0.05) |
|---|---|---|---|---|
| Aspects covered (of 42) | 31 | **27** | 29 | 27 |
| Sub-questions "sufficient" (of 11) | 5 | **4** | 4 | 4 |
| Pairs judged "yes" (of 239) | 103 | 102 | 101 | |

Pair-level changes, stored -> V2 + passage: 83 stay "yes", 20 leave "yes" (11 to "no", 9 to "partial"), 19 enter "yes" (18 from "partial", 1 from "no"). The total hardly changes, but the pairs that are "yes" are different ones.

Aspects whose state changes (stored -> V2 + passage):
- Covered -> uncovered (6): memory cost defined, measured, factors for LoRA (`763a1e90`); basic components of LLMs (`b4ff92b2`, "yes" 4 -> 0: with the correct passage none of the four claims, a training process, the RAG components, a parameter list, is accepted; without the passage 2 are); main components of full fine-tuning (`ec5a0fcd`; the two "how it works" claims become "no"; this flips the sub-question to not sufficient); memory usage increase (`cdf8f029`, one RMT claim becomes "partial").
- Uncovered -> covered (2): how transformers process token sequences (`1e8f8a8c`: embedding lookup, positional encoding, parallel processing) and how RAG improves input/output quality (`856b9105`, the first Loop 2 test case: two accuracy / hallucination claims). On reading the claims these look like genuine answers (my quick read, not a blind labeling).
- These are the aspects the targeted audit (report 8) said were over-covered, and the changes go the way that audit pointed: the memory-cost and LLM-components aspects lose their false coverage.

**One-finding rule.** With V2 it changes no aspect state (27 covered with and without), so V2 already removes the double counting that the rule was designed for. It stays off.

**The passage.** With vs without the correct passage the verdict differs on 24 of 239 pairs and the covered count differs by 2 (27 vs 29): a modest effect, and in the direction of rejecting wrong claims (for example "components of LLMs").

**Labeled pairs.** 47 of the pairs I labeled earlier are still comparable (the other 28 were not judged in the stored run or their aspect wording differs from today's split). On them: stored "yes" 37, strict 17/37 = 0.46, lenient 0.78, 8 false "yes" on label-0 rows; V2 + passage "yes" 30, strict 17/30 = 0.57, lenient 0.87, 4 false "yes"; no label-1 pair is lost (17 of 17). These rows over-represent the suspect aspects (they were chosen for the audits), so the numbers describe the audited problem, not the judge's overall precision.

## Caveats
- The comparison mixes three changes (prompt, passage, judge noise): the judge moves 39 of 239 pairs in and out of "yes" with no change in the total, so one aspect at the 2-yes boundary can flip for reasons that are not about the evidence. Do not read any single aspect flip as proof.
- Same findings as the stored run (no new digests), same aspect split structure (`cdf8f029` restored by hand, wording may differ), LLM labels, quick read of the flipped claims.
- Coverage still depends on the digests, which are regenerated on every run unless the digest cache is used.

## Conclusion
V2 with the correct passage lowers coverage from 31 to 27 aspects and the number of sufficient sub-questions from 5 to 4, and the aspects it uncovers are the ones the audit found over-covered; it also covers two aspects that V1 left uncovered, on plausible evidence. Recommendation: keep V2 and the passage fix, keep the one-finding rule off, and use the V2 coverage states as the starting point for Loop 2 (the aspects that are `uncovered_judged` after V2 are the ones Loop 2 should try to fill). The remaining weakness is the judge's subject confusion on a few cases (report 8, section 14.6), which is a candidate for a V2.1 tested on fresh rows.
