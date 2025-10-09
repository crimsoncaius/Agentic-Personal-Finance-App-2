#!/usr/bin/env python3
"""
Clean Up Test Data

Safely removes test data from the database with user-specific filtering.
Prevents accidental deletion of system user data.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import date, timedelta

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

try:
    from database.connection import db_connection
except ImportError:
    from backend.database.connection import db_connection


SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


async def cleanup_user_data(
    user_id: str = None,
    start_date: str = None,
    end_date: str = None,
    force: bool = False,
):
    """
    Clean up test data with safety checks

    Args:
        user_id: Optional user ID to filter by (required if not using force)
        start_date: Optional start date (YYYY-MM-DD) for date range filtering
        end_date: Optional end date (YYYY-MM-DD) for date range filtering
        force: If True, allows deletion without user_id (dangerous!)
    """
    print("=" * 60)
    print("DATABASE CLEANUP")
    print("=" * 60)

    # Safety check: require user_id or force flag
    if not user_id and not force:
        print("\n❌ Error: Must specify --user-id or use --force")
        print("\nSafety requirement: Specify which user's data to delete")
        print("  python cleanup_test_data.py --user-id <USER_ID>")
        print("\nTo delete ALL data (dangerous!):")
        print("  python cleanup_test_data.py --force")
        sys.exit(1)

    # Protect system user
    if user_id == SYSTEM_USER_ID:
        print(f"\n❌ Error: Cannot delete system user data!")
        print(f"   System user ID: {SYSTEM_USER_ID}")
        print(f"   System user contains legacy/migrated data.")
        print(f"   To clean system data, use --force flag (NOT RECOMMENDED)")
        sys.exit(1)

    # Build query
    query = db_connection.client.table("entry")

    filters_desc = []

    if user_id:
        query = query.eq("user_id", user_id)
        filters_desc.append(f"User ID: {user_id}")

    if start_date:
        query = query.gte("entry_date", start_date)
        filters_desc.append(f"Date >= {start_date}")

    if end_date:
        query = query.lte("entry_date", end_date)
        filters_desc.append(f"Date <= {end_date}")

    # Preview what will be deleted
    print("\nFilters:")
    if filters_desc:
        for f in filters_desc:
            print(f"  - {f}")
    else:
        print("  - ⚠️  NO FILTERS (will delete ALL entries!)")

    try:
        # Count entries to be deleted
        preview_query = db_connection.client.table("entry").select("id", count="exact")
        if user_id:
            preview_query = preview_query.eq("user_id", user_id)
        if start_date:
            preview_query = preview_query.gte("entry_date", start_date)
        if end_date:
            preview_query = preview_query.lte("entry_date", end_date)

        preview = preview_query.execute()
        count_to_delete = preview.count

        print(f"\n📊 Entries matching filters: {count_to_delete}")

        if count_to_delete == 0:
            print("\n✓ No entries to delete")
            return

        # Confirmation prompt
        if not force:
            print(f"\n⚠️  WARNING: This will delete {count_to_delete} entries!")
            response = input("Type 'DELETE' to confirm: ")
            if response != "DELETE":
                print("Aborted.")
                return

        # Perform deletion
        print(f"\n🗑️  Deleting {count_to_delete} entries...")

        # Supabase delete requires a filter
        delete_query = db_connection.client.table("entry").delete()

        if user_id:
            delete_query = delete_query.eq("user_id", user_id)
        if start_date:
            delete_query = delete_query.gte("entry_date", start_date)
        if end_date:
            delete_query = delete_query.lte("entry_date", end_date)

        # If no filters, we need to delete all differently
        if not user_id and not start_date and not end_date:
            # Delete all requires a special approach
            delete_query = delete_query.neq(
                "id", "00000000-0000-0000-0000-000000000000"
            )

        result = delete_query.execute()

        print(f"✓ Deleted {count_to_delete} entries")

        # Verify cleanup
        remaining = db_connection.client.table("entry").select("id", count="exact")
        if user_id:
            remaining = remaining.eq("user_id", user_id)
        remaining_result = remaining.execute()

        print(f"\n📊 Remaining entries for this user: {remaining_result.count}")

        # Show total database state
        total = (
            db_connection.client.table("entry").select("id", count="exact").execute()
        )
        print(f"📊 Total entries in database: {total.count}")

        print("\n✓ CLEANUP COMPLETE")

    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Safely clean up test data from database",
        epilog="Examples:\n"
        "  Clean specific user:     python cleanup_test_data.py --user-id abc-123\n"
        "  Clean date range:        python cleanup_test_data.py --user-id abc-123 --start-date 2025-01-01\n"
        "  Clean all (dangerous!):  python cleanup_test_data.py --force",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--user-id", type=str, help="User ID to clean data for (recommended)"
    )
    parser.add_argument(
        "--start-date", type=str, help="Start date for deletion (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date", type=str, help="End date for deletion (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete all data without user filter (DANGEROUS!)",
    )
    args = parser.parse_args()

    await cleanup_user_data(
        user_id=args.user_id,
        start_date=args.start_date,
        end_date=args.end_date,
        force=args.force,
    )


if __name__ == "__main__":
    asyncio.run(main())
