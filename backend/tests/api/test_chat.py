"""
Mock tests for chat functionality - Fast unit tests without external dependencies
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock

from main import app
from services.nlp_service import NLPService
from models.schemas import ParseError, ErrorDetail

pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.db_mock,  # Database operations are mocked
    pytest.mark.llm_mock,  # LLM/OpenAI API calls are mocked
]


class TestChatE2EMock:
    """Mock tests for chat functionality - Fast unit tests"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_nlp_service(self):
        """Mock NLP service for testing"""
        mock_service = MagicMock(spec=NLPService)
        return mock_service

    def test_chat_read_operation_success(self, client, mock_nlp_service):
        """Test successful read operation through chat endpoint"""
        # Mock NLP service response
        mock_nlp_service.process_query = AsyncMock(
            return_value={
                "operation": "read",
                "result": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "amount": 20.0,
                        "direction": "expense",
                        "entry_date": "2025-01-15",
                        "description": "coffee",
                        "source": "nlp",
                        "parse_confidence": 0.95,
                        "created_at": "2025-01-15T10:00:00Z",
                        "category": {
                            "id": "550e8400-e29b-41d4-a716-446655440001",
                            "name": "Food & Dining (Expense)",
                            "type": "expense",
                        },
                    }
                ],
            }
        )

        with patch("routes.chat.NLPService") as mock_nlp_class:
            mock_nlp_class.return_value = mock_nlp_service
            response = client.post(
                "/api/v1/chat/", json={"text": "show me my expenses"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["operation"] == "read"
            assert len(data["result"]) >= 1
            # Verify the entries are properly formatted
            for entry in data["result"]:
                assert "id" in entry
                assert "amount" in entry
                assert "direction" in entry
                assert "entry_date" in entry
                assert "description" in entry
                assert entry["direction"] == "expense"

    def test_chat_write_operation_success(self, client, mock_nlp_service):
        """Test successful write operation through chat endpoint"""
        # Mock NLP service response
        mock_nlp_service.process_query = AsyncMock(
            return_value={
                "operation": "write",
                "result": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "amount": 20.0,
                    "direction": "expense",
                    "entry_date": "2025-01-15",
                    "description": "coffee",
                    "source": "nlp",
                    "parse_confidence": 0.95,
                    "created_at": "2025-01-15T10:00:00Z",
                    "category": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "name": "Food & Dining (Expense)",
                        "type": "expense",
                    },
                },
            }
        )

        with patch("routes.chat.NLPService") as mock_nlp_class:
            mock_nlp_class.return_value = mock_nlp_service
            response = client.post(
                "/api/v1/chat/", json={"text": "spent $20 on coffee"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["operation"] == "write"
            assert float(data["result"]["amount"]) == 20.0

    def test_chat_parsing_error(self, client, mock_nlp_service):
        """Test chat endpoint handles parsing errors"""
        # Mock NLP service error response
        mock_nlp_service.process_query = AsyncMock(
            return_value=ParseError(
                code="missing_fields",
                message="Could not determine the amount. Please specify a number.",
                details=ErrorDetail(
                    missing_fields=["amount"],
                    suggestions=["Try: 'spent $20 on coffee'"],
                ),
            )
        )

        with patch("routes.chat.NLPService") as mock_nlp_class:
            mock_nlp_class.return_value = mock_nlp_service
            response = client.post(
                "/api/v1/chat/", json={"text": "spent money on food"}
            )

            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"]["code"] == "missing_fields"
            assert "amount" in data["detail"]["error"]["details"]["missing_fields"]

    def test_chat_invalid_input(self, client):
        """Test chat endpoint handles invalid input"""
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

    def test_chat_service_error(self, client, mock_nlp_service):
        """Test chat endpoint handles service errors"""
        # Mock NLP service exception
        mock_nlp_service.process_query = AsyncMock(
            side_effect=Exception("Service error")
        )

        with patch("routes.chat.NLPService") as mock_nlp_class:
            mock_nlp_class.return_value = mock_nlp_service
            response = client.post("/api/v1/chat/", json={"text": "some input"})

            assert response.status_code == 500
            data = response.json()
            assert "Internal server error" in data["detail"]

    def test_chat_multiple_scenarios(self, client, mock_nlp_service):
        """Test multiple chat scenarios"""
        test_cases = [
            {
                "input": "show me food expenses from last week",
                "expected_operation": "read",
                "mock_response": {
                    "operation": "read",
                    "result": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "amount": 15.50,
                            "direction": "expense",
                            "entry_date": "2025-01-10",
                            "description": "lunch",
                            "source": "nlp",
                            "parse_confidence": 0.95,
                            "created_at": "2025-01-10T12:00:00Z",
                        }
                    ],
                },
            },
            {
                "input": "earned $500 from freelance work",
                "expected_operation": "write",
                "mock_response": {
                    "operation": "write",
                    "result": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "amount": 500.0,
                        "direction": "income",
                        "entry_date": "2025-01-15",
                        "description": "freelance work",
                        "source": "nlp",
                        "parse_confidence": 0.95,
                        "created_at": "2025-01-15T14:00:00Z",
                    },
                },
            },
            {
                "input": "what did I spend on transport this month",
                "expected_operation": "read",
                "mock_response": {
                    "operation": "read",
                    "result": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440002",
                            "amount": 45.20,
                            "direction": "expense",
                            "entry_date": "2025-01-12",
                            "description": "bus pass",
                            "source": "nlp",
                            "parse_confidence": 0.95,
                            "created_at": "2025-01-12T08:00:00Z",
                        }
                    ],
                },
            },
        ]

        for case in test_cases:
            mock_nlp_service.process_query = AsyncMock(
                return_value=case["mock_response"]
            )

            with patch("routes.chat.NLPService") as mock_nlp_class:
                mock_nlp_class.return_value = mock_nlp_service
                response = client.post("/api/v1/chat/", json={"text": case["input"]})

                assert response.status_code == 200
                data = response.json()
                assert data["operation"] == case["expected_operation"]

    def test_chat_error_scenarios(self, client, mock_nlp_service):
        """Test various error scenarios"""
        error_cases = [
            {
                "input": "spent money on food",
                "mock_response": ParseError(
                    code="missing_fields",
                    message="Could not determine the amount. Please specify a number.",
                    details=ErrorDetail(
                        missing_fields=["amount"],
                        suggestions=["Try: 'spent $20 on food'"],
                    ),
                ),
                "expected_status": 400,
            },
            {
                "input": "spent $10 and $20 on lunch",
                "mock_response": ParseError(
                    code="ambiguous",
                    message="Multiple amounts detected. Please specify one amount.",
                    details=ErrorDetail(
                        suggestions=[
                            "Try: 'spent $30 on lunch' or 'spent $10 on lunch'"
                        ],
                    ),
                ),
                "expected_status": 400,
            },
            {
                "input": "ambiguous input",
                "mock_response": ParseError(
                    code="ambiguous",
                    message="Could not determine if this is income or expense.",
                    details=ErrorDetail(
                        suggestions=[
                            "Try: 'spent $20 on coffee' or 'earned $20 from work'"
                        ],
                    ),
                ),
                "expected_status": 400,
            },
        ]

        for case in error_cases:
            mock_nlp_service.process_query = AsyncMock(
                return_value=case["mock_response"]
            )

            with patch("routes.chat.NLPService") as mock_nlp_class:
                mock_nlp_class.return_value = mock_nlp_service
                response = client.post("/api/v1/chat/", json={"text": case["input"]})

                assert response.status_code == case["expected_status"]
                data = response.json()
                assert "detail" in data
                assert "error" in data["detail"]
                assert data["detail"]["error"]["code"] == case["mock_response"].code

    def test_chat_performance(self, client, mock_nlp_service):
        """Test chat endpoint responds once per request"""
        mock_nlp_service.process_query = AsyncMock(
            return_value={"operation": "read", "result": []}
        )

        with patch("routes.chat.NLPService") as mock_nlp_class:
            mock_nlp_class.return_value = mock_nlp_service
            response = client.post("/api/v1/chat/", json={"text": "show me expenses"})

        assert response.status_code == 200
        assert mock_nlp_service.process_query.await_count == 1

    @pytest.mark.asyncio
    async def test_chat_concurrent_requests(self, mock_nlp_service):
        """Test chat endpoint handles concurrent requests"""
        import asyncio

        mock_nlp_service.process_query = AsyncMock(
            return_value={"operation": "read", "result": []}
        )

        with patch("routes.chat.NLPService") as mock_nlp_class:
            mock_nlp_class.return_value = mock_nlp_service
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as async_client:
                responses = await asyncio.gather(
                    *[
                        async_client.post(
                            "/api/v1/chat/", json={"text": "show me expenses"}
                        )
                        for _ in range(5)
                    ]
                )

        assert all(response.status_code == 200 for response in responses)
        assert len(responses) == 5
