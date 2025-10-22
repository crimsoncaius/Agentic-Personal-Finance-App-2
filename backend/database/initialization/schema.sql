-- Expense Tracker MVP Database Schema
-- Based on Technical Design Document

-- Create custom types
CREATE TYPE entry_direction AS ENUM ('expense', 'income');
CREATE TYPE category_kind AS ENUM ('expense', 'income');

-- Create category table
CREATE TABLE category (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  type category_kind NOT NULL,
  parent_id UUID REFERENCES category(id),
  is_system BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create entry table
CREATE TABLE entry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  amount_cents BIGINT NOT NULL CHECK (amount_cents >= 0),
  direction entry_direction NOT NULL,
  entry_date DATE NOT NULL,
  category_id UUID REFERENCES category(id),
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_entry_user_id ON entry(user_id);
CREATE INDEX idx_entry_date ON entry(entry_date);
CREATE INDEX idx_entry_direction ON entry(direction);
CREATE INDEX idx_entry_category ON entry(category_id);
CREATE INDEX idx_entry_created_at ON entry(created_at);

-- Create composite indexes for user-scoped queries
CREATE INDEX idx_entry_user_date ON entry(user_id, entry_date);
CREATE INDEX idx_entry_user_direction ON entry(user_id, direction);
CREATE INDEX idx_entry_user_category ON entry(user_id, category_id);

-- Create indexes for category table
CREATE INDEX idx_category_type ON category(type);
CREATE INDEX idx_category_parent ON category(parent_id);
CREATE INDEX idx_category_is_system ON category(is_system);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers to automatically update updated_at
CREATE TRIGGER update_category_updated_at BEFORE UPDATE ON category
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entry_updated_at BEFORE UPDATE ON entry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create view for user-specific entry access
CREATE OR REPLACE VIEW user_entries AS
SELECT 
    e.id,
    e.user_id,
    e.amount_cents,
    e.direction,
    e.entry_date,
    e.category_id,
    e.description,
    e.created_at,
    e.updated_at,
    u.email as user_email,
    c.name as category_name,
    c.type as category_type
FROM entry e
LEFT JOIN auth.users u ON e.user_id = u.id
LEFT JOIN category c ON e.category_id = c.id;

-- Create function to safely get entries for a specific user
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
