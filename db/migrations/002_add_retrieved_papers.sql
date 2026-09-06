-- Migration: Add retrieved_papers table for Stage 2 paper retrieval results
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS retrieved_papers (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    query_id UUID NOT NULL REFERENCES research_queries(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    abstract TEXT,
    authors JSONB DEFAULT '[]'::jsonb,
    year INTEGER,
    venue TEXT,
    citation_count INTEGER,
    influential_citation_count INTEGER,
    is_preprint BOOLEAN DEFAULT FALSE,
    source TEXT NOT NULL,
    arxiv_id TEXT,
    doi TEXT,
    pdf_url TEXT,
    published_date TEXT,
    tldr TEXT,
    fields_of_study JSONB DEFAULT '[]'::jsonb,
    query_variants_matched JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.retrieved_papers TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.retrieved_papers TO authenticated;

CREATE INDEX IF NOT EXISTS idx_retrieved_papers_query_id ON retrieved_papers(query_id);
CREATE INDEX IF NOT EXISTS idx_retrieved_papers_source ON retrieved_papers(source);
CREATE INDEX IF NOT EXISTS idx_retrieved_papers_year ON retrieved_papers(year);
