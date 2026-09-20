-- 005_add_reliability_score_to_papers.sql
-- Adds reliability_score to retrieved_papers so it carries the same
-- scoring signal that web_sources already has from the Reliability Scorer

alter table retrieved_papers
add column reliability_score float;