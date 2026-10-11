-- 010_add_evidence_level_to_digests.sql
-- Stage 3 records what each digest was built from, so coverage and the later stages can tell a finding drawn from a
-- paper's parsed full text from one drawn only from its abstract or a web snippet.
--   digests.evidence_level: 'full_text' | 'abstract' | 'web_snippet'
--   coverage_results.full_text_source_count: how many sources with verified findings had full text
-- The columns are optional: if this migration has not been run, Stage 3 stores its rows without them (warning logged).

alter table digests
add column if not exists evidence_level text;

alter table coverage_results
add column if not exists full_text_source_count integer;
