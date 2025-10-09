"""
Finance tools for LangGraph agent
Provides tools for fetching, creating, and updating financial entries
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from langchain_core.tools import tool

# Try both import paths to handle running from different directories
try:
    from database.connection import db_connection
    from models.query_spec import QuerySpec
except ImportError:
    from backend.database.connection import db_connection
    from backend.models.query_spec import QuerySpec


@tool
def fetch_entries(
    query_spec_json: str,
    user_id: str,
) -> str:
    """
    Fetch financial entries from the database using a QuerySpec.

    Use this tool to retrieve existing income and expense entries for the user.
    Always filter by user_id for security.

    Args:
        query_spec_json: JSON string containing QuerySpec fields:
            - select: List of columns to select (e.g., ["id", "amount_cents", "description", "entry_date"])
            - from: Table name (must be "entry")
            - where: Optional filters (e.g., {"direction": "expense", "entry_date": {">=": "2024-01-01"}})
            - order_by: Optional sort order (e.g., [{"entry_date": "desc"}])
            - limit: Max rows to return (1-10, defaults to 10)
            - offset: Number of rows to skip (defaults to 0)
        user_id: User ID for security filtering (automatically injected)

    Returns:
        JSON string containing list of matching entries

    Examples:
        - To get recent expenses: '{"select": ["*"], "from": "entry", "where": {"direction": "expense"}, "order_by": [{"entry_date": "desc"}], "limit": 10}'
        - To get entries in date range: '{"select": ["*"], "from": "entry", "where": {"entry_date": {">=": "2024-01-01", "<=": "2024-12-31"}}, "limit": 10}'
    """
    try:
        # Parse the QuerySpec JSON
        spec_dict = json.loads(query_spec_json)

        # Add user_id filter to where clause for security
        if "where" not in spec_dict:
            spec_dict["where"] = {}
        spec_dict["where"]["user_id"] = user_id

        # Validate against QuerySpec model (enforces 10-row limit)
        spec = QuerySpec(**spec_dict)

        # Build Supabase query
        query = db_connection.client.table(spec.from_)

        # Apply select
        if spec.select:
            # Handle wildcard select
            if "*" in spec.select:
                query = query.select("*, category:category_id(id, name, type)")
            else:
                query = query.select(",".join(spec.select))

        # Apply where conditions
        if spec.where:
            for column, condition in spec.where.items():
                if isinstance(condition, dict):
                    # Handle range conditions
                    for op, value in condition.items():
                        if op in [">=", "gte"]:
                            query = query.gte(column, value)
                        elif op in ["<=", "lte"]:
                            query = query.lte(column, value)
                        elif op in [">", "gt"]:
                            query = query.gt(column, value)
                        elif op in ["<", "lt"]:
                            query = query.lt(column, value)
                        elif op in ["!=", "neq"]:
                            query = query.neq(column, value)
                        elif op in ["=", "eq"]:
                            query = query.eq(column, value)
                else:
                    # Handle simple equality
                    query = query.eq(column, condition)

        # Apply order_by
        if spec.order_by:
            for order_spec in spec.order_by:
                for column, direction in order_spec.items():
                    query = query.order(column, desc=(direction.lower() == "desc"))

        # Apply limit (already validated to be <= 10)
        query = query.limit(spec.limit)

        # Apply offset
        if spec.offset:
            query = query.range(spec.offset, spec.offset + spec.limit - 1)

        # Execute query
        result = query.execute()

        # Convert result to JSON-serializable format
        entries = []
        for row in result.data or []:
            entry = dict(row)
            # Convert Decimal to float for JSON serialization
            if "amount_cents" in entry:
                entry["amount"] = float(entry["amount_cents"]) / 100
            entries.append(entry)

        return json.dumps({"success": True, "entries": entries, "count": len(entries)})

    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "message": f"Failed to fetch entries: {str(e)}",
            }
        )


@tool
def create_entry(
    amount: float,
    direction: str,
    description: str,
    category: str,
    entry_date: str,
    user_id: str,
) -> str:
    """
    Create a new financial entry (income or expense).

    Use this tool to add new transactions to the user's financial records.

    Args:
        amount: Amount in dollars (e.g., 50.00 for $50)
        direction: Either "income" or "expense"
        description: Description of the transaction
        category: Category name (e.g., "Groceries", "Salary")
        entry_date: Date in YYYY-MM-DD format (e.g., "2024-01-15")
        user_id: User ID for security (automatically injected)

    Returns:
        JSON string with created entry details or error message

    Examples:
        - Create expense: amount=50.00, direction="expense", description="Groceries", category="Food & Dining", entry_date="2024-01-15"
        - Create income: amount=3000.00, direction="income", description="Salary", category="Salary", entry_date="2024-01-01"
    """
    try:
        # Validate direction
        if direction not in ["income", "expense"]:
            return json.dumps(
                {
                    "success": False,
                    "error": "Invalid direction. Must be 'income' or 'expense'",
                }
            )

        # Validate amount
        if amount <= 0:
            return json.dumps({"success": False, "error": "Amount must be positive"})

        # Parse and validate date
        try:
            parsed_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
        except ValueError:
            return json.dumps(
                {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}
            )

        # Find category by name
        category_result = (
            db_connection.client.table("category").select("id, name, type").execute()
        )
        category_id = None

        for cat in category_result.data or []:
            if cat["name"].lower() == category.lower():
                category_id = cat["id"]
                break

        # If category not found, try to find default category by type
        if not category_id:
            category_type = "expense" if direction == "expense" else "income"
            for cat in category_result.data or []:
                if cat["type"] == category_type:
                    category_id = cat["id"]
                    break

        # Create entry
        entry_data = {
            "amount_cents": int(amount * 100),
            "direction": direction,
            "entry_date": parsed_date.isoformat(),
            "category_id": str(category_id) if category_id else None,
            "description": description,
            "source": "nlp",
            "parse_confidence": 0.8,
            "user_id": str(user_id),
        }

        result = db_connection.client.table("entry").insert(entry_data).execute()

        if not result.data:
            return json.dumps(
                {"success": False, "error": "Failed to create entry in database"}
            )

        created_entry = result.data[0]
        created_entry["amount"] = float(created_entry["amount_cents"]) / 100

        return json.dumps(
            {
                "success": True,
                "entry": created_entry,
                "message": f"Created {direction} of ${amount:.2f} for {description}",
            }
        )

    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "message": f"Failed to create entry: {str(e)}",
            }
        )


@tool
def update_entry(
    entry_id: str,
    user_id: str,
    amount: Optional[float] = None,
    direction: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    entry_date: Optional[str] = None,
) -> str:
    """
    Update an existing financial entry.

    Use this tool to modify existing transactions. Only updates the fields provided.
    Always verifies that the entry belongs to the user before updating.

    Args:
        entry_id: ID of the entry to update
        user_id: User ID for security verification (automatically injected)
        amount: New amount in dollars (optional)
        direction: New direction "income" or "expense" (optional)
        description: New description (optional)
        category: New category name (optional)
        entry_date: New date in YYYY-MM-DD format (optional)

    Returns:
        JSON string with updated entry details or error message

    Examples:
        - Update amount: entry_id="123", amount=75.00
        - Update description: entry_id="123", description="Updated description"
        - Update multiple fields: entry_id="123", amount=75.00, description="New desc", entry_date="2024-01-20"
    """
    try:
        # First, verify the entry exists and belongs to the user
        existing = (
            db_connection.client.table("entry")
            .select("*")
            .eq("id", entry_id)
            .eq("user_id", str(user_id))
            .execute()
        )

        if not existing.data:
            return json.dumps(
                {
                    "success": False,
                    "error": "Entry not found or you don't have permission to update it",
                }
            )

        # Build update data with only provided fields
        update_data = {}

        if amount is not None:
            if amount <= 0:
                return json.dumps(
                    {"success": False, "error": "Amount must be positive"}
                )
            update_data["amount_cents"] = int(amount * 100)

        if direction is not None:
            if direction not in ["income", "expense"]:
                return json.dumps(
                    {
                        "success": False,
                        "error": "Invalid direction. Must be 'income' or 'expense'",
                    }
                )
            update_data["direction"] = direction

        if description is not None:
            update_data["description"] = description

        if entry_date is not None:
            try:
                parsed_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
                update_data["entry_date"] = parsed_date.isoformat()
            except ValueError:
                return json.dumps(
                    {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}
                )

        if category is not None:
            # Find category by name
            category_result = (
                db_connection.client.table("category").select("id, name").execute()
            )
            category_id = None

            for cat in category_result.data or []:
                if cat["name"].lower() == category.lower():
                    category_id = cat["id"]
                    break

            if category_id:
                update_data["category_id"] = str(category_id)

        if not update_data:
            return json.dumps(
                {"success": False, "error": "No fields provided to update"}
            )

        # Perform update
        result = (
            db_connection.client.table("entry")
            .update(update_data)
            .eq("id", entry_id)
            .eq("user_id", str(user_id))
            .execute()
        )

        if not result.data:
            return json.dumps({"success": False, "error": "Failed to update entry"})

        updated_entry = result.data[0]
        updated_entry["amount"] = float(updated_entry["amount_cents"]) / 100

        return json.dumps(
            {
                "success": True,
                "entry": updated_entry,
                "message": f"Updated entry {entry_id}",
            }
        )

    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "message": f"Failed to update entry: {str(e)}",
            }
        )


# Export tools for easy import
__all__ = ["fetch_entries", "create_entry", "update_entry"]
