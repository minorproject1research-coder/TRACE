# Report 4 - Stage 3 (summarizer) changes: full-text-first selection, evidence levels, weighted coverage

Date: 2026-10-11. Scope: what was wrong in Stage 3, what was changed, how it was tested, and what the first real run
showed. Run history is in `02_pipeline_runs_report.md`.

Files changed: `apps/api/services/db_service.py` (`get_papers_for_stage3`, `write_digests`, `write_coverage`),
`apps/api/graph/nodes/summarizer_node.py`, `apps/api/agents/stage3_summarizer/coverage_check.py`,
`db/migrations/010_add_evidence_level_to_digests.sql` (new), `.omo/PROJECT_ARCHITECTURE.md`.

## 1. How Stage 3 works (unchanged parts)

For each sub-question `summarizer_node` takes the top `MAX_PAPERS` (3) papers and top `MAX_WEB` (2) web sources (snippets of
200+ characters). For each source: `chunk_selector` splits the text into 300-word chunks (reference, acknowledgement and
appendix sections skipped) and keeps the 5 most similar to the sub-question (bge); `digest_generator` asks Groq
`openai/gpt-oss-120b` for findings with exact quotes; `quote_verifier` marks a finding `verified` only if its quote is found
in the chunks (fuzzy ratio >= 92); `coverage_check` decides whether the sub-question has enough evidence. Results go to the
`digests` and `coverage_results` tables.

## 2. The problem

Papers were ranked by `combined_score` (similarity x reliability) only. Parsing covers just the top 5 papers per sub-question
and about a quarter of those fail (DOI landing pages, publisher 403s, empty Docling output), so the highest-scoring papers
were often ones with no parsed text. For such a paper `chunk_selector.build_chunks` silently falls back to the abstract as the
single chunk; the digest is then built from one abstract and its quotes are verified against that same abstract, so they pass
trivially.

Measured in the earlier runs (paper digest slots, of 9 per run):

| Run | Abstract-only paper digests |
|---|---|
| 1 (RAG, `e882d2b4`) | 4 of 9 |
| 2 (RAG, `e1b91c81`) | 5 of 9 |
| 3 (speculative decoding, `b0f116cf`) | 5 of 9 |

Run 3 example: for "How does speculative decoding affect LLM inference latency?" only 5 of the 20 kept papers had full text, yet
the top-ranked paper (score 0.53) had none and was used, while a parsed 140,000-character survey was left out.

Consequences: the "verified findings" count and the coverage check treated an abstract-only source like a full paper (three
abstracts were enough for "sufficient"), and nothing in the stored data said which findings came from which kind of evidence.

## 3. What was changed

### 3.1 Full-text-first paper selection (`db_service.get_papers_for_stage3`)
- Each paper gets `has_full_text` = its parsed `full_text` has at least 3000 characters (`STAGE3_MIN_FULL_TEXT_CHARS`).
- Papers are sorted by `(has_full_text, combined_score)` descending: parsed papers first, best score first within each group.
  Abstract-only papers fill slots only when there are fewer than 3 full-text papers.

### 3.2 Evidence level on every digest (`summarizer_node`, migration 010)
- Each digest row stores `evidence_level`: `full_text`, `abstract` (a paper without usable text) or `web_snippet`.
- The Stage 3 log line now reads, for example, `5 digests (3 from full text), 20 verified findings, coverage sufficient=False`.
- Migration 010 adds `digests.evidence_level` and `coverage_results.full_text_source_count`.
- The two columns are optional: `write_digests` / `write_coverage` go through `_insert_with_optional_columns`, which on a
  "column missing" error stores the rows without them and logs a warning, so a forgotten migration never loses Stage 3 results.

### 3.3 Weighted coverage (`coverage_check`)
- Distinct sources with at least one verified finding are weighted by evidence level: full text 1.0, abstract 0.5, web snippet 0.5
  (`EVIDENCE_WEIGHT`). A sub-question is sufficient when the weighted total is at least `min_sources` (3) **and** every detail
  question matches a verified claim (bge similarity >= `detail_sim`, 0.6, unchanged).
