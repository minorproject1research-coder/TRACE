# Loop 2: query step (2026-11-05)

Built: `apps/api/agents/stage1_planner/gap_queries.py` (`generate(aspect, sub_question, tried_queries, anchor)`), `trace_llm_service.decompose_many`, and the optional `temperature`, `top_p`, `n`, `seed` fields on the host's `/decompose`. **Not wired into the pipeline**: nothing calls it yet, and the loop that runs the queries, parses, digests and judges again does not exist.

## How it works
1. The uncovered aspect becomes a standalone question (a full question of 6+ words is used as is; a phrase gets the sub-question as context).
2. The domain anchor is added to that question, then one `/decompose` call asks for 3 plans at temperature 0.8 (about 25 s, the same as one plan).
3. Search queries are interleaved across the plans, the anchor is applied, queries within bge cosine 0.90 of a query already tried (or already chosen) are dropped, the rest is ranked by similarity to the aspect question, and the best 4 are returned.
4. Any failure (server down, no usable plan, no embedder) returns fewer queries or none; it never raises. Zero queries means a known gap.

## Live check (`tests/gap_queries_live_check.py`, results in `reports/gap_queries_live.json`)
Criteria fixed before the first run: P1 at least 2 usable plans of 3; P2 at least 3 new queries per case; P3 at least 2 queries contain a content word of the aspect; P4 no returned query within 0.90 of a tried one. Six aspects: five that run 5 left uncovered (queries tried = the ones run 5 searched, from the log) and the RAG-creativity case (sub-question assumed, nothing tried).

| Run | Result |
|---|---|
| 1. no domain information | 5 of 6 cases met P1-P4; case D (compute and memory) returned 1 new query. **Case A, "What are the parameters of a transformer?", returned electrical-transformer queries** ("turns ratio, impedance, and leakage reactance of a transformer deep learning"). |
| 2. after adding the full domain context sentence | all criteria met, but only by P3's lenient rule: 0 of 4 queries for case A contained "parameter" (strict post-hoc check), the context sentence names SSMs and Mamba and pulled the planner back to the whole question. |
| 3. anchor only (final, kept) | A: 4 of 4 queries contain "parameter", no electrical drift. B: limitations (compute and memory, bias, generalization, robustness). C, E, F fine. **D: 2 new queries, P2 not met.** |

Changing from run 1 to run 3 was done after seeing results, on the same six cases, one sample each (the planner is random), so treat the ranking of the two variants as indicative, not proven.

## What case D shows
Stage 1 had already searched "computational and memory requirements for SSMs and transformers deep learning", almost the aspect's own wording, and still found no evidence. New planner queries are then mostly near-duplicates (the 0.90 filter drops them), so a second round of the same kind adds little. For such aspects the cheaper ladder steps (re-select chunks, next-ranked papers from the existing pool) should come first, and Loop 2 should stop with a known gap when fewer than ~3 new queries remain.

## Not measured
Whether the new queries find better papers. That needs the loop wired in and a labeled comparison of the sources before and after.

## Planner behaviour worth knowing
Even with the anchor, about a third of the returned queries are background queries ("transformers overview deep learning", "training efficiency definition"), which the similarity ranking only partly pushes down.
