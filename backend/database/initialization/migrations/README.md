# Database Migration Scripts - User Isolation

This directory contains sequential migration scripts to add user isolation to the entry table.

## Overview

These migrations add `user_id` column to the `entry` table, enabling user-specific data isolation while preserving existing data by assigning it to a system user.

## Migration Order

**IMPORTANT: Run these scripts in order!**

1. **001_create_system_user.sql** - Creates system user for legacy data
2. **002_add_user_id_column.sql** - Adds user_id column with indexes and foreign key
3. **003_backfill_and_constrain.sql** - Assigns existing entries to system user and adds constraints
4. **004_create_helper_objects.sql** - Creates views and functions for convenient data access

## Prerequisites

- PostgreSQL database (Supabase)
- Existing `entry` table with data
- Existing `category` table
- Access to `auth.users` schema

## Running Migrations

### Option 1: Supabase Dashboard

1. Go to SQL Editor in Supabase Dashboard
2. Copy and paste each migration script in order
3. Run each script one at a time
4. Verify output messages for success

### Option 2: Supabase CLI

```bash
# Run migrations in order
supabase db execute --file migrations/001_create_system_user.sql
supabase db execute --file migrations/002_add_user_id_column.sql
supabase db execute --file migrations/003_backfill_and_constrain.sql
supabase db execute --file migrations/004_create_helper_objects.sql
```

### Option 3: MCP Server (from code)

```python
# Using Supabase MCP
from supabase_mcp import apply_migration

apply_migration(name="create_system_user", query=open("001_create_system_user.sql").read())
apply_migration(name="add_user_id_column", query=open("002_add_user_id_column.sql").read())
apply_migration(name="backfill_and_constrain", query=open("003_backfill_and_constrain.sql").read())
apply_migration(name="create_helper_objects", query=open("004_create_helper_objects.sql").read())
```

## What Each Migration Does

### 001 - Create System User
- Creates user `00000000-0000-0000-0000-000000000001`
- Email: `system@example.com`
- This user will own all pre-migration entries
- Creates corresponding identity record

### 002 - Add user_id Column
- Adds nullable `user_id UUID` column to `entry` table
- Creates foreign key constraint to `auth.users(id)`
- Creates 4 composite indexes for query performance:
  - `idx_entry_user_id` - user lookups
  - `idx_entry_user_date` - user + date queries
  - `idx_entry_user_direction` - user + income/expense queries
  - `idx_entry_user_category` - user + category queries

### 003 - Backfill and Constrain
- Assigns all existing entries to system user
- Makes `user_id` NOT NULL (required for all future entries)
- Adds check constraint to prevent invalid UUIDs
- Verifies all entries have valid user_id

### 004 - Create Helper Objects
- **Views:**
  - `user_entries` - Entries with user email and category info
  - `user_summary` - Aggregate statistics per user
- **Functions:**
  - `get_user_entries(user_id, limit, offset)` - Paginated entry retrieval
  - `get_user_stats(user_id, start_date, end_date)` - Financial statistics

## Rollback

If you need to undo these migrations, run rollback scripts in **reverse order**:

```bash
# Rollback in reverse order
migrations/rollback/004_rollback_helper_objects.sql
migrations/rollback/003_rollback_backfill.sql
migrations/rollback/002_rollback_user_id_column.sql
migrations/rollback/001_rollback_system_user.sql
```

**WARNING:** Rollback will delete user associations! Back up your data first.

## Verification Queries

After running all migrations, verify with these queries:

```sql
-- Check system user exists
SELECT id, email FROM auth.users 
WHERE id = '00000000-0000-0000-0000-000000000001';

-- Check user_id column
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'entry' AND column_name = 'user_id';

-- Check all entries have user_id
SELECT 
    COUNT(*) as total_entries,
    COUNT(user_id) as entries_with_user,
    COUNT(*) FILTER (WHERE user_id = '00000000-0000-0000-0000-000000000001') as system_user_entries
FROM entry;

-- Check indexes
SELECT indexname FROM pg_indexes 
WHERE tablename = 'entry' AND indexname LIKE '%user%';

-- Check views
SELECT table_name FROM information_schema.views 
WHERE table_schema = 'public';

-- Check functions
SELECT proname FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public' AND proname LIKE '%user%';
```

## Expected Results

After successful migration:

- System user with ID `00000000-0000-0000-0000-000000000001` exists
- `entry` table has NOT NULL `user_id` column
- All existing entries assigned to system user
- 4 indexes on user_id combinations created
- Foreign key constraint enforcing referential integrity
- 2 views created (`user_entries`, `user_summary`)
- 2 functions created (`get_user_entries`, `get_user_stats`)

## Usage Examples

```sql
-- Get entries for a specific user
SELECT * FROM get_user_entries('user-uuid-here', 20, 0);

-- View user summary
SELECT * FROM user_summary WHERE email = 'user@example.com';

-- Get statistics for date range
SELECT * FROM get_user_stats(
    'user-uuid-here', 
    '2025-01-01'::DATE, 
    '2025-12-31'::DATE
);

-- Browse entries with context
SELECT * FROM user_entries 
WHERE user_email = 'user@example.com' 
LIMIT 10;
```

## Notes

- **System User**: ID `00000000-0000-0000-0000-000000000001` is reserved
- **Data Isolation**: New users automatically get isolated data
- **Legacy Data**: All pre-migration data is owned by system user
- **Foreign Key**: ON DELETE RESTRICT prevents accidental user deletion
- **Performance**: Indexes optimize user-scoped queries

## Troubleshooting

**Error: System user already exists**
- Safe to ignore - migration uses `ON CONFLICT DO NOTHING`

**Error: user_id column already exists**
- Skip migration 002 or run rollback first

**Error: Foreign key constraint fails**
- Ensure system user exists before adding column

**Error: Cannot make column NOT NULL**
- Some entries may not have user_id - check backfill step

## Support

For issues or questions, check:
- Migration script comments (each script is self-documenting)
- RAISE NOTICE messages during execution
- Verification queries after each step

