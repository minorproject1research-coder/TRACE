-- Migration 012: Add judge-based coverage columns to coverage_results
-- Adds columns for judge-based coverage tracking

-- judge_used: whether judge-based coverage was used for this sub-question
ALTER TABLE coverage_results 
ADD COLUMN IF NOT EXISTS judge_used BOOLEAN;

-- fallback_reason: reason for falling back to tag-based coverage
ALTER TABLE coverage_results 
ADD COLUMN IF NOT EXISTS fallback_reason TEXT;

-- judge_stats: JSONB with judge statistics (candidates, yes, partial, no, error)
ALTER TABLE coverage_results 
ADD COLUMN IF NOT EXISTS judge_stats JSONB;

-- aspect_evidence: JSONB with per-aspect evidence from judge
ALTER TABLE coverage_results 
ADD COLUMN IF NOT EXISTS aspect_evidence JSONB;

-- digest_failures: count of digest generation failures for this sub-question
ALTER TABLE coverage_results 
ADD COLUMN IF NOT EXISTS digest_failures INTEGER DEFAULT 0;

-- unjudged_aspects: JSONB array of aspects that were not judged
ALTER TABLE coverage_results 
ADD COLUMN IF NOT EXISTS unjudged_aspects JSONB;

-- uncovered_reasons: JSONB mapping aspect text to reason (no_candidates | judged_insufficient | unjudged)
ALTER TABLE coverage_results 
ADD COLUMN IF NOT EXISTS uncovered_reasons JSONB;

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_coverage_results_judge_used 
ON coverage_results(judge_used);

CREATE INDEX IF NOT EXISTS idx_coverage_results_fallback_reason 
ON coverage_results(fallback_reason);