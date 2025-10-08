-- Migration: Add user_id column to entry table for user isolation (V2)
-- Phase 2: Database Schema & Migration
-- 
-- This migration adds user_id column to the entry table to enable user-specific data isolation.
-- V2: Simplified approach without foreign key constraint to avoid auth.users access issues.

-- Step 1: Add user_id column to entry table (nullable, no foreign key constraint)
-- We'll add the foreign key constraint later if possible
ALTER TABLE entry ADD COLUMN user_id UUID;

-- Step 2: Create index for performance on user_id queries
CREATE INDEX idx_entry_user_id ON entry(user_id);

-- Step 3: Create composite indexes for common query patterns
-- These indexes will improve performance for user-scoped queries
CREATE INDEX idx_entry_user_date ON entry(user_id, entry_date);
CREATE INDEX idx_entry_user_direction ON entry(user_id, direction);
CREATE INDEX idx_entry_user_category ON entry(user_id, category_id);

-- Step 4: Update the updated_at trigger to include user_id changes
-- (The existing trigger will automatically handle this, no changes needed)

-- Verification queries (run these after migration to ensure it worked)
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'entry' AND column_name = 'user_id';

-- SELECT indexname, indexdef 
-- FROM pg_indexes 
-- WHERE tablename = 'entry' AND indexname LIKE '%user_id%';

-- Notes:
-- 1. The user_id column is initially nullable to allow existing entries to be migrated
-- 2. No foreign key constraint is added initially to avoid auth.users access issues
-- 3. After data backfill, we'll make it NOT NULL and optionally add foreign key constraint
-- 4. Indexes are created for optimal query performance on user-scoped operations
-- 5. This migration is safe and reversible (can be rolled back if needed)
