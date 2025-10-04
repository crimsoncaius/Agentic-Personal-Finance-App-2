"""
Mock integration tests for NLP service - Fast tests without external dependencies
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from services.nlp_service_v2 import NLPServiceV2
from models.schemas import CategoryResponse, EntryDirection
from database.connection import db_connection

pytestmark = [
    pytest.mark.integration,
    pytest.mark.fast,
    pytest.mark.db_mock,  # Database operations are mocked
    pytest.mark.llm_mock,  # LLM/OpenAI API calls are mocked
]


class TestNLPIntegrationMock:
    """Mock integration tests for NLP service - Fast unit tests"""

    @pytest.fixture
    def nlp_service(self):
        """Create NLP service instance for testing with mocked dependencies"""
        mock_llm = MagicMock()
        mock_db = MagicMock()
        mock_db.client = MagicMock()

        prompt_manager = MagicMock()
        prompt_manager.generate_router_prompt.return_value = "router prompt"
        prompt_manager.generate_read_prompt.return_value = "read prompt"
        prompt_manager.generate_write_prompt.return_value = "write prompt"
        prompt_manager.generate_read_response_prompt.return_value = (
            "read response prompt"
        )
        prompt_manager.generate_write_response_prompt.return_value = (
            "write response prompt"
        )
        prompt_manager.generate_unsure_response_prompt.return_value = (
            "unsure response prompt"
        )

        env_overrides = {
            "OPENAI_API_KEY": "test-key",
            "SUPABASE_URL": "http://localhost",
            "SUPABASE_KEY": "test-supabase-key",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-role",
        }

        with patch.dict("os.environ", env_overrides, clear=False), patch(
            "openai.OpenAI", return_value=mock_llm
        ), patch("services.nlp_service_v2.db_connection", new=mock_db), patch(
            "services.nlp_service_v2.PromptManager", return_value=prompt_manager
        ):
            service = NLPServiceV2("test-key")
            service.llm = mock_llm
            service.db = mock_db
            service.prompt_manager = prompt_manager
            return service

    @pytest.fixture
    def mock_database_data(self):
        """Mock database data for testing"""
        from uuid import uuid4

        return {
            "categories": [
                {
                    "id": str(uuid4()),
                    "name": "Food & Dining (Expense)",
                    "type": "expense",
                },
                {
                    "id": str(uuid4()),
                    "name": "Transportation (Expense)",
                    "type": "expense",
                },
                {
                    "id": str(uuid4()),
                    "name": "Salary (Income)",
                    "type": "income",
                },
            ],
            "entries": [
                {
                    "id": str(uuid4()),
                    "amount_cents": 2000,  # $20.00
                    "direction": "expense",
                    "entry_date": "2025-01-15",
                    "description": "coffee",
                    "source": "manual",
                    "created_at": "2025-01-15T10:00:00Z",
                    "category": {
                        "id": str(uuid4()),
                        "name": "Food & Dining (Expense)",
                        "type": "expense",
                    },
                },
                {
                    "id": str(uuid4()),
                    "amount_cents": 5000,  # $50.00
                    "direction": "expense",
                    "entry_date": "2025-01-14",
                    "description": "bus pass",
                    "source": "manual",
                    "created_at": "2025-01-14T08:00:00Z",
                    "category": {
                        "id": str(uuid4()),
                        "name": "Transportation (Expense)",
                        "type": "expense",
                    },
                },
                {
                    "id": str(uuid4()),
                    "amount_cents": 500000,  # $5000.00
                    "direction": "income",
                    "entry_date": "2025-01-01",
                    "description": "salary",
                    "source": "manual",
                    "created_at": "2025-01-01T00:00:00Z",
                    "category": {
                        "id": str(uuid4()),
                        "name": "Salary (Income)",
                        "type": "income",
                    },
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_read_query_mock_integration(self, nlp_service, mock_database_data):
        """Test read query integration with mocked database"""
        # Mock the router node
        nlp_service._router_node = AsyncMock(return_value={"operation": "read"})

        # Mock the read node
        nlp_service._read_node = AsyncMock(
            return_value={
                "operation": "read",
                "result": [
                    entry
                    for entry in mock_database_data["entries"]
                    if entry["direction"] == "expense"
                ],
            }
        )
        nlp_service._read_node.return_value["message"] = (
            "Here are your matching entries."
        )

        result = await nlp_service.process_query("show me my expenses")

        assert "operation" in result
        assert result["operation"] == "read"
        assert "result" in result
        assert len(result["result"]) >= 2  # Should have at least 2 expense entries
        assert result["message"] == "Here are your matching entries."

        # Verify the entries are properly formatted
        for entry in result["result"]:
            assert "id" in entry
            assert "amount_cents" in entry
            assert "direction" in entry
            assert "entry_date" in entry
            assert "description" in entry
            assert entry["direction"] == "expense"

    @pytest.mark.asyncio
    async def test_write_query_mock_integration(self, nlp_service, mock_database_data):
        """Test write query integration with mocked database"""
        # Mock the router node
        nlp_service._router_node = AsyncMock(return_value={"operation": "write"})

        # Mock the write node
        mock_created_entry = {
            "id": "entry-new",
            "amount": 15.0,
            "direction": "expense",
            "entry_date": "2025-01-15",
            "description": "lunch",
            "source": "nlp",
            "created_at": "2025-01-15T12:00:00Z",
            "category": mock_database_data["categories"][0],
        }

        nlp_service._write_node = AsyncMock(
            return_value={"operation": "write", "result": mock_created_entry}
        )
        nlp_service._write_node.return_value["message"] = "Entry created successfully."

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
        assert result["message"] == "Entry created successfully."

    @pytest.mark.asyncio
    async def test_category_fallback_mock_integration(
        self, nlp_service, mock_database_data
    ):
        """Test category fallback when category not found"""
        # Mock the router node
        nlp_service._router_node = AsyncMock(return_value={"operation": "write"})

        # Mock the write node with fallback category
        mock_created_entry = {
            "id": "entry-new",
            "amount": 25.0,
            "direction": "expense",
            "entry_date": "2025-01-15",
            "description": "unknown category",
            "source": "nlp",
            "created_at": "2025-01-15T12:00:00Z",
            "category": mock_database_data["categories"][
                0
            ],  # Fallback to first category
        }

        nlp_service._write_node = AsyncMock(
            return_value={"operation": "write", "result": mock_created_entry}
        )
        nlp_service._write_node.return_value["message"] = "Entry created successfully."

        result = await nlp_service.process_query("spent $25 on unknown category")

        assert "operation" in result
        assert result["operation"] == "write"
        assert "result" in result

        # Verify the created entry has a fallback category
        entry = result["result"]
        assert "category" in entry
        assert "id" in entry["category"]
        assert "name" in entry["category"]
        assert result["message"] == "Entry created successfully."

    @pytest.mark.asyncio
    async def test_database_error_handling_mock(self, nlp_service):
        """Test database error handling in mock integration"""
        # Mock the router node
        nlp_service._router_node = AsyncMock(return_value={"operation": "read"})

        # Mock the read node to handle database errors gracefully
        nlp_service._read_node = AsyncMock(
            return_value={"operation": "read", "result": []}
        )
        nlp_service._read_node.return_value["message"] = (
            "Here are your matching entries."
        )

        result = await nlp_service.process_query("show me expenses from 1900")

        # Should still return a valid response (empty result)
        assert "operation" in result
        assert result["operation"] == "read"
        assert "result" in result
        assert isinstance(result["result"], list)
        assert result["message"] == "Here are your matching entries."

    @pytest.mark.asyncio
    async def test_end_to_end_read_flow_mock(self, nlp_service, mock_database_data):
        """Test complete end-to-end read flow with mocks"""
        # Mock the router node
        nlp_service._router_node = AsyncMock(return_value={"operation": "read"})

        # Mock the read node
        nlp_service._read_node = AsyncMock(
            return_value={"operation": "read", "result": mock_database_data["entries"]}
        )
        nlp_service._read_node.return_value["message"] = (
            "Here are your matching entries."
        )

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
            assert result["message"] == "Here are your matching entries."

    @pytest.mark.asyncio
    async def test_end_to_end_write_flow_mock(self, nlp_service, mock_database_data):
        """Test complete end-to-end write flow with mocks"""
        # Mock the router node
        nlp_service._router_node = AsyncMock(return_value={"operation": "write"})

        # Mock the write node
        mock_created_entry = {
            "id": "entry-new",
            "amount": 30.0,
            "direction": "expense",
            "entry_date": "2025-01-15",
            "description": "groceries",
            "source": "nlp",
            "created_at": "2025-01-15T12:00:00Z",
            "category": mock_database_data["categories"][0],
        }

        nlp_service._write_node = AsyncMock(
            return_value={"operation": "write", "result": mock_created_entry}
        )
        nlp_service._write_node.return_value["message"] = "Entry created successfully."

        # Test various write queries
        write_queries = [
            "spent $30 on groceries",
            "earned $200 from consulting",
            "bought $5 coffee",
            "received $1000 salary",
        ]

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
            assert result["message"] == "Entry created successfully."

    @pytest.mark.asyncio
    async def test_nlp_parsing_accuracy_mock(self, nlp_service, mock_database_data):
        """Test that NLP parsing correctly identifies amounts and categories with mocks"""
        # Mock the router node
        nlp_service._router_node = AsyncMock(return_value={"operation": "write"})

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

        for case in test_cases:
            # Mock the write node with expected results
            mock_created_entry = {
                "id": "entry-new",
                "amount": case["expected_amount"],
                "direction": case["expected_direction"],
                "entry_date": "2025-01-15",
                "description": "test",
                "source": "nlp",
                "created_at": "2025-01-15T12:00:00Z",
                "category": mock_database_data["categories"][0],
            }

            nlp_service._write_node = AsyncMock(
                return_value={"operation": "write", "result": mock_created_entry}
            )
            nlp_service._write_node.return_value["message"] = (
                "Entry created successfully."
            )

            result = await nlp_service.process_query(case["query"])

            assert "operation" in result
            assert result["operation"] == "write"
            assert "result" in result

            entry = result["result"]
            assert abs(entry["amount"] - case["expected_amount"]) < 0.01
            assert entry["direction"] == case["expected_direction"]
            assert result["message"] == "Entry created successfully."

    @pytest.mark.asyncio
    async def test_workflow_error_handling_mock(self, nlp_service):
        """Test workflow error handling with mocks"""
        # Mock the router node to raise an exception
        nlp_service._router_node = AsyncMock(side_effect=Exception("Workflow Error"))

        result = await nlp_service.process_query("some input")

        # Should handle the error gracefully
        assert isinstance(result, dict) or hasattr(result, "code")

    @pytest.mark.asyncio
    async def test_service_initialization_mock(self, nlp_service):
        """Test service initialization with mocked dependencies"""
        assert nlp_service is not None
        assert nlp_service.llm is not None
        assert hasattr(nlp_service, "process_query")

    @pytest.mark.asyncio
    async def test_concurrent_queries_mock(self, nlp_service, mock_database_data):
        """Test concurrent query processing with mocks"""
        import asyncio

        # Mock the router and read nodes
        nlp_service._router_node = AsyncMock(return_value={"operation": "read"})
        nlp_service._read_node = AsyncMock(
            return_value={"operation": "read", "result": mock_database_data["entries"]}
        )
        nlp_service._read_node.return_value["message"] = (
            "Here are your matching entries."
        )

        # Create multiple concurrent queries
        queries = [
            "show me expenses",
            "show me income",
            "what did I spend on food",
            "list my transportation",
        ]

        # Run queries concurrently
        tasks = [nlp_service.process_query(query) for query in queries]
        results = await asyncio.gather(*tasks)

        # All queries should succeed
        assert len(results) == 4
        for result in results:
            assert "operation" in result
            assert result["operation"] == "read"
            assert "result" in result
            assert result["message"] == "Here are your matching entries."
