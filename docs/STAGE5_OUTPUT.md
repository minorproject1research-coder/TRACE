# Stage 5 output: what the web app may rely on

Stage 5 writes a cited report from the labels of Stage 4 (`docs/STAGE4_OUTPUT.md`). This file is the contract of the stored document, for whoever renders it (the web app, a download, a script). How Stage 5 works: `docs/STAGE5.md`. The endpoints are in `docs/API_HANDOFF.md` ("Stage 5: the written report").

## Where it is
- Table `written_reports` (migration `db/migrations/016_add_written_reports.sql`, **the user must apply it**; until then nothing is stored and the endpoint answers 404): one row per run (`query_id` unique), replaced when Stage 5 runs again. Columns: `status`, `report` (jsonb, the structured report below), `markdown` (the same report as text), `stats` (jsonb), `model`, `template_version`, `created_at`, `updated_at`.
- `GET /api/research/{id}/written-report` returns `{status, report, markdown, stats, model, templateVersion, generatedAt}` (200), `{"state": "running"}` (202) while it is being written, or 404.
- Stage 5 runs unless `STAGE5=false` on the server (default on since 2026-11-13). A run without it has no row, and `stages.report` is `not_run`.

## `status` (one value per report, also in `report.status`)
| value | meaning | what to show |
|---|---|---|
| `completed` | every sentence was written by the model and passed every check | the report |
| `completed_with_warnings` | some sentence uses the deterministic template wording, was dropped, or a final check complained; the reasons are in `report.warnings` and the limitations | the report and a visible note that it has warnings (link to `warnings`) |
| `insufficient_evidence` | nothing eligible to write about (Stage 4 off or failed, no claims, everything disputed or filtered). The report still has introduction, limitations and gaps; no model call was made | the report; say plainly that the evidence is insufficient for a written answer |
| `failed` | an internal error. `report` is a minimal document whose `limitations` and `warnings` hold the error text | an error state, and keep offering the evidence report (`/report`) |

The stage state of the run follows it: `completed` for the first three, `failed` for `failed`, `not_run` when there is no row. A Stage 5 failure never fails the run.

## The structured report (`report`)
```ts
type WrittenReport = {
  status: string; question: string; generatedAt: string
  overview: { summary: Sentence[]; counts: { sections; documents; claims; supported; partly; single; disputed; filtered; sentences; disagreements; references: number } }
  introduction: string[]                 // paragraphs (Python templates)
  sections: Section[]                    // one per sub-question, in the planner's order
  limitations: string[]                  // Python templates
  conclusion: Sentence[]                 // may be [] (a tiny report has no separate conclusion)
  references: Reference[]
  stats: object; warnings: string[]
}
type Section = { id: string; title: string /* the sub-question */; subQuestionId: string; detailQuestions: string[]; sentences: Sentence[]
                 disagreements: Disagreement[]; gaps: string[]; counts: { total; supported; partly; single; disputed; filtered: number } }
type Sentence = { text: string; claimIds: string[]; refs: number[]; tier: 'supported' | 'partly' | 'single'; origin: 'llm' | 'fallback' | 'template' }
type Disagreement = { claimA: string; claimB: string; claimId: string | null; note: string
                      sideA: { quote: string; ref: number | null; title: string }; sideB: { quote: string; ref: number | null; title: string } }
type Reference = { number: number; title: string; authors: string[]; year: number | null; venue: string | null; doi: string | null; url: string | null
                   kind: 'paper' | 'web'; evidenceLevel: 'full_text' | 'abstract' | 'web_snippet' | null; sourceIds: string[]; text: string; markdown: string }
```
- A **sentence** is one sentence. `claimIds` are stable ids of the Stage 4 claims it is built from (a hash of the sub-question id and the claim text, not the database id: they are the same after Stage 4 is run again on the same claims). `refs` are the numbers of the references behind its claims, in the order of the reference list.
- **`text` never contains a `[n]` marker or a URL.** The renderer adds the markers from `refs`.
- **Sections** are the planner's sub-questions in order. A section can have no sentences; it then has `gaps` (and the limitations say which sections had nothing eligible). `disagreements` and `gaps` are written by Python only.
- **`references`** are numbered in the order of first citation in the rendered text (overview, then sections, then conclusion), one entry per document (the same paper found as a paper and as a web page, or for two sub-questions, is one entry with several `sourceIds`). Papers: authors, year, venue, DOI or URL. Web pages: title, site, date, URL and the date the run was made as "accessed". Fields can be missing: show what is there. `text` and `markdown` are the formatted entry without its number.

