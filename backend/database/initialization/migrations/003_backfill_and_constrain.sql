-- Migration 003: Backfill user_id and Add Constraints
-- ============================================
-- Purpose: Assign existing entries to system user and enforce NOT NULL constraint
-- Prerequisites: 001_create_system_user.sql and 002_add_user_id_column.sql
-- Rollback: See rollback/003_rollback_backfill.sql
-- ============================================

-- Step 1: Verify prerequisites
DO $$
DECLARE
    system_user_exists BOOLEAN;
    user_id_column_exists BOOLEAN;
BEGIN
    -- Check system user exists
    SELECT EXISTS(
        SELECT 1 FROM auth.users 
        WHERE id = '00000000-0000-0000-0000-000000000001'::uuid
    ) INTO system_user_exists;
    
    IF NOT system_user_exists THEN
        RAISE EXCEPTION 'System user does not exist. Run 001_create_system_user.sql first.';
    END IF;
    
    -- Check user_id column exists
    SELECT EXISTS(
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'entry' AND column_name = 'user_id'
    ) INTO user_id_column_exists;
    
    IF NOT user_id_column_exists THEN
        RAISE EXCEPTION 'user_id column does not exist. Run 002_add_user_id_column.sql first.';
    END IF;
    
    RAISE NOTICE '✓ Prerequisites verified';
END $$;

-- Step 2: Check current state before backfill
DO $$
DECLARE
    total_entries INTEGER;
    entries_without_user INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_entries FROM entry;
    SELECT COUNT(*) INTO entries_without_user FROM entry WHERE user_id IS NULL;
    
    RAISE NOTICE 'Current state:';
    RAISE NOTICE '  - Total entries: %', total_entries;
    RAISE NOTICE '  - Entries without user_id: %', entries_without_user;
    
    IF entries_without_user = 0 THEN
        RAISE NOTICE '⚠ No entries need backfill (all already have user_id)';
    END IF;
END $$;

-- Step 3: Backfill all entries without user_id to system user
DO $$
DECLARE
    updated_count INTEGER;
    system_user_id UUID := '00000000-0000-0000-0000-000000000001'::uuid;
BEGIN
    -- Update all entries without user_id
    UPDATE entry 
    SET user_id = system_user_id
    WHERE user_id IS NULL;
    
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    
    IF updated_count > 0 THEN
        RAISE NOTICE '✓ Backfilled % entries to system user', updated_count;
    ELSE
        RAISE NOTICE '✓ No entries needed backfill';
    END IF;
END $$;

-- Step 4: Verify backfill completed successfully
DO $$
DECLARE
    remaining_null INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining_null FROM entry WHERE user_id IS NULL;
    
    IF remaining_null > 0 THEN
        RAISE EXCEPTION 'Backfill incomplete! % entries still have NULL user_id', remaining_null;
    END IF;
    
    RAISE NOTICE '✓ All entries now have user_id assigned';
END $$;

-- Step 5: Make user_id NOT NULL (enforce for all future entries)
DO $$
BEGIN
    ALTER TABLE entry ALTER COLUMN user_id SET NOT NULL;
    RAISE NOTICE '✓ user_id column set to NOT NULL';
END $$;

-- Step 6: Add check constraint to prevent invalid user IDs
-- This prevents using reserved/invalid UUIDs
DO $$
BEGIN
    BEGIN
        ALTER TABLE entry ADD CONSTRAINT check_user_id_valid 
            CHECK (
                user_id IS NOT NULL 
                AND user_id != '00000000-0000-0000-0000-000000000000'::uuid
                AND user_id != '00000000-0000-0000-0000-000000000002'::uuid
            );
        RAISE NOTICE '✓ Check constraint added: check_user_id_valid';
    EXCEPTION
        WHEN duplicate_object THEN
            RAISE NOTICE 'Check constraint already exists';
        WHEN OTHERS THEN
            RAISE EXCEPTION 'Failed to add check constraint: %', SQLERRM;
    END;
END $$;

-- Final verification and statistics
DO $$
DECLARE
    total_entries INTEGER;
    system_user_entries INTEGER;
    real_user_entries INTEGER;
    total_users INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_entries FROM entry;
    
    SELECT COUNT(*) INTO system_user_entries 
    FROM entry 
    WHERE user_id = '00000000-0000-0000-0000-000000000001'::uuid;
    
    SELECT COUNT(*) INTO real_user_entries 
    FROM entry 
    WHERE user_id != '00000000-0000-0000-0000-000000000001'::uuid;
    
    SELECT COUNT(*) INTO total_users FROM auth.users;
    
    RAISE NOTICE '✓ Migration 003 completed successfully';
    RAISE NOTICE '';
    RAISE NOTICE '=== Final Statistics ===';
    RAISE NOTICE 'Total entries: %', total_entries;
    RAISE NOTICE 'System user entries: %', system_user_entries;
    RAISE NOTICE 'Real user entries: %', real_user_entries;
    RAISE NOTICE 'Total users in system: %', total_users;
    RAISE NOTICE '';
    RAISE NOTICE 'Next step: Run 004_create_helper_objects.sql';
END $$;

-- Notes:
-- 1. All existing entries are now owned by system user (00000000-0000-0000-0000-000000000001)
-- 2. user_id is now NOT NULL - all future entries MUST have a valid user_id
-- 3. Check constraint prevents invalid/reserved UUIDs
-- 4. Foreign key constraint ensures data integrity with auth.users
-- 5. New user registrations will automatically create isolated data

