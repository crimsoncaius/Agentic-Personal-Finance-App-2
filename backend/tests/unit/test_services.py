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
    pytest.mark.auth_real,  # Uses real authentication with test users
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
            user_id=test_data_setup["user_id"],
        )

        assert result.amount_cents == 1575
        assert result.direction == "expense"
        assert result.description == "Real test expense"
        assert str(result.category_id) == test_data_setup["category"]["id"]
        assert "id" in result.__dict__

        # Clean up the created entry
        db_connection.client.table("entry").delete().eq("id", result.id).execute()

    @pytest.mark.asyncio
    async def test_entry_validation_real_integration(self):
        """Test entry validation with real service"""
        # Test with invalid amount
        with pytest.raises(ValueError):
            await EntryService.create_entry(
                amount=Decimal("-10.00"),  # Negative amount
                direction="expense",
                entry_date=date(2025, 1, 15),
                user_id=uuid4(),
            )

        # Test with zero amount
        with pytest.raises(ValueError):
            await EntryService.create_entry(
                amount=Decimal("0.00"),  # Zero amount
                direction="expense",
                entry_date=date(2025, 1, 15),
                user_id=uuid4(),
            )


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
