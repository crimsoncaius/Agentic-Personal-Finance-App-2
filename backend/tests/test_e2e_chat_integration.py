"""
Real integration tests for chat functionality with actual database and OpenAI API
"""

import pytest
import pytest_asyncio
import os
from fastapi.testclient import TestClient

from main import app
from database.connection import db_connection

pytestmark = pytest.mark.real


class TestChatE2EIntegration:
    """Real integration tests for chat functionality with actual database"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest_asyncio.fixture
    async def test_data_setup(self):
        """Set up test data in the database for e2e tests"""
        # Create test categories with unique names to avoid conflicts
        import uuid

        test_categories = [
            {
                "name": f"Test Food & Dining (Expense) {uuid.uuid4().hex[:8]}",
                "type": "expense",
                "is_system": True,
            },
            {
                "name": f"Test Transportation (Expense) {uuid.uuid4().hex[:8]}",
                "type": "expense",
                "is_system": True,
            },
            {
                "name": f"Test Salary (Income) {uuid.uuid4().hex[:8]}",
                "type": "income",
                "is_system": True,
            },
        ]

        created_categories = []
        for cat_data in test_categories:
            result = db_connection.client.table("category").insert(cat_data).execute()
            if result.data:
                created_categories.append(result.data[0])

        # Create test entries with current dates
        from datetime import date, timedelta

        today = date.today()

        test_entries = [
            {
                "amount_cents": 2000,  # $20.00
                "direction": "expense",
                "entry_date": (today - timedelta(days=1)).isoformat(),
                "category_id": created_categories[0]["id"],
                "description": "coffee",
                "source": "manual",
            },
            {
                "amount_cents": 5000,  # $50.00
                "direction": "expense",
                "entry_date": (today - timedelta(days=2)).isoformat(),
                "category_id": created_categories[1]["id"],
                "description": "bus pass",
                "source": "manual",
            },
            {
                "amount_cents": 500000,  # $5000.00
                "direction": "income",
                "entry_date": (today - timedelta(days=3)).isoformat(),
                "category_id": created_categories[2]["id"],
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

        # Cleanup - delete test data
        for entry in created_entries:
            db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()

        for category in created_categories:
            db_connection.client.table("category").delete().eq(
                "id", category["id"]
            ).execute()

    @pytest.mark.asyncio
    async def test_real_chat_read_operation(self, client, test_data_setup):
        """Test real read operation through chat endpoint with actual database"""
        # Skip if no OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping real integration test")

        response = client.post("/api/v1/chat/", json={"text": "show me my expenses"})

        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "read"
        assert "result" in data
        assert len(data["result"]) >= 2  # Should have at least 2 expense entries

        # Verify entry structure
        for entry in data["result"]:
            assert "id" in entry
            assert "amount" in entry
            assert "direction" in entry
            assert "entry_date" in entry
            assert "description" in entry
            assert entry["direction"] == "expense"

    @pytest.mark.asyncio
    async def test_real_chat_write_operation(self, client, test_data_setup):
        """Test real write operation through chat endpoint with actual database"""
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
        assert entry["amount"] == "25"  # Decimal serializes as string in JSON
        assert entry["direction"] == "expense"
        assert "description" in entry
        assert "category" in entry

        # Clean up the created entry
        db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()

    @pytest.mark.asyncio
    async def test_real_chat_error_handling(self, client, test_data_setup):
        """Test real error handling through chat endpoint"""
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

    @pytest.mark.asyncio
    async def test_real_chat_multiple_scenarios(self, client, test_data_setup):
        """Test multiple real chat scenarios"""
        # Skip if no OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping real integration test")

        test_cases = [
            {"input": "show me my income", "expected_operation": "read"},
            {"input": "earned $100 from freelance", "expected_operation": "write"},
            {
                "input": "what did I spend on transportation",
                "expected_operation": "read",
            },
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

    @pytest.mark.asyncio
    async def test_real_nlp_parsing_accuracy(self, client, test_data_setup):
        """Test that real NLP parsing correctly identifies amounts and categories"""
        # Skip if no OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping real integration test")

        test_cases = [
            {
                "query": "spent twenty dollars on coffee",
                "expected_amount": 20.0,
                "expected_direction": "expense",
            },
            {
                "query": "earned five hundred from work",
                "expected_amount": 500.0,
                "expected_direction": "income",
            },
            {
                "query": "bought lunch for $12.50",
                "expected_amount": 12.50,
                "expected_direction": "expense",
            },
        ]

        created_entries = []

        for case in test_cases:
            response = client.post("/api/v1/chat/", json={"text": case["query"]})

            assert response.status_code == 200
            data = response.json()
            assert data["operation"] == "write"
            assert "result" in data

            entry = data["result"]
            # Convert string amount to float for comparison
            amount = float(entry["amount"])
            assert abs(amount - case["expected_amount"]) < 0.01
            assert entry["direction"] == case["expected_direction"]

            created_entries.append(entry)

        # Clean up all created entries
        for entry in created_entries:
            db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()

    @pytest.mark.asyncio
    async def test_real_category_matching(self, client, test_data_setup):
        """Test that real NLP correctly matches categories"""
        # Skip if no OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping real integration test")

        # Test category matching with existing categories
        response = client.post("/api/v1/chat/", json={"text": "spent $15 on food"})

        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "write"
        assert "result" in data

        entry = data["result"]
        assert "category" in entry
        assert "name" in entry["category"]

        # Clean up the created entry
        db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()

    @pytest.mark.asyncio
    async def test_real_end_to_end_workflow(self, client, test_data_setup):
        """Test complete end-to-end workflow with real AI"""
        # Skip if no OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping real integration test")

        created_entries = []

        # 1. Create an expense
        response = client.post("/api/v1/chat/", json={"text": "spent $30 on groceries"})
        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "write"
        created_entries.append(data["result"])

        # 2. Create an income
        response = client.post(
            "/api/v1/chat/", json={"text": "earned $200 from consulting"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "write"
        created_entries.append(data["result"])

        # 3. Query expenses
        response = client.post("/api/v1/chat/", json={"text": "show me my expenses"})
        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "read"
        assert len(data["result"]) >= 3  # Original 2 + new 1

        # 4. Query income with a more specific query that shouldn't trigger date filtering
        response = client.post(
            "/api/v1/chat/", json={"text": "show me all my income entries"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "read"
        assert len(data["result"]) >= 2  # Original 1 + new 1

        # Clean up all created entries
        for entry in created_entries:
            db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()
