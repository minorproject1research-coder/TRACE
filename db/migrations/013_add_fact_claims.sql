create table if not exists fact_claims (
    id uuid primary key default gen_random_uuid(),
    query_id uuid references research_queries(id),
    sub_question_id text references sub_questions(id),
    claim text not null,
    label text not null,                 -- supported | contradicted | unverified
    confidence float,
    support_doc_count int default 0,
    contra_doc_count int default 0,
    contested boolean default false,
    evidence jsonb not null,
    created_at timestamptz default now()
);

create table if not exists contradictions (
    id uuid primary key default gen_random_uuid(),
    query_id uuid references research_queries(id),
    sub_question_id text references sub_questions(id),
    claim_a text not null,
    claim_b text not null,
    source_a_title text,
    source_b_title text,
    quote_a text,
    quote_b text,
    prob float,
    created_at timestamptz default now()
);

grant select, insert, update, delete on public.fact_claims to service_role;
grant select, insert, update, delete on public.contradictions to service_role;