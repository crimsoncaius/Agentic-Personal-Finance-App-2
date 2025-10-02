"""
LangGraph-based NLP service V2 for Expense Tracker MVP
Unified approach: single LLM call for parsing + operation detection, then response generation
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from pydantic import ValidationError

# Try both import paths to handle running from different directories
try:
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

        # Use OpenAI client directly to avoid LangChain/Pydantic compatibility issues
        try:
            from openai import OpenAI as OpenAIClient

            self.llm = OpenAIClient(api_key=api_key)
        except ImportError:
            raise Exception("OpenAI client not available")

        self.db = db_connection
        self._categories_cache: Optional[List[CategoryResponse]] = None
        self.prompt_manager = PromptManager()
        self.nlp_config = nlp_config

    async def process_query(self, text: str) -> Union[Dict, ParseError]:
        """
        Process a natural language query and return the result

        Args:
            text: Natural language input from user

        Returns:
            Dictionary with operation result or ParseError
        """
        try:
            # Create the LangGraph workflow
            workflow = self._create_workflow()

            # Execute the workflow
            result = await workflow.ainvoke({"text": text})

            # Check if there's an error in the result
            if "error" in result and result["error"] is not None:
                # Don't treat ambiguous errors as failures - they're successful responses
                if (
                    hasattr(result["error"], "code")
                    and result["error"].code == "ambiguous"
                ):
                    # Return the success response with the generated message
                    return {
                        "operation": result.get("operation", "unsure"),
                        "result": result.get("result", []),
                        "message": result.get(
                            "message",
                            "I'm not sure what you'd like to do. Could you please clarify?",
                        ),
                    }
                else:
                    # Return actual errors
                    return result["error"]

            # Return the result in the expected format
            return {
                "operation": result.get("operation", "read"),
                "result": result.get("result", []),
                "message": result.get("message", "Operation completed successfully"),
            }

        except Exception as e:
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

    def visualize_workflow(self) -> str:
        """Get the actual Mermaid diagram from LangGraph"""
        workflow = self._create_workflow()
        return workflow.get_graph().draw_mermaid()

    async def _parse_node(self, state: Dict) -> Dict:
        """Unified parse node that handles both operation detection and data extraction"""
        try:
            # Get categories for context
            categories = await self._get_categories()
            category_list = [f"{cat.id} ({cat.name})" for cat in categories]

            # Get current date for context
            current_date = date.today()

            # Generate unified prompt
            prompt = self.prompt_manager.generate_unified_prompt(
                state["text"], current_date, category_list
            )

            # Use direct OpenAI client
            response = self.llm.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            content = response.choices[0].message.content.strip()

            try:
                parsed_response = json.loads(content)

                # Validate the response structure
                if "operation" not in parsed_response or "data" not in parsed_response:
                    raise ValueError("Invalid response structure")

                operation = parsed_response["operation"].lower()
                data = parsed_response["data"]
                message = parsed_response.get("message", "")

                # Update state with parsed information
                state["operation"] = operation
                state["data"] = data
                state["message"] = message

                # Process based on operation type
                if operation == "read":
                    # Validate and execute read query
                    query_params = QueryParams(**data)
                    entries = await self._execute_read_query(query_params)
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
                    entry = await self._create_entry(validated_data)
                    state["result"] = entry

                elif operation == "unsure":
                    # Handle unsure case
                    state["result"] = data.get("suggestions", [])

                else:
                    raise ValueError(f"Unknown operation: {operation}")

                return state

            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                state["error"] = ParseError(
                    code="parsing_failed",
                    message="Failed to parse response from LLM",
                    details=ErrorDetail(suggestions=["Try rephrasing your request"]),
                )
                return state

        except Exception as e:
            state["error"] = ParseError(
                code="parsing_failed",
                message="Failed to process query",
                details=ErrorDetail(suggestions=["Try rephrasing your request"]),
            )
            return state

    async def _read_response_node(self, state: Dict) -> Dict:
        """Generate user-friendly response for read operations"""
        try:
            # Generate response using existing template
            response_prompt = self.prompt_manager.generate_read_response_prompt(
                state["text"],
                state["result"],
                QueryParams(**state["data"]),
                date.today(),
            )
            response_message = await self._call_llm_for_response(response_prompt)
            state["message"] = response_message
            return state

        except Exception as e:
            # Fallback to simple message
            state["message"] = (
                f"Found {len(state['result'])} entries matching your criteria."
            )
            return state

    async def _write_response_node(self, state: Dict) -> Dict:
        """Generate user-friendly response for write operations"""
        try:
            # Generate response using existing template
            response_prompt = self.prompt_manager.generate_write_response_prompt(
                state["text"], state["result"], date.today()
            )
            response_message = await self._call_llm_for_response(response_prompt)
            state["message"] = response_message
            return state

        except Exception as e:
            # Fallback to simple message
            state["message"] = (
                f"Successfully created entry: {state['result'].get('description', 'New entry')}"
            )
            return state

    async def _unsure_response_node(self, state: Dict) -> Dict:
        """Generate user-friendly response for unsure operations"""
        try:
            # Generate response using existing template
            response_prompt = self.prompt_manager.generate_unsure_response_prompt(
                state["text"], date.today()
            )
            response_message = await self._call_llm_for_response(response_prompt)
            state["message"] = response_message

            # Set up error for proper handling
            state["error"] = ParseError(
                code="ambiguous",
                message="I'm not sure if you want to view existing entries or create a new one. Could you please clarify?",
                details=ErrorDetail(suggestions=state["result"]),
            )
            return state

        except Exception as e:
            # Fallback to simple message
            state["message"] = (
                "I'm not sure what you'd like to do. Could you please clarify?"
            )
            state["error"] = ParseError(
                code="ambiguous",
                message="I'm not sure what you'd like to do. Could you please clarify?",
                details=ErrorDetail(suggestions=state["result"]),
            )
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

    async def _execute_read_query(self, params: QueryParams) -> List[Dict]:
        """Execute read query with given parameters"""
        try:
            query = self.db.client.table("entry").select(
                """
                id, amount_cents, direction, entry_date, description, source, parse_confidence, created_at,
                category:category_id(id, name, type)
            """
            )

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

    async def _create_entry(self, data: ParsedData) -> Dict:
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

    async def _call_llm_for_response(self, prompt: str) -> str:
        """Call LLM to generate a user-friendly response"""
        try:
            response = self.llm.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,  # Slightly higher temperature for more natural responses
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            # Fallback to a simple response if LLM call fails
            return "Operation completed successfully."
