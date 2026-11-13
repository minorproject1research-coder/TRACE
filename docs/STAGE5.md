# Stage 5: the written report

Stage 5 reads what Stage 4 labelled and writes a cited report: an overview and executive summary, an introduction, one section per sub-question (with a "Sources disagree" part and the evidence gaps), the limitations, a conclusion and a reference list. It does not decide what is true and it does not add anything that Stage 4 did not hand it. **Python decides what may be said, with which wording and with which citations; the language model only phrases one sentence per small group of claims and compresses the finished sentences into a summary.**

Related files: the contract of the stored report is `docs/STAGE5_OUTPUT.md`; the endpoints are in `docs/API_HANDOFF.md`; the labels it reads are in `docs/STAGE4_OUTPUT.md` and `docs/STAGE4.md`; open problems are listed in section 9 below. The user's plan is `docs/TRACE_Stage_5_Implementation_Plan_Short.docx`.

## 1. Where it sits
planner -> retrieval -> Stage 3 -> Stage 4 -> **Stage 5**.
It runs once per run, after Stage 4, unless `STAGE5=false`, and only when Stage 4 ran (with `FACTCHECK` off there are no labels and the stage stays "not run", with a note `stage5_skipped`). It never fails a run: an error gives `status = failed` and a minimal report, the evidence of Stages 3 and 4 is already stored. Code: `apps/api/graph/nodes/report_node.py` (the node), `apps/api/agents/stage5_report/assembler.py` (the whole build), and the modules below.

## 2. The policy (agreed with the user)
The Stage 4 label never changes. The **tier** decides the wording, never whether something is "true".
| Tier | Stage 4 input | Wording | Where it appears |
|---|---|---|---|
| supported | label `supported`, not contested | "Two sources report that ..." (two or more documents state it) | section text |
| partly | label `partially_supported`, not contested | "One source reports X, while another makes a related point that Y" (both wordings quoted) | section text, marked *(partly supported)* |
| single | label `unverified`, not contested, after the filters below | "One study reports that ..." / "According to one source, ..." (attributed, never as fact) | section text, marked *(one source, not confirmed)* |
| disputed | label `contradicted`, or `contested = true` (any label) | never in prose | "Sources disagree": both sides with their quotes and references; never "X is false" |
| gaps | Stage 3 coverage, filtered claims, Stage 4 off or failed | Python templates | "Evidence gaps" of a section and the limitations |

Filters of the single tier (all env-tunable, section 5): at most 3 claims per document in the whole report; the single supporting quote must be full text or confirmed by the Stage 3 judge (`via = stage3_judge`); an optional scope check (the claim must not say more than its quote; needs the NLI model, off by default); at most 8 single claims per section, preferring different documents, then higher confidence, then full text. A filtered claim is counted in the gaps, never silently lost.

Sections are the planner's sub-questions in order (title = the sub-question, the detail questions as the checklist). There is no LLM outline. The introduction is a template from the question, the domain context (only available inside a run), the sub-question list and the counts. The limitations are a template from the tier counts, the filtered counts, the share of single-source findings, fallback and dropped sentences, the sections with nothing eligible, and the Stage 4 caveats, plus one standing caveat: the conflict check compares only the most similar pairs and is automatic, not reviewed.

