-- ============================================================================
-- Migration 003: Create concept_ontology table
-- Date: 2026-02-10
-- Purpose: Persistent storage for canonicalization ontology (concept paths,
--          synonyms) so hierarchy matching survives server restarts.
--
-- Run this in: Supabase Dashboard > SQL Editor > New Query
-- ============================================================================

-- ============================================================================
-- PART 1: Create concept_ontology table
-- ============================================================================

CREATE TABLE IF NOT EXISTS concept_ontology (
    -- Canonical concept identifier (e.g., "chicken", "used", "air conditioning")
    concept_id TEXT PRIMARY KEY,

    -- Full hierarchy path from root to this concept
    -- e.g., ["diet", "non-veg", "chicken"]
    -- Used for ancestor/descendant matching
    concept_path JSONB NOT NULL DEFAULT '[]'::JSONB,

    -- All known synonyms / alternative forms that map to this concept_id
    -- e.g., ["poultry", "hen", "fowl"]
    -- Used to populate synonym_registry on startup
    synonyms JSONB NOT NULL DEFAULT '[]'::JSONB,

    -- Which source resolved this concept (wordnet, wikidata, datamuse, etc.)
    source TEXT NOT NULL DEFAULT 'unknown',

    -- Confidence score from disambiguation (0.0 to 1.0)
    confidence REAL NOT NULL DEFAULT 0.0,

    -- Timestamps for auditing and cache invalidation
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- PART 2: Indexes for performance
-- ============================================================================

-- GIN index on concept_path for array containment queries
-- e.g., "find all concepts where concept_path contains 'non-veg'"
CREATE INDEX IF NOT EXISTS idx_ontology_concept_path
    ON concept_ontology USING GIN (concept_path);

-- GIN index on synonyms for array containment queries
-- e.g., "find concept where synonyms contain 'poultry'"
CREATE INDEX IF NOT EXISTS idx_ontology_synonyms
    ON concept_ontology USING GIN (synonyms);

-- Index on source for filtering by resolution source
CREATE INDEX IF NOT EXISTS idx_ontology_source
    ON concept_ontology (source);

-- Index on updated_at for incremental cache refresh
CREATE INDEX IF NOT EXISTS idx_ontology_updated
    ON concept_ontology (updated_at DESC);

-- ============================================================================
-- PART 3: Auto-update trigger for updated_at
-- ============================================================================

-- Function to auto-update updated_at on row modification
CREATE OR REPLACE FUNCTION update_ontology_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on UPDATE
DROP TRIGGER IF EXISTS trg_ontology_updated ON concept_ontology;
CREATE TRIGGER trg_ontology_updated
    BEFORE UPDATE ON concept_ontology
    FOR EACH ROW
    EXECUTE FUNCTION update_ontology_timestamp();

-- ============================================================================
-- PART 4: Enable Row Level Security (Supabase best practice)
-- ============================================================================

ALTER TABLE concept_ontology ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (used by backend)
CREATE POLICY "service_role_all" ON concept_ontology
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- VERIFICATION QUERIES (Run after migration)
-- ============================================================================

-- Check table exists:
-- SELECT table_name FROM information_schema.tables WHERE table_name = 'concept_ontology';

-- Check structure:
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'concept_ontology'
-- ORDER BY ordinal_position;

-- Check indexes:
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'concept_ontology';

-- Count concepts:
-- SELECT COUNT(*) FROM concept_ontology;

-- Sample hierarchy query (find all descendants of "non-veg"):
-- SELECT concept_id, concept_path
-- FROM concept_ontology
-- WHERE concept_path @> '"non-veg"'::JSONB;
