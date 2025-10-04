"""
Tests for service layer - Tests with actual database operations
"""

import pytest
import pytest_asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

from models.schemas import CategoryQueryParams, EntryQueryParams, EntryUpdate
from services.category_service import CategoryService
from services.entry_service import EntryService
from database.connection import db_connection

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.db_real,  # Uses real database operations
    pytest.mark.llm_mock,  # No LLM operations in service tests
]


class TestEntryService:
    """Tests for entry service with actual database"""

    @pytest.mark.asyncio
    async def test_create_entry(self, test_data_setup):
        """Test real entry creation with database"""
        result = await EntryService.create_entry(
            amount=Decimal("15.75"),
            direction="expense",
            entry_date=date(2025, 1, 15),
            description="Real test expense",
            category_id=test_data_setup["category"]["id"],
        )

        assert result.amount_cents == 1575
        assert result.direction == "expense"
        assert result.description == "Real test expense"
        assert str(result.category_id) == test_data_setup["category"]["id"]
        assert "id" in result.__dict__

        # Clean up the created entry
        db_connection.client.table("entry").delete().eq("id", result.id).execute()

    @pytest.mark.asyncio
    async def test_create_entry_with_nlp_source(self, test_data_setup):
        """Test real entry creation with NLP source"""
        result = await EntryService.create_entry(
            amount=Decimal("25.50"),
            direction="expense",
            entry_date=date(2025, 1, 15),
            description="NLP parsed expense",
            source="nlp",
            category_id=test_data_setup["category"]["id"],
        )

        assert result.amount_cents == 2550
        assert result.direction == "expense"
        assert result.description == "NLP parsed expense"
        assert result.source == "nlp"

        # Clean up the created entry
        db_connection.client.table("entry").delete().eq("id", result.id).execute()

    @pytest.mark.asyncio
    async def test_get_entries_real_integration(self, test_data_setup):
        """Test real entry retrieval with database"""
        # Create test entries
        test_entries = [
            {
                "amount_cents": 1575,  # $15.75
                "direction": "expense",
                "entry_date": "2025-01-15",
                "category_id": test_data_setup["category"]["id"],
                "description": "Test expense 1",
                "source": "manual",
            },
            {
                "amount_cents": 2500,  # $25.00
                "direction": "expense",
                "entry_date": "2025-01-14",
                "category_id": test_data_setup["category"]["id"],
                "description": "Test expense 2",
                "source": "manual",
            },
        ]

        created_entries = []
        for entry_data in test_entries:
            result = db_connection.client.table("entry").insert(entry_data).execute()
            if result.data:
                created_entries.append(result.data[0])

        try:
            params = EntryQueryParams()
            result = await EntryService.get_entries(params)

            assert len(result["items"]) >= 2
            assert result["page"]["total"] >= 2

            # Verify entry structure
            for entry in result["items"]:
                assert hasattr(entry, "id")
                assert hasattr(entry, "amount")
                assert hasattr(entry, "direction")
                assert hasattr(entry, "description")

        finally:
            # Clean up test entries
            for entry in created_entries:
                db_connection.client.table("entry").delete().eq(
                    "id", entry["id"]
                ).execute()

    @pytest.mark.asyncio
    async def test_get_entries_with_filters_real_integration(self, test_data_setup):
        """Test real entry retrieval with filters using database"""
        # Create test entries
        test_entries = [
            {
                "amount_cents": 1575,  # $15.75
                "direction": "expense",
                "entry_date": "2025-01-15",
                "category_id": test_data_setup["category"]["id"],
                "description": "coffee expense",
                "source": "manual",
            },
            {
                "amount_cents": 2500,  # $25.00
                "direction": "expense",
                "entry_date": "2025-01-14",
                "category_id": test_data_setup["category"]["id"],
                "description": "lunch expense",
                "source": "manual",
            },
        ]

        created_entries = []
        for entry_data in test_entries:
            result = db_connection.client.table("entry").insert(entry_data).execute()
            if result.data:
                created_entries.append(result.data[0])

        try:
            # Test with direction filter
            params = EntryQueryParams(direction="expense")
            result = await EntryService.get_entries(params)
            assert len(result["items"]) >= 2

            # Test with search query
            params = EntryQueryParams(q="coffee")
            result = await EntryService.get_entries(params)
            # Should find at least one entry with "coffee" in description
            assert len(result["items"]) >= 1

            # Test with date range
            params = EntryQueryParams(
                date_from=date(2025, 1, 1), date_to=date(2025, 1, 31)
            )
            result = await EntryService.get_entries(params)
            assert len(result["items"]) >= 2

        finally:
            # Clean up test entries
            for entry in created_entries:
                db_connection.client.table("entry").delete().eq(
                    "id", entry["id"]
                ).execute()

    @pytest.mark.asyncio
    async def test_entry_validation_real_integration(self):
        """Test entry validation with real service"""
        # Test with invalid amount
        with pytest.raises(ValueError):
            await EntryService.create_entry(
                amount=Decimal("-10.00"),  # Negative amount
                direction="expense",
                entry_date=date(2025, 1, 15),
            )

        # Test with zero amount
        with pytest.raises(ValueError):
            await EntryService.create_entry(
                amount=Decimal("0.00"),  # Zero amount
                direction="expense",
                entry_date=date(2025, 1, 15),
            )

    @pytest.mark.asyncio
    async def test_concurrent_entry_operations(self, test_data_setup):
        """Test concurrent entry operations"""
        import asyncio

        async def create_entry(amount, description):
            return await EntryService.create_entry(
                amount=Decimal(str(amount)),
                direction="expense",
                entry_date=date(2025, 1, 15),
                description=description,
                category_id=test_data_setup["category"]["id"],
            )

        # Create multiple entries concurrently
        tasks = [
            create_entry(10.50, "Concurrent expense 1"),
            create_entry(20.75, "Concurrent expense 2"),
            create_entry(30.25, "Concurrent expense 3"),
        ]

        results = await asyncio.gather(*tasks)

        try:
            # All entries should be created successfully
            assert len(results) == 3
            for result in results:
                assert result.amount_cents > 0
                assert result.direction == "expense"

        finally:
            # Clean up all created entries
            for result in results:
                db_connection.client.table("entry").delete().eq(
                    "id", result.id
                ).execute()

    @pytest.mark.asyncio
    async def test_update_entry_success(self, test_data_setup):
        """Test successful entry update with real database"""
        # Create a test entry first
        test_entry = await EntryService.create_entry(
            amount=Decimal("20.00"),
            direction="expense",
            entry_date=date(2025, 1, 15),
            description="Original description",
            category_id=test_data_setup["category"]["id"],
        )

        try:
            # Update the entry
            update_data = EntryUpdate(
                amount=Decimal("25.50"),
                description="Updated description",
            )

            updated_entry = await EntryService.update_entry(test_entry.id, update_data)

            assert updated_entry is not None
            assert updated_entry.id == test_entry.id
            assert updated_entry.amount == Decimal("25.50")
            assert updated_entry.description == "Updated description"
            assert updated_entry.direction == "expense"  # Should remain unchanged
            assert updated_entry.entry_date == date(
                2025, 1, 15
            )  # Should remain unchanged

        finally:
            # Clean up
            db_connection.client.table("entry").delete().eq(
                "id", test_entry.id
            ).execute()

    @pytest.mark.asyncio
    async def test_update_entry_partial_update(self, test_data_setup):
        """Test partial entry update with only some fields"""
        # Create a test entry first
        test_entry = await EntryService.create_entry(
            amount=Decimal("30.00"),
            direction="income",
            entry_date=date(2025, 1, 10),
            description="Original income description",
            category_id=test_data_setup["category"]["id"],
        )

        try:
            # Update only the amount
            update_data = EntryUpdate(amount=Decimal("35.75"))

            updated_entry = await EntryService.update_entry(test_entry.id, update_data)

            assert updated_entry is not None
            assert updated_entry.amount == Decimal("35.75")
            assert (
                updated_entry.description == "Original income description"
            )  # Unchanged
            assert updated_entry.direction == "income"  # Unchanged
            assert updated_entry.entry_date == date(2025, 1, 10)  # Unchanged

        finally:
            # Clean up
            db_connection.client.table("entry").delete().eq(
                "id", test_entry.id
            ).execute()

    @pytest.mark.asyncio
    async def test_update_entry_not_found(self, test_data_setup):
        """Test entry update when entry doesn't exist"""
        fake_id = uuid4()
        update_data = EntryUpdate(amount=Decimal("10.00"))

        result = await EntryService.update_entry(fake_id, update_data)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_entry_validation(self, test_data_setup):
        """Test entry update validation with real service"""
        # Create a test entry first
        test_entry = await EntryService.create_entry(
            amount=Decimal("20.00"),
            direction="expense",
            entry_date=date(2025, 1, 15),
            description="Test entry",
            category_id=test_data_setup["category"]["id"],
        )

        try:
            # Test with invalid amount
            with pytest.raises(ValueError):
                update_data = EntryUpdate(amount=Decimal("-10.00"))
                await EntryService.update_entry(test_entry.id, update_data)

            # Test with zero amount
            with pytest.raises(ValueError):
                update_data = EntryUpdate(amount=Decimal("0.00"))
                await EntryService.update_entry(test_entry.id, update_data)

        finally:
            # Clean up
            db_connection.client.table("entry").delete().eq(
                "id", test_entry.id
            ).execute()

    @pytest.mark.asyncio
    async def test_update_entry_empty_update(self, test_data_setup):
        """Test entry update with no fields provided"""
        # Create a test entry first
        test_entry = await EntryService.create_entry(
            amount=Decimal("20.00"),
            direction="expense",
            entry_date=date(2025, 1, 15),
            description="Test entry",
            category_id=test_data_setup["category"]["id"],
        )

        try:
            # Update with no fields
            update_data = EntryUpdate()

            updated_entry = await EntryService.update_entry(test_entry.id, update_data)

            # Should return the original entry unchanged
            assert updated_entry is not None
            assert updated_entry.id == test_entry.id
            assert updated_entry.amount == Decimal("20.00")
            assert updated_entry.description == "Test entry"

        finally:
            # Clean up
            db_connection.client.table("entry").delete().eq(
                "id", test_entry.id
            ).execute()

    @pytest.mark.asyncio
    async def test_delete_entry_success(self, test_data_setup):
        """Test successful entry deletion with real database"""
        # Create a test entry first
        test_entry = await EntryService.create_entry(
            amount=Decimal("15.00"),
            direction="expense",
            entry_date=date(2025, 1, 15),
            description="Entry to be deleted",
            category_id=test_data_setup["category"]["id"],
        )

        # Delete the entry
        deleted = await EntryService.delete_entry(test_entry.id)

        assert deleted is True

        # Verify the entry is actually deleted
        retrieved_entry = await EntryService.get_entry_by_id(test_entry.id)
        assert retrieved_entry is None

    @pytest.mark.asyncio
    async def test_delete_entry_not_found(self, test_data_setup):
        """Test entry deletion when entry doesn't exist"""
        fake_id = uuid4()

        deleted = await EntryService.delete_entry(fake_id)

        assert deleted is False


