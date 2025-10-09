-- Migration 002: Add user_id Column to Entry Table
-- ============================================
-- Purpose: Add user_id column with foreign key constraint for user isolation
-- Prerequisites: 001_create_system_user.sql must be run first
-- Rollback: See rollback/002_rollback_user_id_column.sql
-- ============================================

-- Step 1: Verify system user exists before proceeding
DO $$
DECLARE
    user_exists BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM auth.users 
        WHERE id = '00000000-0000-0000-0000-000000000001'::uuid
    ) INTO user_exists;
    
    IF NOT user_exists THEN
        RAISE EXCEPTION 'System user does not exist. Please run 001_create_system_user.sql first.';
    END IF;
    
    RAISE NOTICE '✓ System user verified';
END $$;

-- Step 2: Add user_id column to entry table (nullable initially)
-- We keep it nullable temporarily to allow backfill in next migration
DO $$
BEGIN
    ALTER TABLE entry ADD COLUMN user_id UUID;
    RAISE NOTICE '✓ Added user_id column to entry table';
END $$;

-- Step 3: Create single-column index on user_id
-- This improves performance for user-specific queries
DO $$
BEGIN
    CREATE INDEX idx_entry_user_id ON entry(user_id);
    RAISE NOTICE '✓ Created index: idx_entry_user_id';
END $$;

-- Step 4: Create composite indexes for common query patterns
-- These optimize typical user-scoped queries

-- Index for queries filtering by user and date (most common pattern)
DO $$
BEGIN
    CREATE INDEX idx_entry_user_date ON entry(user_id, entry_date);
    RAISE NOTICE '✓ Created index: idx_entry_user_date';
END $$;

-- Index for queries filtering by user and transaction direction
DO $$
BEGIN
    CREATE INDEX idx_entry_user_direction ON entry(user_id, direction);
    RAISE NOTICE '✓ Created index: idx_entry_user_direction';
END $$;

-- Index for queries filtering by user and category
DO $$
BEGIN
    CREATE INDEX idx_entry_user_category ON entry(user_id, category_id);
    RAISE NOTICE '✓ Created index: idx_entry_user_category';
END $$;

-- Step 5: Add foreign key constraint to auth.users
-- This ensures referential integrity between entries and users
DO $$
BEGIN
    BEGIN
        ALTER TABLE entry ADD CONSTRAINT entry_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE RESTRICT;
        RAISE NOTICE '✓ Foreign key constraint added: entry_user_id_fkey';
    EXCEPTION
        WHEN duplicate_object THEN
            RAISE NOTICE 'Foreign key constraint already exists';
        WHEN OTHERS THEN
            RAISE EXCEPTION 'Failed to add foreign key constraint: %', SQLERRM;
    END;
END $$;

-- Verification: Confirm column and indexes were created
DO $$
DECLARE
    column_exists BOOLEAN;
    index_count INTEGER;
BEGIN
    -- Check column exists
    SELECT EXISTS(
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'entry' AND column_name = 'user_id'
    ) INTO column_exists;
    
    IF NOT column_exists THEN
        RAISE EXCEPTION 'user_id column was not created!';
    END IF;
    
    -- Check indexes were created
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes 
    WHERE tablename = 'entry' AND indexname LIKE '%user%';
    
    IF index_count < 4 THEN
        RAISE EXCEPTION 'Not all user indexes were created! Found %, expected 4', index_count;
    END IF;
    
    RAISE NOTICE '✓ Migration 002 completed successfully';
    RAISE NOTICE '  - user_id column: CREATED';
    RAISE NOTICE '  - Foreign key constraint: CREATED';
    RAISE NOTICE '  - User indexes: % created', index_count;
END $$;

-- Notes:
-- 1. user_id is nullable until backfill (migration 003)
-- 2. Foreign key constraint ensures users cannot be deleted with entries
-- 3. Four indexes created for optimal user-scoped query performance
-- 4. Next step: Run 003_backfill_and_constrain.sql to populate user_id

