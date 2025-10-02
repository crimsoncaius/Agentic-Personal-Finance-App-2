"""
LangGraph-based NLP service for Expense Tracker MVP
Handles natural language processing for both read and write operations
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


class NLPService:
    """LangGraph-based NLP service for processing natural language queries"""

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
                return result["error"]

            # Return the result in the expected format
            return {
                "operation": result.get("operation", "read"),
                "result": result.get("result", []),
            }

        except Exception as e:
            return ParseError(
                code="parsing_failed",
                message=f"Failed to process query: {str(e)}",
                details=ErrorDetail(suggestions=["Try rephrasing your request"]),
            )

    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow with Router, Read, and Write nodes"""

        # Define the state type as a TypedDict for LangGraph
        from typing import TypedDict

        class WorkflowState(TypedDict):
            text: str
            operation: Optional[str]
            result: Optional[Union[Dict, List]]
            error: Optional[ParseError]

        # Create the graph
        workflow = StateGraph(WorkflowState)

        # Add nodes
        workflow.add_node("router", self._router_node)
        workflow.add_node("read", self._read_node)
        workflow.add_node("write", self._write_node)
        workflow.add_node("unsure", self._unsure_node)

        # Add conditional edges from router
        workflow.add_conditional_edges(
            "router",
            lambda state: state.get("operation", "read"),
            {"read": "read", "write": "write", "unsure": "unsure"},
        )
        workflow.add_edge("read", END)
        workflow.add_edge("write", END)
        workflow.add_edge("unsure", END)

        # Set entry point
        workflow.set_entry_point("router")

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

    async def _router_node(self, state: Dict) -> Dict:
        """Router node that determines if input is READ or WRITE operation"""
        try:
            # Generate prompt using template
            prompt = self.prompt_manager.generate_router_prompt(state["text"])

            # Use direct OpenAI client
            response = self.llm.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            operation = response.choices[0].message.content.strip().upper()

            if operation not in ["READ", "WRITE", "UNSURE"]:
                operation = "UNSURE"  # Default to UNSURE for invalid responses

            # Update the state with the operation
            state["operation"] = operation.lower()
            return state

        except Exception as e:
            state["error"] = ParseError(
                code="parsing_failed",
                message="Failed to determine operation type",
                details=ErrorDetail(suggestions=["Try rephrasing your request"]),
            )
            return state

    async def _read_node(self, state: Dict) -> Dict:
        """Read node that generates query parameters from natural language"""
        try:
            # Get categories for context
            categories = await self._get_categories()
            category_list = [f"{cat.id} ({cat.name})" for cat in categories]

            # Get current date for context
            current_date = date.today()

            # Generate prompt using template
            prompt = self.prompt_manager.generate_read_prompt(
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
                query_params = json.loads(content)
                # Validate query parameters
                validated_params = QueryParams(**query_params)

                # Execute the query
                entries = await self._execute_read_query(validated_params)

                state["result"] = entries
                return state

            except (json.JSONDecodeError, ValidationError) as e:
                state["error"] = ParseError(
                    code="parsing_failed",
                    message="Failed to parse query parameters",
                    details=ErrorDetail(suggestions=["Try rephrasing your request"]),
                )
                return state

        except Exception as e:
            state["error"] = ParseError(
                code="parsing_failed",
                message="Failed to process read request",
                details=ErrorDetail(suggestions=["Try rephrasing your request"]),
            )
            return state

    async def _write_node(self, state: Dict) -> Dict:
        """Write node that extracts structured data from natural language"""
        try:
            # Get categories for context
            categories = await self._get_categories()
            category_list = [f"{cat.name} ({cat.type})" for cat in categories]

            # Get current date for context
            current_date = date.today()

            # Generate prompt using template
            prompt = self.prompt_manager.generate_write_prompt(
                state["text"], category_list, current_date
            )

            # Use direct OpenAI client
            response = self.llm.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            content = response.choices[0].message.content.strip()

            try:
                parsed_data = json.loads(content)

                # Convert date string to date object
                if "date" in parsed_data:
                    parsed_data["entry_date"] = datetime.strptime(
                        parsed_data["date"], "%Y-%m-%d"
                    ).date()
                    del parsed_data["date"]

                validated_data = ParsedData(**parsed_data)

                # Create the entry
                entry = await self._create_entry(validated_data)

                state["result"] = entry
                return state

            except (json.JSONDecodeError, ValidationError) as e:
                state["error"] = ParseError(
                    code="missing_fields",
                    message="Could not extract required fields from your input",
                    details=ErrorDetail(
                        missing_fields=["amount", "direction", "date"],
                        suggestions=["Try: 'spent $20 on coffee yesterday'"],
                    ),
                )
                return state

        except Exception as e:
            state["error"] = ParseError(
                code="parsing_failed",
                message="Failed to process write request",
                details=ErrorDetail(suggestions=["Try rephrasing your request"]),
            )
            return state

    async def _unsure_node(self, state: Dict) -> Dict:
        """Unsure node that handles ambiguous routing cases"""
        try:
            # For unsure cases, we'll provide helpful suggestions to the user
            # and ask them to clarify their intent
            suggestions = [
                "To view your expenses, try: 'show my recent expenses' or 'what did I spend this month?'",
                "To add an expense, try: 'spent $20 on coffee' or 'add $50 for groceries'",
                "To add income, try: 'earned $1000 salary' or 'received $200 gift'",
                "To view income, try: 'show my income' or 'what did I earn this month?'",
            ]

            state["error"] = ParseError(
                code="ambiguous",
                message="I'm not sure if you want to view existing entries or create a new one. Could you please clarify?",
                details=ErrorDetail(suggestions=suggestions),
            )
            return state

        except Exception as e:
            state["error"] = ParseError(
                code="parsing_failed",
                message="Failed to process ambiguous request",
                details=ErrorDetail(suggestions=["Try rephrasing your request"]),
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
