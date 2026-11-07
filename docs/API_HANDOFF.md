# TRACE API: handoff for the frontend (2026-11-05)

`apps/api/main.py` is now a working FastAPI app. This file is the contract the frontend (`apps/web`, `lib/trace-api.ts`) should be written against. It replaces the endpoint guesses in the template's README. Everything below was run against the real database (read paths) and tested offline with a fake graph (`tests/test_api.py`, 17 tests). **A full run through the API has not been done yet** (it takes 15-25 minutes and uses Groq); the run path is tested with a fake graph only.

## Run it
```bash
# from the repository root, with .env in place (Supabase, model server, Groq, OpenAlex, ...)
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```
- Frontend env: `NEXT_PUBLIC_TRACE_API_URL=http://localhost:8000`.
- CORS: allowed origins come from `CORS_ORIGINS` (default `http://localhost:3000,http://127.0.0.1:3000`). Methods GET, POST, OPTIONS.
- Logs: the API writes `logs/pipeline.log` and the per-stage logs like `test_pipeline.py` does, so `python scripts/pipeline_run_report.py --list` works on API runs.
- **There is no authentication and no per-user data.** Every caller sees every run. Do not expose the port to the internet as it is.
- Interactive docs: `http://localhost:8000/docs`.

## What a run is
A run executes the whole graph in a background thread: **planner -> (paper retrieval + web search in parallel) -> summarizer**. It takes **15-25 minutes**. The UI must be built around progress events, not around waiting for a response.
- The run id is a UUID and is also the id of the research query in the database, so a finished run can be read after a server restart.
- Runs are queued: `MAX_CONCURRENT_RUNS` (default 1) at a time, `MAX_PENDING_RUNS` (default 5) waiting. A further `POST` gets **429** `{"detail": "..."}`.
- `report` (Stage 5) **does not exist yet**: always `"not_built"`. `factcheck` (Stage 4) exists and runs after the summarizer **only when the server has `FACTCHECK=true`**; otherwise its state is `"not_run"`. There is no written answer, only collected and judged evidence (see "Report").
- There is no quick or web-only mode: every run uses the full pipeline. (`depth` and `scope` were removed from the request and from the session; a client that still sends them is ignored.)
- A run cannot be cancelled (no endpoint).

