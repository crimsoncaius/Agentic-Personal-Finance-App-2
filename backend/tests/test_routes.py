"""
Tests for API routes - Tests with actual database operations
"""

import pytest
import pytest_asyncio
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from database.connection import db_connection

pytestmark = pytest.mark.real

client = TestClient(app)


class TestEntryRoutes:
    """Tests for entry-related routes with actual database"""

    @pytest_asyncio.fixture
    async def test_data_setup(self):
        """Set up test data in the database"""
        # Create test category
        test_category = {
            "name": f"Test Category {uuid4().hex[:8]}",
            "type": "expense",
            "is_system": True,
        }

        result = db_connection.client.table("category").insert(test_category).execute()
        created_category = result.data[0] if result.data else None

        yield {"category": created_category}

        # Cleanup
        if created_category:
            db_connection.client.table("category").delete().eq(
                "id", created_category["id"]
            ).execute()

    def test_create_entry(self, test_data_setup):
        """Test real entry creation with database"""
        entry_data = {
            "amount": 15.75,
            "direction": "expense",
            "entry_date": "2025-01-15",
            "description": "Real test expense",
            "source": "manual",
            "category_id": test_data_setup["category"]["id"],
        }

        response = client.post("/api/v1/entries/", json=entry_data)

        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == "15.75"
        assert data["direction"] == "expense"
        assert data["description"] == "Real test expense"
        assert "id" in data

        # Clean up the created entry
        db_connection.client.table("entry").delete().eq("id", data["id"]).execute()

    def test_get_entries(self, test_data_setup):
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
            response = client.get("/api/v1/entries/")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) >= 2
            assert data["page"]["total"] >= 2

            # Verify entry structure
            for entry in data["items"]:
                assert "id" in entry
                assert "amount" in entry
                assert "direction" in entry
                assert "description" in entry

        finally:
            # Clean up test entries
            for entry in created_entries:
                db_connection.client.table("entry").delete().eq(
                    "id", entry["id"]
                ).execute()

    def test_get_entries_with_filters(self, test_data_setup):
        """Test entry retrieval with filters using real database"""
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
            response = client.get("/api/v1/entries/", params={"direction": "expense"})
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) >= 2

            # Test with search query
            response = client.get("/api/v1/entries/", params={"q": "coffee"})
            assert response.status_code == 200
            data = response.json()
            # Should find at least one entry with "coffee" in description
            assert len(data["items"]) >= 1

        finally:
            # Clean up test entries
            for entry in created_entries:
                db_connection.client.table("entry").delete().eq(
                    "id", entry["id"]
                ).execute()


