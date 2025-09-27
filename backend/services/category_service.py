"""
Category service for database operations
"""

from typing import List, Optional
from uuid import UUID

from database.connection import db_connection
from models.schemas import Category, CategoryQueryParams, CategoryResponse


class CategoryService:
    """Service for category-related database operations"""

    @staticmethod
    async def get_categories(params: CategoryQueryParams) -> List[CategoryResponse]:
        """Get categories with optional filtering"""
        query = (
            db_connection.client.table("category")
            .select("id, name, type")
            .order("name")
        )

        if params.type:
            query = query.eq(
                "type", params.type.value
            )  # Use .value to get the actual enum value

        result = query.execute()

        if not result.data:
            return []

        return [CategoryResponse(**item) for item in result.data]

    @staticmethod
    async def get_category_by_id(category_id: UUID) -> Optional[Category]:
        """Get a single category by ID"""
        result = (
            db_connection.client.table("category")
            .select("*")
            .eq("id", str(category_id))
            .execute()
        )

        if not result.data:
            return None

        return Category(**result.data[0])

    @staticmethod
    async def get_category_by_name(name: str) -> Optional[Category]:
        """Get a category by name"""
        result = (
            db_connection.client.table("category")
            .select("*")
            .eq("name", name)
            .execute()
        )

        if not result.data:
            return None

        return Category(**result.data[0])

    @staticmethod
    async def get_default_category(direction: str) -> Optional[Category]:
        """Get default category for a direction"""
        if direction == "expense":
            result = (
                db_connection.client.table("category")
                .select("*")
                .eq("name", "Miscellaneous (Expense)")
                .execute()
            )
        elif direction == "income":
            result = (
                db_connection.client.table("category")
                .select("*")
                .eq("name", "Other Income (Income)")
                .execute()
            )
        else:
            return None

        if not result.data:
            return None

        return Category(**result.data[0])
