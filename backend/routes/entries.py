"""
Entry routes for Expense Tracker MVP
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from middleware.auth import get_current_user
from models.schemas import (
    EntryCreateStructured,
    EntryListResponse,
    EntryQueryParams,
    EntryResponse,
    EntryUpdate,
)
from services.entry_service import EntryService

router = APIRouter(prefix="/api/v1/entries", tags=["entries"])


def _convert_entry_to_response(entry) -> dict:
    """Helper function to convert entry object to response dictionary"""
    return {
        "id": entry.id,
        "amount": float(entry.amount),
        "direction": entry.direction,
        "entry_date": entry.entry_date,
        "category": None,  # TODO: Load category data
        "description": entry.description,
        "created_at": entry.created_at,
    }


@router.post("/", response_model=EntryResponse, status_code=201)
async def create_entry_structured(
    entry: EntryCreateStructured, user: dict = Depends(get_current_user)
):
    """Create a new entry with structured data"""
    try:
        # Validate category exists and matches direction if provided
        if entry.category_id:
            # TODO: Add category validation service call
            pass

        created_entry = await EntryService.create_entry(
            amount=entry.amount,
            direction=entry.direction,
            entry_date=entry.entry_date,
            user_id=UUID(user["user_id"]),
            category_id=entry.category_id,
            description=entry.description,
            jwt_token=user.get("jwt_token"),
        )

        return EntryResponse(**_convert_entry_to_response(created_entry))

    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=EntryListResponse)
async def get_entries(
    limit: int = Query(default=10, ge=1, le=10),
    offset: int = Query(default=0, ge=0),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    direction: Optional[str] = Query(default=None),
    category_id: Optional[UUID] = Query(default=None),
    amount_min: Optional[Decimal] = Query(default=None),
    amount_max: Optional[Decimal] = Query(default=None),
    q: Optional[str] = Query(default=None),
    sort: str = Query(default="entry_date.desc"),
    user: dict = Depends(get_current_user),
):
    """Get entries with filtering and pagination"""
    try:
        params = EntryQueryParams(
            limit=limit,
            offset=offset,
            date_from=date_from,
            date_to=date_to,
            direction=direction,
            category_id=category_id,
            amount_min=amount_min,
            amount_max=amount_max,
            q=q,
            sort=sort,
        )

        result = await EntryService.get_entries(
            params, UUID(user["user_id"]), user.get("jwt_token")
        )
        return EntryListResponse(**result)

    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{entry_id}", response_model=EntryResponse)
async def update_entry(
    entry_id: UUID,
    entry_update: EntryUpdate,
    user: dict = Depends(get_current_user),
):
    """Update an existing entry with partial data"""
    try:
        updated_entry = await EntryService.update_entry(
            entry_id, entry_update, UUID(user["user_id"]), user.get("jwt_token")
        )

        if updated_entry is None:
            raise HTTPException(status_code=404, detail="Entry not found")

        return EntryResponse(**_convert_entry_to_response(updated_entry))

    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{entry_id}")
async def delete_entry(entry_id: UUID, user: dict = Depends(get_current_user)):
    """Delete an entry by ID"""
    try:
        deleted = await EntryService.delete_entry(
            entry_id, UUID(user["user_id"]), user.get("jwt_token")
        )

        if not deleted:
            raise HTTPException(status_code=404, detail="Entry not found")

        return {"message": "Entry deleted successfully"}

    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
