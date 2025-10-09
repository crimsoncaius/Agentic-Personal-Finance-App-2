-- Rollback 001: Remove System User
-- ============================================
-- Purpose: Remove the system user from auth.users
-- WARNING: This will fail if entries reference this user (foreign key constraint)
-- You must rollback migrations 002-004 first!
-- ============================================

-- Step 1: Check if any entries reference the system user
DO $$
DECLARE
    entry_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO entry_count 
    FROM entry 
    WHERE user_id = '00000000-0000-0000-0000-000000000001'::uuid;
    
    IF entry_count > 0 THEN
        RAISE EXCEPTION 'Cannot delete system user: % entries still reference it. Rollback migration 003 first!', entry_count;
    END IF;
    
    RAISE NOTICE 'No entries reference system user - safe to proceed';
END $$;

-- Step 2: Delete identity record
DO $$
BEGIN
    DELETE FROM auth.identities 
    WHERE user_id = '00000000-0000-0000-0000-000000000001'::uuid;
    RAISE NOTICE '✓ Deleted system user identity';
END $$;

-- Step 3: Delete system user
DO $$
BEGIN
    DELETE FROM auth.users 
    WHERE id = '00000000-0000-0000-0000-000000000001'::uuid;
    RAISE NOTICE '✓ Deleted system user';
END $$;

-- Verification
DO $$
DECLARE
    user_exists BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM auth.users 
        WHERE id = '00000000-0000-0000-0000-000000000001'::uuid
    ) INTO user_exists;
    
    IF user_exists THEN
        RAISE EXCEPTION 'System user still exists!';
    ELSE
        RAISE NOTICE '✓ Rollback 001 completed - system user removed';
    END IF;
END $$;

