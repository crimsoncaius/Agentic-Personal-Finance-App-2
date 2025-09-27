"""
Chat/NLP routes for Expense Tracker MVP
"""

import os
from fastapi import APIRouter, HTTPException

from models.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    ParseError,
    EntryResponse,
    CategoryResponse,
)
from services.nlp_service import NLPService

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """Handle natural language queries for both read and write operations"""
    try:
        # Get OpenAI API key from environment
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        # Initialize NLP service
        nlp_service = NLPService(openai_api_key)

        # Process the query
        result = await nlp_service.process_query(request.text)

        # Check if result is an error
        if isinstance(result, ParseError):
            raise HTTPException(
                status_code=400, detail=ErrorResponse(error=result).model_dump()
            )

        # Return successful response
        # Convert result to proper format
        if result["operation"] == "write":
            # For write operations, result is a single entry dictionary
            entry_dict = result["result"]
            # Convert category to proper format if it exists
            category = None
            if entry_dict.get("category"):
                cat = entry_dict["category"]
                category = CategoryResponse(
                    id=cat["id"],
                    name=cat["name"],
                    type=cat.get(
                        "type", "expense"
                    ),  # Default to expense if type missing
                )

            # Convert to EntryResponse format
            entry_response = EntryResponse(
                id=entry_dict["id"],
                amount=entry_dict["amount"],  # Keep as Decimal for proper serialization
                direction=entry_dict["direction"],
                entry_date=entry_dict["entry_date"],
                category=category,
                description=entry_dict["description"],
                source=entry_dict["source"],
                parse_confidence=entry_dict.get("parse_confidence"),
                created_at=entry_dict["created_at"],
            )
            return ChatResponse(operation="write", result=entry_response)
        else:
            # For read operations, result is already a list of entry dictionaries
            # Convert each entry to EntryResponse format
            entries = []
            for entry_dict in result["result"]:
                # Convert category to proper format if it exists
                category = None
                if entry_dict.get("category"):
                    cat = entry_dict["category"]
                    category = CategoryResponse(
                        id=cat["id"],
                        name=cat["name"],
                        type=cat.get(
                            "type", "expense"
                        ),  # Default to expense if type missing
                    )

                entry_response = EntryResponse(
                    id=entry_dict["id"],
                    amount=entry_dict[
                        "amount"
                    ],  # Keep as Decimal for proper serialization
                    direction=entry_dict["direction"],
                    entry_date=entry_dict["entry_date"],
                    category=category,
                    description=entry_dict["description"],
                    source=entry_dict["source"],
                    parse_confidence=entry_dict.get("parse_confidence"),
                    created_at=entry_dict["created_at"],
                )
                entries.append(entry_response)
            return ChatResponse(operation="read", result=entries)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
