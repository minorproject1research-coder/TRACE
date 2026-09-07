-- Migration: 004_add_parsed_papers.sql
-- Stores full extracted content from academic papers (Docling + PDFFigures)

CREATE TABLE IF NOT EXISTS parsed_papers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    retrieved_paper_id UUID NOT NULL REFERENCES retrieved_papers(id) ON DELETE CASCADE,
    title           TEXT NOT NULL DEFAULT '',
    authors         TEXT[] DEFAULT '{}',
    abstract        TEXT DEFAULT '',
    sections        JSONB DEFAULT '[]',
    cited_references JSONB DEFAULT '[]',
    figures         JSONB DEFAULT '[]',
    full_text       TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_parsed_papers_retrieved_paper_id
    ON parsed_papers(retrieved_paper_id);

CREATE INDEX IF NOT EXISTS idx_parsed_papers_created_at
    ON parsed_papers(created_at DESC);

-- Grant permissions (Supabase)
GRANT SELECT ON parsed_papers TO anon;
GRANT SELECT ON parsed_papers TO authenticated;
GRANT ALL ON parsed_papers TO service_role;

-- Enable RLS
ALTER TABLE parsed_papers ENABLE ROW LEVEL SECURITY;

-- Public read policy
CREATE POLICY "Allow public read" ON parsed_papers
    FOR SELECT
    TO public
    USING (true);

-- Service role full access
CREATE POLICY "Allow service role full access" ON parsed_papers
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
