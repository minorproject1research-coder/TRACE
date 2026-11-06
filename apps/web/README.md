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
