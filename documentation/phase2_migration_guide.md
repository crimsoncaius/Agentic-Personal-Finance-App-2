# Phase 2: Database Migration Guide

## Overview

This guide walks through the database migration process to add user isolation to the Expense Tracker MVP. The migration adds a `user_id` column to the `entry` table and creates the necessary indexes and constraints.

## Migration Files Created

### 1. `004_add_user_id_to_entry_v2.sql` (Recommended)

- Adds `user_id` column to entry table (initially nullable)
- Creates indexes for performance
- Creates composite indexes for user-scoped queries
- **No foreign key constraint** (avoids auth.users access issues)

### 2. `005_backfill_user_data.sql`

- Assigns existing entries to a fixed system user ID
- Uses a predefined UUID (00000000-0000-0000-0000-000000000001) for system user
- Makes `user_id` NOT NULL after backfill
- Creates views and functions for user-specific data access

### 3. `006_rollback_user_id_migration.sql`

- Rollback script to remove user_id column if needed
- Drops all related indexes and constraints
- Removes user-specific views and functions

### 4. Updated `schema.sql`

- Updated main schema to include user_id column for new installations
- Includes all user-related indexes and functions

## Migration Steps

### Step 1: Backup Your Database

```bash
# Create a backup before migration
# Use your preferred backup method for Supabase/PostgreSQL
```

### Step 2: Run Migration Scripts

Execute these scripts in order in your Supabase SQL Editor:

1. **First, run the migration:**

```sql
-- Copy and paste contents of 004_add_user_id_to_entry_v2.sql
-- (This version avoids foreign key constraint issues)
```

2. **Then, run the backfill:**

```sql
-- Copy and paste contents of 005_backfill_user_data.sql
```

### Step 3: Verify Migration

Run these verification queries to ensure the migration worked:

```sql
-- Check that user_id column exists
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'entry' AND column_name = 'user_id';

-- Check that indexes were created
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'entry' AND indexname LIKE '%user_id%';

-- Check that all entries have user_id
SELECT COUNT(*) as total_entries FROM entry;
SELECT COUNT(*) as entries_with_user_id FROM entry WHERE user_id IS NOT NULL;
SELECT COUNT(*) as entries_without_user_id FROM entry WHERE user_id IS NULL;

-- Check system user entries
SELECT
    CASE
        WHEN e.user_id = '00000000-0000-0000-0000-000000000001'::uuid THEN 'system@example.com'
        ELSE COALESCE(u.email, 'unknown@example.com')
    END as user_email,
    COUNT(e.id) as entry_count
FROM entry e
LEFT JOIN auth.users u ON e.user_id = u.id
GROUP BY e.user_id, u.email
ORDER BY entry_count DESC;
```

### Step 4: Test User-Specific Functions

```sql
-- Test the user entries view
SELECT * FROM user_entries LIMIT 5;

-- Test the get_user_entries function
SELECT * FROM get_user_entries(
    '00000000-0000-0000-0000-000000000001'::uuid,
    5,
    0
);
```

## Updated Database Scripts

### Sample Data Generator

The `generate_sample_data.py` script has been updated to support user_id:

```bash
# Generate sample data for a specific user
python backend/scripts/db/generate_sample_data.py --user-id <user-uuid>

# Generate sample data without user_id (for backward compatibility)
python backend/scripts/db/generate_sample_data.py
```

## Database Schema Changes

### Before Migration

```sql
CREATE TABLE entry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  amount_cents BIGINT NOT NULL CHECK (amount_cents >= 0),
  direction entry_direction NOT NULL,
  entry_date DATE NOT NULL,
  category_id UUID REFERENCES category(id),
  description TEXT,
  source source_type NOT NULL DEFAULT 'manual',
  parse_confidence REAL CHECK (parse_confidence >= 0 AND parse_confidence <= 1),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### After Migration

```sql
CREATE TABLE entry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  amount_cents BIGINT NOT NULL CHECK (amount_cents >= 0),
  direction entry_direction NOT NULL,
  entry_date DATE NOT NULL,
  category_id UUID REFERENCES category(id),
  description TEXT,
  source source_type NOT NULL DEFAULT 'manual',
  parse_confidence REAL CHECK (parse_confidence >= 0 AND parse_confidence <= 1),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## New Indexes Created

### Primary Indexes

- `idx_entry_user_id` - For user-specific queries
- `idx_entry_user_date` - For user + date filtering
- `idx_entry_user_direction` - For user + direction filtering
- `idx_entry_user_category` - For user + category filtering

## New Views and Functions

### `user_entries` View

Provides a comprehensive view of entries with user and category information:

```sql
SELECT * FROM user_entries WHERE user_id = 'your-user-id';
```

### `get_user_entries()` Function

Safely retrieves entries for a specific user with pagination:

```sql
SELECT * FROM get_user_entries('user-uuid', 10, 0);
```

## Data Isolation Strategy

### System User Approach

- All existing entries are assigned to a "system" user
- This preserves existing data while enabling user isolation
- New entries will be properly user-scoped

### Future User Isolation

- Each user will only see their own entries
- Database queries will filter by `user_id`
- Backend API will validate user ownership

## Rollback Procedure

If you need to rollback the migration:

1. **Run the rollback script:**

```sql
-- Copy and paste contents of 006_rollback_user_id_migration.sql
```

2. **Verify rollback:**

```sql
-- Check that user_id column is gone
SELECT column_name FROM information_schema.columns
WHERE table_name = 'entry' AND column_name = 'user_id';
-- Should return no rows
```

## Testing the Migration

### 1. Check Data Integrity

```sql
-- Verify all entries still exist
SELECT COUNT(*) FROM entry;

-- Verify categories are unchanged
SELECT COUNT(*) FROM category;
```

### 2. Test Performance

```sql
-- Test user-specific query performance
EXPLAIN ANALYZE SELECT * FROM entry WHERE user_id = 'system-user-id' LIMIT 10;
```

### 3. Test Sample Data Generation

```bash
# Generate sample data for a test user
python backend/scripts/db/generate_sample_data.py --user-id <test-user-uuid>
```

## Next Steps

After successful migration:

1. **Update Backend Services** - Modify EntryService to include user_id parameters
2. **Add JWT Validation** - Implement authentication middleware
3. **Update API Routes** - Add user context to all entry operations
4. **Test User Isolation** - Verify users can only access their own data

## Troubleshooting

### Common Issues

1. **Foreign Key Constraint Errors**

   - Ensure Supabase auth.users table exists
   - Verify the system user was created successfully

2. **Index Creation Failures**

   - Check for existing indexes with same names
   - Verify sufficient database permissions

3. **Backfill Failures**
   - Check that existing entries don't have conflicting data
   - Verify system user creation was successful

### Recovery Steps

1. **Check Migration Status:**

```sql
-- See which tables have user_id column
SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name = 'user_id';
```

2. **Manual Backfill (if needed):**

```sql
-- Manually assign entries to system user
UPDATE entry SET user_id = 'system-user-uuid' WHERE user_id IS NULL;
```

## Success Criteria

- [ ] All existing entries preserved
- [ ] user_id column added and populated
- [ ] Indexes created successfully
- [ ] Views and functions working
- [ ] Sample data generation supports user_id
- [ ] Rollback procedure tested
- [ ] Performance acceptable for user-scoped queries

## Notes

- Migration is designed to be safe and reversible
- System user approach maintains backward compatibility
- All existing data is preserved during migration
- New installations will include user_id from the start
- Categories remain global (shared across users)
