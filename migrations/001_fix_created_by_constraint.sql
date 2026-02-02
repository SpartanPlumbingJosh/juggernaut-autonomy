-- Migration: 001_fix_created_by_constraint.sql

-- 1. Create system user for autonomous operations
INSERT INTO users (id, name, type) 
VALUES ('00000000-0000-0000-0000-000000000001', 'SYSTEM', 'autonomous')
ON CONFLICT (id) DO NOTHING;

-- 2. Fix all existing NULL values
UPDATE governance_tasks 
SET created_by = '00000000-0000-0000-0000-000000000001'
WHERE created_by IS NULL;

-- 3. Set default for future autonomous task creation
ALTER TABLE governance_tasks 
ALTER COLUMN created_by SET DEFAULT '00000000-0000-0000-0000-000000000001';
