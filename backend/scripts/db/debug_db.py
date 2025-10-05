#!/usr/bin/env python3
"""
Debug database connectivity issues
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

try:
    from database.connection import db_connection

    print("Database connection imported successfully")
except ImportError as e:
    print(f"Failed to import database connection: {e}")
    sys.exit(1)


def test_direct_connection():
    """Test direct database connection"""
    try:
        print("=== Testing Direct Connection ===")

        # Test category table
        print("Testing category table...")
        result = db_connection.client.table("category").select("id").limit(1).execute()
        print(f"Category table: {len(result.data)} rows returned")
        print(f"Result data: {result.data}")

        # Test entry table
        print("Testing entry table...")
        result = db_connection.client.table("entry").select("id").limit(1).execute()
        print(f"Entry table: {len(result.data)} rows returned")
        print(f"Result data: {result.data}")

        return True

    except Exception as e:
        print(f"Direct connection test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_simple_query():
    """Test a simple query that matches what the NLP service does"""
    try:
        print("\n=== Testing Simple Query ===")

        # This is similar to what _get_categories_sync does
        print("Testing category query with specific columns...")
        result = (
            db_connection.client.table("category").select("id, name, type").execute()
        )
        print(f"Category query: {len(result.data)} rows returned")
        print(f"Result data: {result.data}")

        # This is similar to what the entry queries do
        print("Testing entry query with filters...")
        result = (
            db_connection.client.table("entry")
            .select("id, entry_date, amount_cents, direction, category_id, description")
            .eq("direction", "expense")
            .limit(10)
            .execute()
        )
        print(f"Entry query: {len(result.data)} rows returned")
        print(f"Result data: {result.data}")

        return True

    except Exception as e:
        print(f"Simple query test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Database Debug Test")
    print("==================")

    success1 = test_direct_connection()
    success2 = test_simple_query()

    if success1 and success2:
        print("\nSUCCESS: All database tests passed")
    else:
        print("\nFAILURE: Some database tests failed")