## 3. Steps (`assembler.build_report`)
| # | Step (progress step) | Code | What happens | Model |
|---|---|---|---|---|
| 1 | sections | `loader.from_state` / `load_inputs`, `tiers.build_claims`, `make_jobs`, `disputed_for_section` | Inputs as one dict (claims, contradictions, coverage, sources). Stable claim ids (hash of sub-question id and claim text). Tiers and filters. Jobs of one tier and one section: supported up to 3 claims, partly 1, single up to 2 claims of the SAME document (so "One study reports ..." cites one document; changed 2026-11-13 after run 36). "Sources disagree" pairs, linked to claims by text. Gap sentences. | none (the scope check, if on, uses NLI) |
| 2 | write | `writer.write_sections` | One sentence per job, all sections in parallel (`STAGE5_WORKERS`), strict JSON `{job_id, text, claim_ids}`. A section whose prompt would exceed `STAGE5_MAX_PROMPT_TOKENS` is split into several calls. Valid replies are cached. | Groq `openai/gpt-oss-120b`, purpose `stage5_write` |
| 3 | (inside write) check | `grounding.make_check` = `validators.check_sentence`, then `grounding.entails` | Free Python checks first: ids belong to the job, no URL / [n] / author-year / connective, tier wording, every number, name, negation, direction and scope word is in the claims or their quotes, one sentence of at most 60 words. Then NLI (entailment >= 0.5, contradiction >= 0.5 is a hard reject) and, for what NLI rejects, one judge call (confidence >= 0.7). Fail closed. | NLI on CPU, Groq judge `stage5_check` |
| 4 | retry, fallback | `writer._run_group` | A failed sentence is asked again once with the Python-written reasons (`STAGE5_RETRIES`); still failing -> `hedging.fallback_sentence` (the claim's own wording behind the tier's opener, origin `fallback`). | same model |
| 5 | validate | `assembler._body_problems` | Claim ids exist, the tier equals the weakest tier of the sentence's claims, text not empty. A failing sentence is dropped and a warning added. | none |
| 6 | summary | `summary.write_summary`, `write_conclusion` | Written LAST, from at most 12 validated sentences (3 per section, best tier first). The model never sees evidence; each summary sentence names the numbered sentences it compresses. `validators.check_summary`: numbers and names must be in those sentences, the hedge may not be stronger than the weakest of them, 3 to 5 (conclusion 3 to 4) sentences; the conclusion may use connectives. One retry, then an extractive template (the best sentences copied word for word). One template sentence about the single-source share is appended only when the validators accept it. | Groq, purpose `stage5_summary` |
| 7 | references | `references.ReferenceBook` | Numbered by FIRST CITATION IN RENDER ORDER (summary, sections, conclusion) in one pass over the finished text. One reference per document (the same paper under two source ids, or as paper and web page, is one). A sentence cites the documents of its claims' supporting evidence (partly: both documents); a disagreement cites both sides. | none |
| 8 | final checks | `assembler.final_checks` | Claim ids exist, ref numbers exist, no empty section without a gap message, no [n] in a text field, summary numbers and names are in the body. A failure is a warning and sets `completed_with_warnings`. | none |
| 9 | store | `db_service.write_written_report` | One row per run in `written_reports` (replaced on a rerun). A missing function or table costs the stored copy, not the run. | none |

Citations: the model never writes a `[n]`, a URL, an author or a year; the validators reject them. The text fields of the report never contain `[n]`: the Markdown renderer (`assembler.render_markdown`, which works from the stored report dict alone) adds the markers before the final full stop.

## 4. Status
| Status | When |
|---|---|
| `completed` | no fallback sentence, no dropped sentence, no warning |
| `completed_with_warnings` | any fallback or dropped sentence (also in the summary), or a failed final check; the reasons are in `warnings` and the limitations |
| `insufficient_evidence` | nothing eligible to write about: Stage 4 failed or produced no claims, or every claim is disputed or filtered. No model call. The report still lists why in the limitations and the gaps |
| `failed` | an internal error (text in `warnings`); the run is not failed |

