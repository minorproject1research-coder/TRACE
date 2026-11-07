# Stage 4 output: what Stage 5 and the web app may rely on

Stage 4 (fact checking across sources) reads the evidence of Stage 3 and writes two tables and one summary. This file is the contract for whoever reads them (the API report today, Stage 5 later). Design and history of Stage 4: `docs/reports/TRACE Stage 4 Fact Checking, Handoff Report.md`; measurements: `docs/reports/20_stage4.md`.

## When it runs
`FACTCHECK=true` on the server. Off by default: it needs the NLI model (1.7 GB) and a few hundred small LLM calls per sub-question. A run without it has no rows in the two tables, and the API reports `stages.factcheck = "not_run"`.

## What a label means
Stage 4 groups the verified findings of Stage 3 that state the same thing (a "claim"), checks that each quote supports its claim, looks for sources that assert the opposite, and labels each claim:

| Label | Rule | What it does NOT mean |
|---|---|---|
| `supported` | at least 2 DISTINCT documents state the claim with a supporting quote, and their evidence weight is at least 1.5 (a full text counts 1.0, a web snippet or abstract 0.5; the same paper found as web page and as paper counts once), and no conflict outweighs them | that the claim is true: two papers can be wrong, or one can have copied the other |
| `unverified` | the claim rests on one document (or on too little weight) | that it is false: it is simply not confirmed by a second source |
| `contradicted` | another document asserts the opposite about the same subject, property and setting, and that conflict is at least as strong as the support | that the claim is false: the other source may be the wrong one |
| `contested` (flag, not a label) | a `supported` claim that also has a weaker conflicting source | |

`confidence` is a noisy-or of the source weights (reliability times evidence level), capped at 0.95; an `unverified` claim never exceeds 0.5. It is a ranking number, not a probability.

Rules that must hold in every reader (they come from the handoff report): never show an `unverified` claim as a fact; show a `contradicted` or `contested` claim together with the source that disagrees; every statement shown to a user needs its quote and source.

## Tables (Supabase)
`fact_claims` (one row per checked claim; rewritten as a whole for a run, so reading by `query_id` always gives one consistent result):

| Column | Type | Meaning |
|---|---|---|
| `query_id`, `sub_question_id` | uuid, text | the run and the sub-question |
| `claim` | text | the representative sentence of the group (the strongest source's wording) |
| `label` | text | `supported` / `unverified` / `contradicted` |
| `confidence` | float | see above |
| `support_doc_count`, `contra_doc_count` | int | distinct documents for / against |
| `contested` | bool | see above |
| `evidence` | jsonb | list of `{source_id, source_title, quote, relation ('supports' or 'contradicts'), reliability, evidence_level ('full_text' / 'abstract' / 'web_snippet'), prob, via}`; `via = "stage3_judge"` when the quote's support was already established by the independent Stage 3 judge, otherwise `null` (NLI or the Stage 4 support judge) |

`contradictions` (one row per pair of claims that disagree): `claim_a`, `claim_b`, `source_a_title`, `source_b_title`, `quote_a`, `quote_b`, `prob`, `reason` (the judge's one sentence), `query_id`, `sub_question_id`.

## API
`GET /api/research/{id}/report` (see `docs/API_HANDOFF.md`): per sub-question `factCheck` (`counts`, `claims` sorted contradicted first then supported then unverified, `disagreements`), `totals.factChecked`, `stages.factcheck` (`completed` / `not_run`), and extra lines in `limitations`. During a run: stage `factcheck` and steps of the lane `factcheck` (`claims`, `clusters`, `support`, `conflicts`, `store`), with `subQuestion` / `subQuestions` counters.

## Summary in the graph state
`fact_summary[sub_question_id] = {supported, unverified, contradicted, total, digests, claims_loaded, contested, disagreements, judge_calls, judge_cache_hits, judge_failures, support_from_stage3, missing_evidence, needs_replan}` or `{"error": ...}` when that sub-question failed. (the sum over sub-questions is `judgeFailures` in the data of the `stage_completed` event of stage `factcheck`) `judge_failures > 0` means some judge calls could not be answered (usually the Groq rate limit); every such call fails closed, so the labels are cautious but incomplete (fewer `supported`, fewer conflicts). `needs_replan` is only a flag; the replan loop (LOOP 3) is not built.

## Known weaknesses a reader should not hide
- The thresholds (similarity gates, NLI minimum, judge confidences) were checked against a small labeled set written by the assistant, not by a person (`reports/stage4_eval_set.json`, `tests/stage4_eval.py`).
- `supported` needs two documents that state the SAME specific claim; papers rarely word a result alike, so most claims stay `unverified`.
- The conflict check found no real conflict in the data tried so far; its precision is measured on constructed cases for the positives.
