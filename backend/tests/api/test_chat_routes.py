"""
Tests for chat API routes with mocked LLM and authentication
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from main import app
from middleware.auth import get_current_user_id
from database.connection import db_connection

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.db_real,
    pytest.mark.llm_mock,  # Mock LLM to avoid costs
    pytest.mark.auth_mock,  # Mock auth for faster tests
]


@pytest.fixture
def client_with_mock_auth(mock_auth_dependency):
    """Create test client with mocked authentication"""
    mock_get_user_id, mock_user_id = mock_auth_dependency

    # Override the auth dependency
    app.dependency_overrides[get_current_user_id] = mock_get_user_id

    client = TestClient(app)
    yield client, mock_user_id

    # Clean up override
    app.dependency_overrides.clear()


class TestChatRoutes:
    """Tests for chat-related routes"""

    def test_service_info_endpoint(self, client_with_mock_auth):
        """Test service info endpoint"""
        client, _ = client_with_mock_auth

        response = client.get("/api/v1/chat/service-info")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "class_name" in data
        assert data["class_name"] == "AgentService"

    def test_chat_endpoint_with_read_query(
        self, client_with_mock_auth, test_data_setup
    ):
        """Test chat endpoint with a read query"""
        client, user_id = client_with_mock_auth

        with patch("routes.chat.AgentService") as mock_agent_class:
            # Mock agent response
            mock_agent = MagicMock()
            mock_agent.process_query = AsyncMock(
                return_value={
                    "message": "You have 3 expenses totaling $75.00",
                    "entries": [
                        {
                            "id": str(uuid4()),
                            "amount": 20.0,
                            "direction": "expense",
                            "entry_date": "2025-01-15",
                            "description": "coffee",
                            "category": {
                                "id": str(uuid4()),
                                "name": "Food & Dining",
                                "type": "expense",
                            },
                            "created_at": "2025-01-15T10:00:00Z",
                        }
                    ],
                    "chat_id": str(uuid4()),
                }
            )
            mock_agent_class.return_value = mock_agent

            response = client.post(
                "/api/v1/chat/", json={"text": "show me my expenses"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "entries" in data
            assert "chat_id" in data
            assert isinstance(data["entries"], list)

    def test_chat_endpoint_with_write_query(
        self, client_with_mock_auth, test_data_setup
    ):
        """Test chat endpoint with a write query"""
        client, user_id = client_with_mock_auth

        with patch("routes.chat.AgentService") as mock_agent_class:
            # Mock agent response
            new_entry_id = str(uuid4())
            mock_agent = MagicMock()
            mock_agent.process_query = AsyncMock(
                return_value={
                    "message": "I've recorded your $25 lunch expense.",
                    "entries": [
                        {
                            "id": new_entry_id,
                            "amount": 25.0,
                            "direction": "expense",
                            "entry_date": "2025-10-12",
                            "description": "lunch",
                            "category": {
                                "id": str(uuid4()),
                                "name": "Food & Dining",
                                "type": "expense",
                            },
                            "created_at": "2025-10-12T12:00:00Z",
                        }
                    ],
                    "chat_id": str(uuid4()),
                }
            )
            mock_agent_class.return_value = mock_agent

            response = client.post("/api/v1/chat/", json={"text": "spent $25 on lunch"})

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "entries" in data
            assert len(data["entries"]) > 0

    def test_chat_endpoint_with_chat_id(self, client_with_mock_auth):
        """Test chat endpoint with conversation context"""
        client, user_id = client_with_mock_auth

        chat_id = str(uuid4())

        with patch("routes.chat.AgentService") as mock_agent_class:
            # Mock agent response
            mock_agent = MagicMock()
            mock_agent.process_query = AsyncMock(
                return_value={
                    "message": "Yes, I remember we were discussing your food expenses.",
                    "entries": [],
                    "chat_id": chat_id,
                }
            )
            mock_agent_class.return_value = mock_agent

            response = client.post(
                "/api/v1/chat/",
                json={
                    "text": "do you remember what we were talking about?",
                    "chat_id": chat_id,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["chat_id"] == chat_id

    def test_chat_endpoint_invalid_input(self, client_with_mock_auth):
        """Test chat endpoint with invalid input"""
        client, user_id = client_with_mock_auth

        # Test empty text
        response = client.post("/api/v1/chat/", json={"text": ""})
        assert response.status_code == 422

        # Test missing text field
        response = client.post("/api/v1/chat/", json={})
        assert response.status_code == 422

        # Test text too long
        long_text = "x" * 1001
        response = client.post("/api/v1/chat/", json={"text": long_text})
        assert response.status_code == 422

    def test_chat_endpoint_error_handling(self, client_with_mock_auth):
        """Test chat endpoint handles service errors"""
        client, user_id = client_with_mock_auth

        with patch("routes.chat.AgentService") as mock_agent_class:
            # Mock agent exception
            mock_agent = MagicMock()
            mock_agent.process_query = AsyncMock(side_effect=Exception("Service error"))
            mock_agent_class.return_value = mock_agent

            response = client.post("/api/v1/chat/", json={"text": "some input"})

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    def test_conversation_history_endpoint(self, client_with_mock_auth):
        """Test conversation history retrieval"""
        client, user_id = client_with_mock_auth

        chat_id = str(uuid4())

        with patch("routes.chat.redis_service") as mock_redis:
            # Mock Redis response
            mock_redis.get_conversation_history = AsyncMock(return_value=[])

            response = client.get(f"/api/v1/chat/{chat_id}/history")

            assert response.status_code == 200
            data = response.json()
            assert "chat_id" in data
            assert "messages" in data
            assert "count" in data
            assert data["chat_id"] == chat_id

    def test_clear_conversation_endpoint(self, client_with_mock_auth):
        """Test conversation clearing"""
        client, user_id = client_with_mock_auth

        chat_id = str(uuid4())

        with patch("routes.chat.redis_service") as mock_redis:
            # Mock Redis response
            mock_redis.clear_conversation = AsyncMock(return_value=True)

            response = client.delete(f"/api/v1/chat/{chat_id}")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "chat_id" in data
            assert data["chat_id"] == chat_id

    def test_chat_with_multiple_entries(self, client_with_mock_auth, test_data_setup):
        """Test chat response with multiple entries"""
        client, user_id = client_with_mock_auth

        with patch("routes.chat.AgentService") as mock_agent_class:
            # Mock agent response with multiple entries
            mock_agent = MagicMock()
            mock_agent.process_query = AsyncMock(
                return_value={
                    "message": "Here are your top 3 expenses",
                    "entries": [
                        {
                            "id": str(uuid4()),
                            "amount": 50.0,
                            "direction": "expense",
                            "entry_date": "2025-01-15",
                            "description": "groceries",
                            "category": {
                                "id": str(uuid4()),
                                "name": "Food & Dining",
                                "type": "expense",
                            },
                            "created_at": "2025-01-15T10:00:00Z",
                        },
                        {
                            "id": str(uuid4()),
                            "amount": 30.0,
                            "direction": "expense",
                            "entry_date": "2025-01-14",
                            "description": "lunch",
                            "category": {
                                "id": str(uuid4()),
                                "name": "Food & Dining",
                                "type": "expense",
                            },
                            "created_at": "2025-01-14T12:00:00Z",
                        },
                        {
                            "id": str(uuid4()),
                            "amount": 20.0,
                            "direction": "expense",
                            "entry_date": "2025-01-13",
                            "description": "coffee",
                            "category": {
                                "id": str(uuid4()),
                                "name": "Food & Dining",
                                "type": "expense",
                            },
                            "created_at": "2025-01-13T08:00:00Z",
                        },
                    ],
                    "chat_id": str(uuid4()),
                }
            )
            mock_agent_class.return_value = mock_agent

            response = client.post(
                "/api/v1/chat/", json={"text": "show my top 3 expenses"}
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["entries"]) == 3
            assert all("id" in entry for entry in data["entries"])
            assert all("amount" in entry for entry in data["entries"])
