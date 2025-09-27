# Database Documentation

## Overview

This document provides comprehensive documentation for the database layer of the Expense Tracker MVP application. The database is built on **Supabase PostgreSQL** and includes connection management, schema definitions, initialization scripts, and seeding utilities.

## Architecture

The database layer consists of:

- **Connection Management**: Supabase client configuration and connection handling
- **Schema Definition**: PostgreSQL tables, types, indexes, and triggers
- **Initialization**: Database setup and validation scripts
- **Data Seeding**: Pre-populated categories for expense and income tracking

## Files Structure

```
backend/database/
├── connection.py          # Database connection and configuration
├── __pycache__/          # Python cache files
└── initialization/       # Database initialization files
    ├── schema.sql        # Database schema definition
    ├── seed_categories.sql # Initial category data
    └── test_tables.py    # Database testing and validation script
```

## Database Connection (`connection.py`)

### Overview

The `connection.py` file provides a robust database connection manager for Supabase PostgreSQL with support for both standard and service role clients.

### Key Components

#### DatabaseSettings Class

```python
class DatabaseSettings(BaseSettings):
    """Database configuration settings"""
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: Optional[str] = None
```

**Features:**

- Uses Pydantic Settings for environment variable management
- Loads configuration from `.env` file
- Supports both anon key and service role key
- Ignores extra environment variables for security

**Required Environment Variables:**

- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase anon/public key
- `SUPABASE_SERVICE_ROLE_KEY`: Service role key (optional, for admin operations)

#### DatabaseConnection Class

```python
class DatabaseConnection:
    """Supabase database connection manager"""
```

**Features:**

- **Lazy Initialization**: Clients are created only when first accessed
- **Dual Client Support**:
  - `client`: Standard client using anon key (respects RLS)
  - `service_client`: Service role client (bypasses RLS for admin operations)
- **Connection Testing**: Built-in method to validate database connectivity
- **Error Handling**: Graceful handling of connection failures

**Usage Examples:**

```python
from backend.database.connection import db_connection

# Standard client (respects Row Level Security)
client = db_connection.client
result = client.table('category').select('*').execute()

# Service client (bypasses RLS for admin operations)
service_client = db_connection.service_client
result = service_client.table('entry').select('*').execute()

# Test connection
is_connected = await db_connection.test_connection()
```

### Global Instance

A global `db_connection` instance is provided for application-wide use:

```python
# Global database connection instance
db_connection = DatabaseConnection()
```

## Database Schema (`initialization/schema.sql`)

### Overview

The database schema defines the core data model for the expense tracker application, including custom types, tables, indexes, and triggers.

### Custom Types

```sql
CREATE TYPE entry_direction AS ENUM ('expense', 'income');
CREATE TYPE source_type AS ENUM ('manual', 'nlp');
CREATE TYPE category_kind AS ENUM ('expense', 'income');
```

**Purpose:**

- **entry_direction**: Defines whether a financial entry is an expense or income
- **source_type**: Tracks how the entry was created (manual input vs NLP parsing)
- **category_kind**: Specifies whether a category is for expenses or income

### Tables

#### Category Table

```sql
CREATE TABLE category (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  type category_kind NOT NULL,
  parent_id UUID REFERENCES category(id),
  is_system BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Fields:**

- `id`: Unique identifier (UUID v4)
- `name`: Category name (unique across all categories)
- `type`: Whether category is for 'expense' or 'income'
- `parent_id`: Self-referencing foreign key for hierarchical categories
- `is_system`: Flag to protect system-defined categories from deletion
- `created_at`: Timestamp when category was created
- `updated_at`: Timestamp when category was last modified

**Features:**

- **Hierarchical Structure**: Support for parent-child category relationships
- **System Protection**: `is_system` flag prevents accidental deletion of core categories
- **Automatic Timestamps**: Created and updated timestamps with timezone support

#### Entry Table

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

**Fields:**

- `id`: Unique identifier (UUID v4)
- `amount_cents`: Financial amount stored in cents for precision
- `direction`: Whether entry is expense or income
- `entry_date`: Date when the transaction occurred
- `category_id`: Foreign key to category table (nullable)
- `description`: Free-form description of the transaction
- `source`: How the entry was created ('manual' or 'nlp')
- `parse_confidence`: Confidence score for NLP-parsed entries (0.0 to 1.0)
- `created_at`: Timestamp when entry was created
- `updated_at`: Timestamp when entry was last modified

**Features:**

- **Precision Storage**: Amounts stored as integers (cents) to avoid floating-point precision issues
- **NLP Support**: Built-in support for tracking NLP parsing confidence
- **Flexible Categorization**: Category can be null until properly classified
- **Audit Trail**: Complete creation and modification timestamps

### Indexes

```sql
-- Entry table indexes
CREATE INDEX idx_entry_date ON entry(entry_date);
CREATE INDEX idx_entry_direction ON entry(direction);
CREATE INDEX idx_entry_category ON entry(category_id);
CREATE INDEX idx_entry_created_at ON entry(created_at);
CREATE INDEX idx_entry_source ON entry(source);

