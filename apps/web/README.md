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

Keyboard: `Ctrl+K` search and jump, `N` new research, `Ctrl+Enter` start a run from the question box.

## Live mode and demo mode

- **Live** (default) calls the real API. A real run takes 15 to 25 minutes. The run page follows `GET /api/research/{id}/events` (server-sent events), closes the stream after `run_completed` / `run_failed`, and re-reads the run status after every event and every 8 seconds, so a dropped stream never leaves the screen stale.
- **Demo** is an explicit choice in Settings. It is a browser-side simulator (`lib/demo-api.ts`, `lib/demo-report.ts`) with fictional data; a run finishes in about 13 seconds, and a question containing the word "fail" makes it fail, to exercise the failure states. It never sends a request to the backend. Demo mode is announced by a banner, a `DEMO` badge in the top bar, the sidebar card and the composer.
- If the backend is unreachable in live mode, the app says so and offers to switch to demo mode. It never falls back silently.

## What the UI deliberately does not claim

- The report is **collected evidence, not an answer**: Stage 4 (fact check) and Stage 5 (written report) are not built and are shown as "not built yet", never as queued.
- A finding is not a fact: a quote that was not found in its source is flagged; sources that were only partly read (abstract, web snippet) are labelled; a sub-question that is not sufficient, or whose judging did not finish, is never shown as complete.
- There is no sign-in and no per-user data: every visitor sees every run (see `docs/API_HANDOFF.md`).

## Layout

- `lib/trace-types.ts` types and the `TraceApi` interface; `lib/trace-api.ts` live client; `lib/demo-api.ts` simulator; `lib/mode.tsx` mode and health; `lib/use-research.ts` data hooks.
- `components/trace/*` UI. `app/globals.css` holds the Midnight Signal design tokens (see the comment at its top).
