"""
Agent Service - LangGraph ReAct Agent Implementation
Uses prebuilt create_react_agent with tools for database operations
"""

import hashlib
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
from langfuse.langchain import CallbackHandler

# Import paths for running from backend directory
from config.settings import settings
from services.langfuse_service import langfuse_service
from services.redis_service import redis_service, ToolObservation
from services.prompt_manager import PromptManager
from database.connection import db_connection
from services.tools import (
    fetch_entries,
    create_entry,
    update_entry,
    aggregate_entries,
)


class AgentService:
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
        self.prompt_manager = PromptManager()

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
        tags: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a natural language query using LangGraph ReAct agent

        Args:
            text: Natural language input from user
            user_id: User identifier for authentication
            session_id: Session identifier for tracing
            chat_id: Chat identifier for conversation context
            tags: Optional list of tags to add to the trace

        Returns:
            Dictionary with operation result and chat_id
        """
        # Store user_id for tool injection
        self._current_user_id = user_id

        # Generate chat_id if not provided
        if not chat_id:
            chat_id = str(uuid4())

        # Merge default tags with custom tags
        default_tags = ["nlp", "v3", "langgraph", "react_agent"]
        trace_tags = default_tags + (tags if tags else [])

        # Create main trace for the entire query processing
        async with self.langfuse.trace_operation(
            name="nlp_query_processing_v3",
            user_id=user_id,
            session_id=session_id,
            input_data={"text": text},
            tags=trace_tags,
        ) as trace_id:
            try:
                start_time = time.time()

                # Retrieve conversation history from Redis
                conversation_history = await self.redis.get_conversation_history(chat_id)
                tool_observations = await self.redis.get_tool_observations(chat_id)

                # Create the agent with trace info for LLM tracking
                agent = self._create_agent(
                    user_id, trace_id=trace_id, session_id=session_id
                )

                # Build messages for agent input
                messages = []

                # Add conversation history
                for msg in conversation_history:
                    messages.append({"role": msg.role, "content": msg.content})

                # Add trusted tool context
                private_context = self._render_private_context(tool_observations)
                if private_context:
                    messages.append(
                        {
                            "role": "system",
                            "content": private_context,
                        }
                    )

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

                # Extract and log tool calls to Langfuse
                tool_calls = self._extract_tool_calls_from_result(result_state)
                for tool_call in tool_calls:
                    self.langfuse.track_tool_call(
                        tool_name=tool_call["name"],
                        tool_input=tool_call.get("input"),
                        tool_output=tool_call.get("output"),
                        trace_id=trace_id,
                    )

                # Persist trusted tool observations for future turns
                await self._persist_tool_observations(chat_id, tool_calls)

                # Flush to ensure observations are saved
                self.langfuse.flush()

                # Track performance metrics
                self.langfuse.track_performance_metrics_v3(
                    operation="query_processing_v3",
                    trace_id=trace_id,
                    metrics={
                        "total_duration": total_duration,
                        "text_length": len(text),
                        "messages_count": len(result_state.get("messages", [])),
                        "tool_calls_count": len(tool_calls),
                    },
                )

                # Parse agent output to extract response
                response = self._parse_agent_output(result_state)

                # Store messages in Redis for conversation continuity
                await self.redis.store_message(chat_id, "user", text)
                await self.redis.store_message(
                    chat_id, "assistant", response["message"]
                )

                # Add chat_id and trace_id to response
                response["chat_id"] = chat_id
                response["trace_id"] = trace_id

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
                    "trace_id": trace_id,
                }

    def _create_agent(self, user_id: str, trace_id: str = None, session_id: str = None):
        """Create the LangGraph ReAct agent with tools and configuration"""
        # Initialize Langfuse callback handler for LLM tracking
        # The handler will automatically use LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY from env
        callbacks = []
        if self.langfuse.enabled:
            langfuse_handler = CallbackHandler()
            callbacks.append(langfuse_handler)

        # Initialize the language model with Langfuse tracking
        model = ChatOpenAI(
            model="gpt-4.1-nano",
            temperature=0.1,
            callbacks=callbacks if callbacks else None,
        )

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
            create_tool_with_user_id(aggregate_entries, user_id),
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
        """Build system prompt for the agent using PromptManager template"""
        current_date = date.today()

        # Use the PromptManager to render the template
        prompt = self.prompt_manager.generate_react_agent_system_prompt(
            current_date=current_date,
            categories=category_names,
        )

        return prompt

    def _extract_tool_calls_from_result(
        self, result_state: Dict
    ) -> List[Dict[str, Any]]:
        """Extract tool calls from agent result state for logging to Langfuse"""
        messages = result_state.get("messages", [])
        tool_calls = []

        for msg in messages:
            # Check for AIMessage with tool calls
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_calls.append(
                        {
                            "name": (
                                tool_call.get("name")
                                if isinstance(tool_call, dict)
                                else getattr(tool_call, "name", "unknown")
                            ),
                            "input": (
                                tool_call.get("args")
                                if isinstance(tool_call, dict)
                                else getattr(tool_call, "args", {})
                            ),
                            "output": None,  # Will be filled from ToolMessage
                        }
                    )

            # Check for ToolMessage (tool results)
            if hasattr(msg, "content") and msg.__class__.__name__ == "ToolMessage":
                # Find the corresponding tool call and add output
                if tool_calls:
                    # Match by position (last added tool call gets this output)
                    for tool_call in reversed(tool_calls):
                        if tool_call["output"] is None:
                            try:
                                tool_call["output"] = json.loads(msg.content)
                            except json.JSONDecodeError:
                                tool_call["output"] = msg.content
                            break

        return tool_calls

    def _parse_agent_output(self, result_state: Dict) -> Dict[str, Any]:
        """Parse agent output to simple message + entries format"""
        messages = result_state.get("messages", [])

        entries = []
        final_message = "I processed your request."

        # Extract entries from tool results
        for msg in messages:
            # Check for tool messages (results from tool execution)
            if hasattr(msg, "content") and msg.__class__.__name__ == "ToolMessage":
                try:
                    tool_result = json.loads(msg.content)
                    if tool_result.get("success"):
                        # For aggregate results, include entry details from max/min operations
                        if "aggregate_type" in tool_result:
                            # Max/min aggregations include the actual entry with details
                            if (
                                tool_result["aggregate_type"] in ["max", "min"]
                                and "entry" in tool_result
                            ):
                                entries.append(tool_result["entry"])
                            # Skip other aggregate types (sum, count don't have entries)
                            continue
                        # Extract entries from fetch_entries
                        if "entries" in tool_result:
                            entries.extend(tool_result["entries"])
                        # Extract entry from create_entry or update_entry
                        elif "entry" in tool_result:
                            entries.append(tool_result["entry"])
                except json.JSONDecodeError:
                    pass

            # Get the final AI message
            if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage":
                # Only use messages without tool calls as final response
                if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                    if msg.content:
                        final_message = msg.content

        # If no final message found, use last message
        if final_message == "I processed your request." and messages:
            if hasattr(messages[-1], "content"):
                final_message = messages[-1].content

        return {
            "message": final_message,
            "entries": entries,  # All collected entries (agent will naturally filter via prompt)
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

    async def _persist_tool_observations(
        self, chat_id: str, tool_calls: List[Dict[str, Any]]
    ) -> None:
        """Persist tool outputs to Redis for trusted reuse."""
        if not tool_calls:
            return

        for tool_call in tool_calls:
            output = tool_call.get("output")
            if not isinstance(output, dict):
                continue

            tool_name = tool_call.get("name", "unknown")
            sanitized_output = self._sanitize_tool_output(tool_name, output)
            if not sanitized_output:
                continue

            sanitized_args = self._sanitize_tool_args(tool_call.get("input"))

            observation = ToolObservation(
                tool_name=tool_name,
                payload={
                    "args": sanitized_args,
                    "result": sanitized_output,
                },
            )

            await self.redis.store_tool_observation(chat_id, observation)

    def _sanitize_tool_args(self, args: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Strip sensitive or unnecessary fields from tool args before storage."""
        if not isinstance(args, dict):
            return {}
        return {
            key: value
            for key, value in args.items()
            if key not in {"user_id"}
        }

    def _sanitize_tool_output(
        self, tool_name: str, output: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Retain only trustworthy portions of tool output for future use."""
        if not output.get("success"):
            return None

        if tool_name in {"create_entry", "update_entry"}:
            entry = output.get("entry")
            if isinstance(entry, dict) and entry.get("id"):
                sanitized_entry = self._filter_entry(entry)
                return {"entry": sanitized_entry}

        return None

    def _filter_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Extract a safe subset of entry fields and add an alias for reference."""
        allowed_fields = {
            "id",
            "description",
            "direction",
            "entry_date",
            "category_id",
            "amount_cents",
            "amount",
        }
        sanitized = {
            key: entry[key]
            for key in allowed_fields
            if key in entry
        }

        amount = sanitized.get("amount")
        if amount is None and "amount_cents" in sanitized:
            try:
                sanitized["amount"] = float(sanitized["amount_cents"]) / 100
            except (TypeError, ValueError):
                pass

        sanitized["alias"] = self._make_entry_alias(entry["id"])
        sanitized["recorded_at"] = entry.get("entry_date")
        return sanitized

    def _make_entry_alias(self, entry_id: str) -> str:
        """Create a deterministic alias for an entry ID that hides the raw UUID."""
        digest = hashlib.sha256(entry_id.encode("utf-8")).hexdigest()
        return f"entry_ref_{digest[:8]}"

    def _render_private_context(
        self, observations: List[ToolObservation]
    ) -> Optional[str]:
        """Render private memory for the agent while warning against leaking IDs."""
        if not observations:
            return None

        lines = [
            "PRIVATE_TOOL_CONTEXT:",
            "Use these internal references for tool calls only.",
            "Do not reveal entry IDs or aliases to the user.",
        ]

        for observation in observations[-5:]:
            payload = observation.payload or {}
            result = payload.get("result") or {}
            entry = result.get("entry")
            if not isinstance(entry, dict):
                continue

            alias = entry.get("alias", "entry_ref")
            entry_id = entry.get("id")
            description = entry.get("description", "No description")
            direction = entry.get("direction", "unknown")
            entry_date = entry.get("entry_date") or entry.get("recorded_at") or "unknown date"
            amount = entry.get("amount")

            amount_str = f"${amount:.2f}" if isinstance(amount, (int, float)) else "unknown amount"

            lines.append(
                f"- {alias}: {direction} {amount_str} for \"{description}\" on {entry_date} (entry_id={entry_id})"
            )

        if len(lines) <= 3:
            return None

        return "\n".join(lines)

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
