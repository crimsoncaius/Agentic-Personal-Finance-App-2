"""
Test configuration and fixtures for Expense Tracker MVP
Supports both mock and real tests for OpenAI-dependent functionality
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient

# Use real database connection for tests
from database.connection import db_connection


# ============================================================================
# MARKER CONFIGURATION (CLEANED UP)
# ============================================================================
# Removed organizational markers - keeping only functional asyncio markers

# ============================================================================
# CORE FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_db_connection() -> Mock:
    """Mock database connection for testing"""
    mock_connection = Mock()
    mock_connection.client = Mock()
    mock_connection.service_client = Mock()
    return mock_connection


@pytest.fixture
async def app() -> FastAPI:
    """Create FastAPI app instance for testing"""
    from main import app

    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# ============================================================================
# OPENAI MOCK FIXTURES (for cost-free testing)
# ============================================================================


@pytest.fixture
def mock_openai_key():
    """Mock OpenAI API key for mock tests"""
    return "test-openai-key-12345"


@pytest.fixture
def mock_nlp_service():
    """Mock NLP service for testing"""
    from unittest.mock import MagicMock, AsyncMock

    mock_service = MagicMock()
    mock_service.process_query = AsyncMock()
    return mock_service


# ============================================================================
# DATABASE FIXTURES (for all tests)
# ============================================================================


@pytest.fixture
def openai_api_key():
    """Get OpenAI API key from environment"""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set - skipping integration tests")
    return key


@pytest_asyncio.fixture
async def test_category():
    """Create a test category in the database for integration tests"""
    test_category_data = {
        "name": f"Test Category {uuid4().hex[:8]}",
        "type": "expense",
        "is_system": True,
    }

    result = db_connection.client.table("category").insert(test_category_data).execute()
    created_category = result.data[0] if result.data else None

    if not created_category:
        pytest.fail("Failed to create test category")

    yield created_category

    # Cleanup
    db_connection.client.table("category").delete().eq(
        "id", created_category["id"]
    ).execute()


@pytest_asyncio.fixture
async def test_categories():
    """Create multiple test categories in the database for integration tests"""
    test_categories_data = [
        {
            "name": f"Test Food Category {uuid4().hex[:8]}",
            "type": "expense",
            "is_system": True,
        },
        {
            "name": f"Test Income Category {uuid4().hex[:8]}",
            "type": "income",
            "is_system": True,
        },
    ]

    created_categories = []
    for cat_data in test_categories_data:
        result = db_connection.client.table("category").insert(cat_data).execute()
        if result.data:
            created_categories.append(result.data[0])

    yield created_categories

    # Cleanup
    for category in created_categories:
        db_connection.client.table("category").delete().eq(
            "id", category["id"]
        ).execute()


@pytest_asyncio.fixture
async def test_entries(test_category):
    """Create test entries in the database for integration tests"""
    test_entries_data = [
        {
            "amount_cents": 2000,  # $20.00
            "direction": "expense",
            "entry_date": "2025-01-15",
            "category_id": test_category["id"],
            "description": "coffee",
            "source": "manual",
        },
        {
            "amount_cents": 5000,  # $50.00
            "direction": "expense",
            "entry_date": "2025-01-14",
            "category_id": test_category["id"],
            "description": "bus pass",
            "source": "manual",
        },
    ]

    created_entries = []
    for entry_data in test_entries_data:
        result = db_connection.client.table("entry").insert(entry_data).execute()
        if result.data:
            created_entries.append(result.data[0])

    yield created_entries

    # Cleanup
    for entry in created_entries:
        db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()


@pytest_asyncio.fixture
async def test_data_setup():
    """Comprehensive test data setup for integration tests"""
    # Create test categories
    test_categories_data = [
        {
            "name": f"Test Food & Dining {uuid4().hex[:8]}",
            "type": "expense",
            "is_system": True,
        },
        {
            "name": f"Test Transportation {uuid4().hex[:8]}",
            "type": "expense",
            "is_system": True,
        },
        {
            "name": f"Test Salary {uuid4().hex[:8]}",
            "type": "income",
            "is_system": True,
        },
    ]

    created_categories = []
    for cat_data in test_categories_data:
        result = db_connection.client.table("category").insert(cat_data).execute()
        if result.data:
            created_categories.append(result.data[0])

    # Create test entries
    test_entries_data = [
        {
            "amount_cents": 2000,  # $20.00
            "direction": "expense",
            "entry_date": "2025-01-15",
            "category_id": created_categories[0]["id"],
            "description": "coffee",
            "source": "manual",
        },
        {
            "amount_cents": 5000,  # $50.00
            "direction": "expense",
            "entry_date": "2025-01-14",
            "category_id": created_categories[1]["id"],
            "description": "bus pass",
            "source": "manual",
        },
        {
            "amount_cents": 500000,  # $5000.00
            "direction": "income",
            "entry_date": "2025-01-01",
            "category_id": created_categories[2]["id"],
            "description": "salary",
            "source": "manual",
        },
    ]

    created_entries = []
    for entry_data in test_entries_data:
        result = db_connection.client.table("entry").insert(entry_data).execute()
        if result.data:
            created_entries.append(result.data[0])

    yield {
        "category": created_categories[0],  # First category for single category tests
        "categories": created_categories,  # All categories for multi-category tests
        "entries": created_entries,
    }

    # Cleanup
    for entry in created_entries:
        db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()
    for category in created_categories:
        db_connection.client.table("category").delete().eq(
            "id", category["id"]
        ).execute()


# ============================================================================
# LEGACY FIXTURES (for backward compatibility)
# ============================================================================


@pytest.fixture
def sample_category_data():
    """Sample category data for testing"""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "name": "Food & Dining",
        "type": "expense",
        "parent_id": None,
        "is_system": True,
        "created_at": "2025-01-15T10:30:00Z",
        "updated_at": "2025-01-15T10:30:00Z",
    }


@pytest.fixture
def sample_entry_data():
    """Sample entry data for testing"""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "amount_cents": 1250,  # $12.50
        "direction": "expense",
        "entry_date": "2025-01-15",
        "category_id": "550e8400-e29b-41d4-a716-446655440002",
        "description": "laksa lunch",
        "source": "manual",
        "parse_confidence": None,
        "created_at": "2025-01-15T10:30:00Z",
        "updated_at": "2025-01-15T10:30:00Z",
    }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def skip_if_no_openai_key():
    """Skip test if OpenAI API key is not available"""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set - skipping real integration test")


def skip_if_no_database():
    """Skip test if database is not available"""
    try:
        # Try to connect to database
        db_connection.client.table("category").select("id").limit(1).execute()
    except Exception:
        pytest.skip("Database not available - skipping integration test")
