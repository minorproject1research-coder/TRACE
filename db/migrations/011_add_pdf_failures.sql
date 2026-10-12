-- 011_add_pdf_failures.sql
-- Negative cache for PDF downloads: papers whose PDF could not be fetched for a reason that will not change by itself
-- (HTTP 403 / 404 / 410 / 451, an HTML landing page instead of a PDF, an over-size file). The parse step skips them for
-- PDF_FAILURE_TTL_DAYS days (default 7) instead of repeating the download, the Unpaywall lookup and the Playwright fallback
-- in every run. Timeouts, connection errors, 429 and 5xx are NOT recorded: they may succeed next time.
--   paper_key       arxiv:<id> | doi:<doi> | title:<normalised title> (same key as the parse cache)
--   fetcher_version version of the download logic that failed; a row from an older version is ignored, so improving the
--                   download code (PaperRetrievalAgent.DOWNLOADER_VERSION) makes the papers eligible again at once
-- If this table does not exist the pipeline keeps the failures in memory for the current run only (warning logged).

create table if not exists pdf_failures (
    paper_key        text primary key,
    title            text,
    doi              text,
    error_class      text,
    error_detail     text,
    fail_count       integer not null default 1,
    fetcher_version  integer not null default 1,
    first_seen       timestamptz not null default now(),
    last_seen        timestamptz not null default now()
);

create index if not exists idx_pdf_failures_last_seen on pdf_failures(last_seen desc);

grant select, insert, update, delete on public.pdf_failures to service_role;
alter table pdf_failures enable row level security;
