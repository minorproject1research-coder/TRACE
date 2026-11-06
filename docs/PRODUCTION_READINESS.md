# TRACE production readiness audit (2026-11-06)

Scope: `apps/web` (changed) and the behaviour of `apps/api` as the web app sees it (not changed). Evidence was gathered against the running API and the
real Supabase database, with the production build of the web app, in a real browser.

## Verdict

**Fine for one trusted user on a private machine. Not ready for several users or for the open internet.** There are two blockers, both in the backend
and both need a product decision (below). Everything that could be fixed in the frontend without changing the research architecture was fixed.

## Blockers (backend, need a decision)

### 1. No authentication, no per-user data: any caller can read every user's research  (verified, FAILS)
Without any credential, cookie or token:

- `GET /api/research` returned the question text of other runs (the whole history, newest first).
- `GET /api/research/{id}` and `/report` return any run to anyone who has or guesses the UUID. Run ids are not secret: they are in every list response.
- CORS does block *browsers on other origins*, but CORS is not access control: `curl`, a script or a server-side fetch ignore it.

So the requirement "a user cannot access another user's private research records" is **not met**, and the web app cannot meet it on its own. The UI says so
(Settings, "What TRACE does not do yet") and does not pretend otherwise.

### 2. Anyone who can reach the API can start runs  (cost and abuse)
`POST /api/research` is open. A run spends the model server and Groq quota for 15 to 25 minutes and cannot be cancelled. The queue (`MAX_PENDING_RUNS`)
limits the damage to a full queue, which then blocks real users with 429. There is no rate limit per caller.

### Recommended design (not implemented: it changes the database and needs your auth settings)
Use Supabase Auth, which the project already uses for storage.

1. Web: sign-in with `@supabase/supabase-js` (the public anon key is designed for browsers); send `Authorization: Bearer <access token>` to the API.
2. API: a FastAPI dependency verifies the JWT (Supabase JWT secret or JWKS) and yields `user_id`. All five endpoints depend on it.
3. Database: add `owner_id uuid` to `research_queries`; set it in `RunManager.submit`; **every read filters on it** (`list_sessions`, `session_from_db`, `build_report`, the live in-memory run record and the SSE endpoint). Return 404, not 403, for another user's id so ids do not leak.
4. Per-user rate limit and a per-user cap on queued runs; keep `MAX_*` as the global cap.
5. Test: user A creates a run, user B gets 404 on `/{id}`, `/report`, `/events` and does not see it in the list; anonymous gets 401.

Until then: bind the API to `127.0.0.1`, do not expose port 8000, and do not host the web app publicly.

## Backend defects found (not changed)

- **Transient database errors surface as wrong answers.** Under a few concurrent requests the Supabase client intermittently raises `httpx.RemoteProtocolError: Server disconnected` (seen in the uvicorn output). Effects seen: `GET /api/research/{id}` returned **500**, and `GET /api/research/{id}/report` returned **404 "Research session not found"** for a run that exists, because `routers/report_router.py` wraps `build_report` in `except Exception: report = None`. Suggested fix: retry idempotent reads once on connection errors (or use a fresh client / disable HTTP/2 keep-alive), and return 503 for database failures instead of 404.
  The web app now retries a failed GET once and retries a report 404 once, so users rarely see it, but the API should not lie.
- `GET /api/research` is unpaginated beyond `limit` and returns other users' data (see blocker 1).
- The SSE endpoint polls its in-memory list every 0.5 s per connected client; fine for a handful of viewers, worth an `asyncio.Event` if there will be many.
- Run state is in memory: a server restart loses running runs (they later show as failed). Documented in `API_HANDOFF.md`; the UI shows such runs as failed with the stored reason.

## Frontend: what was checked and what was changed

| Area | Result |
|---|---|
| API error handling | Timeouts, network failure, 404, 409 (report still running), 422, 429, 5xx are mapped to readable messages; GETs retry once on a transient failure; every screen has loading, error with retry, and empty states. Offline backend shows a banner and an explicit "use demo mode" choice, never a silent fallback. |
| Authentication | **Not configured in the backend.** Nothing was faked in the UI. |
| Persistence | Verified: runs and reports are read from the database and survive an API restart (the API was stopped and started during testing; history and reports were unchanged). In-memory run progress does not survive a restart (see above). |
| Authorization | **Fails** (blocker 1). |
| Secrets in the frontend | Scanned 31 values from the real `.env` against the browser bundle, the server build and the source: **none found**. The only public variables are `NEXT_PUBLIC_TRACE_API_URL` and `NEXT_PUBLIC_TRACE_ENABLE_DEMO` (a URL and a flag). The backend's Supabase service key stays server-side. |
| TypeScript | `ignoreBuildErrors` was **removed** from `next.config.mjs` (it hid errors); `pnpm typecheck` and the production build now type-check and pass with 0 errors. |
| Environment | Production no longer defaults the API URL to `localhost` (a visitor's browser would call their own machine): unset means same-origin behind a reverse proxy. `NEXT_PUBLIC_TRACE_ENABLE_DEMO=false` removes demo mode. See `apps/web/.env.example`. |
| Dependencies | `next` 16.4.0 → 16.4.5 (critical RCE advisories in 16.4.0); `@vercel/analytics` removed (it called a Vercel-only endpoint and sent usage data to a third party); `shadcn` moved to devDependencies; patched overrides for build-time tooling. `pnpm audit --prod`: **no known vulnerabilities**. About 88 advisories remain in dev-only packages (the `shadcn` CLI and its Express/MCP dependencies); they are not part of the shipped app. |
| Headers | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`; `X-Powered-By` removed. No CSP yet (Next needs nonces for inline scripts; add one when the deployment is fixed). |
| XSS / links | No `dangerouslySetInnerHTML`; source URLs are only linked if `http(s)`, with `rel="noopener noreferrer"`. |
| Responsive | Checked at 1440/1280 px and 390 px on every page (and 1024 px on the overview): no horizontal overflow; mobile drawer, status visible in run rows, no hidden scroll regions. |
| Keyboard and screen readers | axe-core (WCAG 2.0/2.1/2.2 A and AA plus best practices) over 14 views, desktop and mobile: **0 violations**. Verified by hand: skip link, arrow keys and Home/End in every radio group, tab arrows, `Ctrl+K` palette (Esc returns focus), visible focus ring, reduced-motion. Icon-only navigation keeps accessible names; each route has a title and a heading. |

## Open items (small)
- Add a Content-Security-Policy once the production origin and API origin are fixed.
- `components/ui/button.tsx`, `@base-ui/react`, `tw-animate-css` and `shadcn` are no longer used by any page; remove them if the shadcn scaffold is not wanted, which also clears the dev-only advisories.
- Server-side rendering of run pages (for link previews) is not done; pages are client-rendered.
