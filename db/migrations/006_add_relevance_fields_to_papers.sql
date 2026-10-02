-- 006_add_relevance_fields_to_papers.sql
-- Adds relevance scoring fields from the Abstract Relevance Filter —
-- relevance_score (embedding similarity, or LLM confidence if that stage is enabled)
-- and combined_score (relevance x reliability, used for final ranking)

alter table retrieved_papers
add column relevance_score float;

alter table retrieved_papers
add column combined_score float;