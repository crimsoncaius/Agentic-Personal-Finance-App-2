"""
Entry routes for Expense Tracker MVP
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from models.schemas import (
    EntryCreateStructured,
    EntryListResponse,
    EntryQueryParams,
    EntryResponse,
    ErrorResponse,
    ParseError,
)
from services.entry_service import EntryService

router = APIRouter(prefix="/api/v1/entries", tags=["entries"])


@router.post("/", response_model=EntryResponse, status_code=201)
async def create_entry_structured(entry: EntryCreateStructured):
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
            category_id=entry.category_id,
            description=entry.description,
            source=entry.source,
        )

        # Convert to response format
        response_data = {
            "id": created_entry.id,
            "amount": float(
                entry.amount
            ),  # Convert Decimal to float for JSON serialization
            "direction": created_entry.direction,
            "entry_date": created_entry.entry_date,
            "category": None,  # TODO: Load category data
            "description": created_entry.description,
            "source": created_entry.source,
            "parse_confidence": None,  # Manual entries don't have parse confidence
            "created_at": created_entry.created_at,
        }

        return EntryResponse(**response_data)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
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

        result = await EntryService.get_entries(params)
        return EntryListResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
