-- Expense Tracker MVP Database Schema
-- Based on Technical Design Document

-- Create custom types
CREATE TYPE entry_direction AS ENUM ('expense', 'income');
CREATE TYPE source_type AS ENUM ('manual', 'nlp');
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

-- Create indexes for performance
CREATE INDEX idx_entry_date ON entry(entry_date);
CREATE INDEX idx_entry_direction ON entry(direction);
CREATE INDEX idx_entry_category ON entry(category_id);
CREATE INDEX idx_entry_created_at ON entry(created_at);
CREATE INDEX idx_entry_source ON entry(source);

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
