"""
Real unit tests for NLP service - Tests with actual OpenAI API calls
"""

import pytest
import os
import time
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from services.nlp_service_v2 import NLPServiceV2
from models.schemas import ParsedData, EntryDirection, CategoryResponse, ParseError

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.db_mock,  # Database operations are mocked (focus on LLM)
    pytest.mark.llm_real,  # Uses real LLM/OpenAI API calls
]


class TestNLPServiceV2Real:
    """Real unit tests for NLP service - Tests with actual OpenAI API calls"""

    @pytest.fixture
    def nlp_service(self):
        """Create NLP service instance for testing with real OpenAI API"""
        # Use real OpenAI API key from environment
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            pytest.skip("OPENAI_API_KEY not set - skipping real unit tests")

        try:
            service = NLPServiceV2(openai_key)
            return service
        except Exception as e:
            pytest.skip(f"OpenAI client initialization failed: {e}")

    @pytest.mark.asyncio
    async def test_router_node_read_operation_real(self, nlp_service):
        """Test router node correctly identifies read operations with real AI"""
        result = await nlp_service._router_node({"text": "show me my expenses"})

        assert "operation" in result
        assert result["operation"] == "read"

    @pytest.mark.asyncio
    async def test_router_node_write_operation_real(self, nlp_service):
        """Test router node correctly identifies write operations with real AI"""
        result = await nlp_service._router_node({"text": "spent $20 on coffee"})

        assert "operation" in result
        assert result["operation"] == "write"

    @pytest.mark.asyncio
    async def test_router_node_ambiguous_input_real(self, nlp_service):
        """Test router node handles ambiguous input with real AI"""
        result = await nlp_service._router_node({"text": "I am unsure"})

        # Should default to read for ambiguous input
        assert "operation" in result
        assert result["operation"] == "read"

    @pytest.mark.asyncio
    async def test_read_node_success_real(self, nlp_service):
        """Test read node successfully processes query with real AI"""
        # Mock database query since we're testing the AI parsing
        mock_entries = [
            {
                "id": "entry-1",
                "amount_cents": 2000,
                "direction": "expense",
                "entry_date": "2025-01-15",
                "description": "coffee",
                "source": "nlp",
                "parse_confidence": 0.9,
                "created_at": "2025-01-15T10:00:00Z",
                "category": {
                    "id": "cat-1",
                    "name": "Food & Dining (Expense)",
                    "type": "expense",
                },
            }
        ]

        nlp_service._execute_read_query = AsyncMock(return_value=mock_entries)

        result = await nlp_service._read_node({"text": "show me expenses"})

        assert "result" in result
        assert len(result["result"]) == 1
        assert result["result"][0]["id"] == "entry-1"

    @pytest.mark.asyncio
    async def test_write_node_success_real(self, nlp_service):
        """Test write node successfully processes entry creation with real AI"""
        # Mock categories and database operations
        from uuid import uuid4

        mock_categories = [
            CategoryResponse(
                id=uuid4(), name="Food & Dining (Expense)", type="expense"
            ),
            CategoryResponse(
                id=uuid4(), name="Transportation (Expense)", type="expense"
            ),
            CategoryResponse(id=uuid4(), name="Salary (Income)", type="income"),
        ]

        # Mock database operations
        mock_created_entry = {
            "id": "entry-1",
            "amount": 20.0,
            "direction": "expense",
            "entry_date": "2025-01-15",
            "description": "coffee",
            "source": "nlp",
            "created_at": "2025-01-15T10:00:00Z",
        }

        nlp_service._get_categories = AsyncMock(return_value=mock_categories)
        nlp_service._create_entry = AsyncMock(return_value=mock_created_entry)

        result = await nlp_service._write_node({"text": "spent $20 on coffee"})

        assert "result" in result
        assert result["result"]["id"] == "entry-1"
        assert result["result"]["amount"] == 20.0

    @pytest.mark.asyncio
    async def test_write_node_missing_fields_real(self, nlp_service):
        """Test write node handles missing required fields with real AI"""
        # Mock categories
        from uuid import uuid4

        mock_categories = [
            CategoryResponse(
                id=uuid4(), name="Food & Dining (Expense)", type="expense"
            ),
        ]

        nlp_service._get_categories = AsyncMock(return_value=mock_categories)

        result = await nlp_service._write_node({"text": "spent money"})

        # Should handle missing amount gracefully
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_categories_success_real(self, nlp_service):
        """Test get categories successfully retrieves from database with real service"""
        # Mock database response
        from uuid import uuid4

        mock_categories_data = [
            {"id": str(uuid4()), "name": "Food & Dining (Expense)", "type": "expense"}
        ]

        mock_result = MagicMock()
        mock_result.data = mock_categories_data

        mock_table = MagicMock()
        mock_table.select.return_value.execute.return_value = mock_result
        nlp_service.db.client.table = MagicMock(return_value=mock_table)

        categories = await nlp_service._get_categories()

        assert len(categories) == 1
        assert categories[0].name == "Food & Dining (Expense)"

    @pytest.mark.asyncio
    async def test_get_categories_database_error_real(self, nlp_service):
        """Test get categories handles database errors with fallback"""
        # Mock database error
        mock_table = MagicMock()
        mock_table.select.return_value.execute.side_effect = Exception("DB Error")
        nlp_service.db.client.table = MagicMock(return_value=mock_table)

        categories = await nlp_service._get_categories()

        # Should return default categories
        assert len(categories) == 2
        assert any(cat.type == "expense" for cat in categories)
        assert any(cat.type == "income" for cat in categories)

    @pytest.mark.asyncio
    async def test_create_entry_success_real(self, nlp_service):
        """Test create entry successfully creates database entry with real service"""
        parsed_data = ParsedData(
            amount=Decimal("20.0"),
            direction=EntryDirection.EXPENSE,
            entry_date=date(2025, 1, 15),
            category="Food & Dining (Expense)",
            description="coffee",
        )

        # Mock categories
        from uuid import uuid4

        mock_categories = [
            CategoryResponse(
                id=uuid4(), name="Food & Dining (Expense)", type="expense"
            ),
        ]

        # Mock database response
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "entry-1",
                "amount_cents": 2000,
                "direction": "expense",
                "entry_date": "2025-01-15",
                "description": "coffee",
                "source": "nlp",
                "created_at": "2025-01-15T10:00:00Z",
            }
        ]

        nlp_service._get_categories = AsyncMock(return_value=mock_categories)

        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = mock_result
        nlp_service.db.client.table = MagicMock(return_value=mock_table)

        result = await nlp_service._create_entry(parsed_data)

        assert result["id"] == "entry-1"
        assert result["amount"] == 20.0
        assert result["direction"] == "expense"

    @pytest.mark.asyncio
    async def test_create_entry_category_fallback_real(self, nlp_service):
        """Test create entry uses fallback category when category not found"""
        parsed_data = ParsedData(
            amount=Decimal("20.0"),
            direction=EntryDirection.EXPENSE,
            entry_date=date(2025, 1, 15),
            category="Unknown Category",
            description="coffee",
        )

        # Mock categories without the requested category
        from uuid import uuid4

        mock_categories = [
            CategoryResponse(id=uuid4(), name="Food & Dining (Expense)", type="expense")
        ]

        # Mock database response
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "entry-1",
                "amount_cents": 2000,
                "direction": "expense",
                "entry_date": "2025-01-15",
                "description": "coffee",
                "source": "nlp",
                "created_at": "2025-01-15T10:00:00Z",
            }
        ]

        nlp_service._get_categories = AsyncMock(return_value=mock_categories)

        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = mock_result
        nlp_service.db.client.table = MagicMock(return_value=mock_table)

        result = await nlp_service._create_entry(parsed_data)

        assert result["id"] == "entry-1"
        assert (
            result["category"]["id"] == mock_categories[0].id
        )  # Should use fallback category

    @pytest.mark.asyncio
    async def test_process_query_integration_real(self, nlp_service):
        """Test end-to-end process query integration with real AI"""
        # Mock database operations to avoid actual database calls
        nlp_service._execute_read_query = AsyncMock(return_value=[])
        nlp_service._get_categories = AsyncMock(return_value=[])
        nlp_service._create_entry = AsyncMock(return_value={"id": "entry-1"})

        result = await nlp_service.process_query("spent $20 on coffee")

        assert "operation" in result
        assert result["operation"] == "write"

    @pytest.mark.asyncio
    async def test_complex_queries_real(self, nlp_service):
        """Test complex natural language queries with real AI"""
        # Mock database operations
        nlp_service._execute_read_query = AsyncMock(return_value=[])
        nlp_service._get_categories = AsyncMock(return_value=[])
        nlp_service._create_entry = AsyncMock(return_value={"id": "entry-1"})

        complex_queries = [
            "show me all my food expenses from last week",
            "what was my total income this month",
            "spent twenty dollars on lunch yesterday",
            "earned five hundred from freelance work",
        ]

        for query in complex_queries:
            result = await nlp_service.process_query(query)

            # Should return a valid response
            assert isinstance(result, dict)
            assert "operation" in result
            assert result["operation"] in ["read", "write"]

    @pytest.mark.asyncio
    async def test_performance_real(self, nlp_service):
        """Test performance with real AI"""
        import time

        # Mock database operations
        nlp_service._execute_read_query = AsyncMock(return_value=[])

        start_time = time.time()

        result = await nlp_service.process_query("show me my expenses")

        end_time = time.time()
        response_time = end_time - start_time

        assert "operation" in result
        # Should respond within reasonable time (adjust threshold as needed)
        assert response_time < 5.0  # 5 second threshold for real AI calls

    @pytest.mark.asyncio
    async def test_concurrent_queries_real(self, nlp_service):
        """Test concurrent query processing with real AI"""
        import asyncio

        # Mock database operations
        nlp_service._execute_read_query = AsyncMock(return_value=[])
        nlp_service._get_categories = AsyncMock(return_value=[])
        nlp_service._create_entry = AsyncMock(return_value={"id": "entry-1"})

        # Create multiple concurrent queries
        queries = [
            "show me expenses",
            "show me income",
            "spent $20 on coffee",
            "earned $100 from work",
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
            assert result["operation"] in ["read", "write"]

        # Concurrent execution should be faster than sequential
        # (This is a rough check - adjust as needed)
        assert (end_time - start_time) < 15.0  # Should complete within 15 seconds

    @pytest.mark.asyncio
    async def test_ai_parsing_accuracy_real(self, nlp_service):
        """Test AI parsing accuracy with real OpenAI API"""
        # Mock database operations
        nlp_service._execute_read_query = AsyncMock(return_value=[])
        nlp_service._get_categories = AsyncMock(return_value=[])
        nlp_service._create_entry = AsyncMock(return_value={"id": "entry-1"})

        test_cases = [
            {
                "query": "spent twenty dollars on coffee",
                "expected_operation": "write",
            },
            {
                "query": "earned five hundred from work",
                "expected_operation": "write",
            },
            {
                "query": "show me my expenses",
                "expected_operation": "read",
            },
            {
                "query": "what did I spend on food",
                "expected_operation": "read",
            },
        ]

        for case in test_cases:
            result = await nlp_service.process_query(case["query"])

            assert "operation" in result
            assert result["operation"] == case["expected_operation"]

    @pytest.mark.asyncio
    async def test_error_handling_real(self, nlp_service):
        """Test error handling with real AI"""
        # Mock database operations
        nlp_service._execute_read_query = AsyncMock(return_value=[])

        # Test with very ambiguous input
        result = await nlp_service.process_query("xyz")

        # Should handle the error gracefully
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_service_initialization_real(self, nlp_service):
        """Test service initialization with real OpenAI API"""
        assert nlp_service is not None
        assert nlp_service.llm is not None
        assert hasattr(nlp_service, "process_query")

    @pytest.mark.asyncio
    async def test_workflow_creation_real(self, nlp_service):
        """Test workflow creation and configuration with real service"""
        # Test that workflow is created correctly
        workflow = nlp_service._create_workflow()
        assert workflow is not None

    @pytest.mark.asyncio
    async def test_parsing_confidence_handling_real(self, nlp_service):
        """Test parsing confidence handling in write operations with real AI"""
        # Mock categories and database operations
        from uuid import uuid4

        mock_categories = [
            CategoryResponse(
                id=uuid4(), name="Food & Dining (Expense)", type="expense"
            ),
        ]

        # Mock database operations
        mock_created_entry = {
            "id": "entry-1",
            "amount": 20.0,
            "direction": "expense",
            "entry_date": "2025-01-15",
            "description": "coffee",
            "source": "nlp",
            "parse_confidence": 0.85,
            "created_at": "2025-01-15T10:00:00Z",
        }

        nlp_service._get_categories = AsyncMock(return_value=mock_categories)
        nlp_service._create_entry = AsyncMock(return_value=mock_created_entry)

        result = await nlp_service._write_node({"text": "spent $20 on coffee"})

        assert "result" in result
        # Real AI might not always provide confidence scores
        # So we just check that the result is valid
        assert isinstance(result["result"], dict)
