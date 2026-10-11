# Report 2 - Pipeline runs: what each run showed, what was fixed, what the next run showed

Date: 2026-10-11. Format: for each run, the measured behaviour, the problems found, the fixes made afterwards, and
the result in the next run. Source: `logs/pipeline.log`, the Supabase tables of each run, and the saved scratch
analyses. Pipeline: planner -> [paper retrieval, web search] -> summarizer (Stage 3). Stages 4-5 are not built yet.

Caveats: single runs, different topics (runs 2 and 3 are not directly comparable to run 1), and the model server and
search APIs vary from run to run, so small timing differences are not meaningful.

## Summary table

|                                                     | Run 0                                      | Run 1                                           | Run 2                             | Run 3                                               |
| --------------------------------------------------- | ------------------------------------------ | ----------------------------------------------- | --------------------------------- | --------------------------------------------------- |
| Query                                               | RAG vs hallucination                       | same                                            | same                              | speculative decoding vs latency                     |
| Query id                                            | (earlier run)                              | `e882d2b4`                                    | `e1b91c81`                      | `b0f116cf`                                        |
| Date                                                | before 2026-10-10                          | 2026-10-10 ~13:57                               | 2026-10-10 15:02                  | 2026-10-11 16:07                                    |
| Planner                                             | hardcoded mock, 2 sub-questions, 8 queries | model server, 3 sub-questions, 9 queries (22 s) | 3 sub-questions, 9 queries (32 s) | 3 sub-questions, 9 queries,**[3,3,0]** (22 s) |
| Relevance judge                                     | off                                        | on, server                                      | on, server                        | on, server                                          |
| **Total time**                                | 16m 50s                                    | **25m 14s**                               | **13m 10s**                 | **12m 43s**                                   |
| Parsing time                                        | n/a                                        | 16m 35s (43 papers)                             | 5m 06s (24 attempted)             | 5m 36s (20 attempted)                               |
| Papers kept                                         | 40                                         | 43                                              | 42                                | 53                                                  |
| Papers with real full text (of parsed)              | 24 of 40                                   | 30 of 43                                        | 15 usable of 24 attempted         | 15 usable of 20 attempted                           |
| "All PDF URLs failed"                               | 12                                         | 7<br /><br />                                   | 6                                 | 4                                                   |
| Duplicate papers parsed twice                       | 3                                          | 1                                               | at least 1                        | 6                                                   |
| Verified findings (Stage 3)                         | 14                                         | 47                                              | 40                                | 47                                                  |
| Coverage "sufficient"                               | n/a                                        | True x3                                         | True x3                           | **False, False, True**                        |
| OpenAlex HTTP 429s                                  | n/a                                        | bursts                                          | 13 (2 queries abandoned)          | **0**                                         |
| Semantic Scholar queries abandoned                  | many                                       | many                                            | 16                                | 18                                                  |
| Stage 3 digest slots on abstract-only papers (of 9) | n/a                                        | 4                                               | 5                                 | 5                                                   |
| Judge rejections                                    | n/a                                        | 17 of 60                                        | 18 of 60                          | 7 of 60                                             |

---

## Run 0 - baseline before the model server (about 16m 50s)

What the pipeline did: the planner was a hardcoded mock (2 sub-questions); the relevance filter used the embedding
prefilter only (judge off); 40 papers were kept, 24 of them with real full text; all kept papers were parsed.

Problems at that point: 12 "All PDF URLs failed"; 3 duplicate papers; only 14 verified findings; the judge placeholder on Groq
(`llama-3.1-8b-instant`) no longer existed (HTTP 404); a failed judge call silently dropped the paper.

Background work that led to the next step: the relevance judge was benchmarked on 360 hand-labelled rows (12 models);
Qwen3.5-9B was chosen for production for latency.

Fixes before run 1:

- Planner and judge moved to the model server (`trace_llm_service.py`; `/decompose`, `/judge`): retries, circuit
  breaker, JSON repair for the 28 of 360 judge replies missing the final `}` (all 28 recovered).
