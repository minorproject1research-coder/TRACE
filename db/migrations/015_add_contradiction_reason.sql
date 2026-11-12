-- Migration 015: the judge's reason for a contradiction (apps/api/services/db_service.py write_contradictions already
-- sends it when the column exists and falls back to the old columns when it does not). Safe to run twice.

alter table contradictions
add column if not exists reason text;
