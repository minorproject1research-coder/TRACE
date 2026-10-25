# TRACE Stage 3 Coverage Validation Report

Prepared 24 October 2026. Covers the Loop 2 (insufficient coverage) work, the Stage 3 coverage fixes, three tag-precision audits, and the decision to add an independent judge pass.

## 1. Summary

We set out to make Loop 2 regenerate queries for uncovered detail questions. While preparing it we found that Stage 3 was reporting many details as uncovered even though verified evidence existed. We fixed that, but the fix over-corrected: the tagging that now decides coverage is noisy and unreliable. Three labeled audits show precision of the tags that count toward coverage between 50% and 69% (strict) and 81% to 94% (lenient), and it varies from run to run. The conclusion is that the generator should not judge its own evidence. We are adding an independent judge pass, served through the existing vLLM wrapper, which decides whether each candidate finding is supported by its quote and directly answers the aspect.

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
- Verdicts are cached so reruns are stable.
- New wrapper endpoints `/verify_evidence` and `/verify_evidence_batch` serve the judge.
- Before enabling by default, the judge is evaluated against the roughly 125 labeled audit rows, and we require high precision on its "yes" verdicts.

## 7. Open items

- Build the judge pass (pipeline) and the wrapper endpoints.
- Fix `tests/negative_control_coverage.py`, which still uses the old `generate_digest` signature. The negative control (a detail the papers cannot answer must come back uncovered) has not run yet and is the only direct test that the stricter rule can still return "uncovered".
- Make digest JSON parsing robust (retry once, log failures per sub-question). Silent failures mean coverage is computed on fewer sources.
- Build Loop 2 using `uncovered_aspects` as input. One real candidate already exists: "How does retrieval-augmented generation constrain the creativity and diversity of large language models?".

## 8. Caveats

- Labels in all audits were assigned by an LLM (Claude) from claim, quote, and aspect text, not by a human. Hand-check disagreements, especially the 0.5 labels.
- Samples are small (16 `full` tags per round), so differences of about 10 to 12 points are within noise.
- The judge pass is untested until it is evaluated against the labeled rows and a fresh audit.
