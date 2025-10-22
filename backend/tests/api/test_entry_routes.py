"""
Tests for entry API routes with mocked authentication
"""

import pytest
import pytest_asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import Depends

from main import app
from database.connection import db_connection
from middleware.auth import get_current_user_id

pytestmark = [
    pytest.mark.integration,
    pytest.mark.db_real,
    pytest.mark.auth_mock,  # Use mocked auth for speed
]


@pytest_asyncio.fixture
async def client_with_mock_auth(mock_auth_dependency):
    """Create test client with mocked authentication"""
    mock_get_user_id, mock_user_id = mock_auth_dependency

    # Override the auth dependency
    app.dependency_overrides[get_current_user_id] = mock_get_user_id

    client = TestClient(app)
    yield client, mock_user_id

    # Clean up override
    app.dependency_overrides.clear()


class TestEntryRoutes:
    """Tests for entry-related routes with mocked auth"""

    def test_create_entry(self, client_with_mock_auth, test_data_setup):
        """Test entry creation via API"""
        client, user_id = client_with_mock_auth

        entry_data = {
            "amount": 15.75,
            "direction": "expense",
            "entry_date": "2025-01-15",
            "description": "API test expense",
            "category_id": test_data_setup["category"]["id"],
        }

        response = client.post("/api/v1/entries/", json=entry_data)

        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == "15.75"
        assert data["direction"] == "expense"
        assert data["description"] == "API test expense"
        assert "id" in data

        # Clean up the created entry
        db_connection.client.table("entry").delete().eq("id", data["id"]).execute()

    def test_get_entries(self, client_with_mock_auth, test_data_setup):
        """Test entry retrieval via API"""
        client, user_id = client_with_mock_auth

        # Use entries from test_data_setup
        response = client.get("/api/v1/entries/")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "page" in data
        assert isinstance(data["items"], list)

    def test_get_entries_with_filters(self, client_with_mock_auth, test_data_setup):
        """Test entry retrieval with query filters"""
        client, user_id = client_with_mock_auth

        # Test with direction filter
        response = client.get("/api/v1/entries/", params={"direction": "expense"})
        assert response.status_code == 200
        data = response.json()
        for entry in data["items"]:
            assert entry["direction"] == "expense"

        # Test with limit
        response = client.get("/api/v1/entries/", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 5

    def test_update_entry_success(self, client_with_mock_auth, test_data_setup):
        """Test successful entry update via API"""
        client, user_id = client_with_mock_auth

        # Create a test entry
        entry_data = {
            "amount_cents": 2000,
            "direction": "expense",
            "entry_date": "2025-01-15",
            "category_id": test_data_setup["category"]["id"],
            "description": "Original test expense",
            "user_id": str(user_id),
        }

        result = db_connection.client.table("entry").insert(entry_data).execute()
        created_entry = result.data[0] if result.data else None

        try:
            # Update the entry
            update_data = {
                "amount": "25.50",
                "description": "Updated test expense",
            }

            response = client.patch(
                f"/api/v1/entries/{created_entry['id']}", json=update_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["amount"] == "25.5"
            assert data["description"] == "Updated test expense"

        finally:
            # Clean up
            if created_entry:
                db_connection.client.table("entry").delete().eq(
                    "id", created_entry["id"]
                ).execute()

    def test_update_entry_not_found(self, client_with_mock_auth):
        """Test entry update when entry doesn't exist"""
        client, user_id = client_with_mock_auth

        fake_id = uuid4()
        update_data = {"amount": "10.00"}

        response = client.patch(f"/api/v1/entries/{fake_id}", json=update_data)

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Entry not found"

    def test_update_entry_invalid_data(self, client_with_mock_auth, test_data_setup):
        """Test entry update with invalid data"""
        client, user_id = client_with_mock_auth

        # Create a test entry
        entry_data = {
            "amount_cents": 2000,
            "direction": "expense",
            "entry_date": "2025-01-15",
            "category_id": test_data_setup["category"]["id"],
            "description": "Test expense",
            "user_id": str(user_id),
        }

        result = db_connection.client.table("entry").insert(entry_data).execute()
        created_entry = result.data[0] if result.data else None

        try:
            # Test with invalid amount (negative)
            update_data = {"amount": "-10.00"}

            response = client.patch(
                f"/api/v1/entries/{created_entry['id']}", json=update_data
            )

            assert response.status_code == 422  # Pydantic validation error

        finally:
            # Clean up
            if created_entry:
                db_connection.client.table("entry").delete().eq(
                    "id", created_entry["id"]
                ).execute()

    def test_delete_entry_success(self, client_with_mock_auth, test_data_setup):
        """Test successful entry deletion via API"""
        client, user_id = client_with_mock_auth

        # Create a test entry
        entry_data = {
            "amount_cents": 1500,
            "direction": "expense",
            "entry_date": "2025-01-15",
            "category_id": test_data_setup["category"]["id"],
            "description": "Entry to be deleted",
            "user_id": str(user_id),
        }

        result = db_connection.client.table("entry").insert(entry_data).execute()
        created_entry = result.data[0] if result.data else None

        try:
            # Delete the entry
            response = client.delete(f"/api/v1/entries/{created_entry['id']}")

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Entry deleted successfully"

        finally:
            # Clean up (in case deletion failed)
            if created_entry:
                try:
                    db_connection.client.table("entry").delete().eq(
                        "id", created_entry["id"]
                    ).execute()
                except:
                    pass  # Already deleted

    def test_delete_entry_not_found(self, client_with_mock_auth):
        """Test entry deletion when entry doesn't exist"""
        client, user_id = client_with_mock_auth

        fake_id = uuid4()

        response = client.delete(f"/api/v1/entries/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Entry not found"

    def test_create_entry_validation(self, client_with_mock_auth, test_data_setup):
        """Test entry creation with invalid data"""
        client, user_id = client_with_mock_auth

        # Test with negative amount
        entry_data = {
            "amount": -10.00,
            "direction": "expense",
            "entry_date": "2025-01-15",
            "category_id": test_data_setup["category"]["id"],
        }

        response = client.post("/api/v1/entries/", json=entry_data)
        assert response.status_code == 422

        # Test with zero amount
        entry_data["amount"] = 0.00
        response = client.post("/api/v1/entries/", json=entry_data)
        assert response.status_code == 422

    def test_get_entries_pagination(self, client_with_mock_auth, test_data_setup):
        """Test entry pagination"""
        client, user_id = client_with_mock_auth

        # Test first page
        response = client.get("/api/v1/entries/", params={"limit": 2, "offset": 0})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["page"]["limit"] == 2
        assert data["page"]["offset"] == 0

        # Test second page
        response = client.get("/api/v1/entries/", params={"limit": 2, "offset": 2})
        assert response.status_code == 200
        data = response.json()
        assert data["page"]["offset"] == 2
