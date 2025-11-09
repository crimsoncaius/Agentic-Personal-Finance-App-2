"""
Entry service for database operations
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional, Union
from uuid import UUID

from database.connection import db_connection
from models.schemas import (
    CategoryResponse,
    Entry,
    EntryDirection,
    EntryQueryParams,
    EntryResponse,
    EntryUpdate,
    cents_to_dollars,
    dollars_to_cents,
)


class EntryService:
    """Service for entry-related database operations"""

    @staticmethod
    async def create_entry(
        amount: Decimal,
        direction: Union[str, "EntryDirection"],
        entry_date: date,
        user_id: UUID,
        category_id: Optional[UUID] = None,
        description: Optional[str] = None,
        jwt_token: Optional[str] = None,
    ) -> Entry:
        """Create a new entry"""
        # Validate amount
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Validate direction
        direction_value = (
            direction.value if isinstance(direction, EntryDirection) else direction
        )
        if direction_value not in ["expense", "income"]:
            raise ValueError("Direction must be 'expense' or 'income'")

        entry_data = {
            "amount_cents": dollars_to_cents(amount),
            "direction": direction_value,
            "entry_date": entry_date.isoformat(),
            "category_id": str(category_id) if category_id else None,
            "description": description,
            "user_id": str(user_id),
        }

        # Use authenticated client if JWT token is provided, otherwise use regular client
        if jwt_token:
            client = db_connection.get_authenticated_client(jwt_token)
        else:
            client = db_connection.client

        result = client.table("entry").insert(entry_data).execute()

        if not result.data:
            raise ValueError("Failed to create entry")

        # Get the created entry with all fields including timestamps
        created_entry = result.data[0]

        # Convert amount_cents to amount for Entry model
        created_entry["amount"] = cents_to_dollars(created_entry["amount_cents"])

        return Entry(**created_entry)

    @staticmethod
    async def get_entries(
        params: EntryQueryParams, user_id: UUID, jwt_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get entries with filtering and pagination"""
        # For now, use service client to bypass RLS for testing
        # TODO: Fix authenticated client implementation
        client = db_connection.service_client

        query = client.table("entry").select("*, category:category_id(id, name, type)")

        # Manual filter by user_id since we're using service client (bypasses RLS)
        query = query.eq("user_id", str(user_id))

        # Apply filters
        if params.direction:
            query = query.eq(
                "direction", params.direction.value
            )  # Use .value to get the actual enum value

        if params.category_id:
            query = query.eq("category_id", str(params.category_id))

        if params.date_from:
            query = query.gte("entry_date", params.date_from.isoformat())

        if params.date_to:
            query = query.lte("entry_date", params.date_to.isoformat())

        if params.amount_min:
            query = query.gte("amount_cents", dollars_to_cents(params.amount_min))

        if params.amount_max:
            query = query.lte("amount_cents", dollars_to_cents(params.amount_max))

        if params.q:
            query = query.ilike("description", f"%{params.q}%")

        # Apply sorting
        sort_field, sort_order = params.sort.split(".")
        query = query.order(sort_field, desc=(sort_order == "desc"))

        # Get total count for pagination
        count_result = query.execute()
        total = len(count_result.data) if count_result.data else 0

        # Apply pagination
        query = query.range(params.offset, params.offset + params.limit - 1)

        result = query.execute()

        if not result.data:
            return {
                "items": [],
                "page": {"limit": params.limit, "offset": params.offset, "total": 0},
            }

        # Convert to response format
        entries = []
        for item in result.data:
            entry_dict = dict(item)
            entry_dict["amount"] = cents_to_dollars(item["amount_cents"])

            if item.get("category"):
                entry_dict["category"] = CategoryResponse(
                    id=item["category"]["id"],
                    name=item["category"]["name"],
                    type=item["category"]["type"],
                )
            else:
                entry_dict["category"] = None

            entries.append(EntryResponse(**entry_dict))

        return {
            "items": entries,
            "page": {"limit": params.limit, "offset": params.offset, "total": total},
        }

    @staticmethod
    async def get_entry_by_id(
        entry_id: UUID, user_id: UUID, jwt_token: Optional[str] = None
    ) -> Optional[Entry]:
        """Get a single entry by ID"""
        # Use authenticated client if JWT token is provided, otherwise use regular client
        if jwt_token:
            client = db_connection.get_authenticated_client(jwt_token)
        else:
            client = db_connection.client

        result = client.table("entry").select("*").eq("id", str(entry_id)).execute()

        if not result.data:
            return None

        # Add amount field for Entry model (convert from amount_cents)
        entry_data = result.data[0].copy()
        entry_data["amount"] = cents_to_dollars(entry_data["amount_cents"])

        return Entry(**entry_data)

    @staticmethod
    async def update_entry(
        entry_id: UUID,
        update_data: EntryUpdate,
        user_id: UUID,
        jwt_token: Optional[str] = None,
    ) -> Optional[Entry]:
        """Update an existing entry"""
        # Check if entry exists and belongs to user
        existing_entry = await EntryService.get_entry_by_id(
            entry_id, user_id, jwt_token
        )
        if not existing_entry:
            return None

        # Prepare update data (only include fields that are provided)
        update_dict = {}

        if update_data.amount is not None:
            if update_data.amount <= 0:
                raise ValueError("Amount must be positive")
            update_dict["amount_cents"] = dollars_to_cents(update_data.amount)

        if update_data.direction is not None:
            direction_value = (
                update_data.direction.value
                if isinstance(update_data.direction, EntryDirection)
                else update_data.direction
            )
            if direction_value not in ["expense", "income"]:
                raise ValueError("Direction must be 'expense' or 'income'")
            update_dict["direction"] = direction_value

        if update_data.entry_date is not None:
            update_dict["entry_date"] = update_data.entry_date.isoformat()

        if update_data.category_id is not None:
            update_dict["category_id"] = str(update_data.category_id)

        if update_data.description is not None:
            update_dict["description"] = update_data.description

        # If no fields to update, return existing entry
        if not update_dict:
            return existing_entry

        # Update the entry (RLS ensures it belongs to the user)
        # Use authenticated client if JWT token is provided, otherwise use regular client
        if jwt_token:
            client = db_connection.get_authenticated_client(jwt_token)
        else:
            client = db_connection.client

        result = (
            client.table("entry").update(update_dict).eq("id", str(entry_id)).execute()
        )

        if not result.data:
            raise ValueError("Failed to update entry")

        # Get the updated entry
        updated_entry = result.data[0]
        updated_entry["amount"] = cents_to_dollars(updated_entry["amount_cents"])

        return Entry(**updated_entry)

    @staticmethod
    async def delete_entry(
        entry_id: UUID, user_id: UUID, jwt_token: Optional[str] = None
    ) -> bool:
        """Delete an entry by ID"""
        # Check if entry exists and belongs to user
        existing_entry = await EntryService.get_entry_by_id(
            entry_id, user_id, jwt_token
        )
        if not existing_entry:
            return False

        # Delete the entry (RLS ensures it belongs to the user)
        # Use authenticated client if JWT token is provided, otherwise use regular client
        if jwt_token:
            client = db_connection.get_authenticated_client(jwt_token)
        else:
            client = db_connection.client

        result = client.table("entry").delete().eq("id", str(entry_id)).execute()

        # Check if deletion was successful
        return result.data is not None
