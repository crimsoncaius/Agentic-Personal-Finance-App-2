-- Migration 001: Create System User in auth.users
-- ============================================
-- Purpose: Create a system user to own legacy/migrated data
-- Prerequisites: None
-- Rollback: See rollback/001_rollback_system_user.sql
-- ============================================

-- Create the system user in auth.users table
-- This user will own all existing entries during migration
INSERT INTO auth.users (
    id,
    instance_id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    invited_at,
    confirmation_token,
    confirmation_sent_at,
    recovery_token,
    recovery_sent_at,
    email_change_token_new,
    email_change,
    email_change_sent_at,
    last_sign_in_at,
    raw_app_meta_data,
    raw_user_meta_data,
    is_super_admin,
    created_at,
    updated_at,
    phone,
    phone_confirmed_at,
    phone_change,
    phone_change_token,
    phone_change_sent_at,
    email_change_token_current,
    email_change_confirm_status,
    banned_until,
    reauthentication_token,
    reauthentication_sent_at,
    is_sso_user,
    deleted_at
) VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,  -- Fixed system user ID
    '00000000-0000-0000-0000-000000000000'::uuid,  -- Default instance_id
    'authenticated',                                -- aud
    'authenticated',                                -- role
    'system@example.com',                          -- email
    crypt('SYSTEM_USER_NO_LOGIN', gen_salt('bf')), -- encrypted_password (strong random)
    NOW(),                                         -- email_confirmed_at
    NULL,                                          -- invited_at
    '',                                            -- confirmation_token
    NULL,                                          -- confirmation_sent_at
    '',                                            -- recovery_token
    NULL,                                          -- recovery_sent_at
    '',                                            -- email_change_token_new
    '',                                            -- email_change
    NULL,                                          -- email_change_sent_at
    NOW(),                                         -- last_sign_in_at
    '{"provider": "system", "providers": ["system"]}', -- raw_app_meta_data
    '{"name": "System User (Legacy Data)", "description": "Owns pre-migration entries"}', -- raw_user_meta_data
    false,                                         -- is_super_admin
    NOW(),                                         -- created_at
    NOW(),                                         -- updated_at
    NULL,                                          -- phone
    NULL,                                          -- phone_confirmed_at
    '',                                            -- phone_change
    '',                                            -- phone_change_token
    NULL,                                          -- phone_change_sent_at
    '',                                            -- email_change_token_current
    0,                                             -- email_change_confirm_status
    NULL,                                          -- banned_until
    '',                                            -- reauthentication_token
    NULL,                                          -- reauthentication_sent_at
    false,                                         -- is_sso_user
    NULL                                           -- deleted_at
) ON CONFLICT (id) DO NOTHING;

-- Create corresponding identity record for the system user
INSERT INTO auth.identities (
    provider_id,
    user_id,
    identity_data,
    provider,
    last_sign_in_at,
    created_at,
    updated_at
) VALUES (
    '00000000-0000-0000-0000-000000000001',        -- provider_id (matches user UUID)
    '00000000-0000-0000-0000-000000000001'::uuid,  -- user_id
    '{"sub": "00000000-0000-0000-0000-000000000001", "email": "system@example.com", "email_verified": true, "phone_verified": false}', -- identity_data
    'email',                                       -- provider
    NOW(),                                         -- last_sign_in_at
    NOW(),                                         -- created_at
    NOW()                                          -- updated_at
) ON CONFLICT (provider_id, provider) DO NOTHING;

-- Verification: Check that system user was created
DO $$
DECLARE
    user_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO user_count 
    FROM auth.users 
    WHERE id = '00000000-0000-0000-0000-000000000001'::uuid;
    
    IF user_count = 1 THEN
        RAISE NOTICE '✓ System user created successfully: 00000000-0000-0000-0000-000000000001';
    ELSE
        RAISE EXCEPTION 'System user creation failed!';
    END IF;
END $$;

-- Notes:
-- 1. System user ID: 00000000-0000-0000-0000-000000000001
-- 2. Email: system@example.com
-- 3. This user owns all pre-migration entries
-- 4. Cannot be used for actual login (random strong password)
-- 5. This must run BEFORE adding user_id column to entry table

