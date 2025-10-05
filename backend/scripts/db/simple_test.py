#!/usr/bin/env python3
"""
Simple database connectivity test
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


async def test_connection():
    """Test basic database connectivity"""
    try:
        print("Testing database connection...")

        # Test category table
        print("Testing category table...")
        result = db_connection.client.table("category").select("id").limit(1).execute()
        print(f"Category table test: {len(result.data)} rows returned")

        # Test entry table
        print("Testing entry table...")
        result = db_connection.client.table("entry").select("id").limit(1).execute()
        print(f"Entry table test: {len(result.data)} rows returned")

        print("Database connection test PASSED")
        return True

    except Exception as e:
        print(f"Database connection test FAILED: {e}")
        return False


if __name__ == "__main__":
    import asyncio

    success = asyncio.run(test_connection())
    if success:
        print("SUCCESS: Database is accessible")
    else:
        print("FAILURE: Database is not accessible")