class TestCategoryService:
    """Tests for category service with actual database"""

    @pytest.mark.asyncio
    async def test_get_categories_real_integration(self, test_categories):
        """Test real category retrieval with database"""
        params = CategoryQueryParams()
        result = await CategoryService.get_categories(params)

        assert len(result) >= 2  # Should have at least our test categories

        # Verify category structure
        for category in result:
            assert hasattr(category, "id")
            assert hasattr(category, "name")
            assert hasattr(category, "type")
            assert category.type in ["expense", "income"]

    @pytest.mark.asyncio
    async def test_get_categories_with_type_filter_real_integration(
        self, test_categories
    ):
        """Test real category retrieval with type filter using database"""
        # Test expense categories
        params = CategoryQueryParams(type="expense")
        result = await CategoryService.get_categories(params)
        assert len(result) >= 1
        for category in result:
            assert category.type == "expense"

        # Test income categories
        params = CategoryQueryParams(type="income")
        result = await CategoryService.get_categories(params)
        assert len(result) >= 1
        for category in result:
            assert category.type == "income"

    @pytest.mark.asyncio
    async def test_get_category_by_id_real_integration(self, test_categories):
        """Test real category retrieval by ID with database"""
        test_category = test_categories[0]

        result = await CategoryService.get_category_by_id(test_category["id"])

        assert result is not None
        assert str(result.id) == test_category["id"]
        assert result.name == test_category["name"]
        assert result.type == test_category["type"]

    @pytest.mark.asyncio
    async def test_get_category_by_id_not_found_real_integration(self):
        """Test real category retrieval by ID when not found"""
        fake_id = uuid4()

        result = await CategoryService.get_category_by_id(fake_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_category_sorting_real_integration(self, test_categories):
        """Test real category sorting with database"""
        params = CategoryQueryParams()
        result = await CategoryService.get_categories(params)

        assert len(result) >= 2

        # Categories should be sorted by name
        names = [category.name for category in result]
        assert names == sorted(names)

    @pytest.mark.asyncio
    async def test_concurrent_category_requests_real_integration(self, test_categories):
        """Test concurrent category requests with real database"""
        import asyncio

        # Create multiple concurrent requests
        tasks = [
            CategoryService.get_categories(CategoryQueryParams()),
            CategoryService.get_categories(CategoryQueryParams(type="expense")),
            CategoryService.get_categories(CategoryQueryParams(type="income")),
        ]

        results = await asyncio.gather(*tasks)

        # All requests should succeed
        assert len(results) == 3
        for result in results:
            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_category_with_entries_real_integration(self, test_categories):
        """Test category retrieval when it has associated entries"""
        test_category = test_categories[0]

        # Create an entry for this category
        test_entry = {
            "amount_cents": 1500,  # $15.00
            "direction": "expense",
            "entry_date": "2025-01-15",
            "category_id": test_category["id"],
            "description": "Test entry for category",
            "source": "manual",
        }

        result = db_connection.client.table("entry").insert(test_entry).execute()
        created_entry = result.data[0] if result.data else None

        try:
            # Get the category
            category = await CategoryService.get_category_by_id(test_category["id"])

            assert category is not None
            assert str(category.id) == test_category["id"]

        finally:
            # Clean up the created entry
            if created_entry:
                db_connection.client.table("entry").delete().eq(
                    "id", created_entry["id"]
                ).execute()

    @pytest.mark.asyncio
    async def test_category_validation_real_integration(self):
        """Test category validation with real service"""
        # Test with invalid type
        with pytest.raises(ValueError):
            CategoryQueryParams(type="invalid_type")

        # Test with valid types
        params_expense = CategoryQueryParams(type="expense")
        assert params_expense.type == "expense"

        params_income = CategoryQueryParams(type="income")
        assert params_income.type == "income"

        # Test with no type (should be valid)
        params_no_type = CategoryQueryParams()
        assert params_no_type.type is None

    @pytest.mark.asyncio
    async def test_large_dataset_performance(self, test_categories):
        """Test performance with larger dataset"""
        import time

        # Create multiple entries
        test_entries = []
        for i in range(10):
            test_entries.append(
                {
                    "amount_cents": 1000 + i * 100,  # $10.00, $10.10, etc.
                    "direction": "expense",
                    "entry_date": "2025-01-15",
                    "category_id": test_categories[0]["id"],
                    "description": f"Performance test entry {i}",
                    "source": "manual",
                }
            )

        created_entries = []
        for entry_data in test_entries:
            result = db_connection.client.table("entry").insert(entry_data).execute()
            if result.data:
                created_entries.append(result.data[0])

        try:
            # Test performance
            start_time = time.time()

            params = EntryQueryParams()
            result = await EntryService.get_entries(params)

            end_time = time.time()
            response_time = end_time - start_time

            assert len(result["items"]) >= 10
            # Should respond within reasonable time
            assert response_time < 2.0  # 2 second threshold

        finally:
            # Clean up test entries
            for entry in created_entries:
                db_connection.client.table("entry").delete().eq(
                    "id", entry["id"]
                ).execute()
