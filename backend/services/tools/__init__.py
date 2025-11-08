"""
Finance tools for LangGraph agent
Provides tools for fetching, creating, and updating financial entries
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from langchain_core.tools import tool

# Import paths for running from backend directory
from database.connection import db_connection
from models.query_spec import QuerySpec


@tool
def fetch_entries(
    direction: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    description_contains: Optional[str] = None,
    min_amount_cents: Optional[int] = None,
    max_amount_cents: Optional[int] = None,
    limit: int = 10,
    user_id: str = None,
) -> str:
    """
    Fetch financial entries from the database with simple, structured filters.

    Use this tool to retrieve existing income and expense entries for the user.
    Results automatically include category information (name, type) via join.

    Args:
        direction: Filter by "income" or "expense" (optional)
        category: Filter by category name (e.g., "Food & Dining", "Salary") (optional)
        date_from: Filter entries from this date onwards, YYYY-MM-DD format (optional)
        date_to: Filter entries up to this date, YYYY-MM-DD format (optional)
        description_contains: Filter entries with description containing this text (case-insensitive) (optional)
        min_amount_cents: Filter entries with amount >= this value in cents (e.g., 5000 for $50) (optional)
        max_amount_cents: Filter entries with amount <= this value in cents (optional)
        limit: Maximum number of entries to return (1-10, defaults to 10)
        user_id: User ID for security filtering (automatically injected)

    Returns:
        JSON string with entries array, each entry includes:
        - All fields from entry table (id, amount_cents, direction, entry_date, description, etc.)
        - category object with {id, name, type} automatically included
        - amount field (calculated from amount_cents / 100) for display

    Examples:
        - Recent expenses: direction="expense", limit=10
        - Groceries: direction="expense", category="Food & Dining"
        - Date range: date_from="2024-01-01", date_to="2024-01-31"
        - Text search: description_contains="coffee"
        - Amount filter: min_amount_cents=5000 (for entries >= $50)
        - Combined: direction="expense", category="Food & Dining", date_from="2024-01-01", description_contains="lunch"
    """
    try:
        # Build QuerySpec-style dict from simple parameters
        spec_dict = {
            "select": ["*"],  # Always select all fields
            "from": "entry",
            "where": {},
            "order_by": [{"entry_date": "desc"}, {"created_at": "desc"}],
            "limit": min(max(1, limit), 10),  # Enforce 1-10 range
            "offset": 0,
        }

        # Add filters based on provided parameters
        if direction:
            spec_dict["where"]["direction"] = direction

        if date_from:
            if "entry_date" not in spec_dict["where"]:
                spec_dict["where"]["entry_date"] = {}
            spec_dict["where"]["entry_date"][">="] = date_from

        if date_to:
            if "entry_date" not in spec_dict["where"]:
                spec_dict["where"]["entry_date"] = {}
            spec_dict["where"]["entry_date"]["<="] = date_to

        if description_contains:
            spec_dict["where"]["description"] = {"contains": description_contains}

        if min_amount_cents is not None:
            if "amount_cents" not in spec_dict["where"]:
                spec_dict["where"]["amount_cents"] = {}
            spec_dict["where"]["amount_cents"][">="] = min_amount_cents

        if max_amount_cents is not None:
            if "amount_cents" not in spec_dict["where"]:
                spec_dict["where"]["amount_cents"] = {}
            spec_dict["where"]["amount_cents"]["<="] = max_amount_cents

        # Resolve category name to category_id if provided
        if category:
            # Fetch all categories to find matching one
            category_result = (
                db_connection.client.table("category").select("id, name").execute()
            )
            category_id = None

            # Try exact match first, then partial match
            for cat in category_result.data or []:
                if cat["name"].lower() == category.lower():
                    category_id = cat["id"]
                    break

            # If no exact match, try partial/contains match
            if not category_id:
                for cat in category_result.data or []:
                    if category.lower() in cat["name"].lower():
                        category_id = cat["id"]
                        break

            if category_id:
                spec_dict["where"]["category_id"] = category_id
            else:
                # If category not found, use a non-existent ID to return no results
                # This prevents errors and provides clear "no results" behavior
                spec_dict["where"][
                    "category_id"
                ] = "00000000-0000-0000-0000-000000000000"

        # Add manual user_id filter since we're using service client (bypasses RLS)
        spec_dict["where"]["user_id"] = user_id

        # Validate against QuerySpec model (enforces 10-row limit)
        spec = QuerySpec(**spec_dict)

        # Build Supabase query using service client to bypass RLS
        query = db_connection.service_client.table(spec.from_)

        # Apply select - ALWAYS include category join for better user experience
        if spec.select:
            # Handle wildcard select
            if "*" in spec.select:
                query = query.select("*, category:category_id(id, name, type)")
            else:
                # Even when specific columns are requested, add category join
                # This ensures category data is always available in responses
                columns = ",".join(spec.select)
                query = query.select(f"{columns}, category:category_id(id, name, type)")

        # Apply where conditions
        if spec.where:
            for column, condition in spec.where.items():
                if isinstance(condition, dict):
                    # Handle range and comparison conditions
                    for op, value in condition.items():
                        # Comparison operators
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
                        # Text search operators
                        elif op in ["like"]:
                            query = query.like(column, value)
                        elif op in ["ilike", "contains"]:
                            # Case-insensitive like - wrap value with % if not already present
                            search_value = value if "%" in value else f"%{value}%"
                            query = query.ilike(column, search_value)
                        # Array operators
                        elif op in ["in"]:
                            query = query.in_(column, value)
                        elif op in ["not_in"]:
                            # Supabase doesn't have not_in, use filter with not
                            query = query.not_.in_(column, value)
                        # NULL checks
                        elif op in ["is_null"]:
                            if value:
                                query = query.is_(column, "null")
                            else:
                                query = query.not_.is_(column, "null")
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

        # Find category by name using service client
        category_result = (
            db_connection.service_client.table("category")
            .select("id, name, type")
            .execute()
        )
        category_id = None

        # Try exact match first
        for cat in category_result.data or []:
            if cat["name"].lower() == category.lower():
                category_id = cat["id"]
                break

        # If no exact match, try partial/contains match
        if not category_id:
            for cat in category_result.data or []:
                if category.lower() in cat["name"].lower():
                    category_id = cat["id"]
                    break

        # If category still not found, try to find default category by type
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
            "user_id": str(user_id),
        }

        result = (
            db_connection.service_client.table("entry").insert(entry_data).execute()
        )

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
            db_connection.service_client.table("entry")
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
            # Find category by name using service client
            category_result = (
                db_connection.service_client.table("category")
                .select("id, name")
                .execute()
            )
            category_id = None

            # Try exact match first
            for cat in category_result.data or []:
                if cat["name"].lower() == category.lower():
                    category_id = cat["id"]
                    break

            # If no exact match, try partial/contains match
            if not category_id:
                for cat in category_result.data or []:
                    if category.lower() in cat["name"].lower():
                        category_id = cat["id"]
                        break

            if category_id:
                update_data["category_id"] = str(category_id)

        if not update_data:
            return json.dumps(
                {"success": False, "error": "No fields provided to update"}
            )

        # Perform update using service client
        result = (
            db_connection.service_client.table("entry")
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


@tool
def aggregate_entries(
    aggregate_type: str,
    user_id: str,
    direction: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> str:
    """
    Perform aggregate calculations on financial entries (sum, count, max, min).

    Use this for efficient queries like "total spending", "highest expense",
    "number of transactions" without fetching all entries.

    Args:
        aggregate_type: Type of aggregation - "sum", "count", "max", or "min"
        user_id: User ID for security (automatically injected)
        direction: Optional filter - "income" or "expense"
        category: Optional category name filter
        date_from: Optional start date in YYYY-MM-DD format
        date_to: Optional end date in YYYY-MM-DD format

    Returns:
        JSON string with aggregate results

    Examples:
        - Total spending this month: aggregate_type="sum", direction="expense",
          date_from="2024-01-01", date_to="2024-01-31"
        - Highest expense: aggregate_type="max", direction="expense"
        - Count income entries: aggregate_type="count", direction="income"
    """
    try:
        # Validate aggregate type
        valid_types = ["sum", "count", "max", "min"]
        if aggregate_type not in valid_types:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Invalid aggregate_type. Must be one of: {', '.join(valid_types)}",
                }
            )

        # Validate direction if provided
        if direction and direction not in ["income", "expense"]:
            return json.dumps(
                {
                    "success": False,
                    "error": "Invalid direction. Must be 'income' or 'expense'",
                }
            )

        # Resolve category name to ID if provided
        category_id = None
        if category:
            category_result = (
                db_connection.service_client.table("category")
                .select("id, name")
                .execute()
            )
            # Try exact match first
            for cat in category_result.data or []:
                if cat["name"].lower() == category.lower():
                    category_id = cat["id"]
                    break

            # If no exact match, try partial/contains match
            if not category_id:
                for cat in category_result.data or []:
                    if category.lower() in cat["name"].lower():
                        category_id = cat["id"]
                        break

        # Call RPC function using service client
        result = db_connection.service_client.rpc(
            "aggregate_entries",
            {
                "p_user_id": str(user_id),
                "p_aggregate_type": aggregate_type,
                "p_direction": direction,
                "p_category_id": str(category_id) if category_id else None,
                "p_date_from": date_from,
                "p_date_to": date_to,
            },
        ).execute()

        if not result.data:
            return json.dumps(
                {"success": False, "error": "No data returned from aggregate function"}
            )

        agg_data = result.data

        # Build response based on aggregate type
        response = {
            "success": True,
            "aggregate_type": agg_data["aggregate_type"],
            "value": agg_data["value"],
        }

        # Add count for sum/max/min
        if "count" in agg_data:
            response["count"] = agg_data["count"]

        # Add entry details for max/min
        if agg_data["aggregate_type"] in ["max", "min"] and agg_data.get("entry"):
            entry = agg_data["entry"]
            # Convert amount_cents to amount
            if "amount_cents" in entry:
                entry["amount"] = float(entry["amount_cents"]) / 100
            response["entry"] = entry

        # Add helpful message
        if agg_data["aggregate_type"] == "sum":
            response["message"] = (
                f"Total: ${agg_data['value']:.2f} across {agg_data['count']} entries"
            )
        elif agg_data["aggregate_type"] == "count":
            response["message"] = f"Found {agg_data['value']} matching entries"
        elif agg_data["aggregate_type"] == "max" and agg_data.get("entry"):
            entry = agg_data["entry"]
            response["message"] = (
                f"Highest: ${agg_data['value']:.2f} - {entry.get('description', 'N/A')} on {entry.get('entry_date', 'N/A')}"
            )
        elif agg_data["aggregate_type"] == "min" and agg_data.get("entry"):
            entry = agg_data["entry"]
            response["message"] = (
                f"Lowest: ${agg_data['value']:.2f} - {entry.get('description', 'N/A')} on {entry.get('entry_date', 'N/A')}"
            )
        else:
            response["message"] = f"No entries found matching criteria"

        return json.dumps(response)

    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "message": f"Failed to perform aggregation: {str(e)}",
            }
        )


# Export tools for easy import
__all__ = ["fetch_entries", "create_entry", "update_entry", "aggregate_entries"]
