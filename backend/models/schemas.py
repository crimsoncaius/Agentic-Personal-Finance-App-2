"""
Pydantic models for Expense Tracker MVP API
Based on Technical Design Document specifications
"""

from datetime import date, datetime
from decimal import Decimal

# Enums matching database schema
from enum import Enum
from typing import List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntryDirection(str, Enum):
    """Entry direction enum"""

    EXPENSE = "expense"
    INCOME = "income"


class SourceType(str, Enum):
    """Source type enum"""

    MANUAL = "manual"
    NLP = "nlp"


class CategoryKind(str, Enum):
    """Category kind enum"""

    EXPENSE = "expense"
    INCOME = "income"


# Auth models
class UserRegister(BaseModel):
    """User registration request"""

    email: str = Field(
        ..., min_length=3, max_length=255, description="User email address"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="User password (min 8 characters)",
    )
    name: Optional[str] = Field(None, max_length=255, description="User display name")


class UserLogin(BaseModel):
    """User login request"""

    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class SessionResponse(BaseModel):
    """Session information response"""

    access_token: str
    refresh_token: str
    expires_at: int


class UserResponse(BaseModel):
    """User information response"""

    id: str
    email: str
    name: Optional[str] = None
    created_at: str


class AuthResponse(BaseModel):
    """Authentication response (login/register)"""

    user: UserResponse
    session: Optional[SessionResponse] = None
    message: str = "Success"


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str = Field(..., description="Refresh token")


class VerifyTokenResponse(BaseModel):
    """Token verification response"""

    user: UserResponse
    email_confirmed: bool


# Base models
class CategoryBase(BaseModel):
    """Base category model"""

    name: str = Field(..., min_length=1, max_length=255)
    type: CategoryKind
    parent_id: Optional[UUID] = None
    is_system: bool = True


class Category(CategoryBase):
    """Category model with database fields"""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryResponse(BaseModel):
    """Category response model for API"""

    id: UUID
    name: str
    type: CategoryKind

    model_config = ConfigDict(from_attributes=True)


# Entry models
class EntryBase(BaseModel):
    """Base entry model"""

    amount: Decimal = Field(..., gt=0, description="Amount in dollars")
    direction: EntryDirection
    entry_date: date
    category_id: Optional[UUID] = None
    description: Optional[str] = Field(None, max_length=500)
    source: SourceType = SourceType.MANUAL
    parse_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

    @field_validator("parse_confidence")
    @classmethod
    def validate_parse_confidence(cls, v, info):
        """Parse confidence should only be set for NLP entries"""
        if v is not None and info.data.get("source") == SourceType.MANUAL:
            raise ValueError("Parse confidence should only be set for NLP entries")
        return v


class EntryCreateStructured(BaseModel):
    """Structured entry creation model for manual entries"""

    amount: Decimal = Field(..., gt=0, description="Amount in dollars")
    direction: EntryDirection
    entry_date: date
    category_id: Optional[UUID] = Field(
        None,
        description="Category ID (Food & Dining example)",
        json_schema_extra={"example": "280463c5-13c4-47f3-a6aa-db24738af1aa"},
    )
    description: Optional[str] = Field(None, max_length=500)
    source: SourceType = SourceType.MANUAL


class EntryCreateNL(EntryBase):
    """Entry creation model for NLP entries with parse confidence"""

    source: SourceType = SourceType.NLP
    parse_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for NLP parsing"
    )


class EntryUpdate(BaseModel):
    """Entry update model for partial updates"""

    amount: Optional[Decimal] = Field(None, gt=0, description="Amount in dollars")
    direction: Optional[EntryDirection] = None
    entry_date: Optional[date] = None
    category_id: Optional[UUID] = Field(
        None,
        description="Category ID (Food & Dining example)",
        json_schema_extra={"example": "280463c5-13c4-47f3-a6aa-db24738af1aa"},
    )
    description: Optional[str] = Field(None, max_length=500)


class Entry(EntryBase):
    """Entry model with database fields"""

    id: UUID
    amount_cents: int = Field(..., description="Amount in cents")
    created_at: datetime
    updated_at: datetime

    @field_validator("amount_cents")
    @classmethod
    def validate_amount_cents(cls, v):
        """Amount in cents must be positive"""
        if v < 0:
            raise ValueError("Amount in cents must be non-negative")
        return v

    model_config = ConfigDict(from_attributes=True)