- Groq fallback model changed to `openai/gpt-oss-120b`; a judge that fails now keeps the paper (fail open).
- The judge runs in parallel (`JUDGE_WORKERS`, default 8). Validation of the deployed judge: accuracy 0.914 / F1 0.938
  after reply repair (Ollama benchmark 0.908 / 0.934), 0.47 s per paper.
- Retrieval: OpenAlex added with a key pool and query sanitising (`?` and `*` caused HTTP 400); Semantic Scholar
  backoff made configurable.

## Run 1 - first run on the model server (25m 14s)

Result: end to end works, planner sensible (3 sub-questions, queries assigned by embedding), judge 60 papers with no
failures (17 rejected), 47 verified findings (up from 14), 30 of 43 papers with real text.

Problems found (ranked by cost):

1. **Parsing took 16m 35s (66% of the run)**; Stage 3 reads only 9 papers, so about 34 parses were wasted.
2. **Large PDFs block workers**: a 59 MB file held a worker about 2 minutes and then failed (so did a 15.7 MB one).
3. **Semantic Scholar enrichment ran before the filter** (about 3-4 minutes, 25 requests rate-limited, no S2 key).
4. **OpenAlex 429 bursts**: nothing limited concurrent requests.
5. **`relevance_score` was overwritten by the judge's confidence**: all kept papers had 0.90, 0.95 or 1.00, so
   `combined_score` was effectively just the reliability score and Stage 3 picked papers by reliability alone.
6. Stage 3 picked papers with no full text (4 of 9), coverage said "sufficient" for everything (threshold lenient),
   the log said "parsed 43/43" when only 30 had text, the filter log did not say which sub-question or why a paper
   was dropped, Groq rate-limited Stage 3 7 times, PDFFigures returned 400 for some PDFs.

Fixes made after run 1:

- `relevance_score` stays the embedding similarity; the judge is a pass/fail gate. Its verdict is stored
  (`judge_relevant`, `judge_confidence`, `judge_reason`, migration 008) and each rejection is logged with sub-question,
  similarity, confidence and reason.
- Parse only the top N papers per sub-question by `combined_score` (`PARSE_TOP_N_PER_SUBQUESTION`, default 5); a paper
  without usable text is replaced by the next in rank (`PARSE_MAX_ATTEMPTS_FACTOR`, default 2). New log line:
  "Parsing done: X usable full texts out of Y papers attempted".
- PDF size cap `MAX_PDF_SIZE_MB` (default 20): streamed download, abandoned when the declared or actual size is over
  the cap, no fallback sources tried for an oversized file.

## Run 2 - same query, after the filter / parsing fixes (13m 10s)

Result: time almost halved (25m 14s -> 13m 10s); parsing 16m 35s -> 5m 06s; `relevance_score` now spreads over
0.67-0.85; every sub-question reached 5 usable full texts; verdicts stored; rejections readable (18 of 60 rejected).

Timeline: planner 32 s, retrieval 4m 44s (Semantic Scholar waits dominate), filter 46 s, parsing 5m 06s, Stage 3 about 2 min.

Problems found:

1. **Stage 3 still read abstract-only papers**: 5 of 9 digest slots (Stage 3 ranks by `combined_score` and ignores
   whether text exists), while parsed papers such as a 236k-character survey were left unused.
2. **Semantic Scholar** again: 16 abandoned queries, 3 batch backoffs, about 4m 43s of the run.
3. **OpenAlex** still 13 HTTP 429s, 2 queries abandoned (no concurrency cap).
4. **The parsed table was wrong in many places** (see report 1): authors polluted with abstract text for 6 papers,
   a paper with 0 characters in all 49 sections, a journal name as title, 4 papers with no references found.
