#!/usr/bin/env python3
"""
Seed User Data

Generates 6 months of realistic financial data for a specific user.
This is a convenience wrapper around generate_sample_data.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

try:
    from database.connection import db_connection
    from scripts.db.generate_sample_data import SampleDataGenerator
except ImportError:
    from backend.database.connection import db_connection
    from backend.scripts.db.generate_sample_data import SampleDataGenerator


SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


async def seed_user_data(user_id: str):
    """
    Seed 6 months of data for a specific user

    Args:
        user_id: UUID of user to seed data for

    Raises:
        ValueError: If user_id is invalid or is system user
    """
    print("=" * 60)
    print("SEED USER DATA - 6 Months of Sample Financial Data")
    print("=" * 60)
    print(f"\nTarget User ID: {user_id}")

    # Check if trying to seed system user
    if user_id == SYSTEM_USER_ID:
        raise ValueError(
            f"\n❌ Cannot seed data for system user!\n"
            f"   System user ID: {SYSTEM_USER_ID}\n"
            f"   System user is reserved for legacy/migrated data.\n"
            f"   Please create a real test user or use an existing user ID."
        )

    # Check if user already has data
    try:
        existing = (
            db_connection.client.table("entry")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )

        if existing.count > 0:
            print(f"\n⚠️  Warning: User already has {existing.count} entries")
            response = input("Continue and add more data? (yes/no): ")
            if response.lower() not in ["yes", "y"]:
                print("Aborted.")
                return
        else:
            print("✓ User has no existing entries")
    except Exception as e:
        print(f"\n⚠️  Could not check existing entries: {e}")
        print("Continuing anyway...")

    # Generate data
    print("\n" + "=" * 60)
    try:
        generator = SampleDataGenerator(user_id=user_id)
        await generator.generate_sample_data()

        print("\n" + "=" * 60)
        print("✓ DATA SEEDING COMPLETE!")
        print("=" * 60)
        print(f"\nUser {user_id} now has 6 months of sample data.")
        print("\nNext steps:")
        print(f"  1. Verify data: python verify_migration.py")
        print(f"  2. View in app with this user ID")
        print(f"  3. Clean up later: python cleanup_test_data.py --user-id {user_id}")

    except ValueError as e:
        print(f"\n❌ Validation Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed 6 months of sample data for a specific user",
        epilog="Example: python seed_user_data.py --user-id abc-123-def-456",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        required=True,
        help="UUID of user to generate data for (REQUIRED)",
    )
    args = parser.parse_args()

    await seed_user_data(user_id=args.user_id)


if __name__ == "__main__":
    asyncio.run(main())