## 5. Settings (`.env`, defaults in `.env.example`; all read at call time)
| Setting | Default | Meaning |
|---|---|---|
| `STAGE5` | true (since 2026-11-13) | switch for the whole stage (1/true/yes/on) |
| `STAGE5_MODEL` | `openai/gpt-oss-120b` | the writer model (through `groq_pool`) |
| `STAGE5_REASONING_EFFORT` | low | low / medium / high |
| `STAGE5_MAX_OUTPUT_TOKENS` | 2500 | `max_completion_tokens` of one call (reasoning tokens count; 1500 was cut off in the first live run) |
| `STAGE5_MAX_PROMPT_TOKENS` | 4500 | a section above this (about 4 characters per token) is split into several calls |
| `STAGE5_TEMPERATURE` | 0.2 | |
| `STAGE5_RETRIES` | 1 | retries of a failed sentence with the Python reasons before the fallback sentence |
| `STAGE5_WORKERS` | 3 | sections written at the same time |
| `STAGE5_CACHE`, `STAGE5_CACHE_DIR` | true, `.cache/stage5` | validated model replies, keyed on model, template version, effort, max tokens and the rendered prompt; re-validated on a hit; a failure is never cached |
| `STAGE5_RATE_WAIT_MAX` | 300 | a pool-wide rate limit of at most this many seconds is waited out (like `STAGE4_RATE_WAIT_MAX`) |
| `STAGE5_RATE_RETRIES` | 2 | how many times a call waits and asks again |
| `STAGE5_BREAKER_SECONDS` | 300 | after a limit that cannot be waited out the model is not asked again for this long (the sentences fall back at once) |
| `STAGE5_MAX_PER_SOURCE` | 3 | single claims per document in the whole report (below 1 = no cap) |
| `STAGE5_SINGLE_NEEDS_STRONG` | true | the single supporting quote must be full text or `via = stage3_judge` |
| `STAGE5_SCOPE_CHECK` | false | the claim must not be broader than its quote (NLI quote -> claim; loads the NLI model) |
| `STAGE5_MAX_SINGLE_PER_SECTION` | 8 | single claims per section (below 1 = no cap) |
| `STAGE5_ENTAIL_MIN` | 0.5 | NLI entailment needed to accept a sentence (also the scope check) |
| `STAGE5_CONTRA_MIN` | 0.5 | NLI contradiction that rejects a sentence without asking the judge |
| `STAGE5_JUDGE_MIN` | 0.7 | judge confidence needed to accept a sentence that NLI did not accept |
| `STAGE5_NLI_MAX_PREMISES` | 8 | single premises per sentence sent to NLI (1 to 1.7 s per pair on the CPU), plus their concatenation |
| `STAGE5_NLI_MAX_CHARS` | 2000 | the concatenated premise is cut here |
| `STAGE5_MAX_SENTENCE_WORDS` | 60 | word limit of one sentence (validators) |

## 6. What it costs (estimate, not measured yet)
- **Groq tokens: about 50,000 in about 12 calls** for a run of 4 sub-questions with the defaults (one write call of up to 4,500 prompt tokens plus up to 1,500 output tokens per section, about 3 more for sections that must be split or retried, one summary call and one conclusion call of a few hundred tokens each). Purposes in the token meter: `stage5_write`, `stage5_summary`, `stage5_check` (judge re-checks of rejected sentences). **This is an estimate from the prompt sizes; replace it with the measured figure after the first real run** (`groqTokensByPurpose` of the run, or `scripts/groq_usage.py`).
- **NLI time:** every sentence that passes the Python checks is checked by NLI on the CPU (1 to 1.7 s per premise pair, at most 9 pairs per sentence; answers are cached in `.cache/nli`). With 20 to 40 sentences this is a few minutes the first time.
- A rerun on the same claims costs no model call (the write cache, the NLI cache); changing the template version (`settings.TEMPLATE_VERSION`) invalidates the write cache.
- `--dry` (below) costs nothing.

## 7. When something fails
| What fails | What happens | Status |
|---|---|---|
| `STAGE5` off | node returns `{}`; stage stays "not run" | none |
| Stage 4 did not run (`FACTCHECK` off) | node returns `{}`, note `stage5_skipped` | none |
| Stage 4 failed or produced no claims | no model call; limitations say why; every section lists its gaps | `insufficient_evidence` |
| every claim disputed or filtered | no model call; the disagreements are still shown | `insufficient_evidence` |
| model call fails (network, 5xx) | the jobs of that call get the fallback sentence, no retry | `completed_with_warnings` |
| rate limit up to `STAGE5_RATE_WAIT_MAX` | waited out, asked again | unchanged |
| rate limit that cannot be waited out | breaker opens; remaining sentences fall back at once; summary uses the extractive template | `completed_with_warnings` |
| HTTP 413 (prompt too large) | the call is split in two and asked again (not counted as the retry) | unchanged |
| reply is not valid JSON / a job is missing | counts as a failed attempt; one retry, then the fallback sentence | `completed_with_warnings` |
| sentence fails a check twice | the fallback sentence (the claim's own wording behind the tier's opener) | `completed_with_warnings` |
| summary fails its check twice | the extractive template (best sentences copied word for word) | `completed_with_warnings` |
| NLI model or judge fails | fail closed: the sentence is not accepted (so it falls back); it is never accepted unchecked | `completed_with_warnings` |
| source metadata cannot be read | the reference list uses the titles in the evidence | unchanged, a limitation line |
| the database write fails or `written_reports` is missing | the result is still returned in the state; a warning is logged | unchanged |
| any other error | minimal report, error text in `warnings` | `failed` (the run is not failed) |

