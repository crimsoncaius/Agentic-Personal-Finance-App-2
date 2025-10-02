"""
Expandable Workflow Testing Script for NLP Service
Tracks and logs all pathways through LangGraph workflows
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from pydantic import ValidationError

# Load environment variables
try:
    from dotenv import load_dotenv

    # Try multiple locations for .env file
    script_dir = os.path.dirname(__file__)
    possible_env_paths = [
        os.path.join(script_dir, "..", "..", "..", ".env"),  # From backend/scripts/dev/
        os.path.join(script_dir, "..", "..", ".env"),  # From backend/scripts/
        os.path.join(script_dir, "..", ".env"),  # From backend/
        ".env",  # Current directory
    ]

    env_loaded = False
    for env_path in possible_env_paths:
        env_path = os.path.abspath(env_path)
        if os.path.exists(env_path):
            load_dotenv(env_path)
            env_loaded = True
            print(f"Loaded .env from: {env_path}")
            break

    if not env_loaded:
        print("Warning: No .env file found in expected locations")

except ImportError:
    print("Warning: python-dotenv not available, skipping .env loading")

# Add backend to path for imports
# Get the backend directory (2 levels up from this script: dev -> scripts -> backend)
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

# Try both import paths to handle running from different directories
try:
    from services.nlp_service import NLPService
    from database.connection import db_connection
    from models.schemas import ParseError, ErrorDetail
except ImportError:
    # If running from project root, try backend.services
    from backend.services.nlp_service import NLPService
    from backend.database.connection import db_connection
    from backend.models.schemas import ParseError, ErrorDetail


class TracedTable:
    """Wrapper around Supabase table operations to capture database calls"""

    def __init__(self, table, table_name: str, tracer):
        self.table = table
        self.table_name = table_name
        self.tracer = tracer

    def select(self, columns):
        """Capture SELECT operations"""
        if self.tracer:
            self.tracer._log_db_operation(
                "SELECT", self.table_name, {"columns": columns}
            )
        return TracedQuery(
            self.table.select(columns), self.table_name, self.tracer, "SELECT"
        )

    def insert(self, data):
        """Capture INSERT operations"""
        if self.tracer:
            self.tracer._log_db_operation("INSERT", self.table_name, {"data": data})
        return TracedQuery(
            self.table.insert(data), self.table_name, self.tracer, "INSERT"
        )

    def update(self, data):
        """Capture UPDATE operations"""
        if self.tracer:
            self.tracer._log_db_operation("UPDATE", self.table_name, {"data": data})
        return TracedQuery(
            self.table.update(data), self.table_name, self.tracer, "UPDATE"
        )

    def delete(self):
        """Capture DELETE operations"""
        if self.tracer:
            self.tracer._log_db_operation("DELETE", self.table_name, {})
        return TracedQuery(self.table.delete(), self.table_name, self.tracer, "DELETE")


class TracedQuery:
    """Wrapper around Supabase query operations to capture execution"""

    def __init__(self, query, table_name: str, tracer, operation: str):
        self.query = query
        self.table_name = table_name
        self.tracer = tracer
        self.operation = operation

    def execute(self):
        """Capture query execution"""
        start_time = datetime.now()

        try:
            result = self.query.execute()

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            if self.tracer:
                self.tracer._log_db_execution(
                    self.operation,
                    self.table_name,
                    execution_time,
                    len(result.data) if result.data else 0,
                    None,
                )

            return result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            if self.tracer:
                self.tracer._log_db_execution(
                    self.operation, self.table_name, execution_time, 0, str(e)
                )

            raise

    def __getattr__(self, name):
        """Delegate all other methods to the original query"""
        return getattr(self.query, name)


class TracedDatabaseConnection:
    """Wrapper around the database connection to capture all operations"""

    def __init__(self, db_connection, tracer):
        self.db = db_connection
        self.tracer = tracer
        # Preserve all original attributes
        self.client = TracedClient(db_connection.client, tracer)

        # Copy other attributes from original connection
        for attr_name in dir(db_connection):
            if not attr_name.startswith("_") and attr_name != "client":
                setattr(self, attr_name, getattr(db_connection, attr_name))


class TracedClient:
    """Wrapper around the Supabase client to capture table access"""

    def __init__(self, client, tracer):
        self.client = client
        self.tracer = tracer

        # Copy all attributes from original client
        for attr_name in dir(client):
            if not attr_name.startswith("_") and attr_name != "table":
                setattr(self, attr_name, getattr(client, attr_name))

    def table(self, table_name):
        """Capture table access"""
        return TracedTable(self.client.table(table_name), table_name, self.tracer)


class WorkflowTracer:
    """Generic workflow tracer that can track any LangGraph workflow"""

    def __init__(self, openai_api_key: str):
        self.nlp_service = NLPService(openai_api_key)
        self.traced_queries = []

        # DISABLED: Inject traced database connection
        # self.nlp_service.db = TracedDatabaseConnection(self.nlp_service.db, self)

        # Use original database connection without tracing
        # self.nlp_service.db remains unchanged

        # Track database operations per query
        self.current_db_operations = []

        # Track LLM calls per query
        self.current_llm_calls = []

    def _log_db_operation(self, operation: str, table: str, details: Dict[str, Any]):
        """Log a database operation start - DISABLED"""
        # Database tracing is disabled
        pass

    def _log_db_execution(
        self,
        operation: str,
        table: str,
        execution_time_ms: float,
        result_count: int,
        error: Optional[str],
    ):
        """Log a database operation completion - DISABLED"""
        # Database tracing is disabled
        pass

    def _log_llm_call(
        self,
        node_name: str,
        prompt: str,
        response: str,
        execution_time_ms: float,
        error: Optional[str] = None,
        call_type: str = "llm_call",
    ):
        """Log an LLM call or error log entry"""
        llm_call = {
            "node_name": node_name,
            "call_type": call_type,  # "llm_call" or "error_log"
            "prompt": prompt,
            "response": response,
            "execution_time_ms": execution_time_ms,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }
        self.current_llm_calls.append(llm_call)

    async def trace_query(self, query: str, query_id: str = None) -> Dict[str, Any]:
        """
        Trace a single query through the workflow and capture all details

        Args:
            query: The natural language query to process
            query_id: Optional identifier for the query

        Returns:
            Dictionary containing complete trace information
        """
        start_time = datetime.now()

        # Reset database operations and LLM calls for this query
        self.current_db_operations = []
        self.current_llm_calls = []

        trace = {
            "query_id": query_id or f"query_{len(self.traced_queries) + 1}",
            "query": query,
            "start_time": start_time.isoformat(),
            "workflow_path": [],
            "nodes": {},
            "edges": [],
            "execution_time_ms": 0,
            "errors": [],
            "final_result": None,
            "database_operations": [],  # Will be populated after execution
            "llm_calls": [],  # Will be populated after execution
        }

        try:
            # Get the workflow structure
            workflow_structure = self.nlp_service.get_workflow_structure()
            trace["workflow_info"] = workflow_structure

            # Create a custom workflow with tracing
            traced_workflow = self._create_traced_workflow(trace)

            # Execute the workflow
            result = await traced_workflow.ainvoke({"text": query})

            # Add "end" to workflow path since workflow completed successfully
            trace["workflow_path"].append("end")

            # Capture final result
            trace["final_result"] = result

            # Calculate execution time
            end_time = datetime.now()
            trace["execution_time_ms"] = (end_time - start_time).total_seconds() * 1000
            trace["end_time"] = end_time.isoformat()

            # Capture database operations (disabled - no database tracing)
            trace["database_operations"] = (
                []
            )  # Empty since database tracing is disabled

            # Capture LLM calls
            trace["llm_calls"] = self.current_llm_calls.copy()

        except Exception as e:
            trace["errors"].append(
                {
                    "type": "execution_error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            trace["final_result"] = {"error": str(e)}

        return trace

    def _create_traced_workflow(self, trace: Dict[str, Any]):
        """Create a workflow with tracing capabilities"""
        from langgraph.graph import StateGraph, END
        from typing import TypedDict

        class WorkflowState(TypedDict):
            text: str
            operation: Optional[str]
            result: Optional[Any]
            error: Optional[Any]
            message: Optional[str]

        # Get the original workflow structure from NLP service
        original_workflow = self.nlp_service._create_workflow()
        original_graph = original_workflow.get_graph()

        # Create the base workflow
        workflow = StateGraph(WorkflowState)

        # Dynamically add all nodes from the original workflow
        for node_name in original_graph.nodes.keys():
            if node_name not in ["__start__", "__end__"]:
                workflow.add_node(node_name, self._create_traced_node(node_name, trace))

        # Add edges based on the original workflow structure
        # For now, we'll use a simplified approach that works with the current NLP service
        # In a more robust implementation, we'd extract the actual edge conditions

        # Add conditional edges from router (this is the main conditional logic)
        workflow.add_conditional_edges(
            "router",
            lambda state: state.get("operation", "read"),
            {"read": "read", "write": "write", "unsure": "unsure"},
        )

        # Add direct edges to END for terminal nodes
        workflow.add_edge("read", END)
        workflow.add_edge("write", END)
        workflow.add_edge("unsure", END)

        # For any additional nodes that might be added in the future,
        # they would need to be handled here or we could add a more dynamic approach

        # Set entry point (should be "router" based on the original workflow)
        workflow.set_entry_point("router")
        return workflow.compile()

    def _create_traced_node(self, node_name: str, trace: Dict[str, Any]):
        """Create a traced version of a workflow node"""

        async def traced_node(state: Dict) -> Dict:
            node_start = datetime.now()
            node_trace = {
                "node_name": node_name,
                "start_time": node_start.isoformat(),
                "input_state": state.copy(),
                "output_state": None,
                "execution_time_ms": 0,
                "errors": [],
                "metadata": {},
            }

            try:
                # Dynamically call the original node function
                # Get the original workflow to access node functions
                original_workflow = self.nlp_service._create_workflow()
                original_graph = original_workflow.get_graph()

                # Find the original node function
                original_node_func = None
                for node in original_graph.nodes.values():
                    if hasattr(node, "func") and node.func:
                        # Check if this is the node we're looking for
                        # We need to match by function name or other identifier
                        if hasattr(node, "name") and node.name == node_name:
                            original_node_func = node.func
                            break

                if original_node_func:
                    # Call the original node function directly
                    result = await original_node_func(state)
                else:
                    # Fallback to hardcoded node handlers for known nodes
                    if node_name == "router":
                        result = await self._trace_router_node(state, trace)
                    elif node_name == "read":
                        result = await self._trace_read_node(state, trace)
                    elif node_name == "write":
                        result = await self._trace_write_node(state, trace)
                    elif node_name == "unsure":
                        result = await self._trace_unsure_node(state, trace)
                    else:
                        # For unknown nodes, try to call them directly from the NLP service
                        method_name = f"_{node_name}_node"
                        if hasattr(self.nlp_service, method_name):
                            method = getattr(self.nlp_service, method_name)
                            result = await method(state)
                        else:
                            raise ValueError(
                                f"Unknown node: {node_name} - no method found"
                            )

                # Capture output
                node_trace["output_state"] = result.copy()

                # Add to workflow path
                trace["workflow_path"].append(node_name)

            except Exception as e:
                node_trace["errors"].append(
                    {
                        "type": "node_error",
                        "message": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                # Still add to path even if error
                trace["workflow_path"].append(f"{node_name}_error")
                result = state  # Return original state on error

            # Calculate execution time
            node_end = datetime.now()
            node_trace["execution_time_ms"] = (
                node_end - node_start
            ).total_seconds() * 1000
            node_trace["end_time"] = node_end.isoformat()

            # Store node trace
            trace["nodes"][node_name] = node_trace

            return result

        return traced_node

    async def _trace_router_node(self, state: Dict, trace: Dict) -> Dict:
        """Trace router node with LLM call logging"""
        try:
            # Generate prompt using template
            prompt = self.nlp_service.prompt_manager.generate_router_prompt(
                state["text"]
            )

            # Make LLM call with timing
            llm_start = datetime.now()
            response = self.nlp_service.llm.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            llm_end = datetime.now()
            llm_time = (llm_end - llm_start).total_seconds() * 1000

            operation = response.choices[0].message.content.strip().upper()

            # Log the LLM call
            self._log_llm_call("router", prompt, operation, llm_time)

            if operation not in ["READ", "WRITE", "UNSURE"]:
                operation = "UNSURE"

            state["operation"] = operation.lower()
            return state

        except Exception as e:
            # Log failed LLM call as error log
            self._log_llm_call(
                "router",
                prompt if "prompt" in locals() else "Failed to generate prompt",
                "",
                0,
                str(e),
                call_type="error_log",
            )
            state["error"] = ParseError(
                code="parsing_failed",
                message="Failed to determine operation type",
                details=ErrorDetail(suggestions=["Try rephrasing your request"]),
            )
            return state

    async def _trace_read_node(self, state: Dict, trace: Dict) -> Dict:
        """Trace read node with LLM call logging"""
        try:
            # Get categories for context
            categories = await self.nlp_service._get_categories()
            category_list = [f"{cat.id} ({cat.name})" for cat in categories]

            # Get current date for context
            from datetime import date

            current_date = date.today()

            # Generate prompt using template
            prompt = self.nlp_service.prompt_manager.generate_read_prompt(
                state["text"], current_date, category_list
            )

            # Make LLM call with timing
            llm_start = datetime.now()
            response = self.nlp_service.llm.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            llm_end = datetime.now()
            llm_time = (llm_end - llm_start).total_seconds() * 1000

            content = response.choices[0].message.content.strip()

            # Log the LLM call
            self._log_llm_call("read", prompt, content, llm_time)

            try:
                query_params = json.loads(content)
                # Validate query parameters
                from models.schemas import QueryParams

                validated_params = QueryParams(**query_params)

                # Execute the query
                entries = await self.nlp_service._execute_read_query(validated_params)

                # Generate user-friendly response using LLM
                response_prompt = (
                    self.nlp_service.prompt_manager.generate_read_response_prompt(
                        state["text"], entries, validated_params, current_date
                    )
                )

                # Make LLM call for response generation with timing
                response_llm_start = datetime.now()
                response_message = await self.nlp_service._call_llm_for_response(
                    response_prompt
                )
                response_llm_end = datetime.now()
                response_llm_time = (
                    response_llm_end - response_llm_start
                ).total_seconds() * 1000

                # Log the response generation LLM call
                self._log_llm_call(
                    "read_response",
                    response_prompt,
                    response_message,
                    response_llm_time,
                )

                state["result"] = entries
                state["message"] = response_message
                return state

            except (json.JSONDecodeError, ValidationError) as e:
                state["error"] = ParseError(
                    code="parsing_failed",
                    message="Failed to parse query parameters",
                    details=ErrorDetail(suggestions=["Try rephrasing your request"]),
                )
                return state

        except Exception as e:
            # Log failed LLM call as error log
            self._log_llm_call(
                "read",
                prompt if "prompt" in locals() else "Failed to generate prompt",
                "",
                0,
                str(e),
                call_type="error_log",
            )
            state["error"] = ParseError(
                code="parsing_failed",
                message="Failed to process read request",
                details=ErrorDetail(suggestions=["Try rephrasing your request"]),
            )
            return state

    async def _trace_write_node(self, state: Dict, trace: Dict) -> Dict:
        """Trace write node with LLM call logging"""
        try:
            # Get categories for context
            categories = await self.nlp_service._get_categories()
            category_list = [f"{cat.name} ({cat.type})" for cat in categories]

            # Get current date for context
            from datetime import date, datetime

            current_date = date.today()

            # Generate prompt using template
            prompt = self.nlp_service.prompt_manager.generate_write_prompt(
                state["text"], category_list, current_date
            )

            # Make LLM call with timing
            llm_start = datetime.now()
            response = self.nlp_service.llm.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            llm_end = datetime.now()
            llm_time = (llm_end - llm_start).total_seconds() * 1000

            content = response.choices[0].message.content.strip()

            # Log the LLM call
            self._log_llm_call("write", prompt, content, llm_time)

            try:
                parsed_data = json.loads(content)

                # Convert date string to date object
                if "date" in parsed_data:
                    parsed_data["entry_date"] = datetime.strptime(
                        parsed_data["date"], "%Y-%m-%d"
                    ).date()
                    del parsed_data["date"]

                from models.schemas import ParsedData

                validated_data = ParsedData(**parsed_data)

                # Create the entry
                entry = await self.nlp_service._create_entry(validated_data)

                # Generate user-friendly response using LLM
                response_prompt = (
                    self.nlp_service.prompt_manager.generate_write_response_prompt(
                        state["text"], entry, current_date
                    )
                )

                # Make LLM call for response generation with timing
                response_llm_start = datetime.now()
                response_message = await self.nlp_service._call_llm_for_response(
                    response_prompt
                )
                response_llm_end = datetime.now()
                response_llm_time = (
                    response_llm_end - response_llm_start
                ).total_seconds() * 1000

                # Log the response generation LLM call
                self._log_llm_call(
                    "write_response",
                    response_prompt,
                    response_message,
                    response_llm_time,
                )

                state["result"] = entry
                state["message"] = response_message
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
            # Log failed LLM call as error log
            self._log_llm_call(
                "write",
                prompt if "prompt" in locals() else "Failed to generate prompt",
                "",
                0,
                str(e),
                call_type="error_log",
            )
            state["error"] = ParseError(
                code="parsing_failed",
                message="Failed to process write request",
                details=ErrorDetail(suggestions=["Try rephrasing your request"]),
            )
            return state

    async def _trace_unsure_node(self, state: Dict, trace: Dict) -> Dict:
        """Trace unsure node with LLM call logging for response generation"""
        try:
            # Generate helpful response message using LLM
            response_prompt = (
                self.nlp_service.prompt_manager.generate_unsure_response_prompt(
                    state["text"]
                )
            )

            # Make LLM call for response generation with timing
            response_llm_start = datetime.now()
            response_message = await self.nlp_service._call_llm_for_response(
                response_prompt
            )
            response_llm_end = datetime.now()
            response_llm_time = (
                response_llm_end - response_llm_start
            ).total_seconds() * 1000

            # Log the response generation LLM call
            self._log_llm_call(
                "unsure_response", response_prompt, response_message, response_llm_time
            )

            # Create suggestions for the error
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
            state["message"] = response_message
            return state

        except Exception as e:
            # Log failed LLM call as error log
            self._log_llm_call(
                "unsure_response",
                (
                    response_prompt
                    if "response_prompt" in locals()
                    else "Failed to generate prompt"
                ),
                "",
                0,
                str(e),
                call_type="error_log",
            )
            state["error"] = ParseError(
                code="parsing_failed",
                message="Failed to process ambiguous request",
                details=ErrorDetail(suggestions=["Try rephrasing your request"]),
            )
            return state

    async def trace_queries_from_file(self, queries_file: str) -> List[Dict[str, Any]]:
        """
        Load queries from JSON file and trace them all

        Args:
            queries_file: Path to JSON file containing queries

        Returns:
            List of trace results for all queries
        """
        with open(queries_file, "r") as f:
            data = json.load(f)

        queries = data.get("queries", [])
        if not queries:
            print(f"Warning: No queries found in {queries_file}")
            return []

        results = []

        print(f"Starting to trace {len(queries)} queries from {queries_file}...")

        for i, query_data in enumerate(queries):
            query = query_data["query"]
            query_id = query_data.get("id", f"query_{i+1}")

            print(f"Tracing query {i+1}/{len(queries)}: {query_id}")

            trace = await self.trace_query(query, query_id)
            results.append(trace)

            # Add expected vs actual pathway comparison
            expected = query_data.get("expected_pathway", "")
            actual = " -> ".join(trace["workflow_path"])
            trace["pathway_comparison"] = {
                "expected": expected,
                "actual": actual,
                "matches": expected.replace(" ", "").lower()
                == actual.replace(" ", "").lower(),
            }

        return results

    def _has_query_errors(self, query: Dict[str, Any]) -> bool:
        """Check if a query has any errors using comprehensive detection"""
        # Check top-level errors
        has_top_level_errors = query.get("errors") and len(query["errors"]) > 0

        # Check final result errors (but exclude "unsure" responses)
        has_final_result_error = False
        if query.get("final_result") and query["final_result"].get("error") is not None:
            error = query["final_result"]["error"]
            # Don't count "ambiguous" errors as failures - they're expected for unsure queries
            if hasattr(error, "code") and error.code == "ambiguous":
                has_final_result_error = False
            else:
                has_final_result_error = True

        # Check node-level errors (but exclude "unsure" node ambiguous responses)
        has_node_errors = False
        if query.get("nodes"):
            for node_name, node in query["nodes"].items():
                # Skip "unsure" node ambiguous responses
                if node_name == "unsure":
                    continue

                if (node.get("errors") and len(node["errors"]) > 0) or (
                    node.get("output_state")
                    and node["output_state"].get("error") is not None
                ):
                    has_node_errors = True
                    break

        return has_top_level_errors or has_final_result_error or has_node_errors

    def _format_time(self, ms: float) -> str:
        """Format time in milliseconds to human readable format"""
        if ms < 1000:
            return f"{ms:.1f}ms"
        else:
            return f"{ms/1000:.2f}s"

    def _generate_failure_analysis(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate failure analysis data from trace results"""
        failures = []
        status_failures = 0
        path_failures = 0

        for query in results:
            # Check for status failure
            has_errors = self._has_query_errors(query)

            # Check for path failure
            pathway_comparison = query.get("pathway_comparison", {})
            path_match = pathway_comparison.get("matches", True)

            # Only include if there's a failure
            if has_errors or not path_match:
                failure_types = []
                failure_reasons = []
                error_details = []
                node_failures = []
                final_llm_call_data = None

                # Analyze status failures
                if has_errors:
                    status_failures += 1
                    failure_types.append("status")

                    # Top-level errors
                    if query.get("errors"):
                        for error in query["errors"]:
                            failure_reasons.append(error.get("type", "unknown_error"))
                            error_details.append(error.get("message", str(error)))

                    # Final result errors
                    if query.get("final_result", {}).get("error"):
                        error = query["final_result"]["error"]
                        failure_reasons.append("final_result_error")
                        error_details.append(str(error))

                        # Find the last LLM call that likely caused this error
                        llm_calls = query.get("llm_calls", [])
                        if llm_calls:
                            final_llm_call = llm_calls[-1]  # Get the last LLM call
                            final_llm_call_data = {
                                "node_name": final_llm_call.get("node_name", "unknown"),
                                "prompt": final_llm_call.get("prompt", ""),
                                "response": final_llm_call.get("response", ""),
                                "execution_time_ms": final_llm_call.get(
                                    "execution_time_ms", 0
                                ),
                                "timestamp": final_llm_call.get("timestamp", ""),
                            }

                    # Node-level errors
                    if query.get("nodes"):
                        for node_name, node in query["nodes"].items():
                            node_errors = []

                            # Node errors array
                            if node.get("errors"):
                                for error in node["errors"]:
                                    node_errors.append(
                                        {
                                            "type": error.get("type", "unknown"),
                                            "message": error.get("message", str(error)),
                                        }
                                    )

                            # Node output state errors
                            if node.get("output_state", {}).get("error"):
                                node_errors.append(
                                    {
                                        "type": "output_state_error",
                                        "message": str(node["output_state"]["error"]),
                                    }
                                )

                            if node_errors:
                                node_failures.append(
                                    {"node_name": node_name, "errors": node_errors}
                                )

                # Analyze path failures
                if not path_match:
                    path_failures += 1
                    failure_types.append("path")
                    failure_reasons.append("pathway_mismatch")
                    error_details.append(
                        f"Expected: {pathway_comparison.get('expected', 'N/A')}, Got: {pathway_comparison.get('actual', 'N/A')}"
                    )

                # Format workflow path
                workflow_path = query.get("workflow_path", [])
                workflow_path_str = (
                    " → ".join(workflow_path) if workflow_path else "N/A"
                )

                # Create failure record
                failure_record = {
                    "query_id": query.get("query_id", ""),
                    "query_text": query.get("query", ""),
                    "failure_types": failure_types,
                    "failure_reasons": failure_reasons,
                    "error_details": error_details,
                    "workflow_path": workflow_path_str,
                    "expected_path": pathway_comparison.get("expected", "N/A"),
                    "actual_path": pathway_comparison.get("actual", workflow_path_str),
                    "execution_time_ms": query.get("execution_time_ms", 0),
                    "execution_time_formatted": self._format_time(
                        query.get("execution_time_ms", 0)
                    ),
                    "llm_calls_count": len(query.get("llm_calls", [])),
                    "response_generation_calls": len(
                        [
                            call
                            for call in query.get("llm_calls", [])
                            if call.get("call_type") == "llm_call"
                            and "response" in call.get("node_name", "")
                        ]
                    ),
                    "node_failures": node_failures,
                    "start_time": query.get("start_time", ""),
                    "end_time": query.get("end_time", ""),
                }

                # Add final LLM call data if available
                if final_llm_call_data:
                    failure_record["final_llm_call"] = final_llm_call_data

                failures.append(failure_record)

        return {
            "metadata": {
                "total_failures": len(failures),
                "status_failures": status_failures,
                "path_failures": path_failures,
                "generated_at": datetime.now().isoformat(),
                "tracer_version": "1.0.0",
            },
            "failures": failures,
        }

    def save_results(self, results: List[Dict[str, Any]], output_file: str = None):
        """
        Save trace results to JSON file and generate failure analysis

        Args:
            results: List of trace results
            output_file: Optional output file path (defaults to timestamp-based name)
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            # Get the script directory to save output file
            script_dir = Path(__file__).parent
            output_file = (
                script_dir / "data" / f"workflow_trace_results_{timestamp}.json"
            )

        # Save main results file
        output_data = {
            "metadata": {
                "total_queries": len(results),
                "generated_at": datetime.now().isoformat(),
                "tracer_version": "1.0.0",
            },
            "results": results,
        }

        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2, default=str)

        # Generate and save failure analysis
        failure_analysis = self._generate_failure_analysis(results)

        # Create failure file path based on main file
        failure_file = str(output_file).replace(
            "workflow_trace_results_", "workflow_failures_"
        )

        with open(failure_file, "w") as f:
            json.dump(failure_analysis, f, indent=2, default=str)

        print(f"Results saved to: {output_file}")
        print(f"Failure analysis saved to: {failure_file}")
        return output_file


async def main():
    """Main function to run the workflow tracer"""

    # Check for OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        return

    # Initialize tracer
    tracer = WorkflowTracer(openai_api_key)

    # Get the script directory to find input folder
    script_dir = Path(__file__).parent
    input_dir = script_dir / "input"

    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' not found")
        print("Please ensure the input/ folder exists")
        return

    # Find all JSON files in input directory
    json_files = list(input_dir.glob("*.json"))

    if not json_files:
        print(f"Error: No JSON files found in '{input_dir}'")
        print("Please add JSON files with queries to the input/ folder")
        return

    print(f"Found {len(json_files)} JSON files to process:")
    for json_file in json_files:
        print(f"  - {json_file.name}")

    # Process each JSON file
    all_processed_files = []

    for json_file in json_files:
        print(f"\n{'='*60}")
        print(f"Processing: {json_file.name}")
        print(f"{'='*60}")

        try:
            # Check if file has the expected structure
            with open(json_file, "r") as f:
                data = json.load(f)

            if "queries" not in data:
                print(f"Skipping {json_file.name}: No 'queries' array found")
                continue

            if not data.get("queries"):
                print(f"Skipping {json_file.name}: Empty 'queries' array")
                continue

            # Trace queries from this file
            results = await tracer.trace_queries_from_file(str(json_file))

            if not results:
                print(f"No results generated for {json_file.name}")
                continue

            # Generate output filename based on input file
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            input_stem = json_file.stem  # filename without extension
            output_file = (
                script_dir
                / "data"
                / f"workflow_trace_results_{input_stem}_{timestamp}.json"
            )

            # Save results
            tracer.save_results(results, str(output_file))
            all_processed_files.append((json_file.name, output_file))

            # Print summary for this file
            print(f"\nSummary for {json_file.name}:")
            print(f"  Total queries: {len(results)}")

            # Count successes and failures
            successes = 0
            failures = 0
            path_mismatches = 0

            for result in results:
                has_errors = tracer._has_query_errors(result)
                pathway_comparison = result.get("pathway_comparison", {})
                path_match = pathway_comparison.get("matches", True)

                if has_errors:
                    failures += 1
                else:
                    successes += 1

                if not path_match:
                    path_mismatches += 1

            print(f"  Successes: {successes}")
            print(f"  Failures: {failures}")
            print(f"  Path mismatches: {path_mismatches}")
            print(f"  Results saved to: {output_file.name}")

        except Exception as e:
            print(f"Error processing {json_file.name}: {str(e)}")
            import traceback

            traceback.print_exc()
            continue

    # Final summary
    print(f"\n{'='*60}")
    print("PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"Successfully processed {len(all_processed_files)} files:")
    for input_name, output_file in all_processed_files:
        print(f"  {input_name} -> {output_file.name}")

    if not all_processed_files:
        print("No files were successfully processed.")


if __name__ == "__main__":
    asyncio.run(main())
