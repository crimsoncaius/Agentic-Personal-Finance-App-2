#!/usr/bin/env python3
"""
Load Entries from JSON Configuration

Generates realistic financial entries based on today's date using configuration from JSON file.
"""

import asyncio
import json
import random
import sys
import argparse
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

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
    from models.schemas import EntryDirection
except ImportError:
    from backend.database.connection import db_connection
    from backend.models.schemas import EntryDirection


SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


class EntryGenerator:
    """Generate realistic entries based on configuration"""

    def __init__(self, user_ids: List[str], months_back: int = 6):
        """
        Initialize entry generator

        Args:
            user_ids: List of user IDs to generate entries for
            months_back: Number of months back from today to generate data
        """
        self.user_ids = [uid for uid in user_ids if uid != SYSTEM_USER_ID]
        self.months_back = months_back
        self.categories = {}
        self.end_date = date.today()
        self.start_date = date.today() - timedelta(days=30 * months_back)

    async def load_categories(self):
        """Load existing categories from database"""
        print("📁 Loading categories...")
        result = db_connection.service_client.table("category").select("*").execute()

        for cat in result.data:
            self.categories[cat["name"]] = {
                "id": cat["id"],
                "type": cat["type"],
                "name": cat["name"],
            }

        print(f"✅ Loaded {len(self.categories)} categories")

    def _get_category_id(self, category_name: str) -> str:
        """Get category ID by name"""
        return self.categories.get(category_name, {}).get("id")

    def _generate_expenses(self, user_id: str) -> List[Dict[str, Any]]:
        """Generate realistic expense entries"""
        entries = []

        # Expense patterns
        expense_patterns = {
            "Food & Dining (Expense)": {
                "frequency": 0.4,
                "amount_range": (5, 80),
                "descriptions": [
                    "Lunch",
                    "Coffee",
                    "Groceries",
                    "Dinner",
                    "Breakfast",
                    "Snacks",
                    "Restaurant",
                    "Takeout",
                ],
            },
            "Transportation (Expense)": {
                "frequency": 0.15,
                "amount_range": (10, 150),
                "descriptions": [
                    "Gas",
                    "Uber",
                    "Bus fare",
                    "Parking",
                    "Metro card",
                    "Car maintenance",
                ],
            },
            "Housing (Expense)": {
                "frequency": 0.08,
                "amount_range": (800, 3000),
                "descriptions": [
                    "Rent",
                    "Utilities",
                    "Electric bill",
                    "Internet",
                    "Water bill",
                ],
            },
            "Shopping (Expense)": {
                "frequency": 0.12,
                "amount_range": (20, 500),
                "descriptions": [
                    "Amazon",
                    "Clothing",
                    "Electronics",
                    "Home goods",
                    "Online shopping",
                ],
            },
            "Entertainment (Expense)": {
                "frequency": 0.08,
                "amount_range": (15, 200),
                "descriptions": [
                    "Movie tickets",
                    "Concert",
                    "Streaming service",
                    "Gaming",
                    "Sports event",
                ],
            },
            "Healthcare (Expense)": {
                "frequency": 0.05,
                "amount_range": (30, 500),
                "descriptions": [
                    "Doctor visit",
                    "Pharmacy",
                    "Dental",
                    "Medicine",
                    "Health insurance",
                ],
            },
            "Miscellaneous (Expense)": {
                "frequency": 0.12,
                "amount_range": (10, 300),
                "descriptions": [
                    "Subscription",
                    "Gift",
                    "Personal care",
                    "Misc purchase",
                    "Other expense",
                ],
            },
        }

        # Generate entries across date range
        current_date = self.start_date
        while current_date <= self.end_date:
            for category_name, pattern in expense_patterns.items():
                if random.random() < pattern["frequency"] / 30:  # Daily probability
                    category_id = self._get_category_id(category_name)
                    if category_id:
                        amount = round(random.uniform(*pattern["amount_range"]), 2)
                        description = random.choice(pattern["descriptions"])

                        entries.append(
                            {
                                "user_id": user_id,
                                "amount_cents": int(amount * 100),
                                "direction": EntryDirection.EXPENSE.value,
                                "entry_date": current_date.isoformat(),
                                "category_id": category_id,
                                "description": description,
                            }
                        )

            current_date += timedelta(days=1)

        return entries

    def _generate_income(self, user_id: str) -> List[Dict[str, Any]]:
        """Generate realistic income entries"""
        entries = []

        income_patterns = {
            "Salary (Income)": {
                "amount_range": (3000, 8000),
                "day_of_month": 1,  # First of month
                "description": "Monthly salary",
            },
            "Freelance (Income)": {
                "amount_range": (500, 3000),
                "frequency": 0.3,  # 30% chance per month
                "description": "Freelance work",
            },
            "Other Income (Income)": {
                "amount_range": (50, 500),
                "frequency": 0.2,  # 20% chance per month
                "description": "Other income",
            },
        }

        # Generate monthly salary
        current_month = self.start_date.replace(day=1)
        while current_month <= self.end_date:
            # Salary
            salary_cat = self._get_category_id("Salary (Income)")
            if salary_cat:
                amount = round(random.uniform(3000, 8000), 2)
                entries.append(
                    {
                        "user_id": user_id,
                        "amount_cents": int(amount * 100),
                        "direction": EntryDirection.INCOME.value,
                        "entry_date": current_month.isoformat(),
                        "category_id": salary_cat,
                        "description": "Monthly salary",
                    }
                )

            # Occasional freelance
            if random.random() < 0.3:
                freelance_cat = self._get_category_id("Freelance (Income)")
                if freelance_cat:
                    amount = round(random.uniform(500, 3000), 2)
                    day = random.randint(5, 25)
                    income_date = current_month.replace(day=min(day, 28))
                    entries.append(
                        {
                            "user_id": user_id,
                            "amount_cents": int(amount * 100),
                            "direction": EntryDirection.INCOME.value,
                            "entry_date": income_date.isoformat(),
                            "category_id": freelance_cat,
                            "description": "Freelance work",
                        }
                    )

            # Next month
            if current_month.month == 12:
                current_month = current_month.replace(
                    year=current_month.year + 1, month=1
                )
            else:
                current_month = current_month.replace(month=current_month.month + 1)

        return entries

    async def generate_and_insert(self):
        """Generate and insert entries for all users"""
        print(f"\n📊 Generating entries for {len(self.user_ids)} user(s)")
        print(f"   Date range: {self.start_date} to {self.end_date}")
        print(f"   ({self.months_back} months)")

        total_created = 0
        total_failed = 0

        for user_id in self.user_ids:
            print(f"\n👤 Generating for user: {user_id}")

            # Generate entries
            expenses = self._generate_expenses(user_id)
            income = self._generate_income(user_id)
            all_entries = expenses + income

            print(
                f"   Generated {len(all_entries)} entries ({len(expenses)} expenses, {len(income)} income)"
            )

            # Insert in batches
            batch_size = 100
            created = 0
            failed = 0

            for i in range(0, len(all_entries), batch_size):
                batch = all_entries[i : i + batch_size]
                try:
                    result = (
                        db_connection.service_client.table("entry")
                        .insert(batch)
                        .execute()
                    )
                    created += len(batch)
                    print(
                        f"   ✓ Inserted batch {i // batch_size + 1} ({len(batch)} entries)"
                    )
                except Exception as e:
                    failed += len(batch)
                    print(f"   ✗ Failed batch {i // batch_size + 1}: {e}")

            print(f"   Summary: {created} created, {failed} failed")
            total_created += created
            total_failed += failed

        return total_created, total_failed


