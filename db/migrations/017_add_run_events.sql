-- Migration 017: the timeline of a run (one row per event of the run's progress stream).
--
-- The run page draws its timeline from the events that GET /api/research/{id}/events sends (run_started, stage_started, step, branch_completed,
-- stage_completed, run_completed, run_failed, ...). Until now they were kept only in the memory of the API process, so a restart of the server
-- lost the timeline of every finished run. The API now writes each event here as it happens and replays them from here for a run that is no
-- longer in memory.
--
-- query_id = the run id, the same uuid as research_queries.id. There is NO foreign key on purpose: the first events (queued, started, planner running)
-- come before the planner has stored its research_queries row, and a run that fails in the planner never gets one, but its timeline is the
-- most useful thing to read then.
-- seq      = the event number inside the run (0, 1, 2, ...), the SSE event id; (query_id, seq) is unique, so a retried write replaces the row.
-- event    = run_queued | run_started | stage_started | branch_started | step | branch_completed | stage_completed | run_completed | run_failed
-- stage    = planner | retrieval | summarizer | factcheck | report | null
-- status   = the state the event reports (pending | running | completed | failed | not_run ...) or null
-- message  = the short text shown in the timeline
-- data     = the event's numbers and fields exactly as they were sent (lane, step, state, counts, occurredAt, groq usage, ...)
-- event_at = the event's own time (what the stream calls "timestamp"); created_at = when the row was written.
-- Safe to run twice.

create table if not exists run_events (
    query_id uuid not null,
    seq integer not null,
    event text not null,
    stage text,
    status text,
    message text,
    data jsonb not null default '{}'::jsonb,
    event_at timestamptz,
    created_at timestamptz default now(),
    primary key (query_id, seq)
);

-- the primary key already serves "all events of a run in order"; this one serves "the runs that have a timeline, newest first"
create index if not exists run_events_event_at_idx on run_events (event_at desc);

grant select, insert, update, delete on public.run_events to service_role;
