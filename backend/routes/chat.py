"""
Chat/NLP routes for Expense Tracker MVP
"""

import os
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException

from middleware.auth import get_current_user_id
from models.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    ParseError,
    EntryResponse,
    CategoryResponse,
    ChatMessage,
    ConversationHistoryResponse,
)
from services.nlp_factory import create_nlp_service, get_nlp_service_info
from services.redis_service import redis_service

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.get("/service-info")
async def get_service_info():
    """Get information about the current NLP service configuration."""
    return get_nlp_service_info()


@router.post("/", response_model=ChatResponse)
async def chat_query(
    request: ChatRequest, user_id: UUID = Depends(get_current_user_id)
):
    """Handle natural language queries for both read and write operations"""
    try:
        # Get OpenAI API key from environment
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        # Initialize NLP service using factory
        nlp_service = create_nlp_service(openai_api_key)

        # Process the query with user context and chat_id for conversation memory
        result = await nlp_service.process_query(
            request.text, user_id=str(user_id), chat_id=request.chat_id
        )

        # Check if result is an error
        if isinstance(result, ParseError):
            raise HTTPException(
                status_code=400, detail=ErrorResponse(error=result).model_dump()
            )

        # Return successful response
        # Convert result to proper format
        if result["operation"] == "write":
            # For write operations, result can be either a dict or a list with one entry
            # V3 returns a list, V2 returns a dict
            result_data = result["result"]
            if isinstance(result_data, list):
                # V3 format: list with one entry
                entry_dict = result_data[0] if result_data else {}
            else:
                # V2 format: single dict
                entry_dict = result_data

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
            return ChatResponse(
                operation="write",
                result=entry_response,
                message=result.get("message", "Entry created successfully"),
                chat_id=result.get("chat_id"),
            )
        elif result["operation"] == "unsure":
            # For unsure operations, return the suggestions and message
            return ChatResponse(
                operation="unsure",
                result=result.get("result", []),  # This contains the suggestions
                message=result.get(
                    "message",
                    "I'm not sure what you'd like to do. Could you please clarify?",
                ),
                chat_id=result.get("chat_id"),
            )
        else:
            # For read operations, result is already a list of entry dictionaries
            # Convert each entry to EntryResponse format if it has all required fields
            # Otherwise, return raw data (for partial queries like analytics)
            entries = []
            for entry_dict in result["result"]:
                # Check if entry has all required fields for EntryResponse
                required_fields = [
                    "id",
                    "amount",
                    "direction",
                    "entry_date",
                    "description",
                    "source",
                    "created_at",
                ]
                has_all_fields = all(field in entry_dict for field in required_fields)

                if not has_all_fields:
                    # Return raw result for partial data (e.g., analytics queries)
                    return ChatResponse(
                        operation="read",
                        result=result["result"],  # Return raw data as-is
                        message=result.get("message", "Query completed successfully"),
                        chat_id=result.get("chat_id"),
                    )

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
            return ChatResponse(
                operation="read",
                result=entries,
                message=result.get("message", "Query completed successfully"),
                chat_id=result.get("chat_id"),
            )

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        print(f"ERROR in chat endpoint: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{chat_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    chat_id: str, user_id: UUID = Depends(get_current_user_id)
):
    """Retrieve conversation history for a specific chat"""
    try:
        # Get conversation history from Redis
        messages = await redis_service.get_conversation_history(chat_id)

        # Convert to response format
        chat_messages = [
            ChatMessage(role=msg.role, content=msg.content, timestamp=msg.timestamp)
            for msg in messages
        ]

        return ConversationHistoryResponse(
            chat_id=chat_id, messages=chat_messages, count=len(chat_messages)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve conversation history: {str(e)}"
        )


@router.delete("/{chat_id}")
async def clear_conversation(
    chat_id: str, user_id: UUID = Depends(get_current_user_id)
):
    """Clear conversation history for a specific chat"""
    try:
        # Clear conversation from Redis
        success = await redis_service.clear_conversation(chat_id)

        if success:
            return {"message": "Conversation cleared successfully", "chat_id": chat_id}
        else:
            return {
                "message": "Conversation not found or already cleared",
                "chat_id": chat_id,
            }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to clear conversation: {str(e)}"
        )