async def load_entries(json_file: str):
    """
    Load entries from JSON configuration

    Args:
        json_file: Path to JSON file containing configuration
    """
    print("=" * 60)
    print("LOAD ENTRIES FROM JSON CONFIGURATION")
    print("=" * 60)

    # Load JSON file
    json_path = Path(json_file)
    if not json_path.exists():
        print(f"\n❌ Error: File not found: {json_file}")
        return

    print(f"\n📂 Loading file: {json_file}")
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"\n❌ Error: Invalid JSON: {e}")
        return
    except Exception as e:
        print(f"\n❌ Error reading file: {e}")
        return

    # Validate structure
    if "generation_config" not in data:
        print("\n❌ Error: JSON must contain 'generation_config' object")
        print("Expected format:")
        print(
            """
{
  "users": [...],
  "generation_config": {
    "months_back": 6,
    "users_to_populate": ["uuid1", "uuid2"]
  }
}
        """
        )
        return

    config = data["generation_config"]
    months_back = config.get("months_back", 6)
    users_to_populate = config.get("users_to_populate", [])

    if not users_to_populate:
        print("\n❌ Error: 'users_to_populate' must contain at least one user ID")
        return

    print(f"\n📋 Configuration:")
    print(f"   Months back: {months_back}")
    print(f"   Users to populate: {len(users_to_populate)}")

    # Create generator
    generator = EntryGenerator(users_to_populate, months_back)

    # Load categories
    await generator.load_categories()

    # Generate and insert
    created, failed = await generator.generate_and_insert()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total created: {created}")
    print(f"  Total failed: {failed}")

    if failed == 0:
        print("\n✅ All entries loaded successfully!")
    else:
        print(f"\n⚠️  {failed} entries failed to load")

    print("\n🎉 Database is ready for testing!")


def main():
    """Main entry point"""
    # Default path to JSON file in data directory
    default_json = Path(__file__).parent / "data" / "test_users.json"

    parser = argparse.ArgumentParser(
        description="Generate and load entries from JSON configuration"
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        default=str(default_json),
        help=f"Path to JSON file containing generation configuration (default: {default_json})",
    )

    args = parser.parse_args()

    asyncio.run(load_entries(args.json_file))


if __name__ == "__main__":
    main()
