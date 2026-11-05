# TRACE Stage 3 Coverage Validation Report

Covers the Loop 2 (insufficient coverage) work, the Stage 3 coverage fixes, six labeled audits, the independent judge pass and its validation. Sections 1 to 8 are the original report, sections 9 to 12 are an earlier update, and section 13 holds the latest results and corrections and takes precedence where they differ.

## 1. Summary

We set out to make Loop 2 regenerate queries for uncovered detail questions. While preparing it we found that Stage 3 was reporting many details as uncovered even though verified evidence existed. We fixed that, but the fix over-corrected: the tagging that now decides coverage is noisy and unreliable. Three labeled audits show precision of the tags that count toward coverage between 50% and 69% (strict) and 81% to 94% (lenient), and it varies from run to run. The conclusion is that the generator should not judge its own evidence. We added an independent judge pass, served through the existing vLLM wrapper, which decides whether each candidate finding is supported by its quote and directly answers the aspect.

## 2. Starting point

- Stage 3 selects up to 5 papers and 3 web sources per sub-question, picks top chunks, generates findings with quotes (Groq GPT-OSS-120b), verifies quotes against the source text, then runs a coverage check.
- The coverage check returned `sufficient: False` with uncovered details such as "How does it work?" and "How is it measured?".
- The planner (LoRA on Qwen3.5-9B) and judge (base Qwen3.5-9B) are served from one vLLM server behind a FastAPI wrapper (`/decompose`, `/judge`).

## 3. What we did, in order

### 3.1 Loop 2 design

- Agreed the idea is sound: use uncovered details to drive new queries.
- Recommended an escalation order instead of jumping to new retrieval: (1) re-select chunks per detail, (2) take next-ranked papers from the Stage 2 pool, (3) generate new queries with the planner.
- For query generation: reuse `/decompose` by turning each uncovered aspect into a standalone question, keep only the search queries, dedupe against already-tried queries with bge, and cap iterations. No new wrapper endpoint is needed for this; an optional `temperature` and `n` on `/decompose` would add diversity.

### 3.2 Raising the source count did not help

Increasing from 3 to 5 papers and 2 to 3 web sources (8 sources, 5 full text) left the same details uncovered. Source count was not the bottleneck.

### 3.3 Diagnostic script

We built a read-only script that classifies each uncovered detail as: A matching problem, B chunk selection problem, C verification loss, D evidence missing. Result: all three uncovered details were cause A. Verified findings that answered them existed, but raw cosine similarity between a short question and a declarative claim was about 0.49 to 0.53, below the 0.60 threshold. Prefixing the topic raised scores to 0.87 to 0.89, but that inflates any claim that mentions the topic, so it is not a safe fix.

### 3.4 Fix 1: tag-based coverage

- `digest_generator` tags each finding with the detail it answers (`answers_details`).
- `coverage_check` counts a detail as covered if a verified finding is tagged for it and passes a similarity floor (`MIN_TAG_SIM` 0.40).
- `chunk_selector` also picks the top 2 chunks per detail (topic-prefixed), capped at 9 chunks per source, skipping tables and captions.
- Result: every sub-question became `sufficient: True`. Suspicious because it was so uniform.

### 3.5 Audit 1

40 rows sampled and labeled (1 = directly answers, 0.5 = partial, 0 = no).

- 96.9% of findings carried a tag (308 of 318).
- Tagged precision: strict 30% (9 of 30), lenient 87%.
- No good findings were missed among untagged rows (0 of 10).
- Problems: two-part questions ("advantages and disadvantages") were covered by one-sided findings, and a few tags were plainly wrong. The similarity floor could not separate good from bad tags.

### 3.6 Fix 2: strength, aspects, stricter rule

- Tags now carry `strength` (`full` or `partial`).
- Two-part details are split into aspects (for example "advantages of X" and "disadvantages of X").
- An aspect is covered only with at least 2 verified `full` findings from at least 2 distinct sources. A detail is covered only if all its aspects are.
- Test fixes: one failing test was caused by the default `min_sources=3` (a 2-source fixture is covered but not sufficient). Dead duplicate code in `coverage_check.py` was removed, a legacy-path bug (comparing an int to dict tags) was fixed, and encoding was batched.

### 3.7 Audit 2 (new seed)

50 rows. For `full` tags (n=16): strict 69%, lenient 94%. Remaining problems: 7 of 24 `partial` tags were really direct answers (under-promotion), some `full` findings were not supported by their own quote, and one benchmark fact was covering two opposite aspects (improvement and struggles).

### 3.8 Audit 3 (pipeline rerun on the same questions)

35 rows. For `full` tags (n=16): strict 50%, lenient 81%. For `partial` tags (n=14): strict 43%, lenient 71%. Combined scored rows (30): strict 46.7%, lenient 76.7%, AUC of similarity versus correctness 0.612. Findings:

- Strength has stopped carrying signal (50% for full versus 43% for partial).
- Strength was inverted on memory cost: "memory cost is the percentage of trainable parameters" got `full` (its quote was a table header), while the correct "peak active memory in GB" findings got `partial`.
- Two near-duplicate aspects (quality of input data, relevance of input data) were covered by the same claim.
- No good findings were missed among untagged rows.

## 4. Audit results at a glance

- Audit 1 (all tags counted): strict 30%, lenient 87%.
- Audit 2 (`full` tags): strict 69%, lenient 94%.
- Audit 3 (`full` tags): strict 50%, lenient 81%.
- Target used: strict at least 85%, lenient at least 92%. No round has passed both.

## 5. Root cause

1. The generator tags its own findings, and that tagging is noisy and changes between runs of the same pipeline.
2. The quote verifier only proves that the quote exists in the source. It does not check that the claim follows from the quote, so table fragments and unrelated quotes pass.
3. Similarity cannot separate good tags from bad ones, because LLM-written claims echo the question's wording. Raising `MIN_TAG_SIM` is not a fix.
4. Further prompt tuning has not converged (precision rose once and fell once).

What is working: retrieval, source counts, chunk selection, quote existence checks, and clear definitional findings. No good findings were being missed.

## 6. Decision: independent judge pass

