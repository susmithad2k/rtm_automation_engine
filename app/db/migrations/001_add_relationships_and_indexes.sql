-- Migration: Add composite indexes for query optimization
-- Date: 2026-06-04
-- Description: Adds composite indexes to improve JOIN performance and common query patterns

-- Add composite index on mappings table for faster JOINs
CREATE INDEX IF NOT EXISTS ix_mappings_composite 
ON mappings (requirement_id, testcase_id);

-- Note: The relationships and cascade rules are handled by SQLAlchemy ORM
-- and don't require SQL migration. However, if you need to add them at the
-- database level, uncomment the following:

-- Add foreign key constraints with proper cascading (if not already present)
-- ALTER TABLE mappings 
-- DROP CONSTRAINT IF EXISTS mappings_requirement_id_fkey,
-- ADD CONSTRAINT mappings_requirement_id_fkey 
--     FOREIGN KEY (requirement_id) 
--     REFERENCES requirements(id) 
--     ON DELETE CASCADE;

-- ALTER TABLE mappings 
-- DROP CONSTRAINT IF EXISTS mappings_testcase_id_fkey,
-- ADD CONSTRAINT mappings_testcase_id_fkey 
--     FOREIGN KEY (testcase_id) 
--     REFERENCES test_cases(id) 
--     ON DELETE CASCADE;

-- Analyze tables to update statistics for query planner
ANALYZE requirements;
ANALYZE test_cases;
ANALYZE mappings;
