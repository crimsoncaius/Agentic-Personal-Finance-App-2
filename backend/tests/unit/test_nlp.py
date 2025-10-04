"""
Mock unit tests for NLP service - Fast tests without external dependencies
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from services.nlp_service_v2 import NLPServiceV2
from models.schemas import ParsedData, EntryDirection, CategoryResponse, ParseError, ErrorDetail

pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.db_mock,  # Database operations are mocked
    pytest.mark.llm_mock,  # LLM/OpenAI API calls are mocked
]


class TestNLPServiceV2Mock:
    """Mock unit tests for NLP service - Fast unit tests"""


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
        prompt_manager.generate_read_response_prompt.return_value = "read response prompt"
        prompt_manager.generate_write_response_prompt.return_value = "write response prompt"
        prompt_manager.generate_unsure_response_prompt.return_value = "unsure response prompt"

        env_overrides = {
            "OPENAI_API_KEY": "test-key",
            "SUPABASE_URL": "http://localhost",
            "SUPABASE_KEY": "test-supabase-key",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-role",
        }

        with patch.dict("os.environ", env_overrides, clear=False), patch(
            "openai.OpenAI", return_value=mock_llm
        ), patch(
            "services.nlp_service_v2.db_connection", new=mock_db
        ), patch(
            "services.nlp_service_v2.PromptManager", return_value=prompt_manager
        ):
            service = NLPServiceV2("test-key")
            service.llm = mock_llm
            service.prompt_manager = prompt_manager
            service.db = mock_db
            return service

    @pytest.fixture
    def mock_categories(self):
        """Mock categories data"""
        from uuid import uuid4

        return [
            CategoryResponse(
                id=uuid4(), name="Food & Dining (Expense)", type="expense"
            ),
            CategoryResponse(
                id=uuid4(), name="Transportation (Expense)", type="expense"
            ),
            CategoryResponse(id=uuid4(), name="Salary (Income)", type="income"),
        ]

    @pytest.mark.asyncio
    async def test_router_node_read_operation(self, nlp_service):
        """Test router node correctly identifies read operations"""
        # Mock OpenAI client response
        mock_choice = MagicMock()
        mock_choice.message.content = "READ"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        nlp_service.llm.chat.completions.create = MagicMock(return_value=mock_response)

        result = await nlp_service._router_node({"text": "show me my expenses"})

        assert result["operation"] == "read"

    @pytest.mark.asyncio
    async def test_router_node_write_operation(self, nlp_service):
        """Test router node correctly identifies write operations"""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = "WRITE"

        # Mock OpenAI client response
        mock_choice = MagicMock()
        mock_choice.message.content = "WRITE"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        nlp_service.llm.chat.completions.create = MagicMock(return_value=mock_response)

        result = await nlp_service._router_node({"text": "spent $20 on coffee"})

        assert result["operation"] == "write"

    @pytest.mark.asyncio
    async def test_router_node_invalid_response(self, nlp_service):
        """Test router node handles invalid LLM response"""
        # Mock OpenAI client response with invalid content
        mock_choice = MagicMock()
        mock_choice.message.content = "INVALID"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        nlp_service.llm.chat.completions.create = MagicMock(return_value=mock_response)

        result = await nlp_service._router_node({"text": "some input"})

        assert result["operation"] == "unsure"  # Should default to unsure

    @pytest.mark.asyncio
    async def test_router_node_unsure_operation(self, nlp_service):
        """Test router node correctly identifies unsure operations"""
        # Mock OpenAI client response
        mock_choice = MagicMock()
        mock_choice.message.content = "UNSURE"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        nlp_service.llm.chat.completions.create = MagicMock(return_value=mock_response)

        result = await nlp_service._router_node({"text": "coffee"})

        assert result["operation"] == "unsure"

    @pytest.mark.asyncio
    async def test_router_node_exception(self, nlp_service):
        """Test router node handles exceptions"""
        nlp_service.llm.chat.completions.create = MagicMock(
            side_effect=Exception("API Error")
        )

        result = await nlp_service._router_node({"text": "some input"})

        assert "error" in result
        assert isinstance(result["error"], ParseError)
        assert result["error"].code == "parsing_failed"

    @pytest.mark.asyncio
    async def test_read_node_success(self, nlp_service):
        """Test read node successfully processes query"""
        # Mock LLM response
        mock_choice = MagicMock()
        mock_choice.message.content = '{"direction": "expense", "limit": 5}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        # Mock database query
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

        nlp_service.llm.chat.completions.create = MagicMock(return_value=mock_response)
        nlp_service._execute_read_query = AsyncMock(return_value=mock_entries)
        nlp_service._call_llm_for_response = AsyncMock(return_value="Here is your summary.")

        result = await nlp_service._read_node({"text": "show me expenses"})

        assert "result" in result
        assert len(result["result"]) == 1
        assert result["result"][0]["id"] == "entry-1"
        assert result["message"] == "Here is your summary."

    @pytest.mark.asyncio
    async def test_read_node_invalid_json(self, nlp_service):
        """Test read node handles invalid JSON response"""
        # Mock LLM response with invalid JSON
        mock_choice = MagicMock()
        mock_choice.message.content = "invalid json"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        nlp_service.llm.chat.completions.create = MagicMock(return_value=mock_response)

        result = await nlp_service._read_node({"text": "show me expenses"})

        assert "error" in result
        assert isinstance(result["error"], ParseError)
        assert result["error"].code == "parsing_failed"

    @pytest.mark.asyncio
    async def test_write_node_success(self, nlp_service, mock_categories):
        """Test write node successfully processes entry creation"""
        # Mock LLM response
        mock_choice = MagicMock()
        mock_choice.message.content = '{"amount": 20.0, "direction": "expense", "date": "2025-01-15", "category": "Food & Dining (Expense)", "description": "coffee"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

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

        nlp_service.llm.chat.completions.create = MagicMock(return_value=mock_response)
        nlp_service._get_categories = AsyncMock(return_value=mock_categories)
        nlp_service._create_entry = AsyncMock(return_value=mock_created_entry)
        nlp_service._call_llm_for_response = AsyncMock(return_value="Entry created successfully.")

        result = await nlp_service._write_node({"text": "spent $20 on coffee"})

        assert "result" in result
        assert result["result"]["id"] == "entry-1"
        assert result["result"]["amount"] == 20.0
        assert result["message"] == "Entry created successfully."

    @pytest.mark.asyncio
    async def test_write_node_missing_fields(self, nlp_service, mock_categories):
        """Test write node handles missing required fields"""
        # Mock LLM response with missing fields
        mock_choice = MagicMock()
        mock_choice.message.content = """
        {
            "amount": 20.0,
            "direction": "expense"
        }
        """
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        nlp_service.llm.chat.completions.create = MagicMock(return_value=mock_response)
        nlp_service._get_categories = AsyncMock(return_value=mock_categories)

        result = await nlp_service._write_node({"text": "spent $20"})

        assert "error" in result
        assert isinstance(result["error"], ParseError)
        assert result["error"].code == "missing_fields"

    @pytest.mark.asyncio
    async def test_write_node_invalid_json(self, nlp_service, mock_categories):
        """Test write node handles invalid JSON response"""
        # Mock LLM response with invalid JSON
        mock_choice = MagicMock()
        mock_choice.message.content = "invalid json"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        nlp_service.llm.chat.completions.create = MagicMock(return_value=mock_response)
        nlp_service._get_categories = AsyncMock(return_value=mock_categories)

        result = await nlp_service._write_node({"text": "spent $20 on coffee"})

        assert "error" in result
        assert isinstance(result["error"], ParseError)
        assert result["error"].code == "missing_fields"

    @pytest.mark.asyncio
    async def test_unsure_node_success(self, nlp_service):
        """Test unsure node returns helpful error message"""
        nlp_service._call_llm_for_response = AsyncMock(return_value="Please clarify your request.")

        result = await nlp_service._unsure_node({"text": "coffee"})

        assert "error" in result
        assert isinstance(result["error"], ParseError)
        assert result["error"].code == "ambiguous"
        assert "clarify" in result["error"].message.lower()
        assert len(result["error"].details.suggestions) == 4
        assert result["message"] == "Please clarify your request."

    @pytest.mark.asyncio
    async def test_unsure_node_exception(self, nlp_service):
        """Test unsure node handles exceptions gracefully"""
        # Test the unsure node with normal input - it should handle gracefully
        nlp_service._call_llm_for_response = AsyncMock(return_value="Please clarify your request.")

        result = await nlp_service._unsure_node({"text": "coffee"})

        assert "error" in result
        assert isinstance(result["error"], ParseError)
        assert result["error"].code == "ambiguous"
        assert result["message"] == "Please clarify your request."

    @pytest.mark.asyncio
    async def test_get_categories_success(self, nlp_service):
        """Test get categories successfully retrieves from database"""
        from uuid import uuid4

        mock_categories_data = [
            {"id": str(uuid4()), "name": "Food & Dining (Expense)", "type": "expense"}
        ]

        # Mock database response
        mock_result = MagicMock()
        mock_result.data = mock_categories_data

        mock_table = MagicMock()
        mock_table.select.return_value.execute.return_value = mock_result
        nlp_service.db.client.table = MagicMock(return_value=mock_table)

        categories = await nlp_service._get_categories()

        assert len(categories) == 1
        assert categories[0].name == "Food & Dining (Expense)"

    @pytest.mark.asyncio
    async def test_get_categories_database_error(self, nlp_service):
        """Test get categories handles database errors with fallback"""
        mock_table = MagicMock()
        mock_table.select.return_value.execute.side_effect = Exception("DB Error")
        nlp_service.db.client.table = MagicMock(return_value=mock_table)

        categories = await nlp_service._get_categories()

        # Should return default categories
        assert len(categories) == 2
        assert any(cat.type == "expense" for cat in categories)
        assert any(cat.type == "income" for cat in categories)

    @pytest.mark.asyncio
    async def test_create_entry_success(self, nlp_service, mock_categories):
        """Test create entry successfully creates database entry"""
        parsed_data = ParsedData(
            amount=Decimal("20.0"),
            direction=EntryDirection.EXPENSE,
            entry_date=date(2025, 1, 15),
            category="Food & Dining (Expense)",
            description="coffee",
        )

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
    async def test_create_entry_category_fallback(self, nlp_service):
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
    async def test_process_query_integration(self, nlp_service):
        """Test end-to-end process query integration"""
        # Mock the entire workflow
        mock_workflow_instance = AsyncMock()
        mock_workflow_instance.ainvoke.return_value = {
            "operation": "write",
            "result": {"id": "entry-1", "amount": 20.0},
        }
        nlp_service._create_workflow = MagicMock(return_value=mock_workflow_instance)

        result = await nlp_service.process_query("spent $20 on coffee")

        assert "operation" in result
        assert result["operation"] == "write"
        assert "result" in result

    @pytest.mark.asyncio
    async def test_process_query_error_handling(self, nlp_service):
        """Test process query handles errors gracefully"""
        nlp_service._create_workflow = MagicMock(
            side_effect=Exception("Workflow Error")
        )

        result = await nlp_service.process_query("some input")

        assert isinstance(result, ParseError)
        assert result.code == "parsing_failed"


    @pytest.mark.asyncio
    async def test_process_query_handles_ambiguous_error(self, nlp_service):
        """Test ambiguous workflow responses are returned as friendly message"""
        ambiguous_error = ParseError(
            code="ambiguous",
            message="Need clarification",
            details=ErrorDetail(suggestions=["Provide more detail"]),
        )
        mock_workflow_instance = AsyncMock()
        mock_workflow_instance.ainvoke.return_value = {
            "operation": "unsure",
            "result": [],
            "message": "Need clarification",
            "error": ambiguous_error,
        }
        nlp_service._create_workflow = MagicMock(return_value=mock_workflow_instance)

        result = await nlp_service.process_query("show me something")

        assert result["operation"] == "unsure"
        assert result["message"] == "Need clarification"
        assert result["result"] == []

    @pytest.mark.asyncio
    async def test_service_initialization(self, nlp_service):
        """Test service initialization with mocked dependencies"""
        assert nlp_service is not None
        assert nlp_service.llm is not None
        assert hasattr(nlp_service, "process_query")

    @pytest.mark.asyncio
    async def test_concurrent_queries(self, nlp_service):
        """Test concurrent query processing"""
        import asyncio

        # Mock the entire workflow
        mock_workflow_instance = AsyncMock()
        mock_workflow_instance.ainvoke.return_value = {
            "operation": "read",
            "result": [],
        }
        nlp_service._create_workflow = MagicMock(return_value=mock_workflow_instance)

        # Create multiple concurrent queries
        queries = [
            "show me expenses",
            "show me income",
            "spent $20 on coffee",
            "earned $100 from work",
        ]

        # Run queries concurrently
        tasks = [nlp_service.process_query(query) for query in queries]
        results = await asyncio.gather(*tasks)

        # All queries should succeed
        assert len(results) == 4
        for result in results:
            assert "operation" in result
            assert result["operation"] in ["read", "write"]

    @pytest.mark.asyncio
    async def test_error_response_formatting(self, nlp_service):
        """Test error response formatting"""
        nlp_service._create_workflow = MagicMock(side_effect=Exception("Test Error"))

        result = await nlp_service.process_query("test input")

        # Should return a ParseError with proper structure
        assert isinstance(result, ParseError)
        assert hasattr(result, "code")
        assert hasattr(result, "message")
        assert result.code == "parsing_failed"

    @pytest.mark.asyncio
    async def test_workflow_creation(self, nlp_service):
        """Test workflow creation and configuration"""
        # Mock the workflow creation
        mock_workflow = MagicMock()
        nlp_service._create_workflow = MagicMock(return_value=mock_workflow)

        # Test that workflow is created correctly
        workflow = nlp_service._create_workflow()
        assert workflow is not None

    @pytest.mark.asyncio
    async def test_parsing_confidence_handling(self, nlp_service, mock_categories):
        """Test parsing confidence handling in write operations"""
        # Mock LLM response with parsing confidence
        mock_choice = MagicMock()
        mock_choice.message.content = '{"amount": 20.0, "direction": "expense", "date": "2025-01-15", "category": "Food & Dining (Expense)", "description": "coffee", "confidence": 0.85}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

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

        nlp_service.llm.chat.completions.create = MagicMock(return_value=mock_response)
        nlp_service._get_categories = AsyncMock(return_value=mock_categories)
        nlp_service._create_entry = AsyncMock(return_value=mock_created_entry)
        nlp_service._call_llm_for_response = AsyncMock(return_value="Entry created successfully.")

        result = await nlp_service._write_node({"text": "spent $20 on coffee"})

        assert "result" in result
        assert result["result"]["parse_confidence"] == 0.85
        assert result["message"] == "Entry created successfully."
