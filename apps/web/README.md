# TRACE web

Frontend for TRACE: Next.js 16 (App Router), React 19, TypeScript, Tailwind v4, pnpm. It talks to the FastAPI service in `apps/api`;
the contract is `docs/API_HANDOFF.md` and the types are in `lib/trace-types.ts`.

## Run

```bash
pnpm install
cp .env.example .env.local     # NEXT_PUBLIC_TRACE_API_URL=http://localhost:8000
pnpm dev                       # http://localhost:3000
```

Backend, from the repository root: `uvicorn apps.api.main:app --port 8000`. Its `CORS_ORIGINS` must include the origin the web app is served from.

## Pages

| Route | What it does |
|---|---|
| `/` | Overview: ask a question (10-1000 characters), start a run, recent runs |
| `/research/[id]` | One run: pipeline stages, live events, and tabs for Activity, Sources, Evidence, Verification. Deep link: `#sources`, `#evidence`, `#verification` |
| `/research/[id]/papers/[paperId]` | One paper, like a reading view: links (source page, PDF, DOI), why it was kept (relevance, reliability, judge verdict), the evidence taken from it, and its **parsed content** with each quote highlighted where it appears, an outline, figures and references |
| `/research/[id]/report` | The evidence report, sub-question by sub-question, with coverage, known gaps and limitations |
| `/history` | Every run, with filter by text and status |
| `/settings` | Live / demo mode and the backend connection |

The run page's **Activity** tab shows the evidence funnel (papers kept → parsed → used as evidence; web sources found → used), and its views: Timeline (the planner, then the **paper and web retrieval branches side by side on one time axis**, each with a dropdown of its steps: paper search, relevance judge calls, citation counts, scoring, saving and PDF parsing with live counts; then the evidence digest and judge steps. A run that finished before steps were recorded shows an approximate timeline reconstructed from database timestamps, labelled as such), Plan (sub-questions with their paper counts), Papers (searchable, filterable cards) and Web sources. The funnel steps are buttons: they open the matching, filtered list. A paper card opens the paper page (a normal link, so it can be opened in a new browser tab). Data comes from `GET /api/research/{id}/papers` and `/papers/{paper_id}` (see `docs/API_HANDOFF.md`), and refreshes whenever a stage finishes.

**Second search (Loop 2, optional).** When the server runs with `LOOP2=true`, an aspect that stayed uncovered gets a second search, and the UI shows it without changing anything else (a run without Loop 2 renders exactly as before):

- *Timeline:* a sub-step "Searching again for missing evidence" appears between the judge events, with the current rung (re-reading papers we already have, reading more papers from the search results, searching with new queries), the running totals and elapsed time. Unknown steps are ignored.
- *Evidence report:* per sub-question a collapsible "Second search" panel (summary line, steps table, every aspect with its status), the badge "combined from several sources" for aspects covered by synthesis, and "Sufficient, with gaps where no evidence was found." when `sufficientStrict` is false. "Evidence not found for: ..." is always shown next to the sufficient badge, and a warning appears when sources could not be read (`digestFailures`), because "no evidence" may then be wrong.
- *Sources:* a "found by second search" badge and a filter. A source can be listed more than once in a sub-question (read again for another aspect); repeats are marked "read again".
- Every Loop 2 field is optional and tolerant (older runs carry nulls; status words are open strings). The pure logic is in `lib/loop2.ts` and tested in `tests/loop2.test.ts` (`pnpm test`); demo fixtures are in `lib/demo-loop2.ts`.

**Fact checking across sources (Stage 4, optional).** When the server runs with `FACTCHECK=true`, the UI adds it; with it off (`stages.factcheck = 'not_run'`) the stage shows as "skipped (switched off)" and nothing else changes (`totals.factChecked` and every `factCheck` are null, so no panel or row is drawn).

- *Progress:* a normal stage between the summarizer and the report, with the live line "Checking claims across sources: sub-question 2 of 5 - looking for sources that disagree" and the elapsed time (it takes about 3 minutes per sub-question), plus a Timeline lane. A failed stage does not fail the run: it shows "Fact checking failed; the evidence below is not cross-checked." `judgeFailures > 0` shows "Some checks could not be answered (rate limit); labels are cautious and incomplete."
- *Report and Verification tab:* a summary row of the totals and a collapsible "Cross-check" panel per sub-question: counts, every claim with its label, "N independent sources" / "M against" and its evidence (quote, full text or snippet, a badge when the independent judge had already checked it), and the disagreements as side-by-side cards. A contradicted or contested claim always shows the disagreeing source next to it.
- *Wording rules* (from `docs/STAGE4_OUTPUT.md`): "supported" is not "true"; an unverified claim reads "Not yet confirmed by a second source" and is styled as unconfirmed, never as a fact; the confidence is shown as a bar and a word ("evidence strength"), never as a percent, because it is a ranking and not a probability.
- The pure logic is in `lib/factcheck.ts`, tested in `tests/factcheck.test.ts`; demo fixtures are in `lib/demo-factcheck.ts`. In demo mode a question containing "factcheck" simulates a run with Stage 4, and "factfail" one whose Stage 4 fails; the seeded runs `demo-factcheck` and `demo-factcheck-failed` show the same.

