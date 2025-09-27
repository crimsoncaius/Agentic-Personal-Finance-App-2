"""
Category routes for Expense Tracker MVP
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from models.schemas import CategoryQueryParams, CategoryResponse
from services.category_service import CategoryService

router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    type: Optional[str] = Query(default=None, description="Filter by category type")
):
    """Get categories with optional filtering"""
    try:
        params = CategoryQueryParams(type=type)
        categories = await CategoryService.get_categories(params)
        return categories

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
