#!/usr/bin/env python3
"""
Check what data is currently in the database
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


async def check_data():
    print("🔍 Checking database contents...")

    # Check categories
    categories = db_connection.client.table("category").select("*").execute()
    print(f"\n📁 Categories in database: {len(categories.data)}")
    if categories.data:
        print("Sample categories:")
        for cat in categories.data[:5]:
            print(f'  - {cat["name"]} ({cat["type"]})')

    # Check entries
    entries = db_connection.client.table("entry").select("*").execute()
    print(f"\n💰 Entries in database: {len(entries.data)}")
    if entries.data:
        print("Sample entries:")
        for entry in entries.data[:5]:
            print(
                f'  - {entry["description"]} - ${entry["amount_cents"]/100} ({entry["direction"]})'
            )
    else:
        print("  No entries found in database")


if __name__ == "__main__":
    asyncio.run(check_data())
