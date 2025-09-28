#!/usr/bin/env python3
"""
Clean up test data from the database
"""
import asyncio

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Try both import paths to handle running from different directories
try:
    from database.connection import db_connection
except ImportError:
    from backend.database.connection import db_connection


async def cleanup_test_data():
    print("🧹 Cleaning up test data...")

    # Delete test entries (those created by integration tests)
    # Use a condition that will match all entries (since we want to delete all)
    result = (
        db_connection.client.table("entry").delete().is_("id", "not_null").execute()
    )
    print(f"✅ Deleted all test entries from database")

    # Verify cleanup
    entries = db_connection.client.table("entry").select("*").execute()
    print(f"📊 Remaining entries: {len(entries.data)}")

    # Show remaining categories
    categories = db_connection.client.table("category").select("*").execute()
    print(f"📁 Categories remain: {len(categories.data)}")


if __name__ == "__main__":
    asyncio.run(cleanup_test_data())
