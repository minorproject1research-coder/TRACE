-- 009_add_parser_version_and_cache_indexes.sql
-- Parse cache: a paper that was already parsed (same arXiv id / DOI / title) under any earlier query is copied
-- instead of being downloaded and parsed again.
--  * parsed_papers.parser_version: version of markdown_parser.PARSER_VERSION that produced the row. Only rows from the
--    current version are reused, so a parser fix invalidates stale rows. NULL = parsed before versioning (not reused).
--  * indexes on retrieved_papers(arxiv_id, doi, title) so the cache lookup stays fast as the table grows.

alter table parsed_papers
add column if not exists parser_version integer;

create index if not exists idx_retrieved_papers_arxiv_id on retrieved_papers(arxiv_id);
create index if not exists idx_retrieved_papers_doi on retrieved_papers(lower(doi));
create index if not exists idx_retrieved_papers_title on retrieved_papers(title);
