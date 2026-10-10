-- 008_add_relevance_verdict_to_papers.sql
-- Stores the LLM judge's verdict (relevance_filter.filter_relevant) per kept paper.
-- relevance_score stays the embedding similarity; the judge is only a pass/fail gate.
-- All three are NULL when the judge was off; judge_reason = 'judgment_failed' when it was on but every backend failed.

alter table retrieved_papers
add column if not exists judge_relevant boolean;

alter table retrieved_papers
add column if not exists judge_confidence float;

alter table retrieved_papers
add column if not exists judge_reason text;
