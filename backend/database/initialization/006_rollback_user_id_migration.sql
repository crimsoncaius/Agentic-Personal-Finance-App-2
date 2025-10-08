-- Rollback Script: Remove user_id column and related changes
-- Phase 2: Database Schema & Migration - ROLLBACK
--
-- WARNING: This script will remove user isolation and make all data shared again.
-- Only run this if you need to rollback the user_id migration.
-- This will permanently delete the user_id column and all user-specific data isolation.

-- Step 1: Drop the user entries view
DROP VIEW IF EXISTS user_entries;

-- Step 2: Drop the get_user_entries function
DROP FUNCTION IF EXISTS get_user_entries(UUID, INTEGER, INTEGER);

-- Step 3: Drop check constraint
ALTER TABLE entry DROP CONSTRAINT IF EXISTS check_user_id_not_empty;

-- Step 4: Drop indexes related to user_id
DROP INDEX IF EXISTS idx_entry_user_id;
DROP INDEX IF EXISTS idx_entry_user_date;
DROP INDEX IF EXISTS idx_entry_user_direction;
DROP INDEX IF EXISTS idx_entry_user_category;

-- Step 5: Drop the foreign key constraint
ALTER TABLE entry DROP CONSTRAINT IF EXISTS entry_user_id_fkey;

-- Step 6: Drop the user_id column
ALTER TABLE entry DROP COLUMN IF EXISTS user_id;

-- Step 7: Optional - Remove system user if it was created
-- Uncomment the following lines if you want to remove the system user
-- DELETE FROM auth.users WHERE email = 'system@example.com';

-- Verification queries (run these to ensure rollback worked)
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'entry' AND column_name = 'user_id';
-- (Should return no rows)

-- SELECT indexname, indexdef 
-- FROM pg_indexes 
-- WHERE tablename = 'entry' AND indexname LIKE '%user_id%';
-- (Should return no rows)

-- SELECT COUNT(*) as total_entries FROM entry;
-- (Should show all entries are now shared again)

-- Notes:
-- 1. This rollback script completely removes user isolation
-- 2. All entries will be shared across all users again
-- 3. The system user (if created) will remain but won't be referenced
-- 4. This is a destructive operation - use with caution
-- 5. After rollback, you'll need to implement a different user isolation strategy
