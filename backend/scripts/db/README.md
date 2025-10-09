# Database Scripts

Collection of utility scripts for database setup, testing, data seeding, and cleanup.

## Scripts Overview

### 🔍 Verification & Testing

#### `verify_migration.py`

Verifies that all 4 production migrations have been successfully applied.

**Usage:**

```bash
python verify_migration.py
```

**Checks:**

- System user exists (00000000-0000-0000-0000-000000000001)
- user_id column is NOT NULL
- All 4 user-related indexes exist
- Foreign key and check constraints
- Views (user_entries, user_summary)
- Database functions
- Entry statistics per user

#### `test_tables.py`

Comprehensive database structure testing including user isolation features.

**Usage:**

```bash
python test_tables.py
```

**Tests:**

- Connection
- Custom enum types
- Table existence and structure
- **User isolation features** (user_id, indexes, views)
- All indexes (including 4 user indexes)
- Functions and triggers
- Data integrity
- Sample data

#### `simple_test.py`

Basic database connectivity test.

**Usage:**

```bash
python simple_test.py
```

#### `debug_db.py`

Debug database connectivity issues with detailed output.

**Usage:**

```bash
python debug_db.py
```

#### `check_data.py`

Quick overview of database contents (categories and entries).

**Usage:**

```bash
python check_data.py
```

---

### 👤 User Management

#### `create_test_user.py`

Provides instructions for creating test users in Supabase Auth.

**Usage:**

```bash
python create_test_user.py --email test@example.com
```

**Output:**

- Instructions for manual user creation via Supabase Dashboard
- SQL script for creating user directly
- Returns user_id for use in seeding

**Note:** Supabase Python client doesn't support admin user creation, so manual steps are required.

---

### 🌱 Data Seeding

#### `seed_user_data.py` ⭐ **PRIMARY SEEDING SCRIPT**

Generates 6 months of realistic financial data for a specific user.

**Usage:**

```bash
python seed_user_data.py --user-id <USER_UUID>
```

**Features:**

- Requires user_id (prevents accidental data generation)
- Blocks seeding to system user (00000000-0000-0000-0000-000000000001)
- Checks for existing data and prompts for confirmation
- Generates ~400-500 entries over 6 months
- Progress reporting

**Example:**

```bash
# After creating a test user, get their user_id
python seed_user_data.py --user-id abc-123-def-456

# Output:
# - 400-500 expense entries (realistic patterns)
# - 12-18 income entries (salary, freelance, etc.)
# - Proper user_id assignment
```

#### `generate_sample_data.py` (Low-level)

Core data generation logic used by `seed_user_data.py`.

**Usage:**

```bash
python generate_sample_data.py --user-id <USER_UUID>
```

**Note:** Use `seed_user_data.py` instead for better UX.

---

### 🧹 Data Cleanup

#### `cleanup_test_data.py`

Safely removes test data with user-specific filtering.

**Usage:**

```bash
# Clean specific user's data
python cleanup_test_data.py --user-id <USER_UUID>

# Clean specific date range
python cleanup_test_data.py --user-id <USER_UUID> --start-date 2025-01-01 --end-date 2025-06-30

# DANGEROUS: Delete ALL data (requires --force)
python cleanup_test_data.py --force
```

**Safety Features:**

- Requires --user-id or --force flag
- Blocks deletion of system user data
- Confirmation prompt before deletion
- Preview of entries to be deleted
- Reports remaining entries after cleanup

---

## Typical Workflow

### 1. Verify Migration

```bash
python verify_migration.py
```

### 2. Create Test User

Follow instructions from:

```bash
python create_test_user.py --email testuser@example.com
```

Copy the returned user_id.

### 3. Seed Data for Test User

```bash
python seed_user_data.py --user-id <USER_ID_FROM_STEP_2>
```

### 4. Verify Data

```bash
python verify_migration.py
# Should show system user + your test user with entries
```

### 5. Test Your App

Use the test user credentials to log in and test user isolation.

### 6. Clean Up (when done testing)

```bash
python cleanup_test_data.py --user-id <TEST_USER_ID>
```

---

## Important Constants

### System User

- **ID:** `00000000-0000-0000-0000-000000000001`
- **Email:** `system@example.com`
- **Purpose:** Owns legacy/migrated data
- **Protected:** Cannot seed or delete data for this user

---

## Migration Scripts Reference

The database has been migrated with these scripts (in `backend/database/initialization/migrations/`):

1. **001_create_system_user.sql** - Creates system user in auth.users
2. **002_add_user_id_column.sql** - Adds user_id column + 4 indexes
3. **003_backfill_and_constrain.sql** - Backfills data + adds constraints
4. **004_create_helper_objects.sql** - Creates views and functions

---

## Troubleshooting

### "user_id column does not exist"

Run migrations 001-004 in order on your database.

### "Cannot generate data for system user"

Use a real user ID, not `00000000-0000-0000-0000-000000000001`.

### "User may not exist in auth.users"

Create the user first using Supabase Dashboard or `create_test_user.py`.

### Slow queries

Check that all 4 user indexes exist:

```bash
python test_tables.py
```

---

## File Changes Summary

**Removed (outdated):**

- ✗ check_migration_status.py
- ✗ check_migration_simple.py
- ✗ test_user_id_migration.py

**Updated:**

- ✓ generate_sample_data.py - Now requires user_id
- ✓ cleanup_test_data.py - User filtering + safety
- ✓ test_tables.py - Tests user isolation features

**New:**

- ✓ verify_migration.py - Production verification
- ✓ create_test_user.py - User creation helper
- ✓ seed_user_data.py - Primary seeding tool

**Unchanged:**

- simple_test.py
- debug_db.py
- check_data.py
- **init**.py