5. **The judge is strict against the topic string only**: all 8 rejections in "What is RAG?" were RAG-method papers
   with the highest similarity (0.81-0.87), and detection-in-RAG papers were rejected for the rates sub-question.
   Confidence is 0.95 for nearly every verdict, so it carries no signal.
6. Coverage still "sufficient" for all three, 9 of 24 parse attempts gave no text (DOI landing pages, 403s).

Fixes made after run 2:

- OpenAlex: at most `OPENALEX_MAX_CONCURRENT` requests in flight (default 2), backoff sleeps outside the semaphore.
- Citation enrichment moved after the relevance filter (`enrich_papers`, once per unique arXiv id; `min_citations`
  moved with it).
- **Parser rewrite** (`markdown_parser.py`, report 1): reference-flag bug fixed, heading noise filtered, abstract
  recovery, API metadata wins for title / authors / abstract, `PARSER_VERSION` added.
- (Decided not to change: judging against the detail questions as well as the topic.)

## Run 3 - new query, after the OpenAlex / enrichment / parser fixes (12m 43s)

Query: "How effective is speculative decoding at reducing LLM inference latency?"

Result: OpenAlex 429s **13 -> 0**; citation enrichment about 1m 40s -> 37 s (13 papers); parser output clean (authors
from the API, abstracts without dashes, every parsed paper with real section text, 20-243 references); 53 papers
kept, 47 verified findings, and coverage honest for the first time (False, False, True). Judge: 7 rejections out of
60, all sensible (a quantum-computing paper, a sensor-latency paper, a layer-pruning paper).

Timeline: planner 22 s, retrieval 3m 01s, filter 42 s, enrichment 37 s, parsing 5m 36s, Stage 3 2m 24s.

Problems found:

