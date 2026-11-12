-- Migration 016: the written report of Stage 5 (one row per research run, replaced when Stage 5 runs again).
-- report   = the structured report (sections, sentences with claim ids, references, limitations); the web app renders it.
-- markdown = the same report as plain Markdown, for download.
-- stats    = small counts (sentences written, dropped, retried, tier counts, Groq tokens used by Stage 5).
-- Safe to run twice.

create table if not exists written_reports (
    id uuid primary key default gen_random_uuid(),
    query_id uuid not null unique references research_queries(id),
    status text not null,                -- completed | completed_with_warnings | insufficient_evidence | failed
    report jsonb not null,
    markdown text,
    stats jsonb,
    model text,
    template_version text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

grant select, insert, update, delete on public.written_reports to service_role;
