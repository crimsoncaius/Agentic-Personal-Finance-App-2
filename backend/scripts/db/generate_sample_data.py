#!/usr/bin/env python3
"""
Generate comprehensive sample data for Expense Tracker MVP
Creates realistic personal finance data covering 6 months
"""

import asyncio
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from uuid import UUID

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Try both import paths to handle running from different directories
try:
    from database.connection import db_connection
    from models.schemas import CategoryKind, EntryDirection, SourceType
except ImportError:
    from backend.database.connection import db_connection
    from backend.models.schemas import CategoryKind, EntryDirection, SourceType


class SampleDataGenerator:
    """Generate realistic sample data for testing and development"""

    SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"

    def __init__(self, user_id: str):
        """
        Initialize data generator

        Args:
            user_id: UUID of user to generate data for (REQUIRED)

        Raises:
            ValueError: If user_id is system user or invalid
        """
        if not user_id:
            raise ValueError("user_id is required")

        if user_id == self.SYSTEM_USER_ID:
            raise ValueError(
                f"Cannot generate data for system user ({self.SYSTEM_USER_ID}). "
                "System user is reserved for legacy data."
            )

        self.categories = {}
        self.entries_data = []
        self.user_id = user_id

    async def validate_user_exists(self):
        """Validate that user exists in database"""
        try:
            # Check if user has any entries (validates user exists)
            result = (
                db_connection.client.table("entry")
                .select("id")
                .eq("user_id", self.user_id)
                .limit(1)
                .execute()
            )

            # If we can query without error, user_id is valid
            print(f"✓ Validated user_id: {self.user_id}")
        except Exception as e:
            raise ValueError(
                f"Failed to validate user_id {self.user_id}. "
                "User may not exist in auth.users. "
                f"Error: {e}"
            )

    async def load_categories(self):
        """Load existing categories from database"""
        print("📁 Loading categories...")
        result = db_connection.client.table("category").select("*").execute()

        for cat in result.data:
            self.categories[cat["id"]] = {
                "name": cat["name"],
                "type": cat["type"],
                "id": cat["id"],
            }

        print(f"✅ Loaded {len(self.categories)} categories")

    def generate_expense_entries(
        self, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """Generate realistic expense entries"""
        entries = []

        # Define spending patterns by category
        expense_patterns = {
            "Food & Dining (Expense)": {
                "frequency": 0.4,  # 40% of entries
                "amount_range": (5, 80),
                "descriptions": [
                    "Lunch at work",
                    "Coffee shop",
                    "Grocery shopping",
                    "Dinner out",
                    "Fast food",
                    "Restaurant",
                    "Takeout",
                    "Breakfast",
                    "Snacks",
                    "Work lunch",
                    "Date night dinner",
                    "Family dinner",
                    "Pizza delivery",
                ],
            },
            "Transportation (Expense)": {
                "frequency": 0.15,
                "amount_range": (10, 150),
                "descriptions": [
                    "Gas station",
                    "Uber ride",
                    "Bus fare",
                    "Parking meter",
                    "Metro card",
                    "Taxi",
                    "Car maintenance",
                    "Oil change",
                    "Public transport",
                    "Ride share",
                    "Toll road",
                    "Car wash",
                ],
            },
            "Housing (Expense)": {
                "frequency": 0.08,
                "amount_range": (800, 3000),
                "descriptions": [
                    "Rent payment",
                    "Mortgage payment",
                    "Utilities",
                    "Electric bill",
                    "Water bill",
                    "Internet bill",
                    "Cable TV",
                    "Home insurance",
                    "Property tax",
                    "HOA fees",
                    "Maintenance",
                    "Repairs",
                ],
            },
            "Shopping (Expense)": {
                "frequency": 0.12,
                "amount_range": (20, 500),
                "descriptions": [
                    "Amazon purchase",
                    "Clothing store",
                    "Electronics",
                    "Home goods",
                    "Online shopping",
                    "Department store",
                    "Bookstore",
                    "Gift shop",
                    "Furniture",
                    "Apparel",
                    "Accessories",
                    "Household items",
                ],
            },
            "Entertainment (Expense)": {
                "frequency": 0.08,
                "amount_range": (15, 200),
                "descriptions": [
                    "Movie tickets",
                    "Netflix subscription",
                    "Concert",
                    "Theater",
                    "Sports event",
                    "Gaming",
                    "Streaming service",
                    "Museum",
                    "Theme park",
                    "Bowling",
                    "Arcade",
                    "Books",
                ],
            },
            "Health & Fitness (Expense)": {
                "frequency": 0.06,
                "amount_range": (30, 300),
                "descriptions": [
                    "Gym membership",
                    "Doctor visit",
                    "Pharmacy",
                    "Dental checkup",
                    "Fitness class",
                    "Supplements",
                    "Medical supplies",
                    "Therapy",
                    "Eye exam",
                    "Prescription",
                    "Health insurance",
                    "Yoga class",
                ],
            },
            "Education (Expense)": {
                "frequency": 0.03,
                "amount_range": (50, 2000),
                "descriptions": [
                    "Online course",
                    "Textbook",
                    "Tuition",
                    "Workshop",
                    "Certification",
                    "Training",
                    "Software license",
                    "Educational app",
                ],
            },
            "Travel (Expense)": {
                "frequency": 0.04,
                "amount_range": (100, 2000),
                "descriptions": [
                    "Flight ticket",
                    "Hotel booking",
                    "Vacation rental",
                    "Car rental",
                    "Travel insurance",
                    "Sightseeing",
                    "Restaurant while traveling",
                    "Airport parking",
                    "Travel gear",
                    "Tour guide",
                ],
            },
            "Insurance (Expense)": {
                "frequency": 0.02,
                "amount_range": (50, 500),
                "descriptions": [
                    "Car insurance",
                    "Health insurance",
                    "Life insurance",
                    "Home insurance",
                    "Renters insurance",
                    "Disability insurance",
                ],
            },
            "Miscellaneous (Expense)": {
                "frequency": 0.02,
                "amount_range": (5, 100),
                "descriptions": [
                    "ATM fee",
                    "Bank fee",
                    "Service charge",
                    "Late fee",
                    "Donation",
                    "Tip",
                    "Miscellaneous",
                    "Other expense",
                ],
            },
        }

        current_date = start_date
        while current_date <= end_date:
            # Generate 2-8 entries per day (realistic daily spending)
            daily_entries = random.randint(2, 8)

            for _ in range(daily_entries):
                # Select category based on frequency
                category_name = random.choices(
                    list(expense_patterns.keys()),
                    weights=[
                        pattern["frequency"] for pattern in expense_patterns.values()
                    ],
                )[0]

                pattern = expense_patterns[category_name]
                category_id = self._get_category_id_by_name(category_name)

                if category_id:
                    amount = random.uniform(*pattern["amount_range"])
                    description = random.choice(pattern["descriptions"])

                    # Add some randomness to dates (not all on same day)
                    entry_date = current_date + timedelta(days=random.randint(0, 2))

                    entry_data = {
                        "amount_cents": int(amount * 100),
                        "direction": EntryDirection.EXPENSE.value,
                        "entry_date": entry_date.isoformat(),
                        "category_id": category_id,
                        "description": description,
                        "source": random.choices(
                            [SourceType.MANUAL, SourceType.NLP], weights=[0.7, 0.3]
                        )[0].value,
                        "parse_confidence": (
                            random.uniform(0.7, 0.95) if random.random() < 0.3 else None
                        ),
                    }

                    # Add user_id (required)
                    entry_data["user_id"] = self.user_id

                    entries.append(entry_data)

            current_date += timedelta(days=1)

        return entries

    def generate_income_entries(
        self, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """Generate realistic income entries"""
        entries = []

        # Define income patterns
        income_patterns = {
            "Salary (Income)": {
                "frequency": 0.6,  # 60% of income entries
                "amount_range": (2000, 8000),
                "descriptions": [
                    "Monthly salary",
                    "Bi-weekly salary",
                    "Paycheck",
                    "Direct deposit",
                    "Salary payment",
                    "Regular income",
                    "Monthly pay",
                ],
            },
            "Freelance (Income)": {
                "frequency": 0.2,
                "amount_range": (200, 3000),
                "descriptions": [
                    "Freelance project",
                    "Consulting work",
                    "Contract payment",
                    "Side project",
                    "Client payment",
                    "Gig work",
                    "Part-time work",
                ],
            },
            "Investment (Income)": {
                "frequency": 0.1,
                "amount_range": (50, 2000),
                "descriptions": [
                    "Dividend payment",
                    "Stock gains",
                    "Interest earned",
                    "Investment return",
                    "Capital gains",
                    "Bond interest",
                ],
            },
            "Gifts (Income)": {
                "frequency": 0.05,
                "amount_range": (25, 500),
                "descriptions": [
                    "Birthday gift",
                    "Holiday gift",
                    "Cash gift",
                    "Gift card",
                    "Wedding gift",
                    "Anniversary gift",
                    "Thank you gift",
                ],
            },
            "Refunds (Income)": {
                "frequency": 0.03,
                "amount_range": (10, 300),
                "descriptions": [
                    "Purchase refund",
                    "Return credit",
                    "Rebate",
                    "Refund check",
                    "Store credit",
                    "Return processing",
                    "Refund processed",
                ],
            },
            "Other Income (Income)": {
                "frequency": 0.02,
                "amount_range": (100, 1000),
                "descriptions": [
                    "Bonus",
                    "Commission",
                    "Overtime pay",
                    "Cashback",
                    "Reward points",
                    "Cash found",
                    "Miscellaneous income",
                ],
            },
        }

        # Generate monthly income entries
        current_date = start_date.replace(day=1)  # Start of month
        while current_date <= end_date:
            # Generate 1-3 income entries per month
            monthly_entries = random.randint(1, 3)

            for _ in range(monthly_entries):
                category_name = random.choices(
                    list(income_patterns.keys()),
                    weights=[
                        pattern["frequency"] for pattern in income_patterns.values()
                    ],
                )[0]

                pattern = income_patterns[category_name]
                category_id = self._get_category_id_by_name(category_name)

                if category_id:
                    amount = random.uniform(*pattern["amount_range"])
                    description = random.choice(pattern["descriptions"])

                    # Income typically comes at specific times of month
                    if category_name == "Salary (Income)":
                        entry_date = current_date + timedelta(
                            days=random.choice([0, 14, 28])
                        )  # Beginning, middle, or end of month
                    else:
                        entry_date = current_date + timedelta(
                            days=random.randint(0, 28)
                        )

                    entry_data = {
                        "amount_cents": int(amount * 100),
                        "direction": EntryDirection.INCOME.value,
                        "entry_date": entry_date.isoformat(),
                        "category_id": category_id,
                        "description": description,
                        "source": random.choices(
                            [SourceType.MANUAL, SourceType.NLP], weights=[0.8, 0.2]
                        )[0].value,
                        "parse_confidence": (
                            random.uniform(0.8, 0.98) if random.random() < 0.2 else None
                        ),
                    }

                    # Add user_id (required)
                    entry_data["user_id"] = self.user_id

                    entries.append(entry_data)

            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)

        return entries

    def _get_category_id_by_name(self, name: str) -> str:
        """Get category ID by name"""
        for cat_id, cat_data in self.categories.items():
            if cat_data["name"] == name:
                return cat_id
        return None

    async def insert_entries(self, entries: List[Dict[str, Any]]):
        """Insert entries into database"""
        print(f"💾 Inserting {len(entries)} entries...")

        # Insert in batches to avoid overwhelming the database
        batch_size = 50
        for i in range(0, len(entries), batch_size):
            batch = entries[i : i + batch_size]

            try:
                result = db_connection.client.table("entry").insert(batch).execute()
                print(
                    f"✅ Inserted batch {i//batch_size + 1}/{(len(entries)-1)//batch_size + 1}"
                )
            except Exception as e:
                print(f"❌ Error inserting batch {i//batch_size + 1}: {e}")
                # Continue with next batch
                continue

    async def generate_sample_data(self):
        """Generate and insert all sample data"""
        print("🚀 Starting sample data generation...")
        print(f"👤 User ID: {self.user_id}")

        # Validate user exists
        await self.validate_user_exists()

        # Load categories
        await self.load_categories()

        # Define date range (last 6 months)
        end_date = date.today()
        start_date = end_date - timedelta(days=180)

        print(f"📅 Generating data from {start_date} to {end_date}")

        # Generate expense entries
        print("💰 Generating expense entries...")
        expense_entries = self.generate_expense_entries(start_date, end_date)
        print(f"✅ Generated {len(expense_entries)} expense entries")

        # Generate income entries
        print("💵 Generating income entries...")
        income_entries = self.generate_income_entries(start_date, end_date)
        print(f"✅ Generated {len(income_entries)} income entries")

        # Combine all entries
        all_entries = expense_entries + income_entries

        # Shuffle to make it more realistic
        random.shuffle(all_entries)

        # Insert into database
        await self.insert_entries(all_entries)

        print(f"🎉 Sample data generation complete!")
        print(f"📊 Total entries created: {len(all_entries)}")
        print(f"   - Expenses: {len(expense_entries)}")
        print(f"   - Income: {len(income_entries)}")


async def main():
    """Main function to run sample data generation"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate 6 months of sample data for a specific user"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        required=True,
        help="User ID (UUID) to generate data for (REQUIRED)",
    )
    args = parser.parse_args()

    try:
        generator = SampleDataGenerator(user_id=args.user_id)
        await generator.generate_sample_data()
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
