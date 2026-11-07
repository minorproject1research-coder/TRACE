# Report 16: which uncovered aspects deserve another search, and does aspect wording decide the verdict

Date 2026-11-07. Planned items A1 and B1 of `docs/KNOWN_LIMITS.md`. No new runs: the data are the stored judge verdicts of the latest complete run of each test question (Q1 17:33, Q2 23:29, Q3, Q4, Q5, Q6), read from `digests.findings[].judge`. Scripts were scratch files; the table below is the result.

## Data
- 6 runs, 110 aspects, 593 judged (finding, aspect) pairs: 276 yes, 157 partial, 160 no.
- 75 aspects covered (68%), 35 uncovered.
- Covered = at least 2 "yes" from at least 2 sources; this reproduces the coverage rows of every run.

## A1: can the stored verdicts tell a near miss from an unanswerable aspect?

Labels were written by me (an LLM) BEFORE any rule was scored, from the aspect text against the user's question, not from the verdicts:
- **A (answerable):** the user asked for it and the literature on the topic plausibly answers it; more or better-aimed evidence is plausible. 19 aspects.
- **U (unanswerable or not asked):** a dimension the planner invented, or an aspect of a sub-question that is not the user's question. 10 aspects.
- **? (unsure, left out):** 6 aspects (Q1 transformer parameters, Q3 compatibility, Q4 levels of reasoning, Q6 assumptions / compared / combined).

Pass rule (fixed before scoring): a rule passes if it agrees with the label on at least 80% of the 29 labeled uncovered aspects.

| Rule | Agrees | Searches again | Skips |
|---|---|---|---|
| R0 search every uncovered aspect | 66% | 29 (A 19, U 10) | 0 |
| **R1 yes + partial >= 2** | **79%** | 21 (A 17, U 4) | 8 (A 2, U 6) |
| R2 partial >= 2 | 69% | 18 (A 14, U 4) | 11 (A 5, U 6) |
| R3 yes >= 1 and yes + partial >= 2 | 62% | 10 (A 9, U 1) | 19 (A 10, U 9) |
| R4 at least 5 judged candidates | 76% | 18 (A 15, U 3) | 11 (A 4, U 7) |
| R5 yes + partial >= 2 and candidates >= 4 | 69% | 18 | 11 |
| R6 yes + partial >= 3 | 72% | 17 | 12 |

**Result: no rule passes; R1 comes closest (79% against the 80% bar), on 29 aspects labeled by one labeler.** Findings that hold anyway:
- R1 cleanly skips the planner's invented dimensions: diversity, security, interoperability (Q3) and scaling with data size and model size (Q5) all have at most 1 partial and are skipped. That is the case the rule was meant for.
- R1's four wrong searches are three aspects of Q4's off-question sub-question ("best practices", "methods", "open problems of using benchmarks to IMPROVE reasoning", 4 partial each) and Q5 compute scaling. Verdict counts cannot see that a sub-question is not the user's question; that needs a sub-question level decision (B3), not an aspect rule.
- R1's two misses are Q1 training-efficiency metrics (0 yes, 1 partial, 5 no) and Q1 transformer open challenges (1 yes, 2 no): genuine aspects with mostly "no" candidates.
- R3 ("needs a yes") is the worst: near misses with only partial verdicts (Q3 quality 0/5/1, Q4 existing benchmarks 0/4/2, Q5 image types 0/6/0) are exactly what Loop 2 should work on.

Decision for Loop 2: use R1 as the default triage because it separates invented dimensions from the rest, state that it is NOT validated to the bar, and measure its yield in the Loop 2 runs (A4: share of searched aspects that become covered, split by R1 yes/no). Off-question sub-questions are handled separately.

## B1: does the wording of the aspect decide the verdict?

Aspects were typed by a regex on their text (first match wins):

| Wording type | Aspects | Covered | Yes share of pairs | Partial share |
|---|---|---|---|---|
| generic (advantages, limitations, challenges, benefits...) | 28 | 86% | 62% | 18% |
| noun phrase (components, types, sources, impacts...) | 18 | 78% | 53% | 28% |
| question (what / how ...) | 39 | 72% | 44% | 26% |
| comparison (compare / compared) | 6 | 67% | 37% | 27% |
| list ("existing / common X") | 6 | 33% | 28% | 33% |
| **effect ("how does X affect Y")** | 13 | **23%** | **18%** | **47%** |

Reading: the hypothesis from Q3 to Q5 is supported descriptively. The effect aspects have the lowest covered share and the highest partial share; the list aspects are next. But this is NOT a test of wording:
- 12 of the 13 effect aspects belong to one run (Q3), so topic and wording are confounded.
- The regex typing is crude (the "question" group mixes everything).
- The verdicts of one aspect are judged on different findings, so the finding mix also differs.

A real test needs the same findings judged under two wordings of the same aspect. That needs the judge server (`/verify_evidence_batch`) and is the next step of B1: take the 8 aspects of the Q3 core sub-question and the 2 list aspects of Q4, reword each in the forms "what is the effect of X on Y" / "which X are reported", re-judge the same stored finding sets, and compare yes counts to the originals. Pass rule, fixed now: a rewording is only worth adopting if it raises "yes" counts on aspects labeled A and does not raise them on aspects labeled U (the planner's invented ones), checked on the same pairs.

## What this changes in the plan
1. A1: R1 becomes the default triage for Loop 2, marked unvalidated, with its yield measured (A4). The "off-question sub-question" case moves to B3.
2. B1: needs the re-judge experiment above before any change to aspect wording or judge prompt; nothing was changed.
3. The label file and the rule table are the only A1 artifacts; the labels are LLM labels (known limit 5.1) and the B10 human-labeled subset would settle R1 versus R4.
