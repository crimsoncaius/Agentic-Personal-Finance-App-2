#!/usr/bin/env python3
"""
Simple migration status check without Unicode characters
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


async def check_migration_status():
    """Check what migration steps have been completed"""
    print("Checking Database Migration Status")
    print("=" * 50)

    # Check 1: Does user_id column exist?
    print("\n1. Checking user_id column...")
    try:
        result = (
            db_connection.client.table("entry").select("user_id").limit(1).execute()
        )
        print("OK: user_id column exists")
    except Exception as e:
        print(f"ERROR: user_id column does not exist: {e}")
        print("   -> Need to run 004_add_user_id_to_entry_v2.sql")
        return False

    # Check 2: Are there entries with NULL user_id?
    print("\n2. Checking for entries without user_id...")
    try:
        total_result = (
            db_connection.client.table("entry").select("id", count="exact").execute()
        )
        total_entries = total_result.count

        null_user_result = (
            db_connection.client.table("entry")
            .select("id", count="exact")
            .is_("user_id", "null")
            .execute()
        )
        null_user_count = null_user_result.count

        print(f"Total entries: {total_entries}")
        print(f"Entries without user_id: {null_user_count}")

        if null_user_count == 0:
            print("OK: All entries have user_id")
            needs_backfill = False
        elif null_user_count == total_entries:
            print("WARNING: No entries have user_id - need to run backfill")
            needs_backfill = True
        else:
            print(
                f"WARNING: {null_user_count} entries missing user_id - need to run backfill"
            )
            needs_backfill = True

    except Exception as e:
        print(f"ERROR checking user_id population: {e}")
        needs_backfill = True

    # Check 3: Does the system user exist in entries?
    print("\n3. Checking for system user entries...")
    try:
        system_user_id = "00000000-0000-0000-0000-000000000001"
        system_entries = (
            db_connection.client.table("entry")
            .select("id", count="exact")
            .eq("user_id", system_user_id)
            .execute()
        )

        if system_entries.count > 0:
            print(f"OK: Found {system_entries.count} entries with system user ID")
            backfill_completed = True
        else:
            print("WARNING: No system user entries found")
            backfill_completed = False

    except Exception as e:
        print(f"ERROR checking system user: {e}")
        backfill_completed = False

    # Summary and recommendations
    print("\nMigration Status Summary")
    print("=" * 50)

    if not needs_backfill and backfill_completed:
        print("SUCCESS: Migration appears to be COMPLETE!")
        print("   -> All entries have user_id")
        print("   -> System user entries exist")
        print("   -> Ready for Phase 3 (Backend Authentication)")
    elif needs_backfill:
        print("WARNING: Migration PARTIALLY COMPLETE")
        print("   -> user_id column exists")
        print("   -> Need to run backfill script")
        print("   -> Run: 005_backfill_user_data_standalone.sql")
    else:
        print("ERROR: Migration INCOMPLETE")
        print("   -> user_id column exists")
        print("   -> Backfill may have issues")
        print("   -> Check database manually")

    return True


async def main():
    """Main function to check migration status"""
    try:
        await check_migration_status()
    except Exception as e:
        print(f"\nMigration status check crashed: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
