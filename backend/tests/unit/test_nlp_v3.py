"""
Unit tests for NLPServiceV3 with mocked LLM and DB.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.nlp_service_v3 import NLPServiceV3


pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.db_mock,
    pytest.mark.llm_mock,
]


class _DummyMsg:
    def __init__(self, content: str):
        self.content = content


class _DummyChoice:
    def __init__(self, content: str):
        self.message = _DummyMsg(content)


class _DummyResp:
    def __init__(self, content: str):
        self.choices = [_DummyChoice(content)]


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

    exec_result = MagicMock()
    exec_result.data = rows
    table_mock.execute.return_value = exec_result

    client_mock = MagicMock()
    client_mock.table.return_value = table_mock
    return client_mock


@pytest.mark.asyncio
async def test_v3_reply_without_fetch(monkeypatch):
    with patch("database.connection.db_connection") as mock_db_conn:
        service = NLPServiceV3("test-key")

        # Mock the database client
        mock_db_conn.client = _make_db_mock([])

        # Mock LLM: first call replies immediately
        reply_plan = {
            "action": "reply",
            "operation": "read",
            "final": True,
            "reply": "Here is your answer.",
        }
        monkeypatch.setattr(
            service.langfuse,
            "track_unified_llm_call",
            AsyncMock(return_value=(_DummyResp(json.dumps(reply_plan)), "g1")),
        )

        result = await service.process_query("hello")
        assert result["operation"] == "read"
        assert result["message"] == "Here is your answer."


@pytest.mark.asyncio
async def test_v3_fetch_then_reply(monkeypatch):
    with patch("database.connection.db_connection") as mock_db_conn:
        service = NLPServiceV3("test-key")

        # First call: ask to fetch
        fetch_plan = {
            "action": "fetch",
            "operation": "read",
            "need_rows": True,
            "query_spec": {
                "select": [
                    "id",
                    "entry_date",
                    "amount_cents",
                    "direction",
                    "category_id",
                    "description",
                ],
                "from": "entry",
                "where": {"direction": "expense"},
                "order_by": [{"amount_cents": "desc"}],
                "limit": 10,
                "offset": 0,
            },
            "response_kind": "entries",
            "final": False,
        }
        # Second call: reply
        reply_plan = {
            "action": "reply",
            "operation": "read",
            "final": True,
            "reply": "Top expense is $100.",
        }

        monkeypatch.setattr(
            service.langfuse,
            "track_unified_llm_call",
            AsyncMock(
                side_effect=[
                    (_DummyResp(json.dumps(fetch_plan)), "g1"),
                    (_DummyResp(json.dumps(reply_plan)), "g2"),
                ]
            ),
        )

        # Mock DB to return two rows
        rows = [
            {
                "id": "e1",
                "entry_date": "2025-10-01",
                "amount_cents": 10000,
                "direction": "expense",
                "category_id": "c1",
                "description": "Test",
            },
            {
                "id": "e2",
                "entry_date": "2025-10-02",
                "amount_cents": 5000,
                "direction": "expense",
                "category_id": "c1",
                "description": "Test2",
            },
        ]
        mock_db_conn.client = _make_db_mock(rows)

        result = await service.process_query("highest expense last week")
        assert result["operation"] == "read"
        assert "Top expense" in result["message"]


@pytest.mark.asyncio
async def test_v3_invalid_limit_rejected(monkeypatch):
    with patch("database.connection.db_connection") as mock_db_conn:
        service = NLPServiceV3("test-key")

        # First call: invalid spec with limit > 10
        fetch_plan = {
            "action": "fetch",
            "operation": "read",
            "need_rows": True,
            "query_spec": {
                "select": ["id", "entry_date"],
                "from": "entry",
                "where": {},
                "limit": 50,
                "offset": 0,
            },
            "response_kind": "entries",
            "final": False,
        }

        monkeypatch.setattr(
            service.langfuse,
            "track_unified_llm_call",
            AsyncMock(return_value=(_DummyResp(json.dumps(fetch_plan)), "g1")),
        )

        # DB mock (should not be reached due to validation error)
        mock_db_conn.client = _make_db_mock([])

        result = await service.process_query("show many rows")
        assert result["operation"] in ("unsure", "read")
        assert "safe query" in result["message"]

@pytest.mark.asyncio
async def test_v3_category_filter_preserves_uuid(monkeypatch):
    uuid_one = "123e4567-e89b-12d3-a456-426614174000"
    uuid_two = "223e4567-e89b-12d3-a456-426614174000"

    table_mock = MagicMock()
    table_mock.select.return_value = table_mock
    table_mock.eq.return_value = table_mock
    table_mock.gte.return_value = table_mock
    table_mock.lte.return_value = table_mock
    table_mock.ilike.return_value = table_mock
    table_mock.in_.return_value = table_mock
    table_mock.order.return_value = table_mock
    table_mock.range.return_value = table_mock

    exec_result = MagicMock()
    exec_result.data = []
    table_mock.execute.return_value = exec_result

    client_mock = MagicMock()
    client_mock.table.return_value = table_mock

    with patch("database.connection.db_connection") as mock_db_conn:
        mock_db_conn.client = client_mock
        service = NLPServiceV3("test-key")

    resolve_mock = MagicMock(side_effect=AssertionError("resolver should not be called for UUIDs"))
    monkeypatch.setattr(service, "_resolve_category_name_to_id", resolve_mock)

    spec_eq = service.QuerySpec(
        select=["id"],
        **{
            "from": "entry",
            "where": {"category_id": {"=": uuid_one}},
            "limit": 1,
            "offset": 0,
        },
    )

    await service._run_query_spec(spec_eq)
    table_mock.eq.assert_any_call("category_id", uuid_one)

    spec_in = service.QuerySpec(
        select=["id"],
        **{
            "from": "entry",
            "where": {"category_id": {"in": [uuid_one, uuid_two]}},
            "limit": 1,
            "offset": 0,
        },
    )

    await service._run_query_spec(spec_in)
    table_mock.in_.assert_called_once()
    args = table_mock.in_.call_args[0]
    assert args[0] == "category_id"
    assert args[1] == [uuid_one, uuid_two]

    assert resolve_mock.call_count == 0