### Work that runs at the same time (docs/API_HANDOFF.md)
Several stages overlap on the server, so the stream's order and timing changed. The reducer is `lib/stream.ts` (pure, tested in `tests/parallel.test.ts`):
- Events are merged by `seq`; state is keyed by (lane, step, sub-question index), never by a "current" sub-question. The index comes from `subQuestionIndex` (judge, Loop 2) and `subQuestion` (Stage 4), never from the message text. Counters (`done`, `failures`, `usable`, ...) never go backwards, so a late `done=4` after `done=5` is ignored.
- Time is `data.occurredAt` when present, otherwise `timestamp`. Stage 4's real start is the earliest `occurredAt` of its steps, not `stage_started`, and its duration is never `stage_started` to `stage_completed` alone.
- Judge: one chip per sub-question (waiting, judging, done with enough / not enough evidence); two can be judging at once; the bar is finished / total. Loop 2: one line per sub-question with its own rung. Stage 4: a row per sub-question with six steps (claims, clusters, support, near, conflicts, store); near and conflicts can both be running; a replayed burst shows its final state at once because the page is a function of the events. A note "overlapped with Stage 3" appears when part of Stage 4 ran during Stage 3.
- Warnings: `judgeWaits > 0` is a plain note ("N judge calls waited for a Groq rate limit"); `judgeFailures > 0` stays a warning. `run_completed.groqTokensByPurpose` is shown with friendly labels; an unknown purpose is shown as its own key.
- Everything is optional: events without the new fields render as before (no chips, no rows, no note). In demo mode a new run simulates the parallel pipeline; a question containing "oldstyle" simulates the old one (the seeded runs only get a closing event, like the real API after a restart).

### Second search tab and the Timeline details (docs/API_HANDOFF.md, 2026-11-10)
All new fields are optional: a run without them renders as before, with the new blocks hidden or saying "not stored for this run".
- **Second search tab** (`#second-search`, badge = aspects searched): summary strip, "Why it ran", one card per sub-question with the three-rung ladder (reselect, pool, queries), an aspect table with before and after verdict bars (yes / partial / no, never an "after" made from a "before"), the stopped reason, rung "Details" (aspects, the queries asked, the papers and web pages found and kept, digests, a calm warning for failed digests), and the sources the second search added. While the run goes it is built from the events: each rung fills in when its `loop2_step` event arrives, keyed by (sub-question, rung). Logic: `lib/second-search.ts`, tests: `tests/second-search.test.ts`.
- **Timeline** (Activity, Timeline view): a sub-question matrix (judge, second search, fact check), a Gantt of Stages 3 and 4 with the critical path, a Stage 4 worker table (worker count from the data; `done` steps finish a sub-question), a time-share bar with "slower than the two measured runs" hints, per-paper parsing, cache and warm-up chips, Groq use per stage (and a running total in the run header), notes, and an event log with filters, search, warnings only and copy-as-JSON. The time left is an estimate from real progress and is shown in live mode only. Logic: `lib/stream.ts` (reducer), `lib/swimlanes.ts`, `lib/telemetry.ts`, `lib/eta.ts`, `lib/event-log.ts`; tests: `tests/timeline-views.test.ts`.
- **Demo mode:** a new run emits all of it (notes, `paper_parse`, `data.groq`, `done` events with two overlapping workers, `cacheHits`, `loop2_step` with queries, a digest failure and a stopped aspect). `demo-completed` and `demo-factcheck-old` (and a question containing "oldstyle") have none of the new fields.

