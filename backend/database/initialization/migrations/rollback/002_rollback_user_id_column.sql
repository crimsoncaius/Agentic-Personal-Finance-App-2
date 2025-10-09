-- Rollback 002: Remove user_id Column and Related Objects
-- ============================================
-- Purpose: Remove user_id column, indexes, and constraints from entry table
-- WARNING: This will delete all user association data!
-- Rollback migration 003 first if it was applied!
-- ============================================

-- Step 1: Check current state
DO $$
DECLARE
    column_exists BOOLEAN;
    entries_with_user INTEGER;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'entry' AND column_name = 'user_id'
    ) INTO column_exists;
    
    IF NOT column_exists THEN
        RAISE NOTICE 'user_id column does not exist - nothing to rollback';
        RETURN;
    END IF;
    
    SELECT COUNT(*) INTO entries_with_user 
    FROM entry 
    WHERE user_id IS NOT NULL;
    
    RAISE WARNING 'This will remove user_id from % entries!', entries_with_user;
END $$;

-- Step 2: Drop foreign key constraint
DO $$
BEGIN
    ALTER TABLE entry DROP CONSTRAINT IF EXISTS entry_user_id_fkey;
    RAISE NOTICE '✓ Dropped foreign key constraint';
END $$;

-- Step 3: Drop indexes
DO $$
BEGIN
    DROP INDEX IF EXISTS idx_entry_user_id;
    DROP INDEX IF EXISTS idx_entry_user_date;
    DROP INDEX IF EXISTS idx_entry_user_direction;
    DROP INDEX IF EXISTS idx_entry_user_category;
    RAISE NOTICE '✓ Dropped user_id indexes';
END $$;

-- Step 4: Drop the user_id column
DO $$
BEGIN
    ALTER TABLE entry DROP COLUMN IF EXISTS user_id;
    RAISE NOTICE '✓ Dropped user_id column';
END $$;

-- Verification
DO $$
DECLARE
    column_exists BOOLEAN;
    index_count INTEGER;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'entry' AND column_name = 'user_id'
    ) INTO column_exists;
    
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes 
    WHERE tablename = 'entry' AND indexname LIKE '%user%';
    
    IF column_exists THEN
        RAISE EXCEPTION 'user_id column still exists!';
    END IF;
    
    IF index_count > 0 THEN
        RAISE WARNING 'Some user indexes still exist: %', index_count;
    END IF;
    
    RAISE NOTICE '✓ Rollback 002 completed - user_id column removed';
END $$;

