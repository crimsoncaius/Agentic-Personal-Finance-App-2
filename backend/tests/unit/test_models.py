"""
Tests for Pydantic models
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.db_mock,  # No database operations in model tests
    pytest.mark.llm_mock,  # No LLM operations in model tests
]

from models.schemas import (
    CategoryQueryParams,
    CategoryResponse,
    ChatRequest,
    EntryCreateNL,
    EntryCreateStructured,
    EntryListResponse,
    EntryQueryParams,
    EntryResponse,
    EntryUpdate,
    cents_to_dollars,
    dollars_to_cents,
)


class TestEntryModels:
    """Test entry-related models"""

    def test_entry_create_structured_valid(self):
        """Test valid structured entry creation"""
        entry = EntryCreateStructured(
            amount=Decimal("12.50"),
            direction="expense",
            entry_date=date(2025, 1, 15),
            description="Test expense",
            source="manual",
        )

        assert entry.amount == Decimal("12.50")
        assert entry.direction == "expense"
        assert entry.entry_date == date(2025, 1, 15)
        assert entry.description == "Test expense"
        assert entry.source == "manual"

    def test_entry_create_structured_nlp_source(self):
        """Test structured entry with NLP source (should not have parse_confidence)"""
        entry = EntryCreateStructured(
            amount=Decimal("12.50"),
            direction="expense",
            entry_date=date(2025, 1, 15),
            description="Test expense",
            source="nlp",
        )

        assert entry.amount == Decimal("12.50")
        assert entry.direction == "expense"
        assert entry.entry_date == date(2025, 1, 15)
        assert entry.description == "Test expense"
        assert entry.source == "nlp"

    def test_entry_response_valid(self):
        """Test valid entry response"""
        category = CategoryResponse(id=uuid4(), name="Food & Dining", type="expense")

        entry_response = EntryResponse(
            id=uuid4(),
            amount=Decimal("12.50"),
            direction="expense",
            entry_date=date(2025, 1, 15),
            category=category,
            description="Coffee",
            source="manual",
            parse_confidence=None,
            created_at=datetime.now(),
        )

        assert entry_response.amount == Decimal("12.50")
        assert entry_response.direction == "expense"
        assert entry_response.category.name == "Food & Dining"

    def test_entry_update_valid(self):
        """Test valid entry update with all fields"""
        entry_update = EntryUpdate(
            amount=Decimal("25.75"),
            direction="expense",
            entry_date=date(2025, 1, 20),
            category_id=uuid4(),
            description="Updated expense",
        )

        assert entry_update.amount == Decimal("25.75")
        assert entry_update.direction == "expense"
        assert entry_update.entry_date == date(2025, 1, 20)
        assert entry_update.description == "Updated expense"

    def test_entry_update_partial(self):
        """Test partial entry update with only some fields"""
        entry_update = EntryUpdate(
            amount=Decimal("15.50"),
            description="Updated description only",
        )

        assert entry_update.amount == Decimal("15.50")
        assert entry_update.description == "Updated description only"
        assert entry_update.direction is None
        assert entry_update.entry_date is None
        assert entry_update.category_id is None

    def test_entry_update_empty(self):
        """Test empty entry update (all fields optional)"""
        entry_update = EntryUpdate()

        assert entry_update.amount is None
        assert entry_update.direction is None
        assert entry_update.entry_date is None
        assert entry_update.category_id is None
        assert entry_update.description is None


class TestUtilityFunctions:
    """Test utility functions"""

    def test_dollars_to_cents(self):
        """Test dollar to cent conversion"""
        assert dollars_to_cents(Decimal("12.50")) == 1250
        assert dollars_to_cents(Decimal("0.01")) == 1
        assert dollars_to_cents(Decimal("100.00")) == 10000

    def test_cents_to_dollars(self):
        """Test cent to dollar conversion"""
        assert cents_to_dollars(1250) == Decimal("12.50")
        assert cents_to_dollars(1) == Decimal("0.01")
        assert cents_to_dollars(10000) == Decimal("100.00")


class TestQueryParams:
    """Test query parameter models"""

    def test_entry_query_params_valid(self):
        """Test valid entry query parameters"""
        params = EntryQueryParams(
            limit=5, offset=10, direction="expense", sort="created_at.desc"
        )

        assert params.limit == 5
        assert params.offset == 10
        assert params.direction == "expense"
        assert params.sort == "created_at.desc"

    def test_entry_query_params_invalid_limit(self):
        """Test invalid limit parameter"""
        with pytest.raises(ValueError):
            EntryQueryParams(limit=15)  # Should be <= 10

    def test_category_query_params_valid(self):
        """Test valid category query parameters"""
        params = CategoryQueryParams(type="expense")
        assert params.type == "expense"


class TestChatModels:
    """Test chat-related models"""

    def test_chat_request_valid(self):
        """Test valid chat request"""
        request = ChatRequest(text="Show me my expenses")
        assert request.text == "Show me my expenses"

    def test_chat_request_empty_text(self):
        """Test chat request with empty text"""
        with pytest.raises(ValueError):
            ChatRequest(text="")


class TestValidationRules:
    """Test business rule validations"""

    def test_amount_positive(self):
        """Test that amount must be positive"""
        with pytest.raises(ValueError):
            EntryCreateStructured(
                amount=Decimal("0.00"),
                direction="expense",
                entry_date=date(2025, 1, 15),
            )

    def test_parse_confidence_range(self):
        """Test parse confidence is within valid range"""
        with pytest.raises(ValueError):
            EntryCreateNL(
                amount=Decimal("12.50"),
                direction="expense",
                entry_date=date(2025, 1, 15),
                description="Test expense",
                source="nlp",
                parse_confidence=1.5,  # Should be <= 1.0
            )

    def test_entry_update_invalid_amount(self):
        """Test entry update with invalid amount"""
        with pytest.raises(ValueError):
            EntryUpdate(amount=Decimal("0.00"))  # Should be > 0

        with pytest.raises(ValueError):
            EntryUpdate(amount=Decimal("-5.00"))  # Should be > 0

    def test_entry_update_description_length(self):
        """Test entry update description length validation"""
        # Valid description (within 500 char limit)
        valid_description = "x" * 500
        entry_update = EntryUpdate(description=valid_description)
        assert entry_update.description == valid_description

        # Invalid description (over 500 char limit)
        with pytest.raises(ValueError):
            EntryUpdate(description="x" * 501)