## Tiers: what the wording means and how to display it
The Stage 4 label never changes; the **tier** only decides the wording. The tier of a sentence is the weakest tier among its claims.

| tier | from | wording in `text` | display |
|---|---|---|---|
| `supported` | label `supported`, not contested: two or more documents state it | "Two sources report ..." | normal text with its citation marker |
| `partly` | label `partially_supported`, not contested: one document states it, another a close variant | "[A] reports X; [B] makes a related point" (both wordings are given) | normal text with its marker, **and the label "partly supported"** (the Markdown has `*(partly supported)*`) |
| `single` | label `unverified`, not contested, with strong evidence (full text, or confirmed by the Stage 3 judge): one document states it | "One study reports ...", "According to ..." (attributed, never as fact) | **always with the label "one source, not confirmed"** (the Markdown has `*(one source, not confirmed)*`); never styled like a confirmed finding |
| disputed | label `contradicted`, or `contested` with any label | never in `sentences`; only in `section.disagreements` | the block "Sources disagree": both sides, each with its quote and its reference; never "X is false" |

Claims that are filtered (a document already has the maximum number of single-source claims, a section is full, the only quote is an unconfirmed abstract) are counted in `overview.counts.filtered` and named in `limitations`; they are not in the report.

## `origin` of a sentence
| value | meaning |
|---|---|
| `llm` | the model wrote it and every Python check passed (numbers and names appear in the claims or quotes, hedging matches the tier, entailed by the claims and quotes by the NLI model or the judge) |
| `fallback` | the model's sentence failed its checks twice (or the model was unavailable), so Python wrote it from the claim's own wording behind the standard opener of the tier. Still attributed and cited. Counts in `stats.sentences.fallback` and a limitation line |
| `template` | deterministic by design (a limitation sentence in the summary, an extractive summary sentence that is a word-for-word copy of a body sentence) |

A client may show `fallback` and `template` sentences exactly like the others; `origin` is for audit and for an optional "plain wording" hint, not a quality grade.

## How to render the markers
- For a sentence, put the markers before the final full stop: `Two sources report that X [1, 3].` Join the numbers with `, ` inside one pair of brackets, in the order of `refs`. A sentence with no `refs` (a template limitation) has no marker. Each marker links to `references[number - 1]` (the numbers are 1-based and contiguous).
- `markdown` in the response already has the markers and the labels; the web app may render it as it is, or render `report` itself for clickable markers and the tier labels.
- Show `references[].url` as a link, `evidenceLevel` as a small hint when it is not `full_text` ("abstract only", "web snippet").
- Disagreement sides show `quote` and, if `ref` is not null, its marker.

## What must always be shown
1. **The single-source legend.** `report.overview` is introduced by a legend; the Markdown has it as the first block quote: *"How to read the findings: a sentence that starts with "Two sources report" is stated by two or more documents; a finding marked (partly supported) rests on one document with a related point in another; single-source findings are attributed to one document and are not confirmed. Citation numbers point to the references at the end."* A web view that does not use the Markdown must show an equivalent legend near the top and the tier labels on every `partly` and `single` sentence.
2. **The limitations** section (never collapsed away behind a click for a report with warnings), including the standing caveat that the conflict check compares only the most similar pairs and is automatic, not reviewed by a person.
3. **The gaps** of each section (evidence not found, not sufficient) and the "Sources disagree" blocks.
4. The status: `completed_with_warnings`, `insufficient_evidence` and `failed` are visible states, not hidden ones.
5. A link to the evidence report (`/report`) from the written report: every claim behind a sentence can be found there with its quote.

What the report is not: a verified answer. Every check is automatic (language models and rules), none was reviewed by a person, and a `single` sentence rests on one document.

## Stability
- New fields may be added to the report, sentences, sections or `stats`; read unknown fields as ignorable and treat `tier`, `origin`, `kind` and `evidenceLevel` as open strings.
- `template_version` (for example `s5-v1`) changes when a prompt or template changes; a stored report keeps the version it was written with. Write it again with `POST /api/research/{id}/written-report` (only with `STAGE5=true`).
- `stats` is for audit and telemetry (claims by tier, sentences by origin, calls, tokens, NLI and judge counts, seconds); do not build the UI on its keys.
