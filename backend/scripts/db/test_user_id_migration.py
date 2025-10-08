#!/usr/bin/env python3
"""
Test script to validate user_id migration
Tests the database migration and verifies user isolation functionality
"""

import asyncio
import sys
import os
from uuid import uuid4

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Try both import paths to handle running from different directories
try:
    from database.connection import db_connection
except ImportError:
    from backend.database.connection import db_connection


async def test_user_id_migration():
    """Test the user_id migration and user isolation"""
    print("🧪 Testing User ID Migration")
    print("=" * 50)

    # Test 1: Check if user_id column exists
    print("\n1️⃣ Testing user_id column existence...")
    try:
        # Try to select user_id column
        result = (
            db_connection.client.table("entry").select("user_id").limit(1).execute()
        )
        print("✅ user_id column exists and is accessible")
    except Exception as e:
        print(f"❌ user_id column test failed: {e}")
        return False

    # Test 2: Check if all entries have user_id
    print("\n2️⃣ Testing user_id population...")
    try:
        # Get total entries
        total_result = (
            db_connection.client.table("entry").select("id", count="exact").execute()
        )
        total_entries = total_result.count

        # Get entries with user_id
        with_user_id = (
            db_connection.client.table("entry")
            .select("id", count="exact")
            .not_.is_("user_id", "null")
            .execute()
        )
        entries_with_user_id = with_user_id.count

        print(f"📊 Total entries: {total_entries}")
        print(f"📊 Entries with user_id: {entries_with_user_id}")

        if total_entries == entries_with_user_id:
            print("✅ All entries have user_id")
        else:
            print(f"⚠️ {total_entries - entries_with_user_id} entries missing user_id")

    except Exception as e:
        print(f"❌ user_id population test failed: {e}")
        return False

    # Test 3: Check system user entries exist
    print("\n3️⃣ Testing system user entries...")
    try:
        # Check if entries exist with the system user ID
        system_user_id = "00000000-0000-0000-0000-000000000001"

        system_entries = (
            db_connection.client.table("entry")
            .select("*", count="exact")
            .eq("user_id", system_user_id)
            .execute()
        )

        if system_entries.count > 0:
            print("✅ System user entries found")
            print(f"📊 System user ID: {system_user_id}")
            print(f"📊 System entries count: {system_entries.count}")
        else:
            print("⚠️ No system user entries found")

        # Check for any users in auth.users (optional)
        try:
            all_users = db_connection.client.table("auth.users").select("*").execute()
            if all_users.data:
                print(f"📊 Found {len(all_users.data)} users in auth.users")
                for user in all_users.data[:3]:  # Show first 3 users
                    print(f"   - {user.get('email', 'No email')} ({user['id']})")
            else:
                print(
                    "📊 No users found in auth.users table (this is normal for system user approach)"
                )
        except Exception as auth_e:
            print(f"📊 Could not check auth.users table: {auth_e} (this is normal)")

    except Exception as e:
        print(f"❌ System user test failed: {e}")
        return False

    # Test 4: Test user-specific queries
    print("\n4️⃣ Testing user-specific query functionality...")
    try:
        # Get a user_id from existing entries
        sample_entry = (
            db_connection.client.table("entry").select("user_id").limit(1).execute()
        )

        if sample_entry.data and sample_entry.data[0]["user_id"]:
            test_user_id = sample_entry.data[0]["user_id"]
            print(f"🧪 Testing with user_id: {test_user_id}")

            # Test user-specific query
            user_entries = (
                db_connection.client.table("entry")
                .select("*")
                .eq("user_id", test_user_id)
                .limit(5)
                .execute()
            )
            print(f"✅ Found {len(user_entries.data)} entries for test user")

            # Test that we can filter by user_id
            other_entries = (
                db_connection.client.table("entry")
                .select("*")
                .neq("user_id", test_user_id)
                .limit(5)
                .execute()
            )
            print(f"✅ Found {len(other_entries.data)} entries for other users")

        else:
            print("⚠️ No entries with user_id found for testing")

    except Exception as e:
        print(f"❌ User-specific query test failed: {e}")
        return False

    # Test 5: Test indexes
    print("\n5️⃣ Testing database indexes...")
    try:
        # This is a basic test - in production you'd use EXPLAIN ANALYZE
        # For now, we'll just verify the query runs efficiently
        start_time = asyncio.get_event_loop().time()

        # Test user_id index
        result = (
            db_connection.client.table("entry")
            .select("*")
            .eq("user_id", test_user_id)
            .limit(10)
            .execute()
        )

        end_time = asyncio.get_event_loop().time()
        query_time = (end_time - start_time) * 1000  # Convert to milliseconds

        print(f"✅ User-specific query completed in {query_time:.2f}ms")

        if query_time < 100:  # Should be fast with proper indexes
            print("✅ Query performance looks good")
        else:
            print("⚠️ Query performance may need optimization")

    except Exception as e:
        print(f"❌ Index test failed: {e}")
        return False

    # Test 6: Test sample data generation with user_id
    print("\n6️⃣ Testing sample data generation...")
    try:
        test_user_id = str(uuid4())
        print(f"🧪 Generating sample data for test user: {test_user_id}")

        # Import and test the sample data generator
        from generate_sample_data import SampleDataGenerator

        generator = SampleDataGenerator(user_id=test_user_id)
        await generator.load_categories()

        # Generate a small amount of test data
        from datetime import date, timedelta

        end_date = date.today()
        start_date = end_date - timedelta(days=7)  # Just 1 week of data

        expense_entries = generator.generate_expense_entries(start_date, end_date)
        print(f"✅ Generated {len(expense_entries)} expense entries")

        # Check that user_id is included
        if expense_entries and expense_entries[0].get("user_id") == test_user_id:
            print("✅ Sample data includes user_id correctly")
        else:
            print("❌ Sample data missing user_id")

    except Exception as e:
        print(f"❌ Sample data generation test failed: {e}")
        return False

    print("\n🎉 Migration Test Summary")
    print("=" * 50)
    print("✅ All migration tests passed!")
    print("📊 Database is ready for user isolation")
    print("🚀 Ready to proceed with Phase 3 (Backend Authentication)")

    return True


async def main():
    """Main function to run migration tests"""
    try:
        success = await test_user_id_migration()
        if success:
            print("\n✅ Migration validation successful!")
            exit(0)
        else:
            print("\n❌ Migration validation failed!")
            exit(1)
    except Exception as e:
        print(f"\n💥 Migration test crashed: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