## 8. Running and testing
- Whole pipeline: `STAGE5=true FACTCHECK=true venv/Scripts/python.exe test_pipeline.py "question"` (Stage 5 reads the state of the run, plus a database read for source metadata).
- **On a stored run** (no new retrieval, nothing written to the database):
  `venv/Scripts/python.exe scripts/stage5_on_stored_run.py --run <query_id> [--out PATH] [--dry]`
  It loads the stored claims, contradictions, coverage and sources, builds the report, prints the status, the tier counts, the counts per section and the token use, and writes `PATH.md` and `PATH.json` (default `reports/stage5/<run>.md` and `.json`; the folder is not committed). `--dry` uses no model and no NLI: every sentence is the deterministic template sentence and the summary is the extractive template, so it costs no tokens; use it first to see the tiers and gaps of a run. Without `--dry` it spends tokens (section 6) and loads the NLI model.
- Tests (offline, fakes for the model, the check, NLI and the judge): `venv/Scripts/python.exe -m pytest tests/test_stage5_assembler.py tests/test_stage5_data.py tests/test_stage5_checks.py tests/test_stage5_writer.py -q` (importing the Stage 4 helpers takes about 12 s).

## 9. Known limits (honest list)
- **Little to write from.** `supported` needs two documents that state the same specific claim: real runs have 1 to 4 such claims in the whole run (run 34: 1 of 121 claims; 24 partly, 95 unverified). Most of a typical report is therefore single-source sentences, attributed and marked as not confirmed; the report says so in its limitations. `insufficient_evidence` is a normal outcome for a run with Stage 4 off or little corroboration.
- **The lexical layer misses some errors.** It catches changed numbers, swapped names, added or dropped negations, reversed directions, bounds and scope words, but not a swapped lowercase common word, a changed relation between two correct names (a number moved to the wrong subject when both appear in the quote), or a reworded comparison. Those are left to NLI and the judge.
- **NLI is strict.** On real quotes it scored clear paraphrases near 0 entailment (Stage 4 measured 12 of 31 clusters). The judge re-check rescues some; the rest fall back to the template wording, so a report can have many `fallback` sentences. Each re-check is a Groq call.
- **Grounding is quote-only.** A sentence is checked against the claim text and the verbatim quotes that Stage 4 kept, never against the full paper (the web sources only have a snippet). A claim that Stage 4 words more broadly than its quote is only caught by the optional scope check (off by default). A "supported" sentence is not checked for whether the two documents really state the same thing beyond Stage 4's own judge.
- **The conflicts are a lower bound and a guess.** Stage 4 compares only the 80 most similar pairs (`STAGE4_MAX_PAIRS`); its conflict judge had precision 0.71 and recall 0.56 on 41 labeled pairs, and one of two conflicts in run 30 was false. Stage 5 therefore words them "Sources disagree", shows both quotes, and always carries the caveat that the check is automatic and not reviewed.
- **Claim ids are a hash** of the sub-question id and the claim text. They are stable when Stage 4 is rerun on the same claims, but a claim that Stage 4 words differently gets a new id, and two claims with the same text in one sub-question are one claim.
- **Aspect texts are mostly unavailable.** Stage 3 stores aspect indexes, not their text, in the database; gap lines about uncovered aspects appear only when the coverage view has the text. Uncovered detail questions and known gaps are available.
- **A stored run cannot say why a sub-question has no claims.** `fact_summary` (errors, judge failures) lives in the state only, and `domain_context` is not stored. The in-run path has both; `load_inputs` words the missing case as "no claims were checked", never as a verdict.
- **Single-source filters are heuristics.** "Full text or confirmed by the Stage 3 judge" excludes true abstract-only findings; the caps (3 per document, 8 per section) are defaults, not measured optima.
- **Quality is not measured.** The tests check mechanics with fakes; no human has read a real report yet, and the cost in section 6 is an estimate. Prompts and the template version will change after the first real run.
