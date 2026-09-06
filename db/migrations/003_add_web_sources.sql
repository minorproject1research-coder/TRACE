-- 003_add_web_sources.sql
-- Web Search Agent output table (Tavily / Exa / Parallel results)

create table web_sources (
    id uuid primary key default gen_random_uuid(),
    sub_question_id text references sub_questions(id),
    url text not null,
    title text,
    snippet text,
    published_date text,
    provider text,
    reliability_score float,
    created_at timestamptz default now()
);

grant select, insert, update, delete on public.web_sources to service_role;