class TestCategoryRoutes:
    """Tests for category-related routes with actual database"""

    @pytest_asyncio.fixture
    async def test_categories_setup(self):
        """Set up test categories in the database"""
        test_categories = [
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
        for cat_data in test_categories:
            result = db_connection.client.table("category").insert(cat_data).execute()
            if result.data:
                created_categories.append(result.data[0])

        yield {"categories": created_categories}

        # Cleanup
        for category in created_categories:
            db_connection.client.table("category").delete().eq(
                "id", category["id"]
            ).execute()

    def test_get_categories(self, test_categories_setup):
        """Test real category retrieval with database"""
        response = client.get("/api/v1/categories/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2  # Should have at least our test categories

        # Verify category structure
        for category in data:
            assert "id" in category
            assert "name" in category
            assert "type" in category
            assert category["type"] in ["expense", "income"]

    def test_get_categories_with_type_filter_real_integration(
        self, test_categories_setup
    ):
        """Test category retrieval with type filter using real database"""
        # Test expense categories
        response = client.get("/api/v1/categories/", params={"type": "expense"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        for category in data:
            assert category["type"] == "expense"

        # Test income categories
        response = client.get("/api/v1/categories/", params={"type": "income"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        for category in data:
            assert category["type"] == "income"


class TestChatRoutesIntegration:
    """Real integration tests for chat/NLP routes with actual database and OpenAI API"""

    @pytest_asyncio.fixture
    async def test_data_setup(self):
        """Set up test data for chat integration tests"""
        # Create test categories
        test_categories = [
            {
                "name": f"Test Food & Dining {uuid4().hex[:8]}",
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
        for cat_data in test_categories:
            result = db_connection.client.table("category").insert(cat_data).execute()
            if result.data:
                created_categories.append(result.data[0])

        # Create test entries
        test_entries = [
            {
                "amount_cents": 2000,  # $20.00
                "direction": "expense",
                "entry_date": "2025-01-15",
                "category_id": created_categories[0]["id"],
                "description": "coffee",
                "source": "manual",
            },
            {
                "amount_cents": 500000,  # $5000.00
                "direction": "income",
                "entry_date": "2025-01-01",
                "category_id": created_categories[1]["id"],
                "description": "salary",
                "source": "manual",
            },
        ]

        created_entries = []
        for entry_data in test_entries:
            result = db_connection.client.table("entry").insert(entry_data).execute()
            if result.data:
                created_entries.append(result.data[0])

        yield {"categories": created_categories, "entries": created_entries}

        # Cleanup
        for entry in created_entries:
            db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()
        for category in created_categories:
            db_connection.client.table("category").delete().eq(
                "id", category["id"]
            ).execute()

    def test_chat_read_operation_real_integration(self, test_data_setup):
        """Test real chat read operation with database and OpenAI API"""
        # Skip if no OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping real integration test")

        response = client.post("/api/v1/chat/", json={"text": "show me my expenses"})

        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "read"
        assert "result" in data
        assert len(data["result"]) >= 1  # Should have at least 1 expense entry

        # Verify entry structure
        for entry in data["result"]:
            assert "id" in entry
            assert "amount" in entry
            assert "direction" in entry
            assert "description" in entry
            assert entry["direction"] == "expense"

    def test_chat_write_operation_real_integration(self, test_data_setup):
        """Test real chat write operation with database and OpenAI API"""
        # Skip if no OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping real integration test")

        response = client.post("/api/v1/chat/", json={"text": "spent $25 on lunch"})

        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "write"
        assert "result" in data

        # Verify the created entry
        entry = data["result"]
        assert "id" in entry
        assert entry["amount"] == "25"  # API returns amount as string
        assert entry["direction"] == "expense"
        assert "description" in entry
        assert "category" in entry

        # Clean up the created entry
        db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()

    def test_chat_error_handling_real_integration(self, test_data_setup):
        """Test real chat error handling with OpenAI API"""
        # Skip if no OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping real integration test")

        # Test with ambiguous input
        response = client.post("/api/v1/chat/", json={"text": "spent money on food"})

        # Should return an error response
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert "code" in data["detail"]["error"]

    def test_chat_multiple_scenarios_real_integration(self, test_data_setup):
        """Test multiple real chat scenarios"""
        # Skip if no OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping real integration test")

        test_cases = [
            {"input": "show me my income", "expected_operation": "read"},
            {"input": "earned $100 from freelance", "expected_operation": "write"},
            {"input": "what did I spend on food", "expected_operation": "read"},
        ]

        created_entries = []

        for case in test_cases:
            response = client.post("/api/v1/chat/", json={"text": case["input"]})

            assert response.status_code == 200
            data = response.json()
            assert data["operation"] == case["expected_operation"]

            # If it's a write operation, clean up the created entry
            if case["expected_operation"] == "write" and "result" in data:
                entry = data["result"]
                if "id" in entry:
                    created_entries.append(entry)

        # Clean up all created entries
        for entry in created_entries:
            db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()


class TestAppRoutesIntegration:
    """Real integration tests for main app routes"""

    def test_root_endpoint_real(self):
        """Test root endpoint with real app"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Expense Tracker MVP API"
        assert data["version"] == "1.0.0"

    def test_health_check_real(self):
        """Test health check endpoint with real app"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "expense-tracker-mvp"


class TestErrorHandlingIntegration:
    """Real integration tests for error handling"""

    def test_invalid_endpoint_real(self):
        """Test invalid endpoint returns 404 with real app"""
        response = client.get("/api/v1/invalid")
        assert response.status_code == 404

    def test_database_connection_error_simulation(self):
        """Test database connection error handling"""
        # This would require simulating database connection issues
        # For now, we'll test that the app handles missing data gracefully
        response = client.get("/api/v1/entries/", params={"date_from": "1900-01-01"})

        # Should still return a valid response (empty result)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "page" in data

    def test_large_request_handling(self):
        """Test handling of large requests"""
        # Test with large limit
        response = client.get("/api/v1/entries/", params={"limit": 10})
        assert response.status_code == 200

        # Test with large offset
        response = client.get("/api/v1/entries/", params={"offset": 1000})
        assert response.status_code == 200

    def test_concurrent_requests_real(self):
        """Test concurrent requests with real database"""
        import threading
        import time

        def make_request():
            response = client.get("/api/v1/categories/")
            return response.status_code

        # Create multiple threads
        threads = []
        results = []

        for i in range(3):  # Reduced number for real database
            thread = threading.Thread(target=lambda: results.append(make_request()))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 3