### The written report (Stage 5, `docs/STAGE5_OUTPUT.md`)
- **Page:** `/research/{id}/written-report` (`app/research/[id]/written-report/page.tsx`, view in `components/ReportView.tsx`, logic in `lib/written-report.ts`, tests in `tests/written-report.test.ts`). It reads `GET /api/research/{id}/written-report`: 200 shows the report, 202 shows "Writing the report" and asks again every 3 seconds, 404 shows "No written report for this run" with a "Generate report" button (`POST`; 400 = Stage 5 is switched off on the server, 409 = already running), 503 is the usual "try again" state. The run page has an "Open written report" button once `stages.report` is `completed`.
- **Order:** status chip, the legend, warnings, **Answer** (the sentences first, then the overview counts), Introduction, one block per section (detail questions, sentences, "Sources disagree", "Evidence gaps"), Limitations and Evidence Gaps, Conclusion, References. "Download Markdown" saves the `markdown` field; a link goes back to the evidence report.
- **The answer (template `s5-v2`):** the first block answers the question that was asked; the field is still `overview.summary`, but the page titles it "Answer", never "Executive summary" (the Markdown heading is `## Answer and Overview`). A sentence with tier `note` (a template line such as "The evidence collected does not settle: ...", origin `template`, no `refs`) is shown as a plain muted line: no tier chip, no marker and no "plain wording" hint. `conclusion` can be an empty list (the model could not write it within the checks, and `warnings` says so): the Conclusion heading is then hidden, not shown empty.
- **Rules that hold in the view-model, not only in the markup:** the text of a sentence never has a marker and the page adds "[1, 3]" from `refs` before the final full stop, each marker linking to its reference; tier `partly` always shows "partly supported" and tier `single` (and any unknown tier) always shows "one source, not confirmed" and is styled apart from a confirmed finding; the legend is always visible; the limitations are never collapsed; `completed_with_warnings`, `insufficient_evidence` and `failed` are visible states with `report.warnings`; a disagreement shows both sides with quote and reference and never says that one is false; the evidence level of a reference is a hint when it is not full text; missing fields show as nothing.
- **Stage state:** `stages.report` is pending, running, completed, failed or not_run ("not run (Stage 5 is switched off or Stage 4 did not run)"); nothing says "not built yet" any more. The Timeline has a "Written report" lane (sections, write, validate, summary, references, store) and notes `stage5_skipped`, `stage5_fallback`, `stage5_dropped`.
- **Demo:** new runs with the cross-check write a report (completed with warnings, with an Answer that ends in a note and no conclusion). `demo-written-ok` has a conclusion. Seeded runs show the other states: `demo-written-ok`, `demo-written-insufficient`, `demo-written-failed`, `demo-written-running` (202 for three polls), `demo-factcheck-old` (404, then "Generate report" works) and `demo-completed` (Stage 5 off: generating answers 400).

Keyboard: `Ctrl+K` search and jump, `N` new research, `Ctrl+Enter` start a run from the question box.

## Live mode and demo mode

- **Live** (default) calls the real API. A full run takes about 15 to 25 minutes (measured on two runs, 13 min 54 s and 19 min 42 s, so an estimate; the text lives in `lib/format.ts`). The run page follows `GET /api/research/{id}/events` (server-sent events), closes the stream after `run_completed` / `run_failed`, and re-reads the run status after every event and every 8 seconds, so a dropped stream never leaves the screen stale.
- **Demo** is an explicit choice in Settings. It is a browser-side simulator (`lib/demo-api.ts`, `lib/demo-report.ts`) with fictional data; a run finishes in about 20 seconds, and a question containing the word "fail" makes it fail, to exercise the failure states. It never sends a request to the backend. Demo mode is announced by a banner, a `DEMO` badge in the top bar, the sidebar card and the composer.
- If the backend is unreachable in live mode, the app says so and offers to switch to demo mode. It never falls back silently.

## What the UI deliberately does not claim

- The evidence report is **collected evidence, not a verified answer**, and so is the written report of Stage 5: every check is automatic and none was reviewed by a person (the page says so under the legend). A stage that did not run (Stage 4 or Stage 5 switched off, `not_run`) is shown as "not available" or "skipped", never as queued or as done.
- A finding is not a fact: a quote that was not found in its source is flagged; sources that were only partly read (abstract, web snippet) are labelled; a sub-question that is not sufficient, or whose judging did not finish, is never shown as complete.
- There is no sign-in and no per-user data: every visitor sees every run (see `docs/API_HANDOFF.md`).

## Layout

- `lib/trace-types.ts` types and the `TraceApi` interface; `lib/trace-api.ts` live client; `lib/demo-api.ts` simulator; `lib/mode.tsx` mode and health; `lib/use-research.ts` data hooks.
- `public/trace-logo.png` is the sidebar logo (`components/trace/app-shell.tsx`, `.brand-logo`); the start page's orbit graphic and the favicon still use the `TraceMark` component.
- `components/trace/*` UI, `components/ReportView.tsx` the written report. `app/globals.css` holds the Midnight Signal design tokens (see the comment at its top).
