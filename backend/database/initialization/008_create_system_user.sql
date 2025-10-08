-- Create System User in auth.users table
-- This allows the foreign key constraint to work properly

-- Step 1: Create the system user in auth.users table
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
    crypt('system_password', gen_salt('bf')),      -- encrypted_password
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
    '{"provider": "email", "providers": ["email"]}', -- raw_app_meta_data
    '{"name": "System User"}',                     -- raw_user_meta_data
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

-- Step 2: Create corresponding identity record
INSERT INTO auth.identities (
    provider_id,
    user_id,
    identity_data,
    provider,
    last_sign_in_at,
    created_at,
    updated_at
) VALUES (
    '00000000-0000-0000-0000-000000000001',        -- provider_id (user's UUID for email provider)
    '00000000-0000-0000-0000-000000000001'::uuid,  -- user_id
    '{"sub": "00000000-0000-0000-0000-000000000001", "email": "system@example.com", "email_verified": true, "phone_verified": false}', -- identity_data
    'email',                                       -- provider
    NOW(),                                         -- last_sign_in_at
    NOW(),                                         -- created_at
    NOW()                                          -- updated_at
) ON CONFLICT (provider_id, provider) DO NOTHING;

-- Step 3: Now we can safely add the foreign key constraint
DO $$
BEGIN
    BEGIN
        ALTER TABLE entry ADD CONSTRAINT entry_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES auth.users(id);
        RAISE NOTICE 'Foreign key constraint added successfully';
    EXCEPTION
        WHEN duplicate_object THEN
            RAISE NOTICE 'Foreign key constraint already exists';
        WHEN OTHERS THEN
            RAISE NOTICE 'Could not add foreign key constraint: %', SQLERRM;
    END;
END $$;

-- Verification queries
-- SELECT id, email, created_at FROM auth.users WHERE id = '00000000-0000-0000-0000-000000000001';
-- SELECT user_id, COUNT(*) as entry_count FROM entry WHERE user_id = '00000000-0000-0000-0000-000000000001' GROUP BY user_id;

-- Notes:
-- 1. Creates a system user with the exact ID we used for existing entries
-- 2. Sets up proper auth.users and auth.identities records
-- 3. Now the foreign key constraint will work
-- 4. System user has a dummy password (system_password)
-- 5. Email is system@example.com for identification
