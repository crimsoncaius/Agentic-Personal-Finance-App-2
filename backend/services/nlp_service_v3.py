"""
NLP Service V3 - LangGraph ReAct Agent Implementation
Uses prebuilt create_react_agent with tools for database operations
"""

import json
import time
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4
from functools import partial

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import StructuredTool

# Try both import paths to handle running from different directories
try:
    from config.settings import settings
    from services.langfuse_service_v3 import langfuse_service_v3 as langfuse_service
    from services.redis_service import redis_service
    from database.connection import db_connection
    from services.tools import fetch_entries, create_entry, update_entry
except ImportError:
    from backend.config.settings import settings
    from backend.services.langfuse_service_v3 import (
        langfuse_service_v3 as langfuse_service,
    )
    from backend.services.redis_service import redis_service
    from backend.database.connection import db_connection
    from backend.services.tools import fetch_entries, create_entry, update_entry


class NLPServiceV3:
    """LangGraph ReAct agent for natural language finance tracking."""

    def __init__(self, openai_api_key: str = None):
        """Initialize the NLP service with OpenAI API key"""
        # Set up API key
        import os

        if openai_api_key:
            os.environ["OPENAI_API_KEY"] = openai_api_key
        elif getattr(settings, "openai_api_key", None):
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

        self.langfuse = langfuse_service
        self.db = db_connection
        self.redis = redis_service

        # Use MemorySaver for checkpointing (per-conversation memory)
        self.checkpointer = MemorySaver()

        # Store current user_id for tool injection
        self._current_user_id: Optional[str] = None

    async def process_query(
        self,
        text: str,
        user_id: str = None,
        session_id: str = None,
        chat_id: str = None,
    ) -> Dict[str, Any]:
        """
        Process a natural language query using LangGraph ReAct agent

        Args:
            text: Natural language input from user
            user_id: User identifier for authentication
            session_id: Session identifier for tracing
            chat_id: Chat identifier for conversation context

        Returns:
            Dictionary with operation result and chat_id
        """
        # Store user_id for tool injection
        self._current_user_id = user_id

        # Generate chat_id if not provided
        if not chat_id:
            chat_id = str(uuid4())

        # Create main trace for the entire query processing
        async with self.langfuse.trace_operation(
            name="nlp_query_processing_v3",
            user_id=user_id,
            session_id=session_id,
            input_data={"text": text},
            tags=["nlp", "v3", "langgraph", "react_agent"],
        ) as trace_id:
            try:
                start_time = time.time()

                # Retrieve conversation history from Redis
                conversation_history = await self.redis.get_conversation_history(
                    chat_id
                )

                # Create the agent
                agent = self._create_agent(user_id)

                # Build messages for agent input
                messages = []

                # Add conversation history
                for msg in conversation_history:
                    messages.append({"role": msg.role, "content": msg.content})

                # Add current user message
                messages.append({"role": "user", "content": text})

                # Configure agent with thread_id for checkpointing
                config = {
                    "configurable": {
                        "thread_id": chat_id,
                    }
                }

                # Invoke the agent
                result_state = await agent.ainvoke(
                    {"messages": messages}, config=config
                )

                # Calculate total processing time
                total_duration = time.time() - start_time

                # Track performance metrics
                self.langfuse.track_performance_metrics_v3(
                    operation="query_processing_v3",
                    trace_id=trace_id,
                    metrics={
                        "total_duration": total_duration,
                        "text_length": len(text),
                        "messages_count": len(result_state.get("messages", [])),
                    },
                )

                # Parse agent output to extract response
                response = self._parse_agent_output(result_state)

                # Store messages in Redis for conversation continuity
                await self.redis.store_message(chat_id, "user", text)
                await self.redis.store_message(
                    chat_id, "assistant", response["message"]
                )

                # Add chat_id to response
                response["chat_id"] = chat_id

                return response

            except Exception as e:
                # Track error metrics
                self.langfuse.track_performance_metrics_v3(
                    operation="query_processing_v3",
                    trace_id=trace_id,
                    metrics={
                        "success": False,
                        "error": str(e),
                        "text_length": len(text),
                    },
                )

                return {
                    "operation": "unsure",
                    "result": [],
                    "message": f"I encountered an error processing your request: {str(e)}",
                    "chat_id": chat_id,
                }

    def _create_agent(self, user_id: str):
        """Create the LangGraph ReAct agent with tools and configuration"""
        # Initialize the language model
        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)

        # Get categories for system prompt
        categories = self._get_categories_sync()
        category_names = [cat.get("name") for cat in categories if cat.get("name")]

        # Build system prompt
        system_prompt = self._build_system_prompt(category_names)

        # Create wrapper tools with user_id pre-filled using partial
        # This ensures user_id is automatically passed to each tool call without the LLM needing to provide it

        def create_tool_with_user_id(tool_func, user_id_value):
            """Create a new tool with user_id pre-filled"""
            # Get the original tool's metadata
            original_name = tool_func.name
            original_description = tool_func.description

            # Create a partial function with user_id bound
            func_with_user_id = partial(tool_func.func, user_id=user_id_value)

            # Create a new tool with the bound function
            # Remove user_id from the schema since it's now pre-filled
            from pydantic import create_model

            # Get original args schema and remove user_id
            original_schema = tool_func.args_schema
            if original_schema:
                # Create new schema without user_id field
                field_definitions = {
                    k: (v.annotation, v)
                    for k, v in original_schema.model_fields.items()
                    if k != "user_id"
                }
                new_schema = create_model(
                    f"{original_schema.__name__}WithoutUserId", **field_definitions
                )
            else:
                new_schema = None

            return StructuredTool(
                name=original_name,
                description=original_description,
                func=func_with_user_id,
                args_schema=new_schema,
            )

        tools_with_user_id = [
            create_tool_with_user_id(fetch_entries, user_id),
            create_tool_with_user_id(create_entry, user_id),
            create_tool_with_user_id(update_entry, user_id),
        ]

        # Create the ReAct agent
        agent = create_react_agent(
            model=model,
            tools=tools_with_user_id,
            prompt=system_prompt,
            checkpointer=self.checkpointer,
        )

        return agent

    def _build_system_prompt(self, category_names: List[str]) -> str:
        """Build system prompt for the agent"""
        current_date = date.today().isoformat()

        prompt = f"""You are a helpful financial assistant helping users track their income and expenses.

**Current Date:** {current_date}

**Available Categories:**
{', '.join(category_names)}

**Your Capabilities:**
1. **Fetch Entries**: Use the fetch_entries tool to retrieve existing financial records
   - You can filter by date range, category, direction (income/expense)
   - Maximum 10 results per query
   
2. **Create Entry**: Use the create_entry tool to add new income or expense transactions
   - Required: amount, direction, description, category, entry_date
   - Direction must be "income" or "expense"
   
3. **Update Entry**: Use the update_entry tool to modify existing transactions
   - Required: entry_id
   - Optional: amount, direction, description, category, entry_date

**Important Guidelines:**
- Always use tools to fetch or create data - NEVER make up or hallucinate financial data
- When users ask about their finances, use fetch_entries to get real data
- For date queries like "last month" or "this week", calculate the appropriate date range
- Be conversational and helpful in your responses
- If you're unsure what the user wants, ask clarifying questions
- After using tools, provide a natural language summary of the results

**Date Handling:**
- Today is {current_date}
- Convert relative dates (e.g., "yesterday", "last week") to YYYY-MM-DD format
- For date ranges, use the where clause with ">=" and "<=" operators

**Response Format:**
After using tools, provide a clear, conversational summary of what you found or did.
Be specific with numbers and details from the tool results."""

        return prompt

    def _parse_agent_output(self, result_state: Dict) -> Dict[str, Any]:
        """Parse agent output to match expected API response format"""
        messages = result_state.get("messages", [])

        # Extract operation type based on tool calls
        operation = "unsure"
        result_data = []
        final_message = "I'm not sure what you'd like to do. Could you please clarify?"

        # Analyze messages to determine operation and extract results
        tool_calls_made = []

        for msg in messages:
            # Check for tool calls in AI messages
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_calls_made.append(tool_name)

                    # Determine operation type from tool name
                    if tool_name == "fetch_entries" and operation != "write":
                        operation = "read"
                    elif tool_name == "create_entry":
                        operation = "write"
                    elif tool_name == "update_entry":
                        operation = "write"

            # Check for tool messages (results from tool execution)
            if hasattr(msg, "content") and msg.__class__.__name__ == "ToolMessage":
                try:
                    tool_result = json.loads(msg.content)
                    if tool_result.get("success"):
                        # Extract entries from fetch_entries
                        if "entries" in tool_result:
                            result_data = tool_result["entries"]
                        # Extract entry from create_entry or update_entry
                        elif "entry" in tool_result:
                            result_data = [tool_result["entry"]]
                except json.JSONDecodeError:
                    pass

            # Get the final AI message
            if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage":
                # Only use messages without tool calls as final response
                if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                    if msg.content:
                        final_message = msg.content

        # If no clear operation was detected, check the final message
        if operation == "unsure" and not tool_calls_made:
            # Agent didn't use any tools, likely asking for clarification
            final_message = (
                messages[-1].content
                if messages and hasattr(messages[-1], "content")
                else final_message
            )

        return {
            "operation": operation,
            "result": result_data,
            "message": final_message,
        }

    def _get_categories_sync(self) -> List[Dict[str, Any]]:
        """Get categories synchronously for prompt context"""
        try:
            result = self.db.client.table("category").select("id, name, type").execute()
            return result.data or []
        except Exception:
            return []

    def _resolve_category_name_to_id(self, category_name: str) -> Optional[str]:
        """Resolve category name to category_id"""
        try:
            result = (
                self.db.client.table("category")
                .select("id")
                .eq("name", category_name)
                .execute()
            )
            if result.data:
                return result.data[0]["id"]
        except Exception:
            pass
        return None

    def _resolve_category_id_to_name(self, category_id: str) -> Optional[str]:
        """Resolve category_id to category name"""
        try:
            result = (
                self.db.client.table("category")
                .select("name")
                .eq("id", category_id)
                .execute()
            )
            if result.data:
                return result.data[0]["name"]
        except Exception:
            pass
        return None

    def _normalize_query_spec_filters(
        self, spec_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize QuerySpec filters, converting category names to IDs where needed"""
        if "where" in spec_dict and isinstance(spec_dict["where"], dict):
            normalized_where = {}
            for key, value in spec_dict["where"].items():
                if key == "category_id" and isinstance(value, str):
                    # Try to resolve category name to ID
                    category_id = self._resolve_category_name_to_id(value)
                    if category_id:
                        normalized_where[key] = category_id
                    else:
                        normalized_where[key] = value
                else:
                    normalized_where[key] = value
            spec_dict["where"] = normalized_where
        return spec_dict
