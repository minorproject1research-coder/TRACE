# Report 9 - "One finding, one aspect" experiment (handoff item 3)

**Rule.** `ONE_FINDING_ONE_ASPECT=true`: a finding the judge rated "yes" for several aspects counts as covering evidence only for the aspect where its embedding similarity is highest (tie: lower index). Optional `ONE_FINDING_MARGIN=<x>`: a "yes" is dropped only if another aspect is at least `x` more similar. Default off; the verdicts stored in the database are unchanged, only the coverage count is affected. Code: `coverage_check.assign_best_aspect`, used in `check_coverage_judged`. Tests: `tests/test_one_finding_one_aspect.py`.

**Experiment** (`tests/one_finding_one_aspect_experiment.py`, offline, newest stored run of each of the 11 sub-questions of the 3 audit queries; the flag-off reconstruction matches the stored coverage rows for all 11). 42 aspects, 16 "yes" verdicts dropped.

| Sub-question | Aspect | yes before -> after | Covered -> |
|---|---|---|---|
| 763a1e90 LoRA vs full fine-tuning | memory cost defined | 3 -> 0 | uncovered |
| 763a1e90 | memory cost measured | 3 -> 1 | uncovered |
| 1fa8b305 context window | how a context window is measured | 3 -> 1 | uncovered |
| 935cc3b6 LoRA | main components of LoRA | 2 -> 1 | uncovered (sub-question: sufficient True -> False) |
| ec5a0fcd full fine-tuning | main components of full fine-tuning | 2 -> 0 | uncovered (sufficient True -> False) |
| b4ff92b2 LLMs | architectures of LLMs | 2 -> 1 | uncovered |

6 of 42 aspects change state; `sufficient` changes for 2 of 11 sub-questions.

**Were the dropped verdicts the right ones?** I labeled the 16 dropped verdicts (`reports/tag_audit_labeled_dropped.csv`; LLM labels by me, before looking at the rule's choices; n = 16, single labeler): 13 were not a direct answer (5 label 0, 8 label 0.5) and 3 were true answers (label 1: an LLM-architectures claim, a context-window definition, a list of long-context tasks). So the rule removes mostly the over-coverage the targeted audit found (the memory-cost cluster loses defined and measured, as the audit said it should), but it also removes real answers.

**Where it goes wrong.** All 3 wrong drops are near-ties: the other aspect was only 0.01 to 0.02 more similar. One real loss changes a state: "architectures of LLMs" falls from 2 to 1 yes because its best claim is slightly closer to "components". With a margin, on the same 16 rows: margin 0.03 keeps 5 verdicts and drops 11 (0 true answers lost), 0.05 drops 10 (0 lost), 0.08 drops 6 (0 lost). The margin was picked after seeing these rows, so it is a hypothesis, not a validated setting.

**Caveats.** The rule only reduces coverage; it does not make a wrong "yes" right (the "factors" aspects stay covered, and the audit says they should not be). Aspect splits changed between my runs because tests were wiping the aspect cache (fixed: tests now use temp caches); `cdf8f029` was restored to its 6-aspect split and `tag_audit_targeted_*` uses the split of the time (see report 8). Labels are LLM-assigned.

**Recommendation.** Do not switch it on yet. Next: judge V2 (report 8 / validation report section 14), then re-run this experiment with V2 verdicts; if the rule still matters, test `ONE_FINDING_MARGIN=0.05` on a fresh labeled sample before turning it on.
