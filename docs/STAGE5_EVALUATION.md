# Stage 5 evaluation checks (2026-11-13)

Script: `scripts/stage5_evaluate.py` (stored reports only, no Groq tokens, loads the Stage 4 NLI model; the judge is switched off, so it is stricter than the pipeline).
Runs: 35 (`ae23b7cd`, written with the code before 2026-11-13) and 36 (`c7a5feb3`, written after the single-source fixes of commit `4999a30`). These results were NOT repeated for the part-by-part answer of 2026-11-13 (commits `dc2036e` to `940b9db`); rerun `scripts/stage5_evaluate.py --run <id> ...` on a current report (about 10 minutes of NLI on the CPU, no Groq tokens) before quoting them for template `s5-v2`. Outputs go to `reports/stage5/eval` (not committed).

## A. Citation check (every body sentence)
| run | sentences | citation precision | citation recall | sentences with a source-count problem |
|---|---|---|---|---|
| 35 | 40 | 1.0 | 1.0 | 11 (all single-source: "One study reports ..." citing 2 to 4 documents) |
| 36 | 61 | 1.0 | 1.0 | 0 |

Precision and recall are 1.0 by construction (Python builds the citations from the quotes of the claims). The source-count rule (single = one document, partly = two, supported = two or more) is the check that found the run 35 problem, fixed in commit `4999a30`.

## B. Audit sample (100 sentences: 60 from run 36, 40 from run 35; 4 supported, 50 partly, 46 single)
- Deterministic checks (numbers, names, negations, hedge, shape): 0 of 100 flagged.
- NLI (quotes entail the sentence): 96 of 100 accepted (supported 4/4, partly 46/50, single 46/46). The 4 not accepted are partly-supported sentences with entailment 0.09 to 0.49 and contradiction under 0.01: neutral, not contradicted. In the pipeline the judge would have been asked next.
- `reports/stage5/eval/audit_sheet.md` holds the 100 sentences with claims and quotes and an empty "human verdict" line. **No person has reviewed them yet**; the machine columns are not a human review.

## C. Corrupted-copy test (the pipeline's checks must reject a damaged copy)
| corruption | rejected | by deterministic checks | by NLI |
|---|---|---|---|
| number changed | 15/15 | 15 | 0 |
| invented name | 100/100 | 100 | 0 |
| citation marker in the text | 100/100 | 100 | 0 |
| hedge removed | 96/96 | 96 | 0 |
| hedge upgraded ("It is well established that ...") | 96/96 | 96 | 0 |
| claim ids of another section | 100/100 | 100 | 0 |
| unrelated sentence | 40/40 | 34 | 6 |
| negation flipped | 40/40 | 33 | 7 |
| antonym swapped | 35/37 | 25 | 10 |

Known miss: swapping "without" for "with" ("without sharing" -> "with sharing", "without accessing raw data" -> "with accessing raw data") passed both layers twice. The NLI model does not treat it as a contradiction. Not fixed.

## Limits of this evaluation
Two runs, one machine, one seed (42). The corruptions are mechanical and simple; a fluent, wrong paraphrase is harder. Nothing here replaces reading the 100 sentences in the audit sheet.

## Repeated on template s5-v2 (2026-11-13, after the part-by-part answer)
Same script, same seed, on the CURRENT stored reports of run 37 (`f508d667`, planner step on, 69 body sentences) and run 36 (`c7a5feb3`, 61 body sentences). Outputs in `reports/stage5/eval_v2` (not committed).
- **Citations:** precision 1.0 and recall 1.0 on both; 0 sentences with a source-count problem (single-source: exactly one document, partly: two, supported: two or more) on 130 body sentences.
- **Audit sample (100 sentences: 49 from run 37, 51 from run 36; 5 supported, 47 partly, 48 single):** 0 flagged by the deterministic checks; NLI accepted 96 of 100 (supported 5/5, partly 45/47, single 46/48). The 4 not accepted have entailment 0.01 to 0.26 and contradiction under 0.01 (neutral). Still **no human verdict**; the sheet is `reports/stage5/eval_v2/audit_sheet.md`.
- **Corrupted copies:** number changed 5/5, invented name 100/100, citation marker 100/100, hedge removed 95/95, hedge upgraded 95/95, foreign claim ids 100/100, unrelated sentence 40/40 (29 by the deterministic checks, 11 by NLI), negation flipped 39/40, antonym swapped 32/35. The misses: a double negative the corruption itself produced ("no confidential data is not exposed"), an ungrammatical swap ("tend to higher the accuracy"), and again "without" -> "with".

What this does NOT cover: the script samples and checks the BODY sentences. The answer (`overview.summary`), the conclusion and the template note are checked by the pipeline (numbers, names, hedge, parts) but are not in the audit sample; add them before claiming the whole report was audited.