-- Category table indexes
CREATE INDEX idx_category_type ON category(type);
CREATE INDEX idx_category_parent ON category(parent_id);
CREATE INDEX idx_category_is_system ON category(is_system);
```

**Performance Optimizations:**

- **Date Queries**: Fast filtering by entry date
- **Direction Filtering**: Efficient expense vs income queries
- **Category Lookups**: Quick category-based filtering
- **Creation Time**: Fast chronological sorting
- **Source Tracking**: Efficient NLP vs manual entry queries
- **Category Hierarchy**: Fast parent-child relationship queries

### Triggers and Functions

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_category_updated_at BEFORE UPDATE ON category
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entry_updated_at BEFORE UPDATE ON entry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

**Features:**

- **Automatic Timestamps**: Automatically updates `updated_at` field on record modifications
- **Consistent Behavior**: Ensures all records maintain accurate modification timestamps
- **Database-Level**: Handled at the database level for reliability

## Database Testing and Validation (`initialization/test_tables.py`)

### Overview

The database testing script provides comprehensive validation of database setup, schema structure, and data integrity for the Supabase environment.

### Key Features

#### Comprehensive Test Suite

The `test_tables.py` script includes a `DatabaseTableTester` class that performs extensive validation:

```python
class DatabaseTableTester:
    """Comprehensive database table and structure testing"""
```

**Test Categories:**

1. **Connection Test**: Verifies Supabase connection functionality
2. **Custom Types Test**: Validates enum types (entry_direction, source_type, category_kind)
3. **Tables Existence Test**: Confirms required tables (category, entry) exist
4. **Table Structure Test**: Validates column structures and data types
5. **Indexes Test**: Tests performance indexes and query optimization
6. **Functions Test**: Validates database functions (update_updated_at_column)
7. **Triggers Test**: Confirms automatic timestamp updates work
8. **Data Integrity Test**: Validates constraints and data consistency
9. **Sample Data Test**: Confirms seeded categories are properly structured

#### Test Results and Reporting

**Success Output Example:**

```
🧪 Starting Database Table Tests
==================================================

🔍 Running Connection Test...
✅ Connection Test PASSED

🔍 Running Custom Types Test...
✅ Custom Types Test PASSED

🔍 Running Tables Existence Test...
✅ Tables Existence Test PASSED

📊 TEST RESULTS SUMMARY
==================================================
✅ Passed: 9/9
❌ Failed: 0/9

🎉 All tests passed! Your database is properly configured.
```

#### Advanced Testing Features

The testing script provides detailed validation of:

**Database Structure:**

- Custom enum types validation
- Table existence and column structure verification
- Index performance testing
- Function and trigger functionality testing

**Data Validation:**

- Constraint enforcement testing
- Sample data integrity checks
- Category type validation (expense vs income)
- Foreign key relationship testing

**Performance Testing:**

- Query execution with indexes
- Connection stability testing
- Error handling validation

**Test Output Examples:**

**Failed Test Output:**

```
❌ Custom Types Test FAILED
   Custom types error: relation "category" does not exist

❌ Tables Existence Test FAILED
   Tables existence error: relation "entry" does not exist

⚠️  Some tests failed. Check the output above for details.

💡 To fix issues:
   1. Run the schema.sql script in Supabase SQL Editor
   2. Run the seed_categories.sql script
   3. Run this test script again
```

### Usage

```bash
# Run the comprehensive database tests
python backend/database/initialization/test_tables.py
```

**Setup Process:**

1. **Create Supabase Project**: Set up your project at https://supabase.com
2. **Configure Environment**: Set up `.env` file with Supabase credentials
3. **Run Schema Setup**: Execute `initialization/schema.sql` in Supabase SQL Editor
4. **Seed Categories**: Execute `initialization/seed_categories.sql` in Supabase SQL Editor
5. **Validate Setup**: Run the test script to confirm everything works

**Manual Setup Instructions:**

```
📋 MANUAL DATABASE INITIALIZATION REQUIRED
============================================================