- The generator's tags only produce a shortlist of candidates per aspect.
- A separate judge (base Qwen3.5-9B on the existing vLLM server) answers two questions per candidate: does the quote support the claim, and does the claim directly answer the aspect (each yes, partial or no).
- An aspect is covered only with at least 2 "yes" verdicts from 2 distinct sources.
- Near-duplicate aspects are merged so one claim cannot cover two aspects that are really the same question.
- Verdicts are cached, but digests are regenerated on every run, so coverage can still change between runs (see section 13).
- New wrapper endpoints `/verify_evidence` and `/verify_evidence_batch` serve the judge.
- Before enabling by default, the judge is evaluated against the roughly 125 labeled audit rows, and we require high precision on its "yes" verdicts.

## 7. Open items

- Done: the judge pass and the wrapper endpoints are built (see sections 9 and 13).
- Fix `tests/negative_control_coverage.py`, which still uses the old `generate_digest` signature. The negative control (a detail the papers cannot answer must come back uncovered) ran later, but only trivially (see section 13). It is the only direct test that the stricter rule can still return "uncovered".
- Make digest JSON parsing robust (retry once, log failures per sub-question). Silent failures mean coverage is computed on fewer sources.
- Build Loop 2 using `uncovered_aspects` as input. One real candidate already exists: "How does retrieval-augmented generation constrain the creativity and diversity of large language models?".

## 8. Caveats

- Labels in all audits were assigned by an LLM (Claude) from claim, quote, and aspect text, not by a human. Hand-check disagreements, especially the 0.5 labels.
- Samples are small (16 `full` tags per round), so differences of about 10 to 12 points are within noise.
- The judge pass is untested until it is evaluated against the labeled rows and a fresh audit.

## 9. Update: judge pass built (superseded by section 13)

The judge pass is built and wired into Stage 3, but it is not validated, and at the time of writing testing was paused because the machine hosting the judge was offline (it has since come back online). This update supersedes the first open item in section 7.

### 9.1 What was built