1. **Stage 3 reads abstract-only papers again**: 5 of 9 digest slots ("Towards Optimal Speculative Decoding" in two
   sub-questions, "Hybrid Speculative Decoding in RAG", "Formal schedulability analysis...", "Optimizing LLM Inference:
   Metrics that Matter"), while a parsed 140k-character survey was left out.
2. **Semantic Scholar search takes about 3 minutes** (18 queries abandoned at about 10 s each, no API key) and
   contributes almost nothing.
3. **Parsing is spent on papers that cannot be downloaded**: 4 "All PDF URLs failed" and 8 failed downloads, almost
   all `doi.org` landing pages and publisher 403s. arXiv papers parse reliably but rank low on reliability, so
   DOI-only OpenAlex papers are tried first.
4. **Planner query assignment**: [3, 3, 0]. All 9 planner queries matched the first two sub-questions by embedding
   and 3 were dropped by the cap of 3, so the core sub-question ("How does speculative decoding affect latency?") got
   Groq expansion instead of planner queries.
5. **Six papers belong to more than one sub-question** and were parsed twice.
6. The third sub-question's shortlist is capped at 20 of 62 qualifying candidates and all 20 passed the judge, so the
   cap may hide relevant papers.

Fixes made after run 3 (built, not yet run):
- **Stage 3 paper selection**: papers with usable parsed text are ranked first, then by `combined_score`; each digest records
  its `evidence_level` (full text / abstract / web snippet) and coverage counts abstract-only and web-snippet sources as half
  a source (migration 010). On the run-3 data the abstract-only picks among the 9 paper slots fall from 5 to 0, and the real
  Stage 3 node ran end to end on that data (9 full-text digests, 6 web-snippet digests, 41 verified findings).
- **Docling OCR off** (report 3): the pipeline sent a request field Docling ignores, so every paper was converted with OCR
  on. With `do_ocr=false` the same 5 papers took 70 s instead of 158 s with identical text; scanned PDFs are retried
  with OCR. Running more Docling containers did not help on the dev machine.

- **Parse cache** (`PARSE_CACHE`): a paper already parsed (same arXiv id, else DOI, else exact title) under any
  earlier query is copied instead of being downloaded and parsed again; a paper being parsed by another task of the
  same run is waited for rather than downloaded twice. Only rows with `parser_version >= PARSER_VERSION` and 3000+
  characters of full text are reused. Migration 009 (`parser_version`, lookup indexes) and
  `scripts/backfill_parsed_papers.py` (rebuild old rows from stored Markdown, no Docling) support it. Offline tests pass
  (duplicate paper downloaded once, lookup failure falls back to a normal parse, cache can be disabled). The
  version-filtered Supabase lookup could not be tested until migration 009 is applied.

## Run 4 - same query as run 3, after the parser / cache / Stage 3 / OCR changes (16m 49s)

Query id `2ba16f1f` (2026-10-11 19:28), same speculative-decoding question as run 3. 72 papers kept across **4**
sub-questions, 20 usable full texts of 25 papers attempted.

Timeline: planner 28 s, retrieval 4m 00s, filter 1m 02s, enrichment 21 s, parsing 5m 23s, Stage 3 5m 31s.

Whether each earlier change worked (checked in the log and in the database):
- Migrations 008 / 009 / 010 applied (judge verdict stored for 72 of 72, `parser_version=1` on all parsed rows,
  `evidence_level` and `full_text_source_count` filled); no "missing column" warnings.
- OpenAlex 429s: 0 (second run in a row); citation enrichment after the filter: 14 papers in 21 s, `citation_count`
  filled for 72 of 72; top-5 parsing with replacement reached 5 usable texts in all four sub-questions.
- Parser output clean: no polluted author lists, no abstract with a leading dash, sections and references for 20 of 20
  parsed rows, median 75% of the text inside sections.
- Stage 3 full-text-first: all 12 paper digests were `full_text` (run 3: 5 of 9 abstract-only). Coverage was "not
  sufficient" for two sub-questions (1 and 2 detail questions uncovered), "sufficient" for two.
- Judge: 8 rejections out of 80, all reasonable.

What did not work as hoped:
1. **Cross-run parse cache did nothing**: the 5 cache hits were duplicates inside the run. The previous run's 16 parsed rows
   have `parser_version = NULL` (the backfill script had not been run), although 51 of the 72 papers were also in the
   previous run (about 15 avoidable parses).
2. **OCR off gave no visible speed-up in the pipeline**: 5m 23s for 20 real parses (about 16 s each) against 5m 36s for 20
   in run 3. On the host a conversion took 27 to 37 s with three running at once. The 2.2x measured on the laptop is not
   confirmed on the host (host benchmark pending).
3. **The planner produced 4 sub-questions, two of them near-duplicates** (topic similarity 0.97). The same three papers
   were digested twice, the run had 72 papers instead of about 53, and Stage 3 took 5m 31s with 20 Groq 429s.
4. One Docling 504 Gateway Timeout from the host after only 27 s (not the 120 s wait limit), one paper still empty after the
   OCR retry, 3 "All PDF URLs failed" (DOI landing pages and publisher 403s), 2 PDFFigures errors (400, 500).
5. Semantic Scholar search again took about 4 minutes (24 abandoned queries). The PDF size cap was not exercised.

Fixes made after run 4:
- **Near-duplicate sub-questions are merged** in the planner step (`SUBQUESTION_MERGE_SIMILARITY`, default 0.92). On the run 4
  plan it turns 4 sub-questions into 3 and folds the second copy's detail questions into the first; plans without a
  duplicate (runs 2 and 3) are unchanged. Not yet seen in a full pipeline run.

## Run 5 - same query, parse cache warm, Stage 3 and planner merge in place (10m 09s, the fastest so far)

Query id `823e1040` (2026-10-11 20:06). 53 papers kept across 3 sub-questions, 15 usable full texts of 17 attempted.

| | Run 3 | Run 4 | Run 5 |
|---|---|---|---|
| Total time | 12m 43s | 16m 49s | **10m 09s** |
| Sub-questions | 3 | 4 (two near-duplicates) | 3 |
| Retrieval | 3m 01s | 4m 00s | 3m 01s |
| Citation enrichment | 37 s | 21 s | 65 s (two Semantic Scholar 429 backoffs) |
| **Parsing** | 5m 36s | 5m 23s | **1m 03s** (11 parse-cache hits, 6 real parses) |
| Stage 3 | 2m 24s | 5m 31s | 3m 52s (13 Groq 429s) |
| Papers whose digest was abstract-only | 5 of 9 | 0 of 12 | 0 of 9 |
| Verified findings | 47 | 79 | 51 |
| Coverage sufficient | no, no, yes | no, no, yes, yes | no, no, yes |
| OpenAlex 429s | 0 | 0 | 0 |

What worked (checked in the log and the database):
- **The parse cache works across runs**: 43 of the 53 papers were also in run 4, and 11 parses were copied (the first three within a
  second of parsing starting, before any download). Parsing fell from 5m 23s to 1m 03s. Run 3's unversioned rows were not
  reused, as designed; run 4's rows (`parser_version = 1`) were.
- Stage 3 again used full text for all 9 paper digests; judge columns stored for 53 of 53, citation counts for 53 of 53, parser
  output clean (no polluted authors, no dash abstracts, sections and references on all 15 parsed rows); 7 judge rejections of 60, all
  reasonable. No Docling gateway timeouts this time; one OCR retry, one empty Docling result, one PDFFigures 400, one "All PDF URLs failed".

Not exercised: the sub-question merge (the planner returned three distinct sub-questions, all with planner queries, [3, 3, 3]) and the
PDF size cap (no oversized PDF).

Observed problems:
1. **Semantic Scholar is now about 40% of the run**: roughly 3 minutes of search (17 abandoned queries) plus 65 s of citation enrichment.
2. **Some digests keep few verified findings**: "Speculative Speculative Decoding" 1 of 4 and "A Theoretical Perspective for Speculative
   Decoding" 2 of 4 (math-heavy papers); the other digests are 3/4 to 5/5. A quote that does not match its chunk is dropped, so these
   papers contribute little. Cause not yet investigated (likely equation or symbol text in the quote).
3. Stage 3 still takes 3m 52s for 15 digests (13 Groq 429s).
4. Whether OCR-off speeds up the host cannot be read from this run (most papers came from the cache).

Fixes made after run 5:
- **Groq key pool + parallel Stage 3 digests** (`groq_pool.py`, report 4 section 8): two independent keys, `Retry-After`-aware
  retries, one worker per key. Stage 3 is bounded by tokens per minute (about 42k tokens per run), so the gain is moderate (about 2.5 to 3.5
  minutes instead of 3m 52s to 5m 31s), not 2x.

## Remaining backlog (ordered)

1. ~~Stage 3: choose papers with usable text first, then rank by `combined_score`.~~ Done (see above); not yet seen in a full pipeline run.
2. Skip Semantic Scholar search when there is no API key, or get a Semantic Scholar key (search about 3 min + enrichment about 1 min).
3. Rank papers with a direct PDF link ahead of DOI-only ones when choosing what to parse.
4. Planner: guarantee every sub-question gets planner queries (balanced assignment).
5. Per-key OpenAlex concurrency / rate limits (two keys are available).
6. Query-level caching (reuse the plan and papers of a very similar earlier question); needs a stored question
   embedding and a high similarity threshold, because near-identical wording can flip the meaning ("reduces" vs "increases").
7. Raise the coverage threshold and consider judging against detail questions as well as the topic.
8. Smaller: PDFFigures 400s, Groq 429s in Stage 3, the shortlist cap of 20, a regression test for the parser.

Benchmark follow-ups (separate track): rerun GLM-5.3, nemotron-lightning, nemotron-ultra, verify kimi-k3, flip or drop
`sq29_09` and re-publish the dataset.
- Investigate unverified quotes in math-heavy papers (1 of 4 and 2 of 4 verified in run 5) and the Groq 429s in Stage 3.
