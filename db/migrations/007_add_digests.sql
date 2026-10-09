create table digests (
    id uuid primary key default gen_random_uuid(),
    query_id uuid references research_queries(id),
    sub_question_id text references sub_questions(id),
    source_type text not null,
    source_id text not null,
    source_title text,
    findings jsonb not null,
    verified_count int default 0,
    total_count int default 0,
    weight float,
    model text,
    created_at timestamptz default now()
);

create table coverage_results (
    id uuid primary key default gen_random_uuid(),
    query_id uuid references research_queries(id),
    sub_question_id text references sub_questions(id),
    sufficient boolean not null,
    source_count int,
    uncovered_details jsonb,
    created_at timestamptz default now()
);

grant select, insert, update, delete on public.digests to service_role;
grant select, insert, update, delete on public.coverage_results to service_role;