-- Migration 004: Create Helper Views and Functions
-- ============================================
-- Purpose: Create convenient views and functions for user-scoped data access
-- Prerequisites: Migrations 001, 002, and 003 completed
-- Rollback: See rollback/004_rollback_helper_objects.sql
-- ============================================

-- Step 1: Create user_entries view
-- This view joins entries with user info and category info for easy querying
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

-- Step 2: Create get_user_entries function
-- This function provides a safe, performant way to retrieve user-specific entries
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
$$ LANGUAGE plpgsql STABLE;

-- Step 3: Create user summary view
-- Shows aggregate statistics per user
CREATE OR REPLACE VIEW user_summary AS
SELECT 
    u.id,
    u.email,
    u.created_at as user_created_at,
    COUNT(e.id) as total_entries,
    COALESCE(SUM(CASE WHEN e.direction = 'expense' THEN e.amount_cents ELSE 0 END), 0) as total_expenses_cents,
    COALESCE(SUM(CASE WHEN e.direction = 'income' THEN e.amount_cents ELSE 0 END), 0) as total_income_cents,
    COALESCE(
        SUM(CASE WHEN e.direction = 'income' THEN e.amount_cents ELSE 0 END) - 
        SUM(CASE WHEN e.direction = 'expense' THEN e.amount_cents ELSE 0 END), 
        0
    ) as net_balance_cents,
    MIN(e.entry_date) as earliest_entry_date,
    MAX(e.entry_date) as latest_entry_date
FROM auth.users u
LEFT JOIN entry e ON u.id = e.user_id
GROUP BY u.id, u.email, u.created_at
ORDER BY u.created_at DESC;

-- Step 4: Create function to get user stats by date range
CREATE OR REPLACE FUNCTION get_user_stats(
    p_user_id UUID,
    p_start_date DATE DEFAULT NULL,
    p_end_date DATE DEFAULT NULL
)
RETURNS TABLE (
    total_entries BIGINT,
    total_expenses_cents BIGINT,
    total_income_cents BIGINT,
    net_balance_cents BIGINT,
    expense_count BIGINT,
    income_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_entries,
        COALESCE(SUM(CASE WHEN direction = 'expense' THEN amount_cents ELSE 0 END), 0)::BIGINT as total_expenses_cents,
        COALESCE(SUM(CASE WHEN direction = 'income' THEN amount_cents ELSE 0 END), 0)::BIGINT as total_income_cents,
        COALESCE(
            SUM(CASE WHEN direction = 'income' THEN amount_cents ELSE 0 END) - 
            SUM(CASE WHEN direction = 'expense' THEN amount_cents ELSE 0 END),
            0
        )::BIGINT as net_balance_cents,
        COUNT(CASE WHEN direction = 'expense' THEN 1 END)::BIGINT as expense_count,
        COUNT(CASE WHEN direction = 'income' THEN 1 END)::BIGINT as income_count
    FROM entry
    WHERE user_id = p_user_id
        AND (p_start_date IS NULL OR entry_date >= p_start_date)
        AND (p_end_date IS NULL OR entry_date <= p_end_date);
END;
$$ LANGUAGE plpgsql STABLE;

-- Log success
DO $$
BEGIN
    RAISE NOTICE '✓ Created view: user_entries';
    RAISE NOTICE '✓ Created function: get_user_entries(uuid, int, int)';
    RAISE NOTICE '✓ Created view: user_summary';
    RAISE NOTICE '✓ Created function: get_user_stats(uuid, date, date)';
END $$;

-- Verification
DO $$
DECLARE
    view_count INTEGER;
    function_count INTEGER;
BEGIN
    -- Check views
    SELECT COUNT(*) INTO view_count
    FROM information_schema.views
    WHERE table_schema = 'public' 
        AND table_name IN ('user_entries', 'user_summary');
    
    -- Check functions
    SELECT COUNT(*) INTO function_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'public' 
        AND p.proname IN ('get_user_entries', 'get_user_stats');
    
    RAISE NOTICE '✓ Migration 004 completed successfully';
    RAISE NOTICE '  - Views created: %', view_count;
    RAISE NOTICE '  - Functions created: %', function_count;
    
    IF view_count < 2 OR function_count < 2 THEN
        RAISE WARNING 'Some helper objects may not have been created properly';
    END IF;
END $$;

-- Usage Examples (commented out - for reference):
-- 
-- Get user's recent entries:
-- SELECT * FROM get_user_entries('user-uuid-here', 20, 0);
-- 
-- Get user summary:
-- SELECT * FROM user_summary WHERE email = 'user@example.com';
-- 
-- Get user stats for date range:
-- SELECT * FROM get_user_stats('user-uuid-here', '2025-01-01', '2025-12-31');
-- 
-- View all entries with user context:
-- SELECT * FROM user_entries WHERE user_email = 'user@example.com' LIMIT 10;

-- Notes:
-- 1. user_entries view: Easy access to entries with user and category info
-- 2. user_summary view: Aggregate statistics per user
-- 3. get_user_entries(): Paginated, sorted retrieval of user entries
-- 4. get_user_stats(): Statistical summary with optional date filtering
-- 5. All objects are marked STABLE for query optimization
-- 6. System user (system@example.com) is handled specially in views