## Endpoints
Errors are `{"detail": "text"}` (validation errors: FastAPI's list under `detail`, status 422).
- **503** `{"detail": "The database is temporarily unavailable. Try again in a moment."}` with `Retry-After: 2`: a database read failed twice on a connection error (the server already retried once). It means "ask again", not "this run does not exist". Added 2026-11-06 after the production readiness audit; before it, a hiccup could come back as 404 on `/report` or 500 on the session.
- **404** is also returned, without asking the database, for any id that is not a UUID.

| Method and path | Purpose | Success | Errors |
|---|---|---|---|
| `POST /api/research` | start a run | **202** + `Location` header + Session | 422 invalid body, 429 queue full |
| `GET /api/research?limit=20` | latest runs (database + live ones), newest first | `{"items": [{id, question, status, createdAt}]}` | 422 bad limit (1-100) |
| `GET /api/research/{id}` | status of one run | Session | 404 |
| `GET /api/research/{id}/events` | live progress, server-sent events | `text/event-stream` | 404 |
| `GET /api/research/{id}/report` | the evidence report | Report | 404, **409** while the run is still going |
| `GET /health` | liveness | `{"status": "ok", "activeRuns": 0}` | |

### POST body
```json
{ "question": "string, 10-1000 characters (whitespace is collapsed)" }
```

### Types (TypeScript)
```ts
type RunStatus = 'pending' | 'running' | 'completed' | 'failed'
type StageId = 'planner' | 'retrieval' | 'summarizer' | 'factcheck' | 'report'
type StageState = 'pending' | 'running' | 'completed' | 'failed' | 'not_built' | 'not_run' | 'unknown'   // not_run: the stage exists but was switched off for this run

type Session = {
  id: string
  question: string
  status: RunStatus
  createdAt: string | null          // ISO 8601
  startedAt: string | null
  finishedAt: string | null
  error: string | null              // set when status is 'failed'
  stages: Record<StageId, StageState>
}

type WorkflowEvent = {
  seq: number                       // 0, 1, 2, ... also the SSE id
  event: 'run_queued' | 'run_started' | 'stage_started' | 'branch_started' | 'step' | 'branch_completed' | 'stage_completed' | 'run_completed' | 'run_failed'
  stage: StageId | null
  status: string | null
  message: string                   // short, human readable
  data: Record<string, unknown>
  timestamp: string | null
}
```
A session read from the database after a restart has `status` `completed` (all sub-questions have Stage 3 results) or `failed` ("The run did not finish (the server restarted or the run was stopped)"), and `startedAt/finishedAt: null`.

### Events (what the stream looks like)
Typical order for one run (the 11 stage-level events; `branch_started` and `step` events, below, appear between them):
`run_queued` -> `run_started` -> `stage_started` planner -> `stage_completed` planner -> `stage_started` retrieval -> `branch_completed` x2 (papers and web, any order) -> `stage_completed` retrieval -> `stage_started` summarizer -> `stage_completed` summarizer -> `run_completed`.

| event | stage | `data` |
|---|---|---|
| `stage_completed` | planner | `{subQuestions, queries, domainAnchor, topics: string[]}` |
| `branch_started` | retrieval | `{branch: 'papers'}` or `{branch: 'web'}`: the two branches start together and run **at the same time** |
| `step` | retrieval or summarizer | `{lane, step, state, ...counts}`: see "Steps" below |
| `branch_completed` | retrieval | `{branch: 'papers', papers}` or `{branch: 'web', webSources}` |
| `stage_completed` | summarizer | `{digests, subQuestions, sufficientSubQuestions}` |
| `run_completed` | null | `{reportUrl, stagesNotRun: ['report']}` (also `'factcheck'` when it was off) |
| `run_failed` | the stage that was running, or null | `message` is `"ErrorType: text"` (also `session.error`) |

Timing hint for the progress UI: planner about 30 s, retrieval and parsing 2-9 min (longer for a new topic), summarizer 8-11 min.

### Steps (`step` events, added 2026-11-07, `services/progress.py`)
The nodes report what they are doing between a stage's start and its end. `data = { lane, step, state, ...counts }`, `state` is `running | completed | skipped | failed`, `stage` is `retrieval` for the two retrieval lanes and `summarizer` for the third, and `message` is a short sentence. A step sends `running` (more than once for steps with progress) and then `completed`. Counts are small numbers only. The paper and web lanes interleave in the stream because they run in parallel threads.

| lane | step | what it is | counts in `data` |
|---|---|---|---|
| `papers` | `search` | OpenAlex, Scopus, arXiv | running `{subQuestions, queries}`; completed `{candidates}` |
| `papers` | `relevance_filter` | embedding shortlist, then the LLM relevance judge, per sub-question | `{done, total, candidates, shortlisted, judged, passed, judgeUnavailable, backend}` (running after each sub-question; `judged` = real LLM judge calls) |
| `papers` | `citations` | citation counts of the papers that passed | completed `{kept}` |
| `papers` | `scoring` | reliability score and combined rank | completed `{scored}` |
| `papers` | `store` | saved to `retrieved_papers` (the papers list can be read from here on) | completed `{stored}` |
| `papers` | `parsing` | best PDFs to text, in rounds | `{target, attempted, usable}` after every round; `usable` never decreases |
| `web` | `search` | web search per sub-question | `{done, total, found}`; completed `{found}` |
| `web` | `scoring`, `store` | reliability score, saved to `web_sources` | `{scored}`, `{stored}` |
| `summarizer` | `prepare` | choose the passages to read | completed `{jobs, papers, web}` |
| `summarizer` | `digest` | LLM digest per source, in parallel | `{done, total, failures}`, reported in counting order |
| `summarizer` | `judge` | independent evidence judge and coverage, per sub-question | `{done, total, sufficient, judgeUsed, sufficientSoFar}`; completed `{sufficientSubQuestions}` |
| `summarizer` | `loop2` | **only when `LOOP2=true`.** Second search for the aspects that stayed uncovered. Runs between `judge` steps (once per sub-question that has uncovered aspects), then one `completed` | running `{loop2Step, aspects}` (loop2Step = `reselect` \| `pool` \| `queries`) and `{subQuestion, searched, covered}`; completed `{searched, covered}` totals. It adds minutes (budget `LOOP2_MAX_SECONDS`, default 20 min) |
| `summarizer` | `store` | digests and coverage saved | completed `{stored}` |

- Only the events of a run that is still in this server's memory carry steps. A run read after a restart gets one closing event, and one that finished before this change has none: for those, `GET /papers` returns `timing` (below) so a client can reconstruct an approximate timeline.
- Reports are best effort: a node that cannot report (no sink, an error) is never affected, and a lane may skip a step (`skipped`).

### Consuming the stream
- Use `EventSource` on `.../events`. Events arrive as default `message` events with the JSON in `data`; the SSE `id` is `seq`.
- **Close the EventSource when you receive `run_completed` or `run_failed`.** The server ends the stream after those, and a browser would otherwise reconnect forever.
- The server replays all events from the start, so opening the stream late (page reload) is fine. To resume without replay, send `Last-Event-ID` (EventSource does this by itself on reconnect) or pass `?after=<seq>`.
- Keep-alive comments (`: keep-alive`) are sent every 15 s of silence.
- A run that exists only in the database (server restarted since) gets a single closing event (`run_completed` or `run_failed`).
- If the server restarts while a run is in progress, that run is lost: it later shows as `failed`.

## Report (`GET /api/research/{id}/report`)
It is an **evidence report**, not an answer. Read it after `run_completed`. While the run is going it answers 409; if a run failed halfway, a partial report may still exist (and then has `runError`). Size is large (about 100 KB for a 5 sub-question run).

```ts
type Report = {
  id: string
  question: string
  createdAt: string | null
  runError?: string                       // only when the run failed in this server process
  stages: Record<StageId, 'completed' | 'incomplete' | 'unknown' | 'not_built' | 'not_run'>   // factcheck: 'completed' when fact_claims exist, else 'not_run'
  totals: { subQuestions: number; subQuestionsSufficient: number; sources: number; findings: number; findingsQuoteFound: number;
            factChecked: null | { supported: number; unverified: number; contradicted: number; contested: number } }   // null: Stage 4 did not run
  subQuestions: SubQuestionReport[]
  limitations: string[]                   // show these: Stage 4 / Stage 5 missing, retrieval limits, and each sub-question whose evidence is not sufficient
}

type SubQuestionReport = {
  id: string
  topic: string                           // the sub-question, e.g. "What is a mixture of experts (MoE) model?"
  detailQuestions: string[]
  coverage: null | {                      // null: Stage 3 did not finish for this sub-question
    sufficient: boolean                   // every aspect (and the sub-question itself) has >= 2 independent supporting sources
    judgeUsed: boolean | null
    sourceCount: number | null
    fullTextSourceCount: number | null
    digestFailures: number | null
    aspects: AspectRow[]
    uncoveredAspects: string[]            // texts of the aspects without enough evidence = the known gaps
    unjudgedAspects: string[]
    fallbackReason: string | null
    loop2: null | {                       // null: Loop 2 (LOOP2=true) did not run for this sub-question
      searched: number                    // uncovered aspects that were searched again
      covered: number                     // of those, covered afterwards
      seconds: number
      triage: 'r1' | 'all'
      gapRule: 'core' | 'strict'          // core (default with Loop 2): an aspect that stays uncovered after the whole search and has thin evidence does not stop `sufficient`
      sufficientStrict: boolean | null    // `sufficient` under the old rule (every aspect covered); `coverage.sufficient` is the gapRule value
      coveredBySynthesis: number          // aspects covered because the judge accepted several sources' findings TOGETHER (weaker than two single claims: say so in the UI)
      knownGapsNoEvidence: string[]       // searched, nothing usable found: show "evidence not found" (also added to `limitations`)
      steps: { step: 'reselect' | 'pool' | 'queries', aspects: number, newSources: number, newVerifiedFindings: number, covered: number, seconds: number }[]
      aspects: { text: string, status: 'covered' | 'known_gap' | 'known_gap_no_evidence' | 'known_gap_skipped_triage' | 'known_gap_skipped_cap' | 'unjudged_not_searched',
                 coveredBy: string | null,           // 'synthesis' | 'reselect' | 'pool' | 'queries'
                 how: 'single claims' | 'synthesis' | null, nearMiss: boolean | null,   // nearMiss: evidence exists (>= 3 partial/yes findings, >= 2 sources) but no answer was complete: still blocks `sufficient`
                 steps: string[] }[]
      knownGaps: string[]                 // aspects still uncovered after the search (or not searched): show "evidence not found" for them
    }
  }
  sources: SourceReport[]                 // ordered by evidence weight, highest first
}

type AspectRow = {
  index: number
  text: string | null                     // null when the aspect texts could not be rebuilt (then only index and counts are known)
  state: 'covered' | 'judged_insufficient' | 'no_candidates' | 'unjudged' | 'uncovered' | 'unknown'
  coveredBy: 'single_claims' | 'synthesis' | null   // synthesis = findings of several sources judged together (Loop 2)
  yesVerdicts: number                     // findings the independent judge accepted as answering this aspect
  sources: number                         // distinct sources behind those
}

type SourceReport = {
  foundByLoop2Step: null | 'reselect' | 'pool' | 'queries'   // set when this source was added by Loop 2 (a badge such as "found by a second search")
  id: string
  type: 'paper' | 'web'
  title: string | null
  evidenceLevel: 'full_text' | 'abstract' | 'web_snippet'   // how much of the source was read
  weight: number | null
  findingsTotal: number
  findingsQuoteFound: number              // findings whose quote was found verbatim in the source
  findings: Finding[]
  url?: string | null                     // DOI link, arXiv page, PDF or web page
  // papers: authors, year, venue, doi, arxivId, citations, origin ('openalex' | 'scopus' | 'arxiv' | 'both' | ...)
  // web: provider, publishedDate
}

type Finding = {
  claim: string                           // one sentence, the digest model's words
  quote: string                           // up to 40 words from the source
  stance: string                          // usually 'supports' | 'contradicts' | 'neutral', but it is free output of the digest model and NOT validated: a real run produced 'challenges'. Treat it as an open string.
  quoteFound: boolean                     // false: the quote could not be located in the source; treat the claim as unverified
  judgements: { aspect: string | null; verdict: 'yes' | 'partial' | 'no' | null; quoteSupportsClaim: string | null; answersAspect: string | null; reason: string | null }[]
}
```

How to present it honestly (these are product requirements, not suggestions):
- A finding is **not a fact**. `quoteFound` only means the quote exists in the source; the claim may still be wrong. Stage 4 would check that and is not there.
- "Sufficient" means enough independent sources answered the aspects; it does not mean the question is answered. Show `uncoveredAspects` and `limitations` prominently, per sub-question.
- A source with `evidenceLevel` `abstract` or `web_snippet` was only partly read; label it.
- Never present a sub-question with `coverage: null` or `sufficient: false` as complete.

## Try it without running the pipeline
These ids are in the development database; the read paths work on them right now:
- `cc81e9cc-1bfd-48d1-a3cc-ed23e8c00320`: complete run (mixture of experts question): 5 sub-questions, 40 sources, 4 sufficient, one with two uncovered aspects.
- `2397750f-41eb-4693-a21e-fd5a7045e9d7`: complete run (Mamba question), 2 of 5 sufficient.
- `d02050fb-...` (listed by `GET /api/research`): an interrupted run, shows as `failed`.

`GET /api/research/{id}`, `/report` and `/events` (single closing event) work for them. A live event stream can only be seen on a real run, or by running `pytest tests/test_api.py` to read the fake-graph sequence.

## Papers and web sources (added 2026-11-06, `routers/paper_router.py`, `services/paper_service.py`)
Read-only views for the web app's Activity tab and paper page. They work **while a run is going** (they show what has been written to the database so far): papers appear after the paper branch finishes, digests after the summarizer. A queued run that has no database rows yet answers an empty funnel, not 404. Responses are gzip-compressed (`GZipMiddleware` in `main.py`; `text/event-stream` is excluded by Starlette).

| Method and path | Purpose | Errors |
|---|---|---|
| `GET /api/research/{id}/papers` | the funnel plus a summary of every paper and web source kept | 404 unknown run |
| `GET /api/research/{id}/papers/{paper_id}` | one paper: parsed content and its findings with quote positions | 404 unknown run, **or a paper that belongs to another run**, or a malformed id |

```ts
type PapersOverview = {
  id: string
  counts: { papersKept: number; papersJudged: number; papersParsed: number; papersUsedAsEvidence: number; papersUsedFullText: number; papersUsedAbstractOnly: number
            papersWithPdfLink: number; webFound: number; webUsedAsEvidence: number; subQuestions: number }
  timing: { plannedAt; papersStoredAt; parsingFirstAt; parsingLastAt; webStoredAt; digestsFirstAt; digestsLastAt; coverageAt }   // UTC ISO or null: when rows were written (see below)
  subQuestions: { id: string; topic: string }[]
  papers: PaperSummary[]          // best combined score first
  web: WebSummary[]               // best reliability first
}
type PaperSummary = {
  id; title; authors: string[]; year; venue; source: 'openalex'|'scopus'|'arxiv'|'both'; doi; arxivId; url; pdfUrl; citations; isPreprint; publishedDate; fieldsOfStudy: string[]
  scores: { relevance; reliability; combined }                       // 0..1
  judge: { relevant: boolean|null; confidence: number|null; reason: string|null }
  tldr: string|null; abstractPreview: string                          // first 320 characters of the abstract
  subQuestionId; subQuestion
  parse: { status: 'parsed'|'not_parsed'; parserVersion }              // 'parsed' = a parsed_papers row exists (it can still hold no text)
  evidence: { level: 'full_text'|'abstract'|...; findings; quotesFound; weight } | null    // null: no finding was taken from this paper
}
type PaperDetail = {
  paper: PaperSummary
  abstract: string
  parsed: null | { parserVersion; chars; text: string /* the parser's markdown */; outline: {heading; level}[]; figures: {page; label; caption}[]; references: string[] /* first 400 */; referenceCount }
  findings: (Finding & { subQuestion: string|null; spans: {start: number; end: number}[] })[]
}
```
- **`timing`** is when each part of the run was *written* to the database, normalised to UTC (checked against the live events of a real run: within about 1 s). A client without step events reconstructs an approximate timeline from it (search and judge calls cannot be recovered; `papersJudged` counts the kept papers that carry a judge verdict).
- **Funnel honesty:** candidates removed by the relevance filter are not stored, so the funnel starts at `papersKept`. "Used as evidence" means a digest exists for the paper in the newest Stage 3 run.
- **`spans`** locate a finding's quote in `parsed.text`, in **UTF-16 code units** (JavaScript string indexes). They are computed with Stage 3's own quote normalization (`quote_verifier._norm`: hyphenation, citation markers, typographic hyphens, whitespace) plus its fuzzy threshold, so a quote has a span exactly when the verifier could have found it (verified on 74 of 74 findings of a real run: no disagreement either way). A quote with an elision (`[...]`) has one span per piece. If a quote cannot be placed, `spans` is `[]`: show no highlight rather than a guess.
- The web app only shows what is returned: it never fetches papers itself.

## Not built, for the product plan
Authentication and per-user data access; cancelling a run; Stage 4 and Stage 5; progress inside a stage; a database-backed run queue (runs are in memory, so a restart loses running ones); rate limiting per user; a saved-report or export endpoint.

## Files
`apps/api/main.py` (app, CORS, logging), `routers/query_router.py` (sessions and events), `routers/report_router.py`, `services/run_manager.py` (queue, thread, events), `services/report_service.py` (database to report), `config.py`, `dependencies.py`, `graph/state.py` and `graph/nodes/planner_node.py` (the run id is chosen by the API), tests in `tests/test_api.py`. Environment variables are in `.env.example` under "API server".
