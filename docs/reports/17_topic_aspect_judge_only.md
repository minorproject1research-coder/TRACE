# Report 17: the sub-question as an aspect for the judge only (planned item B2)

Date 2026-11-07. Code: `TOPIC_ASPECT=judge` (`detail_aspects.topic_aspect_mode`, `summarizer_node`, `evidence_judge.select_candidates(topic_aspect_idx=...)`). Default stays `false`.

## Why
`TOPIC_ASPECT=true` (limit 3.12) put the sub-question into the aspect list that the digest prompt also receives, and the digest model then returned 65% fewer findings (4.25 to 1.50 per digest). The aspect itself judged well on stored digests. The new mode gives the judge and the coverage rule one more aspect and leaves the digest prompt and the chunk selection exactly as they are; the topic aspect gets the 6 most similar verified findings as candidates (no finding is tagged for it).

## Experiment (tests/topic_aspect_judge_only.py)
The stored digests of Q1 to Q6 (25 sub-questions) were written without the topic aspect, so they are exactly the situation of the new mode (the first experiment was biased the other way). Real judge, no database writes, 6 candidates per sub-question, about 150 pairs.

Rule fixed before the run: (1) a verdict for every candidate; (2) at least 80% of the "yes" claims directly answer the sub-question when I read them; (3) digests unchanged by construction (unit test `TestJudgeOnlyMode`).

| Check | Result |
|---|---|
| (1) verdict for every pair | **missed by one pair:** 1 of about 150 returned no verdict ("the judge returned no verdict and gave no error text"); the pipeline records such a pair as `error` and the aspect as `unjudged`, never as `uncovered` |
| (2) "yes" claims that directly answer | **42 of 47 (89%)** by my labels. The five that do not: a post-hoc routing sentence about prompt embeddings (not MoE), one side of a trade-off ("4-bit causes an accuracy drop"), one paper's proposed metrics, "GANs encounter training stability challenges" (one side of a comparison), and "federated learning mitigates many privacy risks compared to centralized learning" (about FL, not its defenses) |
| (3) digests unchanged | by construction (the digest step uses `topic_aspect_enabled()`, true only for `TOPIC_ASPECT=true`) |

## Effect on "sufficient" (reported, not a pass condition)
10 of the 25 sub-questions were sufficient in the stored runs. The topic aspect is covered (2 yes from 2 sources) for 7 of them and **not** for 3, which would no longer be sufficient:
- Q1 "What are state space models (SSMs) and how do they work?": 1 yes, 2 partial, 3 no.
- Q3 "What is quantization and how does it affect large language models?": 0 yes, 6 partial.
- Q5 "What are diffusion models and GANs?": 1 yes, 1 partial, 4 no.

All three are the "definition never checked" case of limit 3.12: sufficiency came from generic aspects (benefits, challenges, advantages) while no finding defined the subject. Of the 15 sub-questions that were not sufficient, 5 have the topic covered anyway (Q2 "How is expert routing implemented in LLMs?", Q4 "What is a large language model?" with 6 of 6 yes and "What is reasoning ability...", and the Q5 quality and stability comparisons with 5 and 4 yes), so the aspect does not only add failures.

## Decision
- `TOPIC_ASPECT=judge` is implemented and tested (unit tests `TestJudgeOnlyMode`, full suite 248 passed), default off. Rule (1) was missed by one pair out of about 150; I consider that within the judge's normal error rate (it is also how pairs fail in production) and the pipeline handles it, but it is a miss of the pre-registered rule and is recorded as such.
- Still open: one real run with `PLAN_CACHE=true` and `TOPIC_ASPECT=judge` to check the wiring end to end (the stored judge_stats marker, the report, the web app's aspect list). Do it as part of the Q1 to Q6 rerun after Loop 2, or earlier on one question.
- Effect to expect: 3 of 10 sufficient sub-questions in Q1 to Q6 become not sufficient. Whether that is "right" is a labeling question (is a sub-question sufficient when its subject was never defined?).
