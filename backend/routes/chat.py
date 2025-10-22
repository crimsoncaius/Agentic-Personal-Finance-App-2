"""
Chat/NLP routes for Expense Tracker MVP
"""

import os
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from openai import OpenAI

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
    TranscriptionResponse,
    VoiceChatResponse,
)
from services.agent_service import AgentService
from services.redis_service import redis_service

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.get("/service-info")
async def get_service_info():
    """Get information about the current NLP service configuration."""
    return {
        "version": "v3",
        "class_name": "AgentService",
        "description": "LangGraph ReAct agent with fetch, create, and update tools",
    }


@router.post("/", response_model=ChatResponse)
async def chat_query(
    request: ChatRequest, user_id: UUID = Depends(get_current_user_id)
):
    """Handle natural language queries"""
    try:
        # Get OpenAI API key from environment
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        # Initialize NLP service
        nlp_service = AgentService(openai_api_key)

        # Process the query
        result = await nlp_service.process_query(
            request.text, user_id=str(user_id), chat_id=request.chat_id
        )

        # Check if result is an error
        if isinstance(result, ParseError):
            raise HTTPException(
                status_code=400, detail=ErrorResponse(error=result).model_dump()
            )

        # Convert entries to proper format
        entries = []
        for entry_dict in result.get("entries", []):
            # Convert category to proper format if it exists
            category = None
            if entry_dict.get("category"):
                cat = entry_dict["category"]
                category = CategoryResponse(
                    id=cat["id"],
                    name=cat["name"],
                    type=cat.get("type", "expense"),
                )

            entry_response = EntryResponse(
                id=entry_dict["id"],
                amount=entry_dict["amount"],
                direction=entry_dict["direction"],
                entry_date=entry_dict["entry_date"],
                category=category,
                description=entry_dict["description"],
                created_at=entry_dict["created_at"],
            )
            entries.append(entry_response)

        # Return simplified response
        return ChatResponse(
            message=result.get("message", "I processed your request."),
            entries=entries,
            chat_id=result.get("chat_id"),
        )

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


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio_file: UploadFile = File(...), user_id: UUID = Depends(get_current_user_id)
):
    """Transcribe audio file using OpenAI Whisper API"""
    try:
        # Get OpenAI API key from environment
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        # Initialize OpenAI client
        client = OpenAI(api_key=openai_api_key)

        # Validate file type
        if not audio_file.content_type or not audio_file.content_type.startswith(
            "audio/"
        ):
            raise HTTPException(status_code=400, detail="File must be an audio file")

        # Reset file pointer to beginning
        await audio_file.seek(0)

        # Read the file content
        file_content = await audio_file.read()

        # Create a temporary file-like object for OpenAI
        import io

        audio_file_obj = io.BytesIO(file_content)
        audio_file_obj.name = audio_file.filename or "audio.webm"

        # Transcribe using OpenAI Whisper API
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file_obj,
            response_format="text",
            language="en",
        )

        return TranscriptionResponse(text=transcription)

    except Exception as e:
        import traceback

        print(f"ERROR in transcribe endpoint: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@router.post("/voice", response_model=VoiceChatResponse)
async def voice_chat(
    audio_file: UploadFile = File(...),
    chat_id: str = None,
    user_id: UUID = Depends(get_current_user_id),
):
    """Handle voice chat with transcription and NLP processing"""
    try:
        # Get OpenAI API key from environment
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        # Initialize OpenAI client
        client = OpenAI(api_key=openai_api_key)

        # Validate file type
        if not audio_file.content_type or not audio_file.content_type.startswith(
            "audio/"
        ):
            raise HTTPException(status_code=400, detail="File must be an audio file")

        # Reset file pointer to beginning
        await audio_file.seek(0)

        # Read the file content
        file_content = await audio_file.read()

        # Create a temporary file-like object for OpenAI
        import io

        audio_file_obj = io.BytesIO(file_content)
        audio_file_obj.name = audio_file.filename or "audio.webm"

        # Transcribe using OpenAI Whisper API
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file_obj,
            response_format="text",
            language="en",
        )

        # Initialize NLP service
        nlp_service = AgentService(openai_api_key)

        # Process the transcribed text through the NLP service
        result = await nlp_service.process_query(
            transcription, user_id=str(user_id), chat_id=chat_id
        )

        # Check if result is an error
        if isinstance(result, ParseError):
            raise HTTPException(
                status_code=400, detail=ErrorResponse(error=result).model_dump()
            )

        # Convert entries to proper format
        entries = []
        for entry_dict in result.get("entries", []):
            # Convert category to proper format if it exists
            category = None
            if entry_dict.get("category"):
                cat = entry_dict["category"]
                category = CategoryResponse(
                    id=cat["id"],
                    name=cat["name"],
                    type=cat.get("type", "expense"),
                )

            entry_response = EntryResponse(
                id=entry_dict["id"],
                amount=entry_dict["amount"],
                direction=entry_dict["direction"],
                entry_date=entry_dict["entry_date"],
                category=category,
                description=entry_dict["description"],
                created_at=entry_dict["created_at"],
            )
            entries.append(entry_response)

        # Create chat response
        chat_response = ChatResponse(
            message=result.get("message", "I processed your request."),
            entries=entries,
            chat_id=result.get("chat_id"),
        )

        # Return voice chat response with both transcription and chat response
        return VoiceChatResponse(
            transcription=transcription, chat_response=chat_response
        )

    except Exception as e:
        import traceback

        print(f"ERROR in voice chat endpoint: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Voice chat failed: {str(e)}")
