-- Rollback 003: Remove Constraints and Clear user_id Data
-- ============================================
-- Purpose: Remove NOT NULL constraint and check constraint, clear user_id values
-- WARNING: This removes all user associations from entries!
-- ============================================

-- Step 1: Check current state
DO $$
DECLARE
    total_entries INTEGER;
    entries_with_user INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_entries FROM entry;
    
    BEGIN
        SELECT COUNT(*) INTO entries_with_user FROM entry WHERE user_id IS NOT NULL;
        RAISE NOTICE 'Current state: % of % entries have user_id', entries_with_user, total_entries;
    EXCEPTION
        WHEN undefined_column THEN
            RAISE NOTICE 'user_id column does not exist - nothing to rollback';
            RETURN;
    END;
END $$;

-- Step 2: Drop check constraint
DO $$
BEGIN
    ALTER TABLE entry DROP CONSTRAINT IF EXISTS check_user_id_valid;
    ALTER TABLE entry DROP CONSTRAINT IF EXISTS check_user_id_not_empty;
    RAISE NOTICE '✓ Dropped check constraints';
END $$;

-- Step 3: Make user_id nullable again
DO $$
BEGIN
    ALTER TABLE entry ALTER COLUMN user_id DROP NOT NULL;
    RAISE NOTICE '✓ user_id column is now nullable';
END $$;

-- Step 4: Clear all user_id values (optional - uncomment if needed)
-- WARNING: This removes all user associations!
-- UPDATE entry SET user_id = NULL WHERE user_id IS NOT NULL;
-- RAISE NOTICE '✓ Cleared all user_id values';

-- Verification
DO $$
DECLARE
    is_nullable TEXT;
BEGIN
    SELECT is_nullable INTO is_nullable
    FROM information_schema.columns 
    WHERE table_name = 'entry' AND column_name = 'user_id';
    
    IF is_nullable = 'YES' THEN
        RAISE NOTICE '✓ Rollback 003 completed - constraints removed, column is nullable';
    ELSE
        RAISE EXCEPTION 'user_id column is still NOT NULL!';
    END IF;
END $$;

-- Note: To fully rollback, also run 002_rollback_user_id_column.sql

