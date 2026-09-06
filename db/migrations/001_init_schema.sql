-- 001_init_schema.sql
-- Initial schema for TRACE — Stage 1 (Planner) output tables

create table research_queries (
    id uuid primary key,
    raw_query text not null,
    created_at timestamptz default now()
);

create table sub_questions (
    id text primary key,
    query_id uuid references research_queries(id),
    main_topic text not null,
    detail_questions jsonb not null,
    created_at timestamptz default now()
);

create table queries (
    id uuid primary key default gen_random_uuid(),
    sub_question_id text references sub_questions(id),
    query_text text not null,
    created_at timestamptz default now()
);

grant select, insert, update, delete on public.research_queries to service_role;
grant select, insert, update, delete on public.sub_questions to service_role;
grant select, insert, update, delete on public.queries to service_role;

grant usage on schema public to service_role;