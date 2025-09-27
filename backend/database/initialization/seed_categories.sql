-- Seed initial categories for Expense Tracker MVP
-- Based on Technical Design Document

-- Insert expense categories
INSERT INTO category (id, name, type, is_system) VALUES
  (gen_random_uuid(), 'Food & Dining (Expense)', 'expense', true),
  (gen_random_uuid(), 'Transportation (Expense)', 'expense', true),
  (gen_random_uuid(), 'Housing (Expense)', 'expense', true),
  (gen_random_uuid(), 'Shopping (Expense)', 'expense', true),
  (gen_random_uuid(), 'Entertainment (Expense)', 'expense', true),
  (gen_random_uuid(), 'Health & Fitness (Expense)', 'expense', true),
  (gen_random_uuid(), 'Education (Expense)', 'expense', true),
  (gen_random_uuid(), 'Travel (Expense)', 'expense', true),
  (gen_random_uuid(), 'Insurance (Expense)', 'expense', true),
  (gen_random_uuid(), 'Miscellaneous (Expense)', 'expense', true);

-- Insert income categories
INSERT INTO category (id, name, type, is_system) VALUES
  (gen_random_uuid(), 'Salary (Income)', 'income', true),
  (gen_random_uuid(), 'Freelance (Income)', 'income', true),
  (gen_random_uuid(), 'Investment (Income)', 'income', true),
  (gen_random_uuid(), 'Gifts (Income)', 'income', true),
  (gen_random_uuid(), 'Refunds (Income)', 'income', true),
  (gen_random_uuid(), 'Other Income (Income)', 'income', true);
