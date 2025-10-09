-- Rollback 004: Remove Helper Views and Functions
-- ============================================
-- Purpose: Drop all helper views and functions created in migration 004
-- ============================================

-- Step 1: Drop views
DO $$
BEGIN
    DROP VIEW IF EXISTS user_entries CASCADE;
    DROP VIEW IF EXISTS user_summary CASCADE;
    RAISE NOTICE '✓ Dropped views';
END $$;

-- Step 2: Drop functions
DO $$
BEGIN
    DROP FUNCTION IF EXISTS get_user_entries(UUID, INTEGER, INTEGER);
    DROP FUNCTION IF EXISTS get_user_stats(UUID, DATE, DATE);
    RAISE NOTICE '✓ Dropped functions';
END $$;

-- Verification
DO $$
DECLARE
    view_count INTEGER;
    function_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO view_count
    FROM information_schema.views
    WHERE table_schema = 'public' 
        AND table_name IN ('user_entries', 'user_summary');
    
    SELECT COUNT(*) INTO function_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'public' 
        AND p.proname IN ('get_user_entries', 'get_user_stats');
    
    IF view_count = 0 AND function_count = 0 THEN
        RAISE NOTICE '✓ Rollback 004 completed - all helper objects removed';
    ELSE
        RAISE WARNING 'Some objects may still exist: views=%, functions=%', view_count, function_count;
    END IF;
END $$;

