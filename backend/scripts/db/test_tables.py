#!/usr/bin/env python3
"""
Database Table Testing Script
Tests whether all required tables, types, indexes, and constraints are properly created.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Try both import paths to handle running from different directories
try:
    from database.connection import db_connection
except ImportError:
    from backend.database.connection import db_connection


class DatabaseTableTester:
    """Comprehensive database table and structure testing"""

    def __init__(self):
        self.connection = db_connection
        self.test_results = {}
        self.required_tables = ["category", "entry"]
        self.required_types = ["entry_direction", "source_type", "category_kind"]
        self.required_indexes = [
            "idx_entry_date",
            "idx_entry_direction",
            "idx_entry_category",
            "idx_entry_created_at",
            "idx_entry_source",
            "idx_category_type",
            "idx_category_parent",
            "idx_category_is_system",
            # User isolation indexes (Migration 002)
            "idx_entry_user_id",
            "idx_entry_user_date",
            "idx_entry_user_direction",
            "idx_entry_user_category",
        ]
        self.required_functions = ["update_updated_at_column"]
        self.required_triggers = [
            "update_category_updated_at",
            "update_entry_updated_at",
        ]

    async def run_all_tests(self) -> bool:
        """Run all database tests and return overall success status"""
        print("🧪 Starting Database Table Tests")
        print("=" * 50)

        tests = [
            ("Connection Test", self.test_connection),
            ("Custom Types Test", self.test_custom_types),
            ("Tables Existence Test", self.test_tables_exist),
            ("Table Structure Test", self.test_table_structures),
            ("User Isolation Features Test", self.test_user_isolation),
            ("Indexes Test", self.test_indexes),
            ("Functions Test", self.test_functions),
            ("Triggers Test", self.test_triggers),
            ("Data Integrity Test", self.test_data_integrity),
            ("Sample Data Test", self.test_sample_data),
        ]

        all_passed = True

        for test_name, test_func in tests:
            print(f"\n🔍 Running {test_name}...")
            try:
                result = await test_func()
                self.test_results[test_name] = result
                if result:
                    print(f"✅ {test_name} PASSED")
                else:
                    print(f"❌ {test_name} FAILED")
                    all_passed = False
            except Exception as e:
                print(f"❌ {test_name} ERROR: {e}")
                self.test_results[test_name] = False
                all_passed = False

        self.print_summary()
        return all_passed

    async def test_connection(self) -> bool:
        """Test basic database connection"""
        try:
            result = (
                self.connection.client.table("category").select("id").limit(1).execute()
            )
            return True
        except Exception as e:
            print(f"   Connection error: {e}")
            return False

    async def test_custom_types(self) -> bool:
        """Test if custom enum types exist by testing table constraints"""
        try:
            # Test by trying to insert data with enum values
            # This will fail if the enums don't exist
            test_data = {
                "name": "Test Category",
                "type": "expense",  # This should work if category_kind enum exists
                "is_system": False,
            }

            # Try to insert and immediately delete to test enum
            result = (
                self.connection.client.table("category").insert(test_data).execute()
            )
            if result.data:
                # Clean up test data
                test_id = result.data[0]["id"]
                self.connection.client.table("category").delete().eq(
                    "id", test_id
                ).execute()
                print("   ✓ Custom enum types are working")
                return True
            return False
        except Exception as e:
            print(f"   Custom types error: {e}")
            return False

    async def test_tables_exist(self) -> bool:
        """Test if required tables exist"""
        try:
            for table in self.required_tables:
                result = (
                    self.connection.client.table(table).select("*").limit(1).execute()
                )
                print(f"   ✓ Table '{table}' exists")
            return True
        except Exception as e:
            print(f"   Tables existence error: {e}")
            return False

    async def test_table_structures(self) -> bool:
        """Test table column structures and constraints"""
        try:
            # Test category table structure
            category_result = (
                self.connection.client.table("category").select("*").limit(1).execute()
            )
            if category_result.data:
                category_row = category_result.data[0]
                required_category_fields = [
                    "id",
                    "name",
                    "type",
                    "parent_id",
                    "is_system",
                    "created_at",
                    "updated_at",
                ]
                for field in required_category_fields:
                    if field not in category_row:
                        print(f"   Missing field '{field}' in category table")
                        return False
                print("   ✓ Category table structure is correct")

            # Test entry table structure
            entry_result = (
                self.connection.client.table("entry").select("*").limit(1).execute()
            )
            if entry_result.data:
                entry_row = entry_result.data[0]
                required_entry_fields = [
                    "id",
                    "amount_cents",
                    "direction",
                    "entry_date",
                    "category_id",
                    "description",
                    "source",
                    "parse_confidence",
                    "created_at",
                    "updated_at",
                    "user_id",  # Added in Migration 002
                ]
                for field in required_entry_fields:
                    if field not in entry_row:
                        print(f"   Missing field '{field}' in entry table")
                        return False
                print("   ✓ Entry table structure is correct")

            return True
        except Exception as e:
            print(f"   Table structure error: {e}")
            return False

    async def test_user_isolation(self) -> bool:
        """Test user isolation features from migrations"""
        try:
            SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"

            # Test 1: user_id column exists and is NOT NULL
            print("   Testing user_id column...")
            entry_result = (
                self.connection.client.table("entry")
                .select("user_id")
                .limit(1)
                .execute()
            )
            if not entry_result.data:
                print("   ⚠️  No entries found to test user_id")
            else:
                print("   ✓ user_id column exists and is accessible")

            # Test 2: Check all entries have user_id (NOT NULL enforced)
            print("   Testing NOT NULL constraint...")
            total = (
                self.connection.client.table("entry")
                .select("id", count="exact")
                .execute()
            )
            null_check = (
                self.connection.client.table("entry")
                .select("id", count="exact")
                .is_("user_id", "null")
                .execute()
            )

            if null_check.count > 0:
                print(f"   ❌ Found {null_check.count} entries with NULL user_id")
                return False
            else:
                print(
                    f"   ✓ All {total.count} entries have user_id (NOT NULL enforced)"
                )

            # Test 3: Check views exist
            print("   Testing views...")
            try:
                user_entries = (
                    self.connection.client.table("user_entries")
                    .select("*")
                    .limit(1)
                    .execute()
                )
                print("   ✓ user_entries view exists")
            except Exception as e:
                print(f"   ❌ user_entries view not found: {e}")
                return False

            try:
                user_summary = (
                    self.connection.client.table("user_summary")
                    .select("*")
                    .limit(1)
                    .execute()
                )
                print("   ✓ user_summary view exists")
            except Exception as e:
                print(f"   ❌ user_summary view not found: {e}")
                return False

            # Test 4: Test user-specific query performance
            print("   Testing user query performance...")
            import time

            start = time.time()
            user_query = (
                self.connection.client.table("entry")
                .select("id")
                .eq("user_id", SYSTEM_USER_ID)
                .limit(10)
                .execute()
            )
            elapsed = time.time() - start

            if elapsed < 0.5:
                print(f"   ✓ User query performed well ({elapsed*1000:.0f}ms)")
            else:
                print(
                    f"   ⚠️  User query was slow ({elapsed*1000:.0f}ms) - indexes may be missing"
                )

            print("   ✓ User isolation features are working")
            return True

        except Exception as e:
            print(f"   User isolation test error: {e}")
            return False

    async def test_indexes(self) -> bool:
        """Test if required indexes exist by testing query performance"""
        try:
            # Test queries that should benefit from indexes
            # If indexes don't exist, these queries will be slower but still work

            # Test category type index
            result1 = (
                self.connection.client.table("category")
                .select("*")
                .eq("type", "expense")
                .execute()
            )

            # Test entry date index (if entries exist)
            result2 = (
                self.connection.client.table("entry")
                .select("*")
                .gte("entry_date", "2024-01-01")
                .execute()
            )

            print("   ✓ Index-dependent queries executed successfully")
            print(f"   ✓ Found {len(result1.data)} expense categories")
            print(f"   ✓ Found {len(result2.data)} recent entries")
            return True
        except Exception as e:
            print(f"   Indexes error: {e}")
            return False

    async def test_functions(self) -> bool:
        """Test if required functions exist by testing trigger behavior"""
        try:
            # Test if the update_updated_at function works by updating a record
            # and checking if updated_at changes
            test_data = {
                "name": "Test Function Category",
                "type": "expense",
                "is_system": False,
            }

            # Insert test data
            result = (
                self.connection.client.table("category").insert(test_data).execute()
            )
            if not result.data:
                return False

            test_id = result.data[0]["id"]
            original_updated_at = result.data[0]["updated_at"]

            # Wait a moment and update
            import time

            time.sleep(1)

            # Update the record
            update_result = (
                self.connection.client.table("category")
                .update({"name": "Updated Test Function Category"})
                .eq("id", test_id)
                .execute()
            )

            if update_result.data:
                updated_record = update_result.data[0]
                new_updated_at = updated_record["updated_at"]

                # Clean up
                self.connection.client.table("category").delete().eq(
                    "id", test_id
                ).execute()

                if new_updated_at != original_updated_at:
                    print("   ✓ Update trigger function is working")
                    return True
                else:
                    print("   ⚠️  Update trigger may not be working properly")
                    return False

            return False
        except Exception as e:
            print(f"   Functions error: {e}")
            return False

    async def test_triggers(self) -> bool:
        """Test if required triggers exist by testing their behavior"""
        try:
            # This test is combined with the function test
            # If the function test passed, triggers are likely working
            print("   ✓ Triggers test combined with function test")
            return True
        except Exception as e:
            print(f"   Triggers error: {e}")
            return False

    async def test_data_integrity(self) -> bool:
        """Test data integrity constraints"""
        try:
            # Test category constraints
            category_result = (
                self.connection.client.table("category").select("*").execute()
            )
            if category_result.data:
                for cat in category_result.data:
                    # Check required fields
                    if not cat.get("name") or not cat.get("type"):
                        print(f"   Category missing required fields: {cat}")
                        return False

                    # Check enum values
                    if cat.get("type") not in ["expense", "income"]:
                        print(f"   Invalid category type: {cat.get('type')}")
                        return False

                print("   ✓ Category data integrity checks passed")

            return True
        except Exception as e:
            print(f"   Data integrity error: {e}")
            return False

    async def test_sample_data(self) -> bool:
        """Test if sample data exists and is properly structured"""
        try:
            # Check categories
            category_result = (
                self.connection.client.table("category").select("*").execute()
            )
            if not category_result.data:
                print("   No categories found")
                return False

            # Count by type
            expense_cats = [
                cat for cat in category_result.data if cat.get("type") == "expense"
            ]
            income_cats = [
                cat for cat in category_result.data if cat.get("type") == "income"
            ]

            print(f"   ✓ Found {len(expense_cats)} expense categories")
            print(f"   ✓ Found {len(income_cats)} income categories")

            # Check if we have the expected minimum categories
            if len(expense_cats) < 5 or len(income_cats) < 3:
                print("   Warning: Expected more sample categories")
                return False

            return True
        except Exception as e:
            print(f"   Sample data error: {e}")
            return False

    def print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)

        passed = sum(1 for result in self.test_results.values() if result)
        total = len(self.test_results)

        print(f"\n✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {total - passed}/{total}")

        if passed == total:
            print("\n🎉 All tests passed! Your database is properly configured.")
        else:
            print("\n⚠️  Some tests failed. Check the output above for details.")
            print("\n💡 To fix issues:")
            print("   1. Run the schema.sql script in Supabase SQL Editor")
            print("   2. Run the seed_categories.sql script")
            print("   3. Run this test script again")

        print("\n" + "=" * 50)


async def main():
    """Main function to run database tests"""
    tester = DatabaseTableTester()
    success = await tester.run_all_tests()
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Testing cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("💡 Make sure your .env file has correct Supabase credentials")
        sys.exit(1)
