# Report 8 - Targeted audit of the evidence judge (over-coverage suspects)

**Question.** The judge says "yes" to findings that look like half answers. Are the six suspect aspects really over-covered?
**Data.** Every judge-"yes" finding (verified, newest Stage 3 run per sub-question) for 6 aspects: 18 rows (15 distinct findings; the same finding can be a row for several aspects).
Files: `reports/tag_audit_targeted_20261104_2154.csv` (unlabeled, no judge columns), `..._verdicts_....json` (judge fields), `reports/tag_audit_labeled_targeted.csv` (labels).
**Labels.** Assigned by an LLM (Claude) from the CSV alone, before looking at any verdict, using the conventions in the Stage 3 handoff. Not human labels. Single labeler, n = 18.

| Aspect (sub-question) | Judge yes (rows / sources) | Label 1 | Label >= 0.5 | Covered if judged by labels (>=0.5, >=2 sources) |
|---|---|---|---|---|
| memory cost defined (763a1e90) | 3 / 3 | 0 | 3 | yes |
| memory cost measured | 3 / 2 | 1 | 1 | **no** |
| memory cost factors | 2 / 2 | 0 | 1 | **no** |
| basic components of LLMs (b4ff92b2) | 4 / 4 | 0 | 0 | **no** (all four are about something else) |
| motivation of RAG (e96996ab) | 4 / 4 | 0 | 2 | yes |
| attention degradation (cdf8f029) | 2 / 2 | 0 | 1 | **no** |
| **All 18 rows** | | **1 (0.06)** | **8 (0.44)** | |

(The sixth suspect, computational complexity on `cdf8f029`, has no "yes" at all in the stored run, so it is not an over-coverage case.)

## What it shows
1. **The suspicion is confirmed.** Of 18 "yes" rows, 10 are label 0 and only 1 is a direct answer. Both judge answers (`quote_supports_claim` and `answers_aspect`) were "yes" on all 10 label-0 rows, so the judge is not hedging; it is wrong with full confidence.
2. **Three error types.** (a) Vocabulary match with the wrong kind of thing: "components of LLMs" accepted a training process, a retriever + LM (that is RAG), and a list of comparison parameters. (b) Cause or result accepted as a definition, measurement or factor ("gradients are stored" for how memory cost is defined and measured; "LoRA cuts memory 40%" for how it is measured). (c) Method description accepted as motivation (iterative retrieval, FLARE's query design).
3. **One finding covers several aspects.** 10 of the 18 rows are the same finding also judged "yes" for 1-2 other aspects (the gradient-storage claim is "yes" for defined, measured and factors). This inflates coverage on top of the precision problem.
4. **Quote support is mostly not the issue.** 15 of 18 quotes state what the claim says; rows 11, 17 and 18 are the exceptions (claim adds details or the quote does not mention the claimed subject), and the judge said `quote_supports_claim = yes` for them too. The main failure is `answers_aspect`.
5. **Coverage impact:** with these labels, 4 of the 6 aspects drop below "2 yes from 2 sources" at lenient labeling, and all 6 at strict labeling.

## Limits
- These aspects were chosen BECAUSE they looked over-covered, so 0.06 / 0.44 is not the judge's overall precision. The earlier random samples (strict 0.83 to 0.85) still stand, but they were taken before the digest/aspect-text problems found on 2026-11-04 (see below), so they should be recomputed (handoff item 7).
- One LLM labeler with a strict reading (e.g. "source of a cost is not a definition"); a human could be more lenient on rows 1, 6, 11, 15.
- 15 distinct findings from 4 sub-questions.

## Decision on a tighter judge prompt
Justified to TEST, not to ship. The judge prompt is deployed on the model host (outside this repo), so it was not changed. Before any change: write V2 (add "the claim must be the same KIND of thing the aspect asks for: a definition, a measurement, a factor, a component, a motivation; a cause, result or method description of something else is partial or no"), run it on ALL labeled rows (the 6 earlier files + these 18) and compare strict precision and recall against V1 (gate: strict >= 0.85, lenient >= 0.95, recall >= 0.60). Item 3 (one finding counts for one aspect) is independent and would remove finding 3 above without touching the prompt.

## Data problems found while doing this (affect older numbers)
- Every Stage 3 re-run appends new `digests`/`coverage_results` rows; older audits that read every row of a query mixed runs. The audit scripts now use only the newest run.
- Aspect splits are LLM output and differ between runs; the aspect text a verdict was judged against was not stored for covered aspects. Verdicts now store it (`judge[<idx>].aspect`); older runs are matched by aspect INDEX and checked for alignment.
