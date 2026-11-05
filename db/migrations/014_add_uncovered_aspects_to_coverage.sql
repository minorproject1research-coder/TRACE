-- Migration 013: Add missing uncovered_aspects column to coverage_results
-- This column was referenced in OPTIONAL_COVERAGE_COLUMNS as migration 010
-- but was never actually added by migration 010 (which only added full_text_source_count)

alter table coverage_results
add column if not exists uncovered_aspects jsonb;