- Wrapper endpoints `/verify_evidence` and `/verify_evidence_batch` on the existing FastAPI wrapper, served by the base Qwen3.5-9B judge at temperature 0. Each returns `quote_supports_claim` and `answers_aspect` (yes, partial or no), and the final verdict is computed in code.
- Pipeline: `evidence_judge.py` (candidate shortlist from the generator's tags plus top-by-similarity extras, batching, retries, caching), near-duplicate aspect merging at 0.92 in `detail_aspects.py`, `check_coverage_judged()` in `coverage_check.py`, and integration in `summarizer_node.py`, which also retries a failed Groq JSON parse once.
- Rule: an aspect is covered only with at least 2 "yes" verdicts from at least 2 distinct sources, and a detail is covered only if all its aspects are. The weighted source rule (full text 1.0, abstract or web snippet 0.5, minimum 3) is unchanged.
- 53 pytest tests pass. Scripts exist for judge calibration, negative control, positive control (not completed) and audit export.

### 9.2 Results so far

| Check                                       | Result                                                                                              | Status                                                        |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Mock calibration                            | 1.000 on every metric                                                                               | Meaningless: the mock returns the labels                      |
| Real calibration, 125 labeled rows          | Strict yes-precision 0.703, lenient 0.865, recall of label 1 0.634                                  | Gate fails (needs 0.85, 0.95 and 0.60)                        |
| Blind comparison, seed-11 sample (41 rows)  | Judge said yes 5 times: 4 were label 1, 1 was label 0.5, none label 0; it found 4 of 8 label-1 rows | Cautious, but too strict on broad aspects                     |
| Combined 166-row calibration (agent report) | Internally inconsistent; recomputed from its own matrix: strict 0.66, lenient 0.83, recall 0.625    | Must be recomputed with a verified script                     |
| Negative control (9 controls)               | All pass                                                                                            | Weak evidence: the judge says "no" to about 60% of candidates |
| Positive control                            | Not completed (endpoint timeouts)                                                                   | Open                                                          |
| Judge-enabled Stage 3 re-run                | Several aspects fell back with "judge unavailable (no verdicts)"                                    | Open: key matching or timeouts                                |

### 9.3 What we learned

- The judge errs in both directions. It is too strict on broad aspects (a correct core answer is marked partial because it does not cover "various tasks and models"), and too lenient on adjacent-topic claims (causes accepted as risks, general LLM applications accepted as long-context tasks, the motivation of adaptive retrieval accepted as the motivation of RAG).
- The judge's reason text sometimes contradicts its structured verdict, so only the structured fields should be used.
- Silent per-aspect fallback mixes two rule sets inside one sub-question. It should be replaced by explicit states: covered, uncovered after judging, and unjudged.
- The audit CSVs were written with the Windows default encoding, so claims were garbled (for example "â€‘"), and the seed-11 verdicts were computed on that text. A later re-run of the seed-11 verdicts on clean UTF-8 text changed only 2 of 41 final verdicts (both rows labeled 0.5, partial versus no) and none of the 5 yes verdicts, so the encoding problem did not materially affect the results.
- The `coverage_results` table has no columns for the new judge fields, so they are not persisted. A migration is needed.
- The audit export samples only one of the three audit queries and has no covering rows from the judge path.

### 9.4 Status

Superseded: the judge host came back online and validation resumed. See section 13 for the results.

## 10. Resume checklist

1. Reproduce and fix the verdict key-matching bug by giving each candidate a stable item id; log items sent, returned and matched.
2. Log batch latency and timeouts against the real wrapper (report only, no tuning).
3. Replace silent fallback with explicit aspect states. Unjudged aspects count as not covered but must never trigger Loop 2 query generation.
4. Add a migration for the judge fields on `coverage_results`.
5. Recompute calibration over all four labeled files with file-prefixed row ids and sum assertions, and list every false "yes".
6. Re-run the seed-11 judge verdicts on UTF-8 text and compare them with the old ones.
7. Re-run Stage 3 with the judge on the three audit queries and check the state of every aspect.
8. Fix the audit export (all queries, judge-path covering rows, a `covering_basis` column).
9. Run the positive and negative controls.
10. Superseded (see section 13): do not loosen the judge. If a second prompt is tested, tighten it against adjacent-topic answers without adding false "yes" verdicts, tuning on rounds 1 and 2 and evaluating on round 3 and seed 11.

## 11. Loop 2: insufficient coverage

Loop 2 is designed but not implemented or wired into the pipeline. It should wait until the coverage decision is reproducible (see section 13).

**Trigger.** After Stage 3, every aspect whose state is "uncovered after judging" enters Loop 2. Unjudged aspects are never retried here, because they were never evaluated. The reason for the gap (no candidate findings versus candidates judged insufficient) decides the first step.

**Escalation ladder, cheapest first, per aspect:**

1. Re-select the top 1 to 2 chunks for that aspect from papers that are already parsed, then digest, verify and judge them.
2. Take the next-ranked papers from the Stage 2 pool, parse them, then digest, verify and judge.
3. Generate new queries with the planner and run retrieval again.

After each step the aspect is judged again, and the ladder stops as soon as it is covered.

**Query generation.**

- Turn the uncovered aspect into a standalone question that includes the main topic, because aspects such as "how memory cost is measured" are vague on their own.
- Send it through the existing `/decompose` endpoint with the same prompt format and the empty think block, keep only the search queries from the output, and drop any query too similar (cosine 0.90 with bge) to one already tried. Keep 3 to 4.
- No new endpoint is required. Optional `temperature` and `n` fields on `/decompose` would give more varied queries.
- Extract queries from planner output keyed by "queries" or "search\_queries". This is an assumption about the planner's output format and should be checked against a real output.

**Limits.** At most 2 rounds per aspect, and the loop stops early if a round adds no new relevant source. After the cap the aspect becomes a known gap that goes to the report generator, which should say that evidence was not found. Tried queries, the round count and the state of each aspect are kept in the shared research state.

**First test case.** "How does retrieval-augmented generation constrain the creativity and diversity of large language models?" already came back uncovered under the stricter rule, probably because the retrieved papers do not discuss it.

**Metrics to track.** Share of aspects covered after each ladder step, new sources added per round, judge calls per round, and the number of known gaps at the end.

## 12. Updated caveats

- All labels in the six labeled audit files were assigned by an LLM. Judge-versus-label agreement is therefore LLM against LLM, and disagreements should be spot-checked by hand.
- Samples are small: 16 `full` tags per audit round, and 41 rows in seed 11 from a single topic.
- Sections 9 to 11 were written before the later results in section 13; where they differ, section 13 applies.

## 13. Latest results and corrections

This section takes precedence over sections 1 to 12 where they differ. In short: the judge's "yes" verdicts are precise on fresh samples, but coverage still changes between runs, some aspects look over-covered, and the controls do not yet test the judge.

### 13.1 Corrections to earlier sections

- A notebook was mentioned in an earlier version of this report. It was never created, so there is no reference implementation of Loop 2 yet.
- The judge host came back online and validation resumed (section 9 said it was paused).
- Encoding: re-running the seed-11 verdicts on clean text changed only 2 of 41 final verdicts and none of the "yes" verdicts, so it was not a significant cause of the earlier results.
- Caching: only judge verdicts are cached. Digests (findings) are regenerated on every run, so coverage can change between runs on the same sources.

### 13.2 Judge versus labels on fresh samples

| Sample                        | Rows | Judge "yes" | Yes precision (strict) | Yes precision (lenient) | Recall of label 1 |
| ----------------------------- | ---- | ----------- | ---------------------- | ----------------------- | ----------------- |
| Seed 11, re-run on clean text | 41   | 5           | 4 of 5                 | 5 of 5                  | 4 of 8            |
| Export A                      | 45   | 24          | 20 of 24               | 24 of 24                | 20 of 23          |
| Export B                      | 45   | 23          | 19 of 23               | 22 of 23                | 19 of 21          |

- Labels were assigned by an LLM without seeing the verdicts. Exports A and B share many findings, so the results should not be pooled as if they were independent.
- Across the three samples the judge said "yes" to a label-0 row once: a claim that an implementation hides internal steps, accepted as an advantage of transformer models. Its other false "yes" verdicts were half answers: loosely stated advantages, the first step of a process, and the source of a cost accepted as a definition.
- Misses were broad aspects judged "partial", and one context-window claim judged "no" twice because its quote only gives an example limit (my label there may have been generous).
- Exact agreement with the labels was 68% (seed 11), 73% (export A) and 73% (export B).
- The generator's `full` tags in exports A and B scored 17 of 21 and 16 of 21 strict (19 of 21 lenient in both), compared with 69% and 50% strict in earlier rounds. Tag quality moves a lot between runs.
- Recommendation: keep the current judge prompt and do not loosen it, because recall is acceptable. Tighten it against adjacent-topic answers only if the targeted audit below confirms false "yes" verdicts.

### 13.3 Pipeline run results and concerns

- Fixed: the evidence log now holds the real claim prefix, quote prefix and item id, and the migration warning is no longer printed. No database read-back has been shown yet.
- 10 of 11 sub-questions were fully judged. One transient judge error left one aspect "unjudged", which is the intended state.
- Coverage is not reproducible. On the same sources, "disadvantages of LoRA" had 4 yes verdicts in one run and 1 in the next, and a quadratic-complexity claim covered the complexity aspect in one run and the attention-degradation aspect in the next.
- Aspects that may be over-covered (judged from claim prefixes and judge reasons only, not yet labeled): the same gradient-storage claim covers "memory cost defined", "measured" and "factors"; "basic components of LLMs" is covered partly by a training-process claim and by a claim about a retriever and a language model, which describes RAG; "motivation of RAG" is covered partly by method descriptions; "how attention degrades with long context" is covered partly by a mitigation claim.
- Negative control: all 6 controls passed, but trivially. The control aspect had no candidate findings, so the judge was never asked to reject anything. The log also shows a fallback to the tag rule after the judge returned 25 verdicts, because one aspect had no verdicts, and the 30-call cap was reached on the last control.
- Audit export: covering rows are still chosen by tag strength rather than by the judge's verdict, only 2 of the 3 audit queries were sampled, and there were no untagged rows.

### 13.4 Open items, in priority order

1. Fix the audit export: covering rows must be findings the judge rated "yes" that count toward a covered aspect, from all three queries, with untagged and judged-partial or no rows included.
2. Targeted audit: label every "yes" finding for the memory-cost, LLM-components, RAG-motivation and attention-degradation aspects.
3. Test a rule that lets a finding cover only one aspect (the one it matches best).
4. Make digests reproducible (cache plus temperature) and show that two consecutive runs give identical coverage results.
5. Fall back to the tag rule only when a whole sub-question has zero verdicts, and add a forced-candidate negative control that sends adjacent-topic findings for a control aspect to the judge.
6. Show a database read-back of every judge field for all 11 sub-questions.
7. Recompute calibration over all six labeled files with file-prefixed row ids and sum assertions.
8. Implement Loop 2 after items 4 and 5. First test case: "How does retrieval-augmented generation constrain the creativity of large language models?", which still has no "yes" verdicts.

I have no results for these items, so they are listed as open until each one is verified.

### 13.5 Caveats

- All labels are LLM-assigned, so judge-versus-label agreement is LLM against LLM. Hand-check disagreements and the 0.5 labels.
- Samples are small and overlapping.
- Run results above come from pasted logs and were not independently re-run.

## 14. Judge prompt V2 (to be deployed on the host wrapper and evaluated)

Written 2026-11-04 after the targeted audit (`docs/reports/08_stage3_targeted_audit.md`): on the 18 findings the judge rated "yes" for the six suspect aspects, 10 were label 0 and only 1 was a direct answer, and on all 10 both `quote_supports_claim` and `answers_aspect` were "yes". The errors were about the KIND of answer, not about the quote: a training process accepted as "components", a cause or a result accepted as a definition, measurement or factor, a method description accepted as a motivation, an answer about a variant method accepted for the general topic, and a mitigation accepted as the problem. V2 changes only question 2 (`answers_aspect`) plus one clause in question 1, and keeps the output format, so the wrapper's parser and the `final` computation do not change.

### 14.1 Before deploying: the judge cache

The pipeline caches judge verdicts under a key made of the aspect, claim, quote and `JUDGE_MODEL_ID`, not the prompt. If the prompt changes and the id stays `judge`, V1 verdicts will be served as if they were V2. After the host runs V2, set `JUDGE_MODEL_ID=judge-v2` in the TRACE `.env` (new cache keys), and keep the V1 results under the old id for comparison.

### 14.2 V2 prompt text (replace the V1 text in the wrapper; keep the placeholders and the output format)

```
You are an evidence checker for a research assistant. You are given a research aspect (a question to answer), a claim extracted from a paper, the exact quote it was based on, and optionally the passage around the quote.

Aspect: {aspect}
Claim: {claim}
Quote: {quote}
Surrounding passage (may be empty): {context}

Answer two questions.

1. quote_supports_claim. Does the quote itself state what the claim says? Use the passage only to work out what words such as "it", "our method" or table columns refer to.
   yes = the claim is a faithful restatement of the quote.
   partial = the quote supports only part of the claim, or the claim generalizes (for example "generally", "always"), adds details, names a subject the quote does not mention, or draws an inference the quote does not state.
   no = the quote does not say this. This includes quotes that are only table fragments, headers or captions that do not state the claimed meaning.

2. answers_aspect. Would the claim, on its own, be an acceptable one-sentence answer to the aspect?
   First decide what KIND of answer the aspect asks for, for example: a definition, a way of measuring, the factors or causes of something, the components or parts, the motivation or goal, how something works, results or evidence, advantages or disadvantages, examples, challenges or limitations. Then decide what KIND of statement the claim is. The claim answers the aspect only if it is that kind of statement, about the same subject.
   yes = the claim is the kind of answer the aspect asks for, about the same subject, and complete enough to stand alone as the answer. When the aspect asks for examples, items, advantages, metrics and similar lists, one concrete valid item counts as yes.
   partial = related but incomplete, vague, or only touches the topic; or it gives one half of a two-part aspect; or it is the right kind of answer but about a variant, a specific system or a special case when the aspect asks about the topic in general.
   no = it is about a different subject, a different kind of thing than the aspect asks for, or only shares vocabulary with the aspect.

   These are NOT answers, even when they are true and on topic:
   - A cause, reason or source of something is not its definition and not a way of measuring it. A result or number is not a way of measuring, a definition, or a factor, unless the claim says that this is the factor or the measure.
   - A description of how a method works is not the motivation for it, and a motivation is not a description of how it works.
   - A list of things or a process is not "the components" unless the claim names the parts the thing is made of. A training procedure, a list of properties used to compare models, or the parts of a different system are not the components of the subject.
   - A fix, mitigation or improvement is not an account of the problem it addresses, and a statement of a problem is not an account of its fix.
   - A claim about a different system or modality than the one the aspect asks about is "no" unless the aspect is general. A claim about a named variant of the subject is at most "partial" when the aspect is about the subject in general.
   Examples on an unrelated topic, to show the rule: for the aspect "how the size of a database index is measured", the claim "indexes slow down writes because every insert must update them" is "no" (a consequence, not a measurement); for "components of a database index", the claim "an index is built with a sorted copy of one column plus row pointers" is "yes", and "indexes are created by running a CREATE INDEX statement" is "no" (a procedure, not components); for "motivation of caching", the claim "a cache stores results in a hash table" is "no" (how it works), and "caches avoid recomputing results that are requested again, which saves time" is "yes".

Be strict. Sharing words with the aspect is not an answer. Return ONLY a JSON object, nothing else, in this exact format:
{"quote_supports_claim": "yes" or "partial" or "no", "answers_aspect": "yes" or "partial" or "no", "reason": "one short sentence"}
```

Differences from V1: (1) question 1 `partial` also covers a claim that names a subject the quote does not mention (rows 17 and 18 of the audit); (2) question 2 now asks for the kind of answer before the verdict; (3) `partial` also covers one half of a two-part aspect and a variant or special case; (4) a list of five "not answers" rules taken from the observed errors; (5) three examples on an unrelated topic. The examples are deliberately NOT taken from the audit rows, so the 18 audit rows remain a fair test. Keep `max_new_tokens` at 200 (the output format and length are unchanged), temperature 0, thinking off.

### 14.2a Braces in the wrapper (found on the first test run)

The prompt above shows the JSON answer line with single braces. If the wrapper builds the prompt with Python `str.format()` (the placeholders `{aspect}`, `{claim}`, `{quote}`, `{context}` suggest it does), every literal brace must be doubled in the wrapper's string or the server fails with `KeyError: '"quote_supports_claim"'` for every item (observed 2026-11-04: all 18 test rows came back as errors). In the wrapper the last line must read:

```
{{"quote_supports_claim": "yes" or "partial" or "no", "answers_aspect": "yes" or "partial" or "no", "reason": "one short sentence"}}
```

(or fill the four placeholders with `.replace()` instead of `.format()`). V2 has no other braces.

### 14.3 How to evaluate V2 before using it (rule: no prompt change without held-out before/after numbers)

1. Rebuild the wrapper, set `JUDGE_MODEL_ID=judge-v2` locally, and keep the V1 verdicts you already have as the baseline.
2. Targeted rows (the test the prompt was written for): run the judge on `reports/tag_audit_labeled_targeted.csv` and report how many of the 10 label-0 rows are still "yes" and how many of the 8 label >= 0.5 rows stay "yes". Targets: at most 3 of the 10 false "yes" remain; the row labeled 1 (row 12) stays "yes".
3. Regression rows: `python tests/eval_judge_vs_labels.py --csv reports/tag_audit_labeled.csv reports/tag_audit_labeled_round2.csv reports/tag_audit_labeled_round3.csv reports/tag_audit_labeled_judge2.csv` (the other labeled files are missing from the repo; restore them first if you have them) and compare with V1: strict yes-precision at least 0.85, lenient at least 0.95, recall of label 1 at least 0.60 and not more than 5 points below V1.
4. Report the numbers for V1 and V2 side by side, including every row whose verdict changed. The main risk is recall: the "kind" rules may turn correct but loosely worded answers into "partial", which would leave real aspects uncovered. If recall falls below 0.60, relax the "components" rule in the "not answers" list first and re-test.
5. Only then switch the pipeline to V2. If V2 is adopted, re-run Stage 3 on the three audit queries and compare the covered aspects with the V1 run.

If V2 is not enough, the next step is a two-field output that forces the reasoning before the verdict (`kind_asked`, `kind_given`, then the two answers). That changes the output format and needs a wrapper change, so it is not part of V2.

### 14.4 Results of the V2 test (2026-11-04, `reports/judge_eval_judge-v2_20261104_2243.json`)

Real judge, `JUDGE_MODEL_ID=judge-v2`, 204 labeled rows (194 unique), no surrounding passage, labels LLM-assigned. Script: `tests/eval_judge_prompt.py`.

| Rows                                                         | V1                                                                               | V2                                                                   |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Targeted audit, 18 rows (10 label 0, 7 label 0.5, 1 label 1) | 18 of 18 "yes" (pipeline, wrong passage; fresh V1 without passage: 12, see 14.5) | **8 "yes"**: 3 of 10 label-0, 4 of 7 label-0.5, 1 of 1 label-1 |
| Dropped-by-rule rows, 16 (5 label 0, 8 label 0.5, 3 label 1) | 16 of 16 "yes" (pipeline; fresh V1: 11, see 14.5)                                | **7 "yes"**: 0 of 5 label-0, 4 of 8 label-0.5, 3 of 3 label-1  |
| Round 1-3, 125 rows                                          | strict 0.703, lenient 0.865, recall 0.634 (earlier run, not re-verified)         | strict 0.660 (31/47), lenient 0.936 (44/47), recall 0.756 (31/41)    |
| Export B, 45 rows                                            | strict 19/23, lenient 22/23, recall 19/21 (section 13.2)                         | strict 17/22, lenient 20/22, recall 17/21                            |
| All four regression files, 170 rows                          | not available                                                                    | strict 0.696, lenient 0.928, recall 0.774                            |
| Pooled, 194 unique rows                                      | not available                                                                    | strict 0.622, lenient 0.902, recall 0.785 (gate FAIL)                |

Reading: the two goals of V2 are met on the rows it was written for (at most 3 of the 10 false "yes" remain: 3; the label-1 rows stay "yes": 4 of 4; no label-0 "yes" survives on the dropped-by-rule rows). On the older rows it is mixed and does not pass the gate: strict precision is about the same as V1's reported numbers or slightly lower, lenient is higher on round 1-3 and slightly lower on export B, recall is higher. The V1 numbers for the older rows come from earlier logs, not from a re-run, and differences of 1-2 rows (export B) are noise.

What V2 still gets wrong: (1) subject confusion is not fixed: "retriever + language model" and "decoder-only / encoder-decoder / hybrid designs" are still accepted as the components of an LLM, and the FLARE "intuition" is still accepted as the motivation of RAG (3 of the 8 label-0 "yes" rows); (2) new misses: of 14 label-1 rows V2 does not call "yes", 8 have a supported quote but `answers_aspect` partial or no, mostly "a specific result or example is not comprehensive" for aspects that ask for results or evidence (for example one task result for "results of experiments comparing LoRA and full fine-tuning"). The phrase "complete enough to stand alone as the answer" in the `yes` line is the likely cause, because V1 and V2 both say one concrete item counts as "yes" for list-type aspects, and the judge reads "complete" as stronger.

Not yet done: a paired V1 versus V2 comparison on rows neither prompt was written for, and any V2.1 change. Any V2.1 must be tested on fresh labeled rows, not on these 204.

### 14.5 V1 baseline on the same rows (2026-11-04, `reports/judge_eval_judge-v1_20261104_2303.json`) and a correction to 14.4

V1 was redeployed on the host, `JUDGE_MODEL_ID=judge-v1`, and the same 204 rows were judged under the same conditions as V2 (no surrounding passage, `tests/eval_judge_prompt.py`). Table 14.4 compared V2 with V1 verdicts from the pipeline (which had the wrong-paper passage, see below) and with figures from earlier logs; use this table instead.

| Rows                         | V1 (fresh)                                                           | V2                                                                   |
| ---------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Targeted audit, 18           | 12 yes: strict 1/12, lenient 6/12, recall 1/1                        | 8 yes: strict 1/8, lenient 5/8, recall 1/1                           |
| Dropped-by-rule, 16          | 11 yes: strict 3/11, lenient 8/11, recall 3/3                        | 7 yes: strict 3/7, lenient 7/7, recall 3/3                           |
| Round 1-3, 125               | strict 0.703, lenient 0.892, recall 0.634                            | strict 0.660, lenient 0.936, recall 0.756                            |
| Export B, 45                 | strict 18/22 = 0.818, lenient 0.955, recall 0.857                    | strict 17/22 = 0.773, lenient 0.909, recall 0.810                    |
| Regression files, 170        | strict 0.746, lenient 0.915, recall 0.710                            | strict 0.696, lenient 0.928, recall 0.774                            |
| **Pooled, 194 unique** | **strict 0.610, lenient 0.844, recall 0.723, agreement 0.603** | **strict 0.622, lenient 0.902, recall 0.785, agreement 0.619** |

Paired, on the 194 unique rows: V1 "yes" -> V2 not "yes": 5 label-0, 2 label-0.5, 3 label-1. V1 not "yes" -> V2 "yes": 1 label-0, 7 label-0.5, 7 label-1. False "yes" on label-0 rows: V1 12, V2 8.

Corrections:

1. The fresh V1 numbers on round 1-3 reproduce the earlier logged figures (strict 0.703, recall 0.634; lenient 0.892 vs 0.865), so those logged V1 numbers were reliable. Export B differs by one row (18/22 vs 19/23).
2. "V1 said yes to all 18 targeted rows" (report 8, section 14.4) was the pipeline run, where the judge was shown a passage from the wrong paper (chunk ids repeat in every source; fixed 2026-11-04). With no passage, V1 says "yes" to 12 of the 18. So V2's improvement on those rows is 12 -> 8 "yes", not 18 -> 8, and part of the pipeline's V1 behaviour came from the wrong passage. How much is not measured; it needs a re-judge of the stored runs with the correct passage.
3. The V2 rules were written while looking at the targeted rows, so the targeted and dropped rows overstate V2's benefit.

Reading: V2 is modestly better on every pooled number (strict +0.012, lenient +0.058, recall +0.062, agreement +0.016) and removes 4 more false label-0 "yes", but on the regression files its strict precision is lower, and every difference rests on a handful of rows (for example label-1 rows gained 7 vs lost 3), so it is not a demonstrated improvement. Neither prompt passes the gate on these rows (strict ~0.61). Decision still open: test V1 and V2 on a fresh labeled sample that neither prompt has seen.

### 14.6 Held-out test: V1 versus V2 on 50 fresh rows (2026-11-04)

Rows: `reports/tag_audit_labeled_heldout.csv` (the 50-row audit export of `reports/tag_audit_export_11_20261104_2153.csv`: 19 label 1, 15 label 0.5, 16 label 0). Labels assigned by an LLM from the CSV alone, before any judge verdict was seen; neither prompt was written or tuned on these rows. Same conditions for both prompts (no surrounding passage). Results: `reports/judge_eval_judge-v1_20261104_2306.json`, `reports/judge_eval_judge-v2_20261104_2326.json`.

| 50 held-out rows                | V1                 | V2              |
| ------------------------------- | ------------------ | --------------- |
| Judge "yes"                     | 24                 | 25              |
| Strict precision                | 17/24 = 0.708      | 18/25 = 0.720   |
| Lenient precision               | 21/24 = 0.875      | 23/25 = 0.920   |
| Recall of label 1               | 17/19 = 0.895      | 18/19 = 0.947   |
| False "yes" on label-0 rows     | 3 (rows 8, 15, 44) | 2 (rows 15, 44) |
| Exact agreement with the labels | 0.58               | 0.64            |

Nine verdicts changed: six moved closer to the label, three further away (a sign test on 6 against 3 is nowhere near significant). The only "yes" V2 removed was a label-0 row (8, the 40% memory result offered for "how memory cost is measured"). The two it added were one label-1 row and one label-0.5 row. The two remaining label-0 "yes" rows are the same two that survived V2 earlier: the FLARE query-design principle for "motivation of RAG" (15) and a vision-hallucination definition for "defined in large language models" (44).

All 233 unique rows tested so far (the 194 of section 14.5 plus these 50, duplicates removed): V1 strict 0.646, lenient 0.865, recall 0.756; V2 strict 0.650, lenient 0.913, recall 0.817.

Reading: V2 is equal or slightly better than V1 on every measure on fresh rows and on all rows together, with no sign of the recall loss that the first test suggested. The size of the gain is small (strict precision is unchanged at about 0.65; the gain is in lenient precision, +0.05, and recall, +0.06), it rests on a few rows, and neither prompt passes the gate (strict >= 0.85). About half of the strict shortfall is half answers (label 0.5) that the judge accepts, which depends on how strictly my labels read "source of a cost is not a definition" and similar; a human review of the 0.5 labels would show how much of the gap is real. Recommendation: keep V2 deployed (`JUDGE_MODEL_ID=judge-v2`), do not expect it to fix over-coverage by itself, and measure its effect on real coverage by re-running the judge on the stored runs with the correct passages. A V2.1 aimed at the two remaining subject-confusion cases should wait for fresh rows to test it on.

## 15. Judge prompt V2.1 (draft, to be deployed and tested)

Written 2026-11-05 after the second Mamba run. It changes V2 in four places and adds one precision guard; everything else (output format, placeholders, temperature, `max_new_tokens`) is unchanged. The host wrapper needs the same brace escaping as for V2 (section 14.2a): double the braces of the JSON line if the template is built with `str.format()`.

### 15.1 Why

On run 2 the central comparison sub-questions were almost uncoverable under V2 (sub-question "long-sequence performance": 1 "yes", 8 "partial" out of 18). To check that this was not specific to those rows, 66 judged pairs of run 2 were exported (41 from the two comparison sub-questions, 25 from the others), labeled blind from the CSV by an LLM (me; `reports/tag_audit_labeled_run2.csv`), and V2 was run on them: strict precision 0.478 (11 of 23), lenient 0.870, **recall of label 1 only 0.524 (11 of 21)**, 3 false "yes" on label-0 rows. Labeling policy for aspects that list several systems ("state space models, transformers, and Mamba"), fixed before labeling: a claim that states a difference or relationship between at least two of the listed systems is a direct answer (1); a claim about one system alone is partial (0.5). This policy matches the intent of V2.1, so the results are also reported under the stricter reading (multi-system aspects capped at 0.5).

The rows were split at random into 32 development and 34 test rows (`reports/v21_split.json`, seed 21, stratified by multi-system aspect). V2.1 was drafted after reading V2's verdicts and reasons on the development rows only (plus the run 1 reasons and the held-out misses already seen). The 34 test rows' verdicts and reasons have not been looked at.

Patterns found on the development rows (V2 disagreeing with the label):

1. V2 misapplies its own exception: "LRA benchmark scores are used to measure long-sequence performance" and "accuracy is used as the metric" were judged "a result, not the metric", although V2 says a claim that names the measure counts.
2. A concrete comparison from one task ("Mamba trains slower than optimized Transformers on document ranking") was judged partial as "only a specific example, not a general comparison".
3. A claim that reverses the quote (Mamba "has ten times fewer parameters" where the quote says more) got `quote_supports_claim = yes`.

### 15.2 V2.1 prompt text (changes against V2 are marked with `<<` at the end of the line; remove the marks when you paste it)

```
You are an evidence checker for a research assistant. You are given a research aspect (a question to answer), a claim extracted from a paper, the exact quote it was based on, and optionally the passage around the quote.

Aspect: {aspect}
Claim: {claim}
Quote: {quote}
Surrounding passage (may be empty): {context}

Answer two questions.

1. quote_supports_claim. Does the quote itself state what the claim says? Use the passage only to work out what words such as "it", "our method" or table columns refer to.
   yes = the claim is a faithful restatement of the quote.
   partial = the quote supports only part of the claim, or the claim generalizes (for example "generally", "always"), adds details, names a subject the quote does not mention, or draws an inference the quote does not state.
   no = the quote does not say this. This includes quotes that are only table fragments, headers or captions that do not state the claimed meaning, and claims that reverse the quote or give different numbers or a different direction (for example "fewer" where the quote says "more"). <<

2. answers_aspect. Would the claim, on its own, be an acceptable one-sentence answer to the aspect?
   First decide what KIND of answer the aspect asks for, for example: a definition, a way of measuring, the factors or causes of something, the components or parts, the motivation or goal, how something works, results or evidence, advantages or disadvantages, examples, challenges or limitations. Then decide what KIND of statement the claim is. The claim answers the aspect only if it is that kind of statement, about the same subject.
   yes = the claim is the kind of answer the aspect asks for, about the same subject, and states a concrete answer. When the aspect asks for examples, items, advantages, metrics, results and similar lists, one concrete valid item counts as yes. << ("complete enough to stand alone" removed)
   partial = related but incomplete, vague, or only touches the topic; or it gives one half of a two-part aspect; or it is the right kind of answer but about a variant, a specific system or a special case when the aspect asks about the topic in general.
   no = it is about a different subject, a different kind of thing than the aspect asks for, or only shares vocabulary with the aspect.

   These ARE answers, even though they are specific: <<
   - A concrete finding from one task, dataset or setting answers an aspect about results, differences or comparisons. The aspect does not require a result for every task. <<
   - For an aspect that asks for metrics, indicators or benchmarks, a claim that names the metric or benchmark that is used (for example "accuracy is the metric", "scores on benchmark X measure it") answers it, even when the claim also reports a result. <<
   - For an aspect that lists several systems (for example A, B and C), a claim that states a difference or a relationship between at least two of them is a direct answer. A claim about only one of them is partial. <<

   These are NOT answers, even when they are true and on topic:
   - A cause, reason or source of something is not its definition and not a way of measuring it. A result or number is not a way of measuring, a definition, or a factor, unless the claim says that this is the factor or the measure.
   - A description of how a method works is not the motivation for it, and a motivation is not a description of how it works.
   - A list of things or a process is not "the components" unless the claim names the parts the thing is made of. A training procedure, a list of properties used to compare models, or the parts of a different system are not the components of the subject.
   - A fix, mitigation or improvement is not an account of the problem it addresses, and a statement of a problem is not an account of its fix.
   - A claim about a different system or modality than the one the aspect asks about is "no" unless the aspect is general. A claim about a named variant of the subject is at most "partial" when the aspect is about the subject in general.
   Examples on an unrelated topic, to show the rules: for the aspect "how the size of a database index is measured", the claim "indexes slow down writes because every insert must update them" is "no" (a consequence, not a measurement); for "components of a database index", the claim "an index is built with a sorted copy of one column plus row pointers" is "yes", and "indexes are created by running a CREATE INDEX statement" is "no" (a procedure, not components); for "motivation of caching", the claim "a cache stores results in a hash table" is "no" (how it works), and "caches avoid recomputing results that are requested again, which saves time" is "yes". <<(unchanged)
   More examples: for the aspect "metrics used to evaluate cache performance", the claim "hit rate is the main metric, and an LRU policy reached 92%" is "yes" (it names the metric); for "how Redis, Memcached and a local dictionary differ in latency", the claim "Redis answers in about 1 ms while Memcached needs 0.6 ms" is "yes" (it relates two of them) and "Redis answers in about 1 ms" is "partial" (one of them only). <<

Be strict. Sharing words with the aspect is not an answer. Return ONLY a JSON object, nothing else, in this exact format:
{{"quote_supports_claim": "yes" or "partial" or "no", "answers_aspect": "yes" or "partial" or "no", "reason": "one short sentence"}}
```

Differences from V2: (1) `no` in question 1 also covers a claim that reverses the quote or changes its numbers or direction; (2) "complete enough to stand alone" is removed from the `yes` line and "metrics, results" are added to the one-item rule; (3) a new list of three kinds of specific answers that count (a concrete finding from one setting, a claim naming the metric used, a claim relating at least two listed systems); (4) two more examples on an unrelated topic. Deliberately NOT changed: the "NOT answers" rules, the variant rule, and the rule that a claim about one of several listed systems is only partial, because the false "yes" rows (a technique overview taken as "parameters", Mamba versus Mamba-2, an accuracy gain taken as training efficiency) show where loosening would hurt.

### 15.3 Deployment and test (decision rule fixed before V2.1 is run)

1. Put the V2.1 text on the host (with the brace escaping), set `JUDGE_MODEL_ID=judge-v2-1` in `.env`.
2. Run `tests/eval_judge_prompt.py` on: the run 2 rows (`reports/tag_audit_labeled_run2.csv`), the older labeled files (round 1-3, export B, targeted, dropped, held-out), and compare each with the saved V2 results (`reports/judge_eval_judge-v2_*.json`).
3. Adopt V2.1 over V2 only if ALL of these hold:
   - On the 34 TEST rows: at least 2 more label-1 rows are called "yes" than under V2, and at most 1 more label-0 row is called "yes".
   - On the 254 older labeled rows (a regression check, not independent: V2 was shaped by them): pooled strict precision is not more than 0.03 below V2, recall is not below V2, and label-0 "yes" rows do not increase by more than 2.
   - Reported under both labelings (policy and strict multi-system); the decision uses the policy labels, the strict reading is shown next to it.
4. The test set is small (34 rows: 12 label 1, 15 label 0.5, 7 label 0): it can show a clear gain or a clear harm, not a small difference. If the results are within a few rows, V2.1 is not adopted on this evidence.

V2 baseline on the split (run 2 rows, `reports/judge_eval_judge-v2_20261105_1433.json`, no surrounding passage):

|                                                            | Judge "yes" | Strict precision | Lenient | Recall of label 1         | Label-0 rows called "yes" |
| ---------------------------------------------------------- | ----------- | ---------------- | ------- | ------------------------- | ------------------------- |
| Development (32 rows)                                      | 10          | 0.400            | 0.800   | 0.444                     | 2                         |
| **Test (34 rows)**                                   | 13          | 0.538 (7 of 13)  | 0.923   | **0.583 (7 of 12)** | **1**               |
| Test, strict labeling (multi-system aspects capped at 0.5) | 13          | 0.385            | 0.923   | 0.500                     | 1                         |

So the rule above, in numbers: V2.1 must call at least **9 of the 12** label-1 test rows "yes" (V2: 7) and at most **2** label-0 test rows "yes" (V2: 1). Command: `python tests/eval_judge_prompt.py --csv reports/tag_audit_labeled_run2.csv --split reports/v21_split.json --compare reports/judge_eval_judge-v2_20261105_1433.json`.

### 15.4 Result (2026-11-05): V2.1 is NOT adopted

Run with `JUDGE_MODEL_ID=judge-v2-1` on the same rows and under the same conditions as the V2 baseline (no surrounding passage); results `reports/judge_eval_judge-v2-1_20261105_1448.json` (run 2 rows) and `..._1451.json` (the 254 older rows). No errors.

| | V2 | V2.1 |
|---|---|---|
| **Run 2, TEST (34 rows)**: "yes" / label-1 found / label-0 called "yes" | 13 / 7 of 12 / 1 | 17 / **7 of 12** / **3** |
| Run 2, DEV (32 rows) | 10 / 4 of 9 / 2 | 15 / 6 of 9 / 4 |
| Run 2, all 66: strict / lenient / recall | 0.478 / 0.870 / 0.524 | 0.406 / 0.781 / 0.619 |
| Older 254 rows (233 unique): strict / lenient / recall | 0.650 / 0.913 / 0.817 | 0.585 / 0.911 / 0.878 |
| Older rows: label-0 rows called "yes" | 9 | 11 |

Decision rule (fixed beforehand): on the test rows at least 9 of 12 label-1 rows and at most 2 label-0 "yes"; on the older rows strict precision not more than 0.03 lower, recall not lower, label-0 "yes" at most 2 more. Outcome: test recall 7 of 12 (needed 9) **FAIL**; test label-0 "yes" 3 (limit 2) **FAIL**; older rows strict -0.065 (limit -0.03) **FAIL**; recall +0.061 pass; label-0 "yes" +2 pass.

What happened: V2.1 never removed a "yes" that V2 gave; it only added 29 (across all 320 rows): 7 were label-1 rows, 16 label 0.5 and 6 label 0, so 76% of what it added is not a direct answer. The development rows improved (recall 4 to 6 of 9) and the test rows did not (7 to 7): the changes fitted the rows they were written from. The precision guard did not work either: the claim that reversed its quote ("ten times fewer" parameters) went from "no" to "yes", and "results are reported" or "experiments are presented" claims became "yes" (rows 41, 44, 56). The 9B judge applies a loosened rule to claims it should still reject.

**What this says about the original problem.** On the aspects that list several systems, my own labels (policy: a claim relating at least two of the systems is an answer) mark only 4 of the 23 judged claims as direct answers; 14 are about one system alone and 5 are not answers. V2 found 2 of those 4 with no false "yes" on those rows; V2.1 found 3 of 4 with none either, so the aspect type is not where V2.1's extra errors come from (they come from the other aspects: label-0 "yes" 3 to 7). So the low coverage of the three-system sub-questions in run 2 is mostly a property of the evidence and of the aspect wording, not of a too strict judge: few retrieved claims directly compare two of the three systems.

**Decision.** Keep V2. Put the host back to the V2 text and `JUDGE_MODEL_ID=judge-v2`. Do not iterate on V2.1 with this model: each loosening adds mostly wrong "yes" verdicts. The levers left are upstream: aspects that name one comparison (A versus B on one dimension) instead of listing three systems, queries that look for comparisons, and Loop 2 to search for the missing comparisons.
