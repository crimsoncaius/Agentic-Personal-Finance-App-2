-- Create a users view for application access
-- This provides a way to see user information without direct auth.users access

-- Create a simple users table for application use
-- This can be populated when users register through Supabase Auth
CREATE TABLE IF NOT EXISTS app_users (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create a function to sync users from auth.users to app_users
-- This would be called when users register
CREATE OR REPLACE FUNCTION sync_user_from_auth()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO app_users (id, email, name, created_at, updated_at)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'name', NEW.email),
        NEW.created_at,
        NEW.updated_at
    )
    ON CONFLICT (id) DO UPDATE SET
        email = EXCLUDED.email,
        name = EXCLUDED.name,
        updated_at = EXCLUDED.updated_at;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a view that shows users with their entry counts
CREATE OR REPLACE VIEW user_summary AS
SELECT 
    u.id,
    u.email,
    u.name,
    u.created_at,
    COUNT(e.id) as entry_count,
    COALESCE(SUM(CASE WHEN e.direction = 'expense' THEN e.amount_cents ELSE 0 END), 0) as total_expenses_cents,
    COALESCE(SUM(CASE WHEN e.direction = 'income' THEN e.amount_cents ELSE 0 END), 0) as total_income_cents
FROM app_users u
LEFT JOIN entry e ON u.id = e.user_id
GROUP BY u.id, u.email, u.name, u.created_at
ORDER BY u.created_at DESC;

-- Add the system user to app_users for reference
INSERT INTO app_users (id, email, name, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    'system@example.com',
    'System User',
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Notes:
-- 1. This creates an app_users table that mirrors auth.users
-- 2. The sync_user_from_auth() function can be used to populate it
-- 3. The user_summary view shows users with their financial data
-- 4. The system user is added for reference
-- 5. In production, you'd set up triggers to auto-sync from auth.users
