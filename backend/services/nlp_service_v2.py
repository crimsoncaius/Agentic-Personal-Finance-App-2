"""
LangGraph-based NLP service V2 for Expense Tracker MVP
Unified approach: single LLM call for parsing + operation detection, then response generation
"""

import json
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union
from uuid import uuid4

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from pydantic import ValidationError

# Try both import paths to handle running from different directories
try:
    # First try direct imports (when running from backend directory)
    from database.connection import db_connection
    from models.schemas import (
        CategoryResponse,
        EntryDirection,
        ParsedData,
        QueryParams,
        RouterDecision,
        ParseError,
        ErrorDetail,
    )
    from services.prompt_manager import PromptManager
    from services.langfuse_service_v2 import langfuse_service_v2 as langfuse_service
    from services.redis_service import redis_service
except ImportError:
    # If running from project root, try backend.*
    from backend.database.connection import db_connection
    from backend.models.schemas import (
        CategoryResponse,
        EntryDirection,
        ParsedData,
        QueryParams,
        RouterDecision,
        ParseError,
        ErrorDetail,
    )
    from backend.services.prompt_manager import PromptManager
    from backend.services.langfuse_service_v2 import (
        langfuse_service_v2 as langfuse_service,
    )
    from backend.services.redis_service import redis_service