- The result now also returns `full_text_source_count`; `source_count` is still the number of distinct sources.
- Rows without an `evidence_level` (older data) count as full text, so existing stored digests behave as before.

| Sources with verified findings | Weighted total | Sufficient (details covered) |
|---|---|---|
| 3 full text | 3.0 | yes |
| 3 abstract-only | 1.5 | no |
| 3 web snippets | 1.5 | no |
| 2 full text + 2 abstract | 3.0 | yes |
| 3 older rows without a level | 3.0 | yes |

## 4. Testing

1. **Selection, on the stored run 3 data (read-only)**: abstract-only papers among the 9 picks fell from **5 to 0**. For the first
   sub-question the old picks were two unparsed papers (scores 0.60 and 0.49) plus one parsed paper; the new picks are three
   parsed papers ("Speculative Speculative Decoding", "Tutorial Proposal", "Faster Cascades").
2. **Coverage rule**: the five cases in the table above all behave as shown (unit assertions).
3. **End to end**: the real Stage 3 node ran on the run 3 data with Groq and the database writes stubbed out (so nothing was
   duplicated): 9 full-text digests and 6 web-snippet digests, 41 verified findings, coverage not sufficient / not sufficient /
   sufficient, and the new fields present in the rows.
4. **First real pipeline run with the change (run 4, `2ba16f1f`)**: all **12 paper digests were `full_text`**, plus 8 `web_snippet`
   digests; every sub-question had 3 full-text sources; verified findings per sub-question 20, 22, 18, 19 (79 in total);
   coverage insufficient for 2 sub-questions (1 and 2 detail questions uncovered) and sufficient for 2. The migration columns
   were populated and no "column missing" warning appeared.

## 5. Results compared with before

| | Before (runs 1 to 3) | After (run 4) |
|---|---|---|
| Abstract-only paper digests | 4 to 5 of 9 | **0 of 12** |
| Digest rows say what they are built from | no | yes (`evidence_level`) |
| Three abstracts count as "sufficient" | yes | no |
| "Insufficient" coverage in a run | 0 to 2 of 3 | 2 of 4, for lack of covered details |

## 6. Limitations and open items

- **"Has full text" is a length test** (3000 characters). A parse that captured only a first page could still pass.
- **The weights (1.0 / 0.5 / 0.5) and `min_sources=3` are judgement, not calibrated** against any labelled data.
- **A finding is "verified" when its quote exists in the supplied chunks**, not when it is true; the check says nothing about
  whether the paper's claim is correct (that is Stage 4's job).
- **The detail-question threshold (0.6) is unchanged** and is still lenient.
- **A paper kept under two sub-questions is still digested twice.** In run 4 this doubled the digests for a duplicated sub-question
  (3 papers x 2); the planner-side merge of near-duplicate sub-questions now removes the common cause.
- **Stage 3 time is dominated by Groq rate limits**: 5m 31s in run 4 (4 sub-questions, 20 HTTP 429s) against 2m 24s in run 3
  (3 sub-questions, 7 429s). The change adds no model calls, and it does not reduce them either.
- Still limited to 3 papers and 2 web sources per sub-question (`MAX_PAPERS`, `MAX_WEB`), a free-tier choice.
- Abstract-only papers can still be chosen if a sub-question has fewer than 3 parsed papers (they are then labelled `abstract`).

## 7. Next steps

1. Run the pipeline again to confirm the Stage 3 time with 3 sub-questions (after the sub-question merge).
2. Consider reusing a digest when the same paper is selected for near-identical sub-questions, and a request-rate limit or
   backoff tuned for the Groq free tier.
3. Revisit `detail_sim` (0.6) and the evidence weights once there is labelled data on what counts as "sufficient".