class EntryResponse(BaseModel):
    """Entry response model for API"""

    id: UUID
    amount: Decimal
    direction: EntryDirection
    entry_date: date
    category: Optional[CategoryResponse] = None
    description: Optional[str]
    source: SourceType
    parse_confidence: Optional[float]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EntryListResponse(BaseModel):
    """Entry list response model"""

    items: List[EntryResponse]
    page: dict = Field(..., description="Pagination information")

    model_config = ConfigDict(from_attributes=True)


# Chat/Query models
class ChatRequest(BaseModel):
    """Natural language query request model"""

    text: str = Field(..., min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    """Chat response model"""

    operation: Literal["read", "write", "unsure"]
    result: Union[EntryResponse, List[EntryResponse], List[str]]
    message: str = Field(..., description="User-friendly response message")


# LangGraph specific models
class ParsedData(BaseModel):
    """Parsed data from natural language input"""

    amount: Decimal = Field(..., gt=0, description="Amount in dollars")
    direction: EntryDirection
    entry_date: date
    category: Optional[str] = Field(None, description="Category name from LLM")
    description: Optional[str] = Field(None, max_length=500)


class RouterDecision(BaseModel):
    """Router decision model"""

    operation: Literal["read", "write", "unsure"]


class QueryParams(BaseModel):
    """Query parameters for read operations"""

    limit: int = Field(default=10, ge=1, le=10)
    offset: int = Field(default=0, ge=0)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    direction: Optional[EntryDirection] = None
    category_id: Optional[UUID] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None
    q: Optional[str] = Field(None, max_length=255)
    sort: Literal[
        "entry_date.desc",
        "entry_date.asc",
        "amount_cents.desc",
        "amount_cents.asc",
        "created_at.desc",
    ] = "entry_date.desc"

    @field_validator("amount_min", "amount_max")
    @classmethod
    def validate_amounts(cls, v):
        """Amount must be positive"""
        if v is not None and v <= 0:
            raise ValueError("Amount must be positive")
        return v

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, v, info):
        """date_to must be after date_from"""
        if v is not None and info.data.get("date_from") is not None:
            if v < info.data["date_from"]:
                raise ValueError("date_to must be after date_from")
        return v


# Error models
class ErrorDetail(BaseModel):
    """Error detail model"""

    missing_fields: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None


class ParseError(BaseModel):
    """Parse error model"""

    code: Literal["missing_fields", "ambiguous", "validation_error", "parsing_failed"]
    message: str
    details: Optional[ErrorDetail] = None


class ErrorResponse(BaseModel):
    """Error response model"""

    error: ParseError


# Query parameter models
class EntryQueryParams(BaseModel):
    """Entry query parameters model"""

    limit: int = Field(
        default=10, ge=1, le=10, description="Maximum number of entries to return"
    )
    offset: int = Field(default=0, ge=0, description="Number of entries to skip")
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    direction: Optional[EntryDirection] = None
    category_id: Optional[UUID] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None
    q: Optional[str] = Field(
        None, max_length=255, description="Text search on description"
    )
    sort: Literal["entry_date.desc", "created_at.desc"] = "entry_date.desc"

    @field_validator("amount_min", "amount_max")
    @classmethod
    def validate_amounts(cls, v):
        """Amount must be positive"""
        if v is not None and v <= 0:
            raise ValueError("Amount must be positive")
        return v

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, v, info):
        """date_to must be after date_from"""
        if v is not None and info.data.get("date_from") is not None:
            if v < info.data["date_from"]:
                raise ValueError("date_to must be after date_from")
        return v


class CategoryQueryParams(BaseModel):
    """Category query parameters model"""

    type: Optional[CategoryKind] = None


# Utility functions for data conversion
def cents_to_dollars(cents: int) -> Decimal:
    """Convert cents to dollars"""
    return Decimal(cents) / 100


def dollars_to_cents(dollars: Decimal) -> int:
    """Convert dollars to cents"""
    return int(dollars * 100)
