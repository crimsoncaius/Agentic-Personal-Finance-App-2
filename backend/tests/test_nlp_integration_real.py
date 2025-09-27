"""
Real integration tests for NLP service with actual database and OpenAI API
"""

import pytest
import pytest_asyncio
import os
import time
from datetime import date, datetime
from decimal import Decimal

from services.nlp_service import NLPService
from models.schemas import CategoryResponse, EntryDirection
from database.connection import db_connection

pytestmark = pytest.mark.real


class TestNLPIntegrationReal:
    """Real integration tests for NLP service with actual database and OpenAI API"""

    @pytest.fixture
    def nlp_service(self):
        """Create NLP service instance for testing with real OpenAI API"""
        # Use real OpenAI API key from environment
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            pytest.skip("OPENAI_API_KEY not set - skipping real integration tests")

        try:
            service = NLPService(openai_key)
            return service
        except Exception as e:
            pytest.skip(f"OpenAI client initialization failed: {e}")

    @pytest_asyncio.fixture
    async def test_data_setup(self):
        """Set up test data in the database for real integration tests"""
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
    async def test_read_query_real_integration(self, nlp_service, test_data_setup):
        """Test read query integration with real database and OpenAI API"""
        # Test reading expenses
        result = await nlp_service.process_query("show me my expenses")

        assert "operation" in result
        assert result["operation"] == "read"
        assert "result" in result
        assert len(result["result"]) >= 2  # Should have at least 2 expense entries

        # Verify the entries are properly formatted
        for entry in result["result"]:
            assert "id" in entry
            assert "amount" in entry
            assert "direction" in entry
            assert "entry_date" in entry
            assert "description" in entry
            assert entry["direction"] == "expense"

        # Test reading income
        result = await nlp_service.process_query("show me my income")

        assert "operation" in result
        assert result["operation"] == "read"
        assert "result" in result
        assert len(result["result"]) >= 1  # Should have at least 1 income entry

        for entry in result["result"]:
            assert entry["direction"] == "income"

    @pytest.mark.asyncio
    async def test_write_query_real_integration(self, nlp_service, test_data_setup):
        """Test write query integration with real database and OpenAI API"""
        # Test creating a new expense entry
        result = await nlp_service.process_query("spent $15 on lunch")

        assert "operation" in result
        assert result["operation"] == "write"
        assert "result" in result

        # Verify the created entry
        entry = result["result"]
        assert "id" in entry
        assert entry["amount"] == 15.0
        assert entry["direction"] == "expense"
        assert "description" in entry
        assert "category" in entry

        # Clean up the created entry
        db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()

        # Test creating a new income entry
        result = await nlp_service.process_query("earned $100 from freelance work")

        assert "operation" in result
        assert result["operation"] == "write"
        assert "result" in result

        # Verify the created entry
        entry = result["result"]
        assert "id" in entry
        assert entry["amount"] == 100.0
        assert entry["direction"] == "income"
        assert "description" in entry
        assert "category" in entry

        # Clean up the created entry
        db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()

    @pytest.mark.asyncio
    async def test_category_fallback_real_integration(
        self, nlp_service, test_data_setup
    ):
        """Test category fallback when category not found"""
        # Test creating entry with unknown category
        result = await nlp_service.process_query("spent $25 on unknown category")

        assert "operation" in result
        assert result["operation"] == "write"
        assert "result" in result

        # Verify the created entry has a fallback category
        entry = result["result"]
        assert "category" in entry
        assert "id" in entry["category"]
        assert "name" in entry["category"]

        # Clean up the created entry
        db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()

    @pytest.mark.asyncio
    async def test_database_error_handling_real(self, nlp_service):
        """Test database error handling in real integration"""
        # This test would require simulating database errors
        # For now, we'll test that the service handles missing data gracefully
        result = await nlp_service.process_query("show me expenses from 1900")

        # Should still return a valid response (empty result)
        assert "operation" in result
        assert result["operation"] == "read"
        assert "result" in result
        assert isinstance(result["result"], list)

    @pytest.mark.asyncio
    async def test_end_to_end_read_flow_real(self, nlp_service, test_data_setup):
        """Test complete end-to-end read flow with real AI"""
        # Test various read queries
        queries = [
            "show me all my expenses",
            "what did I spend on food",
            "show me my income this month",
            "list my transportation expenses",
        ]

        for query in queries:
            result = await nlp_service.process_query(query)

            assert "operation" in result
            assert result["operation"] == "read"
            assert "result" in result
            assert isinstance(result["result"], list)

    @pytest.mark.asyncio
    async def test_end_to_end_write_flow_real(self, nlp_service, test_data_setup):
        """Test complete end-to-end write flow with real AI"""
        # Test various write queries
        write_queries = [
            "spent $30 on groceries",
            "earned $200 from consulting",
            "bought $5 coffee",
            "received $1000 salary",
        ]

        created_entries = []

        for query in write_queries:
            result = await nlp_service.process_query(query)

            assert "operation" in result
            assert result["operation"] == "write"
            assert "result" in result

            entry = result["result"]
            assert "id" in entry
            assert "amount" in entry
            assert "direction" in entry
            assert "description" in entry

            created_entries.append(entry)

        # Clean up all created entries
        for entry in created_entries:
            db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()

    @pytest.mark.asyncio
    async def test_nlp_parsing_accuracy_real(self, nlp_service, test_data_setup):
        """Test that real NLP parsing correctly identifies amounts and categories"""
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
            result = await nlp_service.process_query(case["query"])

            assert "operation" in result
            assert result["operation"] == "write"
            assert "result" in result

            entry = result["result"]
            assert abs(float(entry["amount"]) - case["expected_amount"]) < 0.01
            assert entry["direction"] == case["expected_direction"]

            created_entries.append(entry)

        # Clean up all created entries
        for entry in created_entries:
            db_connection.client.table("entry").delete().eq("id", entry["id"]).execute()

    @pytest.mark.asyncio
    async def test_complex_queries_real(self, nlp_service, test_data_setup):
        """Test complex natural language queries with real AI"""
        complex_queries = [
            "show me all my food and dining expenses from last week",
            "what was my total income this month",
            "list expenses over $50",
            "show me transportation costs",
        ]

        for query in complex_queries:
            result = await nlp_service.process_query(query)

            # Should return a valid response
            assert "operation" in result
            assert result["operation"] in ["read", "write"]
            assert "result" in result

    @pytest.mark.asyncio
    async def test_error_handling_real(self, nlp_service, test_data_setup):
        """Test error handling with real AI"""
        # Test with ambiguous input
        result = await nlp_service.process_query("spent money on food")

        # Should handle the error gracefully
        assert isinstance(result, dict)

        # Test with incomplete input
        result = await nlp_service.process_query("bought something")

        # Should handle the error gracefully
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_performance_real(self, nlp_service, test_data_setup):
        """Test performance with real AI"""
        import time

        start_time = time.time()

        result = await nlp_service.process_query("show me my expenses")

        end_time = time.time()
        response_time = end_time - start_time

        assert "operation" in result
        # Should respond within reasonable time (adjust threshold as needed)
        assert response_time < 10.0  # 10 second threshold for real AI calls

    @pytest.mark.asyncio
    async def test_concurrent_queries_real(self, nlp_service, test_data_setup):
        """Test concurrent query processing with real AI"""
        import asyncio

        # Create multiple concurrent queries
        queries = [
            "show me expenses",
            "show me income",
            "what did I spend on food",
            "list my transportation",
        ]

        # Run queries concurrently
        start_time = time.time()
        tasks = [nlp_service.process_query(query) for query in queries]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # All queries should succeed
        assert len(results) == 4
        for result in results:
            assert "operation" in result
            assert result["operation"] == "read"
            assert "result" in result

        # Concurrent execution should be faster than sequential
        # (This is a rough check - adjust as needed)
        assert (end_time - start_time) < 20.0  # Should complete within 20 seconds

    @pytest.mark.asyncio
    async def test_ambiguous_query_unsure_real(self, nlp_service, test_data_setup):
        """Test that ambiguous queries are routed to unsure node with real AI"""
        # Test with ambiguous queries that could be interpreted as either read or write
        ambiguous_queries = [
            "coffee",  # Could be asking about coffee expenses or wanting to add coffee
            "food",  # Could be asking about food expenses or wanting to add food
            "transportation",  # Could be asking about transport expenses or wanting to add transport
            "salary",  # Could be asking about salary income or wanting to add salary
        ]

        for query in ambiguous_queries:
            result = await nlp_service.process_query(query)

            # The result should either be unsure or have helpful suggestions
            if "error" in result:
                assert result["error"].code == "ambiguous"
                assert "clarify" in result["error"].message.lower()
                assert len(result["error"].details.suggestions) > 0
            else:
                # If AI routes to read/write, that's also acceptable
                assert "operation" in result
                assert result["operation"] in ["read", "write"]
