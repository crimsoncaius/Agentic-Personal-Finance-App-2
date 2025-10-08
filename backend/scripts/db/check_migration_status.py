#!/usr/bin/env python3
"""
Check the current migration status of the database
Helps determine what migration steps have been completed
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

        # Check if it's nullable
        # We'll check this by trying to insert a NULL value (we'll rollback)
        print("   - Column is accessible")
    except Exception as e:
        print(f"❌ user_id column does not exist: {e}")
        print("   → Need to run 004_add_user_id_to_entry_v2.sql")
        return False

    # Check 2: Do user_id indexes exist?
    print("\n2️⃣ Checking user_id indexes...")
    try:
        # Test if we can query by user_id efficiently
        start_time = asyncio.get_event_loop().time()
        result = (
            db_connection.client.table("entry")
            .select("*")
            .eq("user_id", "test")
            .limit(1)
            .execute()
        )
        end_time = asyncio.get_event_loop().time()

        if end_time - start_time < 0.1:  # Should be fast with indexes
            print("✅ user_id indexes appear to exist (query was fast)")
        else:
            print("⚠️ user_id indexes may be missing (query was slow)")

    except Exception as e:
        print(f"❌ Error checking indexes: {e}")

    # Check 3: Are there entries with NULL user_id?
    print("\n3️⃣ Checking for entries without user_id...")
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

        print(f"📊 Total entries: {total_entries}")
        print(f"📊 Entries without user_id: {null_user_count}")

        if null_user_count == 0:
            print("✅ All entries have user_id")
            needs_backfill = False
        elif null_user_count == total_entries:
            print("⚠️ No entries have user_id - need to run backfill")
            needs_backfill = True
        else:
            print(f"⚠️ {null_user_count} entries missing user_id - need to run backfill")
            needs_backfill = True

    except Exception as e:
        print(f"❌ Error checking user_id population: {e}")
        needs_backfill = True

    # Check 4: Does the system user exist in entries?
    print("\n4️⃣ Checking for system user entries...")
    try:
        system_user_id = "00000000-0000-0000-0000-000000000001"
        system_entries = (
            db_connection.client.table("entry")
            .select("id", count="exact")
            .eq("user_id", system_user_id)
            .execute()
        )

        if system_entries.count > 0:
            print(f"✅ Found {system_entries.count} entries with system user ID")
            backfill_completed = True
        else:
            print("⚠️ No system user entries found")
            backfill_completed = False

    except Exception as e:
        print(f"❌ Error checking system user: {e}")
        backfill_completed = False

    # Check 5: Do views and functions exist?
    print("\n5️⃣ Checking for views and functions...")
    try:
        # Test user_entries view
        view_result = (
            db_connection.client.table("user_entries").select("*").limit(1).execute()
        )
        print("✅ user_entries view exists")
    except Exception as e:
        print(f"⚠️ user_entries view may not exist: {e}")

    # Summary and recommendations
    print("\n📋 Migration Status Summary")
    print("=" * 50)

    if not needs_backfill and backfill_completed:
        print("✅ Migration appears to be COMPLETE!")
        print("   → All entries have user_id")
        print("   → System user entries exist")
        print("   → Ready for Phase 3 (Backend Authentication)")
    elif needs_backfill:
        print("⚠️ Migration PARTIALLY COMPLETE")
        print("   → user_id column exists")
        print("   → Need to run backfill script")
        print("   → Run: 005_backfill_user_data.sql")
    else:
        print("❌ Migration INCOMPLETE")
        print("   → user_id column exists")
        print("   → Backfill may have issues")
        print("   → Check database manually")

    return True


async def main():
    """Main function to check migration status"""
    try:
        await check_migration_status()
    except Exception as e:
        print(f"\n💥 Migration status check crashed: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
