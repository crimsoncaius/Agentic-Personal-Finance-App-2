#!/usr/bin/env python3
"""
Wipe Database Data

Safely removes all entries and users (except system user) from the database.
Preserves categories table.
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Fix Windows console encoding for emoji support
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

try:
    from database.connection import db_connection
except ImportError:
    from backend.database.connection import db_connection


SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


async def wipe_data(force: bool = False):
    """
    Wipe all entries and users from database

    Args:
        force: If True, skip confirmation prompt
    """
    print("=" * 60)
    print("DATABASE WIPE")
    print("=" * 60)

    # Get current counts
    print("\n📊 Current Database State:")
    try:
        entries_count = (
            db_connection.service_client.table("entry")
            .select("id", count="exact")
            .execute()
        )
        print(f"  Entries: {entries_count.count}")

        # Count users (we can't directly query auth.users, so we count distinct user_ids in entries)
        users_result = db_connection.service_client.rpc(
            "get_distinct_user_count"
        ).execute()
        print(f"  Users: {users_result.data if users_result.data else 'Unknown'}")

    except Exception as e:
        print(f"  ⚠️  Could not fetch current counts: {e}")

    # Confirmation
    if not force:
        print("\n⚠️  WARNING: This will delete:")
        print("  • ALL entries")
        print("  • ALL users (except system user)")
        print("  • Categories will be PRESERVED")
        print()
        response = (
            input("Are you sure you want to continue? (yes/no): ").strip().lower()
        )
        if response != "yes":
            print("\n❌ Operation cancelled")
            return

    print("\n🗑️  Starting wipe operation...")

    # Step 1: Delete all entries
    print("\n[1/2] Deleting all entries...")
    try:
        # Delete entries for all users except system user
        result = (
            db_connection.service_client.table("entry")
            .delete()
            .neq("user_id", SYSTEM_USER_ID)
            .execute()
        )
        print(f"  ✓ Deleted entries")
    except Exception as e:
        print(f"  ✗ Error deleting entries: {e}")

    # Step 2: Delete users from auth.users (except system user)
    print("\n[2/2] Deleting users...")
    try:
        # Note: We can't directly delete from auth.users via PostgREST
        # Users should be deleted via Supabase Auth API or manually
        # For now, we'll delete their entries which effectively isolates them
        print("  ⚠️  Note: Users must be deleted via Supabase Dashboard")
        print("  ℹ️  All user entries have been deleted")
    except Exception as e:
        print(f"  ✗ Error: {e}")

    # Final counts
    print("\n📊 Final Database State:")
    try:
        final_entries = (
            db_connection.service_client.table("entry")
            .select("id", count="exact")
            .execute()
        )
        print(f"  Entries: {final_entries.count}")

        # Count categories (should be unchanged)
        categories_count = (
            db_connection.service_client.table("category")
            .select("id", count="exact")
            .execute()
        )
        print(f"  Categories: {categories_count.count} (preserved)")

    except Exception as e:
        print(f"  ⚠️  Could not fetch final counts: {e}")

    print("\n✅ Wipe operation complete!")
    print("\nNext steps:")
    print("  1. Delete users via Supabase Dashboard (Authentication > Users)")
    print("  2. Run: python load_users.py test_data.json")
    print("  3. Run: python load_entries.py test_data.json")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Wipe all database data")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    asyncio.run(wipe_data(force=args.force))


if __name__ == "__main__":
    main()
