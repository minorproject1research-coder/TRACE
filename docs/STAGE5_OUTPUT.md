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
  overview: { summary: Sentence[] /* THE ANSWER to the question (template s5-v2), see below */; counts: { sections; documents; claims; supported; partly; single; disputed; filtered; sentences; disagreements; references: number } }
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

## Added when the report is read (2026-11-19)
`GET /api/research/{id}/written-report` returns the stored report plus fields that the server computes at read time (`services/written_report_links.py`): nothing is stored, no model is called, so it works for every stored report. If computing them fails, the stored report is returned without them, so a client must treat all of them as optional. The stored `markdown` is unchanged.

```ts
type Citation = { ref: number; paperId: string | null; parsed: boolean; quotes: CitedQuote[] }
type CitedQuote = { text: string; findingId: string; paperId: string | null; parsed: boolean; relation: 'supports' | 'near_match'; evidenceLevel: string | null }
// on every Sentence (overview.summary, sections[].sentences, conclusion):  citations: Citation[]     ([] for a note and for a sentence whose claims were not found)
// on every Reference:  paper: { id: string; parsed: boolean } | null ;  citedIn: number
// on overview:         answer?: Answer       (absent when the report has no answer sentence)
type Answer = {
  headline: { sentenceIndex: number } | null           // the first statement of overview.summary: the verdict, to be shown largest
  parts: { sentenceIndex: number; sectionId: string | null; title: string | null; sentence: Sentence; supporting: Sentence[] }[]
  strength: { statements: number; byTier: { supported: number; partly: number; single: number }; documents: number; fullTextDocuments: number
              documentsInReport: number | null; partsCovered: number; sections: number; disagreements: number; openQuestions: number; line: string }
  figures: { value: string; sentenceIndex: number; refs: number[] }[]      // percentages found in the answer sentences, at most 6 (may be [])
  openQuestions: string[]                              // read from the template line "The evidence collected does not settle: ...; ..."
  disputes: { count: number; items: { sectionId: string; title: string; claimA: string; claimB: string; refs: number[] }[] }   // at most 3 items
}
```
- **`citations`** are the verbatim quotes behind a sentence's claims (the supporting quote, and for a partly supported claim the near-match quote of the second document; never the conflicting side), grouped by reference, at most 3 per reference. Their reference numbers are exactly the sentence's `refs`. They are the "evidence" to show under a sentence.
- **Opening the parsed paper.** `paperId` is a `retrieved_papers` id of this run: its page is `/research/{id}/papers/{paperId}` (`GET /api/research/{id}/papers/{paperId}` has the parsed text, the findings and where each quote sits in the text). `parsed: true` means TRACE has the parsed text; `parsed: false` means only the abstract and the findings exist. `paperId: null` is a web source: there is no parsed page, only `references[].url`. `findingId` equals `findings[].id` of that paper's response, so the page can scroll to the highlighted quote. The citation's `paperId` is the paper that holds its first quote (one document can be several rows, one per sub-question), so that `findingId` is on that page; each quote also has its own `paperId`. `reference.paper` is the paper to open from the reference list (the parsed copy that is cited most).
- **`overview.answer`** is the same answer as `overview.summary`, organised: each part is one answer sentence with the sub-question section it comes from and up to 2 supporting sentences of that section (strongest tier first, never a claim already used in the answer). Every sentence in it keeps its tier label and citations: the rules of "What must always be shown" apply to them. `strength.line` is a ready sentence about how well the answer rests on the evidence; the numbers behind it are in the other `strength` fields. Everything in `answer` is computed from the stored report and the stored claims; it says nothing the report did not already say.

## The answer (`overview.summary`, template `s5-v2`, 2026-11-13)
From template `s5-v2` the first block of the report answers the question that was asked; the field keeps its name `overview.summary` so no client breaks, but a client should title it **"Answer"**, not "Executive summary". The Markdown heading is `## Answer and Overview`.
- Written from the question: Python ranks the sections by how many words of the question their title shares (background sections come last), offers the best sentences of the top four sections (stronger tier first, sentences with a figure first, near duplicates removed; shown to the model grouped under "== Part: <section title> ==" headers), and checks that the answer draws on at least three of them. The model only words it from numbered, already verified sentences (verdict on the main part of the question first, then the conditions or figures, then the other parts), and each answer sentence is cited from the sentences it is based on and hedged like the weakest of them.
- If a sentence of the answer fails the checks after the retries, the sentences that passed are kept (at least 3); only when too few remain is the extractive template used (`origin: "fallback"`, spread over the sections).
- The last sentence can be a template (`origin: "template"`, `tier: "note"`, no `refs`; show NO tier label on it): "The evidence collected does not settle: ..." from the Stage 3 gap data of the top sections. Show it like the others; it has no citation marker.
- `conclusion` is now a short bottom line written from sentences the answer did not use. It may be `[]`: a conclusion that the model could not write within the checks is left out (with a warning), not copied from the body.
- **Repeated sentences:** within one section, a sentence that says nearly the same as a stronger or earlier one (Jaccard of the finding words >= 0.6, the attribution wording ignored) is left out of `sentences`; the count is in `stats.sentences.repeated` and one limitation line ("N sentences repeated another sentence of the same section and were left out"). Their claims still count in the section's `counts`.

- **Built part by part (2026-11-13):** when at least 3 sections qualify as parts (relevance to the question at least 30% of the best section's; sections whose title is about where the method is applied or which datasets exist are skipped when 3 others remain), Python picks ONE sentence per part (by embedding similarity to the question and the section, `STAGE5_EMBED_SELECT`, else by word overlap) and the model words exactly one answer sentence per part from that sentence alone; a sentence mixing parts, two for one part, or a missing part is rejected, failed sentences are dropped when at least 3 remain. The answer then follows the order of the parts (the most relevant first). With fewer than 3 qualifying sections the unstructured answer described above is used.

- **Wording style (template s5-v3, default since 2026-11-14, `STAGE5_STYLE`):** sentences are plain claims; `text` no longer starts with "One source reports" / "Two sources report". The strength of the evidence is shown by the **tier label** (`partly`: "(partly supported)", `single`: "(one source, not confirmed)") and the citations, so a client MUST show that label on every `partly` and `single` sentence. A `single` sentence says what its source is in words taken from its claim or quote ("A review reports ...", "According to one study, ..."). The legend text of the Markdown changed accordingly (`LEGEND_NATURAL`); a client that has its own legend must not say that sentences start with "Two sources report". Reports stored with template `s5-v2` keep the old wording.
