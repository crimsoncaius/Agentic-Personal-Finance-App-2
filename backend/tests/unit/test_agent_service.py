"""
Unit tests for AgentService with mocked LLM and DB.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.db_mock,
    pytest.mark.llm_mock,
    pytest.mark.auth_mock,
]


class MockLLMMessage:
    """Mock LLM message response"""

    def __init__(self, content: str):
        self.content = content


class MockLLMResponse:
    """Mock LLM response"""

    def __init__(self, messages: list):
        self.messages = messages


def _make_db_mock(rows):
    """Create a minimal Supabase-like chaining mock that returns rows on execute."""
    table_mock = MagicMock()
    # chain methods return self
    table_mock.select.return_value = table_mock
    table_mock.eq.return_value = table_mock
    table_mock.gte.return_value = table_mock
    table_mock.lte.return_value = table_mock
    table_mock.ilike.return_value = table_mock
    table_mock.in_.return_value = table_mock
    table_mock.order.return_value = table_mock
    table_mock.range.return_value = table_mock
    table_mock.insert.return_value = table_mock
    table_mock.update.return_value = table_mock
    table_mock.delete.return_value = table_mock

    exec_result = MagicMock()
    exec_result.data = rows
    table_mock.execute.return_value = exec_result

    client_mock = MagicMock()
    client_mock.table.return_value = table_mock
    return client_mock


@pytest.mark.asyncio
async def test_agent_simple_reply():
    """Test agent replying without needing to fetch data"""
    with patch("database.connection.db_connection") as mock_db_conn, patch(
        "services.agent_service.create_react_agent"
    ) as mock_create_agent:

        from services.agent_service import AgentService

        # Mock database client
        mock_db_conn.client = _make_db_mock([])

        # Mock agent response
        mock_agent = MagicMock()
        mock_agent.invoke = AsyncMock(
            return_value={
                "messages": [
                    MockLLMMessage(
                        "Hello! How can I help you track your finances today?"
                    )
                ]
            }
        )
        mock_create_agent.return_value = mock_agent

        service = AgentService("test-key")
        result = await service.process_query("hello", user_id=str(uuid4()))

        assert result is not None
        assert "message" in result or "entries" in result


@pytest.mark.asyncio
async def test_agent_fetch_entries():
    """Test agent fetching entries from database"""
    with patch("database.connection.db_connection") as mock_db_conn, patch(
        "services.agent_service.create_react_agent"
    ) as mock_create_agent:

        from services.agent_service import AgentService

        # Mock database with entries
        mock_entries = [
            {
                "id": str(uuid4()),
                "entry_date": "2025-10-01",
                "amount_cents": 10000,
                "direction": "expense",
                "category_id": str(uuid4()),
                "description": "Test expense",
                "user_id": str(uuid4()),
                "created_at": "2025-10-01T12:00:00Z",
                "updated_at": "2025-10-01T12:00:00Z",
            }
        ]
        mock_db_conn.client = _make_db_mock(mock_entries)

        # Mock agent response with tool call
        mock_agent = MagicMock()
        mock_agent.invoke = AsyncMock(
            return_value={
                "messages": [
                    MockLLMMessage(
                        "Here are your expenses: You spent $100 on a test expense."
                    )
                ]
            }
        )
        mock_create_agent.return_value = mock_agent

        service = AgentService("test-key")
        result = await service.process_query(
            "show me my expenses", user_id=str(uuid4())
        )

        assert result is not None


@pytest.mark.asyncio
async def test_agent_create_entry():
    """Test agent creating a new entry"""
    with patch("database.connection.db_connection") as mock_db_conn, patch(
        "services.agent_service.create_react_agent"
    ) as mock_create_agent:

        from services.agent_service import AgentService

        # Mock database for entry creation
        new_entry_id = str(uuid4())
        mock_created_entry = {
            "id": new_entry_id,
            "entry_date": "2025-10-12",
            "amount_cents": 2500,
            "direction": "expense",
            "category_id": str(uuid4()),
            "description": "lunch",
            "user_id": str(uuid4()),
            "created_at": "2025-10-12T12:00:00Z",
            "updated_at": "2025-10-12T12:00:00Z",
        }
        mock_db_conn.client = _make_db_mock([mock_created_entry])

        # Mock agent response
        mock_agent = MagicMock()
        mock_agent.invoke = AsyncMock(
            return_value={
                "messages": [MockLLMMessage("I've recorded your $25 lunch expense.")]
            }
        )
        mock_create_agent.return_value = mock_agent

        service = AgentService("test-key")
        result = await service.process_query("spent $25 on lunch", user_id=str(uuid4()))

        assert result is not None


@pytest.mark.asyncio
async def test_agent_with_conversation_context():
    """Test agent maintaining conversation context"""
    with patch("database.connection.db_connection") as mock_db_conn, patch(
        "services.agent_service.create_react_agent"
    ) as mock_create_agent:

        from services.agent_service import AgentService

        mock_db_conn.client = _make_db_mock([])

        # Mock agent response
        mock_agent = MagicMock()
        mock_agent.invoke = AsyncMock(
            return_value={
                "messages": [
                    MockLLMMessage(
                        "Yes, I remember we were discussing your food expenses."
                    )
                ]
            }
        )
        mock_create_agent.return_value = mock_agent

        service = AgentService("test-key")
        chat_id = str(uuid4())

        # Simulate conversation with same chat_id
        result = await service.process_query(
            "do you remember what we were talking about?",
            user_id=str(uuid4()),
            chat_id=chat_id,
        )

        assert result is not None
        assert result.get("chat_id") == chat_id