class NLPServiceV2:
    """Unified LangGraph-based NLP service for processing natural language queries"""

    def __init__(self, openai_api_key: str = None):
        """Initialize the NLP service with OpenAI API key"""
        # Import configuration
        try:
            from config.nlp import nlp_config
            from config.settings import settings
        except ImportError:
            from backend.config.nlp import nlp_config
            from backend.config.settings import settings

        # Use provided key or fall back to config
        api_key = openai_api_key or settings.openai_api_key

        # Set the API key in environment for LangChain
        import os

        os.environ["OPENAI_API_KEY"] = api_key

        # Use Langfuse-enabled OpenAI client for observability
        self.llm = langfuse_service.openai_client
        self.langfuse = langfuse_service

        self.db = db_connection
        self._categories_cache: Optional[List[CategoryResponse]] = None
        self.prompt_manager = PromptManager()
        self.nlp_config = nlp_config
        self._current_user_id: Optional[str] = (
            None  # Store current user_id for request context
        )

        # Redis service for conversation memory
        self.redis = redis_service

    async def process_query(
        self,
        text: str,
        user_id: str = None,
        session_id: str = None,
        chat_id: str = None,
    ) -> Union[Dict, ParseError]:
        """
        Process a natural language query and return the result

        Args:
            text: Natural language input from user
            user_id: Optional user identifier for tracing
            session_id: Optional session identifier for tracing
            chat_id: Optional chat identifier for conversation context

        Returns:
            Dictionary with operation result, ParseError, and chat_id
        """
        # Store user_id in instance for access in workflow nodes
        self._current_user_id = user_id

        # Generate chat_id if not provided
        if not chat_id:
            chat_id = str(uuid4())

        # Create main trace for the entire query processing
        async with self.langfuse.trace_operation(
            name="nlp_query_processing_v2",
            user_id=user_id,
            session_id=session_id,
            input_data={"text": text},
            tags=["nlp", "query_processing", "v2"],
        ) as trace_id:
            try:
                start_time = time.time()

                # Retrieve conversation history from Redis
                conversation_history = await self.redis.get_conversation_history(
                    chat_id
                )

                # Create the LangGraph workflow
                workflow = self._create_workflow()

                # Execute the workflow with tracing and conversation history
                result = await workflow.ainvoke(
                    {
                        "text": text,
                        "trace_id": trace_id,
                        "chat_id": chat_id,
                        "conversation_history": conversation_history,
                    }
                )

                # Calculate total processing time
                total_duration = time.time() - start_time

                # Track performance metrics
                self.langfuse.track_performance_metrics_v2(
                    operation="query_processing",
                    trace_id=trace_id,
                    metrics={
                        "total_duration": total_duration,
                        "operation": result.get("operation", "unknown"),
                        "success": "error" not in result or result["error"] is None,
                        "text_length": len(text),
                    },
                )

                # Check if there's an error in the result
                if "error" in result and result["error"] is not None:
                    # Don't treat ambiguous errors as failures - they're successful responses
                    if (
                        hasattr(result["error"], "code")
                        and result["error"].code == "ambiguous"
                    ):
                        assistant_message = result.get(
                            "message",
                            "I'm not sure what you'd like to do. Could you please clarify?",
                        )

                        # Store messages in Redis for conversation continuity
                        await self.redis.store_message(chat_id, "user", text)
                        await self.redis.store_message(
                            chat_id, "assistant", assistant_message
                        )

                        # Return the success response with the generated message
                        return {
                            "operation": result.get("operation", "unsure"),
                            "result": result.get("result", []),
                            "message": assistant_message,
                            "chat_id": chat_id,
                        }
                    else:
                        # Return actual errors (don't store in conversation)
                        return result["error"]

                # Store successful conversation in Redis
                assistant_message = result.get(
                    "message", "Operation completed successfully"
                )
                await self.redis.store_message(chat_id, "user", text)
                await self.redis.store_message(chat_id, "assistant", assistant_message)

                # Return the result in the expected format
                return {
                    "operation": result.get("operation", "read"),
                    "result": result.get("result", []),
                    "message": assistant_message,
                    "chat_id": chat_id,
                }

            except Exception as e:
                # Track error metrics
                self.langfuse.track_performance_metrics_v2(
                    operation="query_processing",
                    trace_id=trace_id,
                    metrics={
                        "success": False,
                        "error": str(e),
                        "text_length": len(text),
                    },
                )

                return ParseError(
                    code="parsing_failed",
                    message=f"Failed to process query: {str(e)}",
                    details=ErrorDetail(suggestions=["Try rephrasing your request"]),
                )

    def _create_workflow(self) -> StateGraph:
        """Create the simplified LangGraph workflow with Parse and Response nodes"""

        # Define the state type as a TypedDict for LangGraph
        from typing import TypedDict

        class WorkflowState(TypedDict):
            text: str
            operation: Optional[str]
            data: Optional[Dict]
            result: Optional[Union[Dict, List]]
            error: Optional[ParseError]
            message: Optional[str]
            trace_id: Optional[str]
            chat_id: Optional[str]
            conversation_history: Optional[List]

        # Create the graph
        workflow = StateGraph(WorkflowState)

        # Add nodes
        workflow.add_node("parse", self._parse_node)
        workflow.add_node("read_response", self._read_response_node)
        workflow.add_node("write_response", self._write_response_node)
        workflow.add_node("unsure_response", self._unsure_response_node)

        # Add conditional edges from parse
        workflow.add_conditional_edges(
            "parse",
            lambda state: state.get("operation", "read"),
            {
                "read": "read_response",
                "write": "write_response",
                "unsure": "unsure_response",
            },
        )
        workflow.add_edge("read_response", END)
        workflow.add_edge("write_response", END)
        workflow.add_edge("unsure_response", END)

        # Set entry point
        workflow.set_entry_point("parse")

        return workflow.compile()

    def get_workflow_structure(self) -> Dict:
        """Get the actual workflow structure from LangGraph"""
        workflow = self._create_workflow()
        graph = workflow.get_graph()

        # Extract edge information with proper error handling
        edges = []
        for edge in graph.edges:
            edge_info = {"from": edge.source, "to": edge.target}
            # Add type information if available
            if hasattr(edge, "type"):
                edge_info["type"] = edge.type
            else:
                # Determine type based on edge properties
                if hasattr(edge, "condition") and edge.condition:
                    edge_info["type"] = "conditional"
                else:
                    edge_info["type"] = "direct"
            edges.append(edge_info)

        return {
            "nodes": list(graph.nodes.keys()),
            "edges": edges,
            "entry_point": "__start__",
            "end_points": ["__end__"],
        }

    async def _parse_node(self, state: Dict) -> Dict:
        """Unified parse node that handles both operation detection and data extraction"""
        trace_id = state.get("trace_id")

        # Debug: Check if user_id is in state
        print(f"DEBUG _parse_node: user_id in state = {state.get('user_id')}")
        print(f"DEBUG _parse_node: state keys = {list(state.keys())}")

        # Track parse node execution
        async with self.langfuse.span_operation(
            name="parse_node", trace_id=trace_id, input_data={"text": state["text"]}
        ) as span_id:
            try:
                start_time = time.time()

                # Get categories for context
                categories = await self._get_categories()
                category_list = [f"{cat.id} ({cat.name})" for cat in categories]

                # Get current date for context
                current_date = date.today()

                # Get conversation history from state
                conversation_history = state.get("conversation_history", [])

                # Convert ChatMessage objects to dicts for prompt manager
                history_dicts = []
                if conversation_history:
                    for msg in conversation_history:
                        if hasattr(msg, "to_dict"):
                            history_dicts.append(msg.to_dict())
                        elif hasattr(msg, "__dict__"):
                            history_dicts.append(
                                {
                                    "role": msg.role,
                                    "content": msg.content,
                                    "timestamp": msg.timestamp,
                                }
                            )

                # Generate unified prompt with conversation history
                prompt = self.prompt_manager.generate_unified_prompt(
                    state["text"], current_date, category_list, history_dicts
                )

                # Use Langfuse-tracked LLM call for unified parsing
                response, generation_id = await self.langfuse.track_unified_llm_call(
                    name="unified_parse",
                    model="gpt-4.1-nano",
                    messages=[{"role": "user", "content": prompt}],
                    trace_id=trace_id,
                    parent_id=span_id,
                    temperature=0.1,
                    operation_type="unified_parse",
                )
                content = response.choices[0].message.content.strip()

                # Debug: Log the LLM response
                print(f"DEBUG: LLM Response: {content[:200]}...")  # First 200 chars

                try:
                    parsed_response = json.loads(content)

                    # Validate the response structure
                    if (
                        "operation" not in parsed_response
                        or "data" not in parsed_response
                    ):
                        raise ValueError("Invalid response structure")

                    operation = parsed_response["operation"].lower()
                    data = parsed_response["data"]
                    message = parsed_response.get("message", "")

                    # Update state with parsed information
                    state["operation"] = operation
                    state["data"] = data
                    state["message"] = message
                    # Note: user_id should already be in state from initial invoke

                    # Process based on operation type
                    if operation == "read":
                        # Validate and execute read query
                        query_params = QueryParams(**data)
                        query_start = time.time()
                        # Get user_id from instance (stored in process_query)
                        current_user_id = self._current_user_id
                        if not current_user_id:
                            raise ValueError("user_id is required for read operations")
                        entries = await self._execute_read_query(
                            query_params, current_user_id, trace_id
                        )
                        query_duration = time.time() - query_start

                        # Track database operation
                        self.langfuse.track_database_operation(
                            operation="select",
                            table="entry",
                            trace_id=trace_id,
                            parent_id=span_id,
                            query_params=(
                                data.model_dump()
                                if hasattr(data, "model_dump")
                                else (
                                    data.dict() if hasattr(data, "dict") else str(data)
                                )
                            ),
                            result_count=len(entries),
                            duration=query_duration,
                        )
                        state["result"] = entries

                    elif operation == "write":
                        # Validate and create entry
                        # Convert date string to date object if present
                        if "date" in data:
                            data["entry_date"] = datetime.strptime(
                                data["date"], "%Y-%m-%d"
                            ).date()
                            del data["date"]

                        validated_data = ParsedData(**data)
                        entry_start = time.time()
                        # Get user_id from instance (stored in process_query)
                        current_user_id = self._current_user_id
                        if not current_user_id:
                            raise ValueError("user_id is required for creating entries")
                        entry = await self._create_entry(
                            validated_data, current_user_id, trace_id
                        )
                        entry_duration = time.time() - entry_start

                        # Track database operation
                        self.langfuse.track_database_operation(
                            operation="insert",
                            table="entry",
                            trace_id=trace_id,
                            parent_id=span_id,
                            query_params={
                                "amount": validated_data.amount,
                                "direction": validated_data.direction.value,
                            },
                            result_count=1,
                            duration=entry_duration,
                        )
                        state["result"] = entry

                    elif operation == "unsure":
                        # Handle unsure case
                        state["result"] = data.get("suggestions", [])

                    else:
                        raise ValueError(f"Unknown operation: {operation}")

                    # Track parse operation success
                    duration = time.time() - start_time
                    self.langfuse.track_parse_operation(
                        trace_id=trace_id,
                        parent_id=span_id,
                        input_text=state["text"],
                        parsed_data=data,
                        operation=operation,
                        duration=duration,
                    )

                    # Track workflow node performance
                    self.langfuse.track_workflow_node_v2(
                        node_name="parse",
                        trace_id=trace_id,
                        parent_id=span_id,
                        input_data={"text": state["text"]},
                        output_data={
                            "operation": operation,
                            "data_keys": list(data.keys()),
                        },
                        duration=duration,
                        operation_type="unified_parse",
                    )

                    return state

                except (json.JSONDecodeError, ValidationError, ValueError) as e:
                    duration = time.time() - start_time

                    # Debug: Log the parsing error
                    print(f"DEBUG: JSON Parse Error: {str(e)}")
                    print(f"DEBUG: LLM returned: {content}")

                    self.langfuse.track_parse_operation(
                        trace_id=trace_id,
                        parent_id=span_id,
                        input_text=state["text"],
                        parsed_data=None,
                        operation=None,
                        duration=duration,
                        error=f"Parse error: {str(e)}",
                    )

                    self.langfuse.track_workflow_node_v2(
                        node_name="parse",
                        trace_id=trace_id,
                        parent_id=span_id,
                        input_data={"text": state["text"]},
                        output_data=None,
                        duration=duration,
                        error=f"Parse error: {str(e)}",
                        operation_type="unified_parse",
                    )

                    state["error"] = ParseError(
                        code="parsing_failed",
                        message=f"Failed to parse response from LLM: {str(e)}",
                        details=ErrorDetail(
                            suggestions=["Try rephrasing your request"]
                        ),
                    )
                    return state

            except Exception as e:
                duration = time.time() - start_time

                # Log the actual error for debugging
                import traceback

                print(f"ERROR in _parse_node: {str(e)}")
                print(f"ERROR type: {type(e).__name__}")
                print(f"Traceback: {traceback.format_exc()}")

                self.langfuse.track_parse_operation(
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_text=state["text"],
                    parsed_data=None,
                    operation=None,
                    duration=duration,
                    error=str(e),
                )

                self.langfuse.track_workflow_node_v2(
                    node_name="parse",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"text": state["text"]},
                    output_data=None,
                    duration=duration,
                    error=str(e),
                    operation_type="unified_parse",
                )

                state["error"] = ParseError(
                    code="parsing_failed",
                    message=f"Failed to process query: {str(e)}",
                    details=ErrorDetail(suggestions=["Try rephrasing your request"]),
                )
                return state

    async def _read_response_node(self, state: Dict) -> Dict:
        """Generate user-friendly response for read operations"""
        trace_id = state.get("trace_id")

        # Check if result exists (error might have occurred in parse node)
        if "result" not in state:
            return state

        # Track read response node execution
        async with self.langfuse.span_operation(
            name="read_response_node",
            trace_id=trace_id,
            input_data={
                "operation": "read",
                "entries_count": len(state.get("result", [])),
            },
        ) as span_id:
            try:
                start_time = time.time()

                # Generate response using existing template
                response_prompt = self.prompt_manager.generate_read_response_prompt(
                    state["text"],
                    state["result"],
                    QueryParams(**state["data"]),
                    date.today(),
                )
                response_message = await self._call_llm_for_response(
                    response_prompt, trace_id, span_id
                )
                state["message"] = response_message

                # Track response operation
                duration = time.time() - start_time
                self.langfuse.track_response_operation(
                    response_type="read",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"entries_count": len(state.get("result", []))},
                    response_message=response_message,
                    duration=duration,
                )

                # Track workflow node performance
                self.langfuse.track_workflow_node_v2(
                    node_name="read_response",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"entries_count": len(state.get("result", []))},
                    output_data={"message_length": len(response_message)},
                    duration=duration,
                    operation_type="response_generation",
                )

                return state

            except Exception as e:
                duration = time.time() - start_time
                # Fallback to simple message
                state["message"] = (
                    f"Found {len(state['result'])} entries matching your criteria."
                )

                self.langfuse.track_response_operation(
                    response_type="read",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"entries_count": len(state.get("result", []))},
                    response_message=state["message"],
                    duration=duration,
                    error=str(e),
                )

                self.langfuse.track_workflow_node_v2(
                    node_name="read_response",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"entries_count": len(state.get("result", []))},
                    output_data={"fallback_message": state["message"]},
                    duration=duration,
                    error=str(e),
                    operation_type="response_generation",
                )

                return state

    async def _write_response_node(self, state: Dict) -> Dict:
        """Generate user-friendly response for write operations"""
        trace_id = state.get("trace_id")

        # Check if result exists (error might have occurred in parse node)
        if "result" not in state:
            return state

        # Track write response node execution
        async with self.langfuse.span_operation(
            name="write_response_node",
            trace_id=trace_id,
            input_data={
                "operation": "write",
                "entry_id": state.get("result", {}).get("id"),
            },
        ) as span_id:
            try:
                start_time = time.time()

                # Generate response using existing template
                response_prompt = self.prompt_manager.generate_write_response_prompt(
                    state["text"], state["result"], date.today()
                )
                response_message = await self._call_llm_for_response(
                    response_prompt, trace_id, span_id
                )
                state["message"] = response_message

                # Track response operation
                duration = time.time() - start_time
                self.langfuse.track_response_operation(
                    response_type="write",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"entry_id": state.get("result", {}).get("id")},
                    response_message=response_message,
                    duration=duration,
                )

                # Track workflow node performance
                self.langfuse.track_workflow_node_v2(
                    node_name="write_response",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"entry_id": state.get("result", {}).get("id")},
                    output_data={"message_length": len(response_message)},
                    duration=duration,
                    operation_type="response_generation",
                )

                return state

            except Exception as e:
                duration = time.time() - start_time
                # Fallback to simple message
                state["message"] = (
                    f"Successfully created entry: {state['result'].get('description', 'New entry')}"
                )

                self.langfuse.track_response_operation(
                    response_type="write",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"entry_id": state.get("result", {}).get("id")},
                    response_message=state["message"],
                    duration=duration,
                    error=str(e),
                )

                self.langfuse.track_workflow_node_v2(
                    node_name="write_response",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"entry_id": state.get("result", {}).get("id")},
                    output_data={"fallback_message": state["message"]},
                    duration=duration,
                    error=str(e),
                    operation_type="response_generation",
                )

                return state

    async def _unsure_response_node(self, state: Dict) -> Dict:
        """Generate user-friendly response for unsure operations"""
        trace_id = state.get("trace_id")

        # Check if result exists (error might have occurred in parse node)
        if "result" not in state:
            state["result"] = []  # Set empty suggestions if none exist

        # Track unsure response node execution
        async with self.langfuse.span_operation(
            name="unsure_response_node",
            trace_id=trace_id,
            input_data={
                "operation": "unsure",
                "suggestions_count": len(state.get("result", [])),
            },
        ) as span_id:
            try:
                start_time = time.time()

                # Generate response using existing template
                response_prompt = self.prompt_manager.generate_unsure_response_prompt(
                    state["text"], date.today()
                )
                response_message = await self._call_llm_for_response(
                    response_prompt, trace_id, span_id
                )
                state["message"] = response_message

                # Track response operation
                duration = time.time() - start_time
                self.langfuse.track_response_operation(
                    response_type="unsure",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"suggestions_count": len(state.get("result", []))},
                    response_message=response_message,
                    duration=duration,
                )

                # Track workflow node performance
                self.langfuse.track_workflow_node_v2(
                    node_name="unsure_response",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"suggestions_count": len(state.get("result", []))},
                    output_data={"message_length": len(response_message)},
                    duration=duration,
                    operation_type="response_generation",
                )

                # Don't set error - "unsure" is a valid operation response
                # The error handling in process_query will check for "ambiguous" code
                return state

            except Exception as e:
                duration = time.time() - start_time
                # Fallback to simple message
                state["message"] = (
                    "I'm not sure what you'd like to do. Could you please clarify?"
                )

                self.langfuse.track_response_operation(
                    response_type="unsure",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"suggestions_count": len(state.get("result", []))},
                    response_message=state["message"],
                    duration=duration,
                    error=str(e),
                )

                self.langfuse.track_workflow_node_v2(
                    node_name="unsure_response",
                    trace_id=trace_id,
                    parent_id=span_id,
                    input_data={"suggestions_count": len(state.get("result", []))},
                    output_data={"fallback_message": state["message"]},
                    duration=duration,
                    error=str(e),
                    operation_type="response_generation",
                )

                # Don't set error - "unsure" is a valid operation response
                return state

    async def _get_categories(self) -> List[CategoryResponse]:
        """Get categories from database with caching"""
        if self._categories_cache is None:
            try:
                result = (
                    self.db.client.table("category").select("id, name, type").execute()
                )
                self._categories_cache = [
                    CategoryResponse(**row) for row in result.data
                ]
            except Exception as e:
                # Return default categories if database fails
                from uuid import uuid4

                self._categories_cache = [
                    CategoryResponse(
                        id=uuid4(), name="Miscellaneous (Expense)", type="expense"
                    ),
                    CategoryResponse(
                        id=uuid4(), name="Other Income (Income)", type="income"
                    ),
                ]
        return self._categories_cache

    async def _execute_read_query(
        self, params: QueryParams, user_id: str, trace_id: str = None
    ) -> List[Dict]:
        """Execute read query with given parameters"""
        try:
            query = self.db.client.table("entry").select(
                """
                id, amount_cents, direction, entry_date, description, source, parse_confidence, created_at,
                category:category_id(id, name, type)
            """
            )

            # Filter by user_id first (most important)
            query = query.eq("user_id", str(user_id))

            # Apply filters
            if params.date_from:
                query = query.gte("entry_date", params.date_from.isoformat())
            if params.date_to:
                query = query.lte("entry_date", params.date_to.isoformat())
            if params.direction:
                query = query.eq("direction", params.direction.value)
            if params.category_id:
                query = query.eq("category_id", str(params.category_id))
            if params.amount_min:
                query = query.gte("amount_cents", int(params.amount_min * 100))
            if params.amount_max:
                query = query.lte("amount_cents", int(params.amount_max * 100))
            if params.q:
                query = query.ilike("description", f"%{params.q}%")

            # Apply sorting
            if params.sort == "entry_date.desc":
                query = query.order("entry_date", desc=True)
            else:
                query = query.order("created_at", desc=True)

            # Apply pagination
            query = query.range(params.offset, params.offset + params.limit - 1)

            result = query.execute()

            # Convert to response format
            entries = []
            for row in result.data:
                entry = {
                    "id": row["id"],
                    "amount": Decimal(row["amount_cents"]) / 100,
                    "direction": row["direction"],
                    "entry_date": row["entry_date"],
                    "description": row["description"],
                    "source": row["source"],
                    "parse_confidence": row["parse_confidence"],
                    "created_at": row["created_at"],
                }

                if row.get("category"):
                    entry["category"] = {
                        "id": row["category"]["id"],
                        "name": row["category"]["name"],
                        "type": row["category"]["type"],
                    }

                entries.append(entry)

            return entries

        except Exception as e:
            raise Exception(f"Failed to execute read query: {str(e)}")

    async def _create_entry(
        self, data: ParsedData, user_id: str, trace_id: str = None
    ) -> Dict:
        """Create a new entry from parsed data"""
        try:
            # Find category by name
            categories = await self._get_categories()
            category_id = None

            for cat in categories:
                if (
                    cat.name.lower() == data.category.lower()
                    if data.category
                    else False
                ):
                    category_id = cat.id
                    break

            # Use default category if not found
            if not category_id:
                if data.direction == EntryDirection.EXPENSE:
                    category_id = next(
                        (cat.id for cat in categories if cat.type == "expense"), None
                    )
                else:
                    category_id = next(
                        (cat.id for cat in categories if cat.type == "income"), None
                    )

            # Create entry data with parse confidence
            # For now, set a default confidence score of 0.8 for NLP entries
            # TODO: Implement actual confidence calculation based on LLM response
            entry_data = {
                "amount_cents": int(data.amount * 100),
                "direction": data.direction.value,
                "entry_date": data.entry_date.isoformat(),
                "category_id": str(category_id) if category_id else None,
                "description": data.description,
                "source": "nlp",
                "parse_confidence": 0.8,  # Default confidence score
                "user_id": str(user_id),
            }

            # Insert into database
            result = self.db.client.table("entry").insert(entry_data).execute()

            if not result.data:
                raise Exception("Failed to create entry")

            # Return the created entry
            created_entry = result.data[0]
            return {
                "id": created_entry["id"],
                "amount": data.amount,
                "direction": data.direction.value,
                "entry_date": data.entry_date.isoformat(),
                "category": {"id": category_id, "name": data.category or "Default"},
                "description": data.description,
                "source": "nlp",
                "parse_confidence": 0.8,  # Default confidence score
                "created_at": created_entry["created_at"],
            }

        except Exception as e:
            raise Exception(f"Failed to create entry: {str(e)}")

    async def _call_llm_for_response(
        self, prompt: str, trace_id: str = None, parent_id: str = None
    ) -> str:
        """Call LLM to generate a user-friendly response"""
        try:
            response, generation_id = await self.langfuse.track_response_llm_call(
                name="response_generation",
                model="gpt-4.1-nano",
                messages=[{"role": "user", "content": prompt}],
                trace_id=trace_id,
                parent_id=parent_id,
                temperature=0.7,  # Slightly higher temperature for more natural responses
                response_type="user_friendly",
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            # Fallback to a simple response if LLM call fails
            return "Operation completed successfully."