🔗 Follow these steps in your Supabase Dashboard:
   1. Go to https://supabase.com
   2. Sign in and select your project
   3. Navigate to 'SQL Editor' in the left sidebar
   4. Create a new query

📄 Step 1: Create Schema
   Copy and paste the contents of:
   backend/database/initialization/schema.sql
   Then click 'Run' to execute

🌱 Step 2: Seed Categories
   Copy and paste the contents of:
   backend/database/initialization/seed_categories.sql
   Then click 'Run' to execute

🧪 Step 3: Validate Setup
   Run: python backend/database/initialization/test_tables.py
```

## Data Seeding (`initialization/seed_categories.sql`)

### Overview

The seeding script populates the database with initial expense and income categories for the MVP.

### Expense Categories

```sql
INSERT INTO category (id, name, type, is_system) VALUES
  (gen_random_uuid(), 'Food & Dining (Expense)', 'expense', true),
  (gen_random_uuid(), 'Transportation (Expense)', 'expense', true),
  (gen_random_uuid(), 'Housing (Expense)', 'expense', true),
  -- ... additional categories
```

**Categories Include:**

- **Food & Dining**: Restaurants, groceries, coffee, meals
- **Transportation**: Public transit, rideshare, fuel, parking
- **Housing**: Rent, mortgage, utilities, maintenance
- **Shopping**: Clothing, electronics, household items
- **Entertainment**: Movies, games, subscriptions, hobbies
- **Health & Fitness**: Medical, pharmacy, gym, healthcare
- **Education**: Courses, books, school fees, training
- **Travel**: Flights, hotels, vacation expenses
- **Insurance**: Health, auto, home, life insurance
- **Miscellaneous**: Default fallback for uncategorized expenses

### Income Categories

```sql
INSERT INTO category (id, name, type, is_system) VALUES
  (gen_random_uuid(), 'Salary (Income)', 'income', true),
  (gen_random_uuid(), 'Freelance (Income)', 'income', true),
  -- ... additional categories
```

**Categories Include:**

- **Salary**: Regular employment income, wages, bonuses
- **Freelance**: Contract work, consulting, gig economy
- **Investment**: Dividends, interest, capital gains
- **Gifts**: Birthday money, wedding gifts, cash gifts
- **Refunds**: Purchase returns, overpayments, rebates
- **Other Income**: Default fallback for uncategorized income

### Features

- **UUID Generation**: Uses `gen_random_uuid()` for unique identifiers
- **System Flag**: All seeded categories marked as `is_system = true`
- **Type Safety**: Properly typed as 'expense' or 'income'
- **Comprehensive Coverage**: Covers common financial transaction types

## Environment Configuration

### Required Environment Variables

Create a `.env` file in the project root with:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-anon-public-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Optional: Application Configuration
CORS_ORIGINS=http://localhost:3000,https://your-domain.com
RATE_LIMIT_PER_MINUTE=100
```

### Security Considerations

- **Environment Variables**: Never commit `.env` files to version control
- **Key Rotation**: Regularly rotate Supabase keys
- **Service Role Key**: Use service role key only for admin operations
- **RLS Policies**: Implement Row Level Security for multi-tenant support

## Database Operations

### Common Queries

#### Retrieve All Categories

```python
from backend.database.connection import db_connection

# Get all categories
result = db_connection.client.table('category').select('*').execute()
categories = result.data

# Get expense categories only
expense_categories = db_connection.client.table('category')\
    .select('*')\
    .eq('type', 'expense')\
    .execute()
```

#### Create New Entry

```python
# Create a new expense entry
entry_data = {
    'amount_cents': 1250,  # $12.50
    'direction': 'expense',
    'entry_date': '2025-01-15',
    'category_id': 'category-uuid-here',
    'description': 'Coffee at Starbucks',
    'source': 'manual'
}

result = db_connection.client.table('entry').insert(entry_data).execute()
```

#### Query Entries with Filters

