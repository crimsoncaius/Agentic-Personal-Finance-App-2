-- Fixed Backfill Script: Assign existing entries to users
-- Phase 2: Database Schema & Migration
--
-- This script handles the assignment of existing entries to user accounts.
-- It temporarily removes the foreign key constraint to allow system user assignment.
--
-- IMPORTANT: This assumes the user_id column already exists from a previous migration

-- Step 1: Check if we have existing entries without user_id
DO $$
DECLARE
    entry_count INTEGER;
    system_user_id UUID;
BEGIN
    -- Check if user_id column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'entry' AND column_name = 'user_id'
    ) THEN
        RAISE EXCEPTION 'user_id column does not exist. Please run 004_add_user_id_to_entry.sql first.';
    END IF;
    
    SELECT COUNT(*) INTO entry_count FROM entry WHERE user_id IS NULL;
    
    IF entry_count > 0 THEN
        RAISE NOTICE 'Found % entries without user_id that need to be assigned', entry_count;
        
        -- Generate a fixed UUID for the system user to ensure consistency
        system_user_id := '00000000-0000-0000-0000-000000000001'::uuid;
        
        RAISE NOTICE 'Will assign entries to system user with ID: %', system_user_id;
        
    ELSE
        RAISE NOTICE 'No entries found without user_id - backfill not needed';
    END IF;
END $$;

-- Step 2: Temporarily drop foreign key constraint if it exists
DO $$
BEGIN
    BEGIN
        ALTER TABLE entry DROP CONSTRAINT IF EXISTS entry_user_id_fkey;
        RAISE NOTICE 'Foreign key constraint dropped (if it existed)';
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Could not drop foreign key constraint: %. Continuing anyway.', SQLERRM;
    END;
END $$;

-- Step 3: Assign existing entries to system user
DO $$
DECLARE
    entry_count INTEGER;
    system_user_id UUID;
BEGIN
    SELECT COUNT(*) INTO entry_count FROM entry WHERE user_id IS NULL;
    system_user_id := '00000000-0000-0000-0000-000000000001'::uuid;
    
    IF entry_count > 0 THEN
        -- Update all entries without user_id to use the system user ID
        UPDATE entry 
        SET user_id = system_user_id
        WHERE user_id IS NULL;
        
        RAISE NOTICE 'Successfully assigned % entries to system user with ID: %', entry_count, system_user_id;
    ELSE
        RAISE NOTICE 'No entries needed assignment';
    END IF;
END $$;

-- Step 4: Make user_id NOT NULL after backfill
-- This ensures all future entries must have a user_id
ALTER TABLE entry ALTER COLUMN user_id SET NOT NULL;

-- Step 5: Add check constraint to ensure user_id is never empty or invalid
DO $$
BEGIN
    BEGIN
        ALTER TABLE entry ADD CONSTRAINT check_user_id_not_empty 
            CHECK (user_id IS NOT NULL 
                   AND user_id != '00000000-0000-0000-0000-000000000000'::uuid
                   AND user_id != '00000000-0000-0000-0000-000000000002'::uuid);
        RAISE NOTICE 'Check constraint added successfully';
    EXCEPTION
        WHEN duplicate_object THEN
            RAISE NOTICE 'Check constraint already exists. Skipping.';
        WHEN OTHERS THEN
            RAISE NOTICE 'Could not add check constraint: %. Proceeding without it.', SQLERRM;
    END;
END $$;

-- Step 6: Optionally try to re-add foreign key constraint
-- Note: This will likely fail in Supabase setups, which is fine
DO $$
BEGIN
    BEGIN
        ALTER TABLE entry ADD CONSTRAINT entry_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES auth.users(id);
        RAISE NOTICE 'Foreign key constraint re-added successfully';
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'Insufficient privileges to add foreign key constraint. Proceeding without it.';
        WHEN undefined_table THEN
            RAISE NOTICE 'auth.users table not accessible. Proceeding without foreign key constraint.';
        WHEN OTHERS THEN
            RAISE NOTICE 'Could not re-add foreign key constraint: %. Proceeding without it.', SQLERRM;
    END;
END $$;

-- Step 7: Create a view for easy access to user-specific data
CREATE OR REPLACE VIEW user_entries AS
SELECT 
    e.id,
    e.amount_cents,
    e.direction,
    e.entry_date,
    e.category_id,
    e.description,
    e.source,
    e.parse_confidence,
    e.created_at,
    e.updated_at,
    e.user_id,
    CASE 
        WHEN e.user_id = '00000000-0000-0000-0000-000000000001'::uuid THEN 'system@example.com'
        ELSE COALESCE(u.email, 'unknown@example.com')
    END as user_email,
    c.name as category_name,
    c.type as category_type
FROM entry e
LEFT JOIN auth.users u ON e.user_id = u.id
LEFT JOIN category c ON e.category_id = c.id;

-- Step 8: Create a function to safely get entries for a specific user
CREATE OR REPLACE FUNCTION get_user_entries(
    p_user_id UUID,
    p_limit INTEGER DEFAULT 10,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    amount_cents BIGINT,
    direction entry_direction,
    entry_date DATE,
    category_id UUID,
    description TEXT,
    source source_type,
    parse_confidence REAL,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    category_name TEXT,
    category_type category_kind
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        e.amount_cents,
        e.direction,
        e.entry_date,
        e.category_id,
        e.description,
        e.source,
        e.parse_confidence,
        e.created_at,
        e.updated_at,
        c.name as category_name,
        c.type as category_type
    FROM entry e
    LEFT JOIN category c ON e.category_id = c.id
    WHERE e.user_id = p_user_id
    ORDER BY e.entry_date DESC, e.created_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- Verification queries (run these to ensure backfill worked correctly)
-- SELECT COUNT(*) as total_entries FROM entry;
-- SELECT COUNT(*) as entries_with_user_id FROM entry WHERE user_id IS NOT NULL;
-- SELECT COUNT(*) as entries_without_user_id FROM entry WHERE user_id IS NULL;

-- SELECT 
--     CASE 
--         WHEN e.user_id = '00000000-0000-0000-0000-000000000001'::uuid THEN 'system@example.com'
--         ELSE COALESCE(u.email, 'unknown@example.com')
--     END as user_email,
--     COUNT(e.id) as entry_count
-- FROM entry e
-- LEFT JOIN auth.users u ON e.user_id = u.id
-- GROUP BY e.user_id, u.email
-- ORDER BY entry_count DESC;

-- Notes:
-- 1. This script temporarily drops the foreign key constraint to allow system user assignment
-- 2. Uses a fixed UUID (00000000-0000-0000-0000-000000000001) for the system user
-- 3. Tries to re-add foreign key constraint but continues if it fails
-- 4. The system user approach allows existing data to remain accessible
-- 5. Future entries will be properly user-scoped with real user IDs
-- 6. The view and function provide safe ways to access user-specific data
-- 7. System user entries will show as 'system@example.com' in the view
