"""
SUPABASE DB2 SETUP SCRIPT

Creates all tables and indexes on the NEW Supabase database (DB2).
Uses DATABASE_URL_2 from .env

Tables:
- matches (search history)
- product_listings
- service_listings
- mutual_listings
- concept_ontology

Author: Migration Script
Date: 2026-02-14
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Get DB2 connection string
DATABASE_URL_2 = os.getenv("DATABASE_URL_2")

# Combined migration SQL
MIGRATION_SQL = """
-- ============================================================================
-- STEP 1: Create matches table (must be first - others reference it)
-- ============================================================================

CREATE TABLE IF NOT EXISTS matches (
    match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_user_id UUID NOT NULL,
    query_text TEXT NOT NULL,
    query_json JSONB NOT NULL,
    has_matches BOOLEAN NOT NULL,
    match_count INTEGER NOT NULL DEFAULT 0,
    matched_user_ids UUID[] DEFAULT '{}',
    matched_listing_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_matches_user ON matches(query_user_id);
CREATE INDEX IF NOT EXISTS idx_matches_created ON matches(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_matches_has_matches ON matches(has_matches);

-- ============================================================================
-- STEP 2: Create product_listings table
-- ============================================================================

CREATE TABLE IF NOT EXISTS product_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    match_id UUID REFERENCES matches(match_id),
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_user ON product_listings(user_id);
CREATE INDEX IF NOT EXISTS idx_product_created ON product_listings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_product_match ON product_listings(match_id);

-- ============================================================================
-- STEP 3: Create service_listings table
-- ============================================================================

CREATE TABLE IF NOT EXISTS service_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    match_id UUID REFERENCES matches(match_id),
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_service_user ON service_listings(user_id);
CREATE INDEX IF NOT EXISTS idx_service_created ON service_listings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_service_match ON service_listings(match_id);

-- ============================================================================
-- STEP 4: Create mutual_listings table
-- ============================================================================

CREATE TABLE IF NOT EXISTS mutual_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    match_id UUID REFERENCES matches(match_id),
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mutual_user ON mutual_listings(user_id);
CREATE INDEX IF NOT EXISTS idx_mutual_created ON mutual_listings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mutual_match ON mutual_listings(match_id);

-- ============================================================================
-- STEP 5: Create concept_ontology table
-- ============================================================================

CREATE TABLE IF NOT EXISTS concept_ontology (
    concept_id TEXT PRIMARY KEY,
    concept_path JSONB NOT NULL DEFAULT '[]'::JSONB,
    synonyms JSONB NOT NULL DEFAULT '[]'::JSONB,
    source TEXT NOT NULL DEFAULT 'unknown',
    confidence REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ontology_concept_path ON concept_ontology USING GIN (concept_path);
CREATE INDEX IF NOT EXISTS idx_ontology_synonyms ON concept_ontology USING GIN (synonyms);
CREATE INDEX IF NOT EXISTS idx_ontology_source ON concept_ontology (source);
CREATE INDEX IF NOT EXISTS idx_ontology_updated ON concept_ontology (updated_at DESC);

-- Auto-update trigger for updated_at
CREATE OR REPLACE FUNCTION update_ontology_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ontology_updated ON concept_ontology;
CREATE TRIGGER trg_ontology_updated
    BEFORE UPDATE ON concept_ontology
    FOR EACH ROW
    EXECUTE FUNCTION update_ontology_timestamp();

-- Enable Row Level Security
ALTER TABLE concept_ontology ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
DROP POLICY IF EXISTS "service_role_all" ON concept_ontology;
CREATE POLICY "service_role_all" ON concept_ontology
    FOR ALL
    USING (true)
    WITH CHECK (true);
"""

VERIFY_SQL = """
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('matches', 'product_listings', 'service_listings', 'mutual_listings', 'concept_ontology')
ORDER BY table_name;
"""


def main():
    print()
    print("=" * 70)
    print("SUPABASE DB2 SETUP - SCHEMA MIGRATION")
    print("=" * 70)
    print()

    if not DATABASE_URL_2:
        print("ERROR: DATABASE_URL_2 not set in .env")
        return False

    # Extract host for display (hide password)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(DATABASE_URL_2)
        print(f"Target: {parsed.hostname}")
    except:
        print("Target: DB2")
    print()

    # Connect to database
    try:
        print("Connecting to Supabase DB2...")
        conn = psycopg2.connect(DATABASE_URL_2)
        conn.autocommit = True
        cursor = conn.cursor()
        print("Connected!")
        print()
    except Exception as e:
        print(f"ERROR: Failed to connect to database")
        print(f"  Error: {e}")
        return False

    # Run migrations
    try:
        print("Running migrations...")
        print("-" * 70)
        cursor.execute(MIGRATION_SQL)
        print("Migrations executed successfully!")
        print()
    except Exception as e:
        print(f"ERROR: Migration failed")
        print(f"  Error: {e}")
        conn.close()
        return False

    # Verify tables
    try:
        print("=" * 70)
        print("VERIFICATION")
        print("=" * 70)
        print()
        cursor.execute(VERIFY_SQL)
        tables = cursor.fetchall()

        print("Tables created:")
        for table in tables:
            print(f"  - {table[0]}")

        if len(tables) == 5:
            print()
            print("All 5 tables created successfully!")
        else:
            print()
            print(f"WARNING: Expected 5 tables, found {len(tables)}")

        print()

        # Get row counts
        print("Table row counts:")
        for table in ['matches', 'product_listings', 'service_listings', 'mutual_listings', 'concept_ontology']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  - {table}: {count} rows")

    except Exception as e:
        print(f"ERROR: Verification failed")
        print(f"  Error: {e}")
        conn.close()
        return False

    conn.close()

    print()
    print("=" * 70)
    print("SUPABASE DB2 SETUP COMPLETE!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