```python
# Get expenses from last week
from datetime import datetime, timedelta

last_week = datetime.now() - timedelta(days=7)
result = db_connection.client.table('entry')\
    .select('*, category(name)')\
    .eq('direction', 'expense')\
    .gte('entry_date', last_week.strftime('%Y-%m-%d'))\
    .order('entry_date', desc=True)\
    .execute()
```

### Error Handling

```python
from backend.database.connection import db_connection

try:
    # Test database connection
    is_connected = await db_connection.test_connection()
    if not is_connected:
        raise ConnectionError("Database connection failed")

    # Perform database operations
    result = db_connection.client.table('category').select('*').execute()

except Exception as e:
    print(f"Database operation failed: {e}")
    # Handle error appropriately
```

## Best Practices

### Connection Management

1. **Use Global Instance**: Use the provided `db_connection` global instance
2. **Lazy Loading**: Clients are created only when needed
3. **Error Handling**: Always wrap database operations in try-catch blocks
4. **Connection Testing**: Use `test_connection()` method for health checks

### Query Optimization

1. **Use Indexes**: Leverage the provided indexes for efficient queries
2. **Select Specific Fields**: Use `.select()` to limit returned data
3. **Use Filters**: Apply `.eq()`, `.gte()`, `.lte()` for efficient filtering
4. **Limit Results**: Use `.limit()` for pagination

### Data Integrity

1. **Use Transactions**: Wrap related operations in transactions
2. **Validate Input**: Validate data before database operations
3. **Handle Constraints**: Properly handle foreign key and check constraints
4. **Monitor Performance**: Use database monitoring tools

### Security

1. **Row Level Security**: Implement RLS policies for multi-tenant support
2. **Parameterized Queries**: Always use parameterized queries (Supabase client handles this)
3. **Key Management**: Rotate API keys regularly
4. **Audit Logging**: Log database operations for security monitoring

## Troubleshooting

### Common Issues

#### Connection Failures

**Symptoms:**

- `Database connection test failed`
- `SUPABASE_SERVICE_ROLE_KEY not configured`

**Solutions:**

1. Verify `.env` file exists and contains correct values
2. Check Supabase project URL and keys
3. Ensure internet connectivity
4. Verify Supabase project is active

#### Schema Issues

**Symptoms:**

- `relation "category" does not exist`
- `type "entry_direction" does not exist`

**Solutions:**

1. Run `initialization/schema.sql` in Supabase SQL Editor
2. Verify all custom types are created
3. Check table creation order
4. Ensure proper permissions

#### Data Issues

**Symptoms:**

- No categories found
- Foreign key constraint violations

**Solutions:**

1. Run `initialization/seed_categories.sql` to populate initial data
2. Check category IDs before creating entries
3. Verify data types match schema definitions
4. Use proper UUID format for foreign keys

### Debugging Tools

#### Database Status Check

```bash
python backend/database/initialization/test_tables.py
```

#### Direct SQL Queries

Use Supabase SQL Editor for direct database inspection:

```sql
-- Check table existence
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public';

-- Check category data
SELECT COUNT(*) as total_categories FROM category;

-- Check entry data
SELECT COUNT(*) as total_entries FROM entry;

-- Check recent entries
SELECT e.*, c.name as category_name
FROM entry e
LEFT JOIN category c ON e.category_id = c.id
ORDER BY e.created_at DESC
LIMIT 10;
```

## Future Enhancements

### Planned Features

1. **Multi-tenancy**: Add user_id foreign keys and RLS policies
2. **Soft Deletes**: Add deleted_at timestamps for data recovery
3. **Audit Trail**: Enhanced logging for data modifications
4. **Data Validation**: Additional check constraints and triggers
5. **Performance Monitoring**: Query performance tracking and optimization

### Migration Strategy

1. **Version Control**: Use Supabase migrations for schema changes
2. **Backward Compatibility**: Maintain compatibility with existing data
3. **Testing**: Test migrations in development environment first
4. **Rollback Plan**: Prepare rollback procedures for failed migrations

## Related Documentation

- [Technical Design Document](../technical_design_document.md) - Overall system architecture
- [Backend Libraries](../backend_libraries.md) - Backend dependencies and libraries
- [Requirements](../requirements.md) - Project requirements and specifications

## Support

For database-related issues:

1. Check this documentation first
2. Run the test script for comprehensive status: `python backend/database/initialization/test_tables.py`
3. Review Supabase dashboard for errors
4. Check application logs for detailed error messages
5. Consult Supabase documentation for advanced topics
