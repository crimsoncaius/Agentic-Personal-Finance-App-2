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
            print(f"📁 Loaded .env from: {env_path}")
            break

    if not env_loaded:
        print("⚠️  No .env file found in expected locations")

except ImportError:
    print("⚠️  python-dotenv not available, skipping .env loading")

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

        # Create the base workflow
        workflow = StateGraph(WorkflowState)

        # Add traced nodes
        workflow.add_node("router", self._create_traced_node("router", trace))
        workflow.add_node("read", self._create_traced_node("read", trace))
        workflow.add_node("write", self._create_traced_node("write", trace))
        workflow.add_node("unsure", self._create_traced_node("unsure", trace))

        # Add conditional edges
        workflow.add_conditional_edges(
            "router",
            lambda state: state.get("operation", "read"),
            {"read": "read", "write": "write", "unsure": "unsure"},
        )
        workflow.add_edge("read", END)
        workflow.add_edge("write", END)
        workflow.add_edge("unsure", END)

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
                # Call the original node function with LLM call tracing
                if node_name == "router":
                    result = await self._trace_router_node(state, trace)
                elif node_name == "read":
                    result = await self._trace_read_node(state, trace)
                elif node_name == "write":
                    result = await self._trace_write_node(state, trace)
                elif node_name == "unsure":
                    result = await self.nlp_service._unsure_node(state)
                else:
                    raise ValueError(f"Unknown node: {node_name}")

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
                model="gpt-3.5-turbo",
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
                model="gpt-3.5-turbo",
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
            from datetime import date

            current_date = date.today()

            # Generate prompt using template
            prompt = self.nlp_service.prompt_manager.generate_write_prompt(
                state["text"], category_list, current_date
            )

            # Make LLM call with timing
            llm_start = datetime.now()
            response = self.nlp_service.llm.chat.completions.create(
                model="gpt-3.5-turbo",
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
                    from datetime import datetime

                    parsed_data["entry_date"] = datetime.strptime(
                        parsed_data["date"], "%Y-%m-%d"
                    ).date()
                    del parsed_data["date"]

                from models.schemas import ParsedData

                validated_data = ParsedData(**parsed_data)

                # Create the entry
                entry = await self.nlp_service._create_entry(validated_data)

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
        results = []

        print(f"Starting to trace {len(queries)} queries...")

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

    def save_results(self, results: List[Dict[str, Any]], output_file: str = None):
        """
        Save trace results to JSON file

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

        print(f"Results saved to: {output_file}")
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

    # Load and trace queries
    # Get the script directory to find input file
    script_dir = Path(__file__).parent
    queries_file = script_dir / "input" / "test_queries.json"
    if not queries_file.exists():
        print(f"Error: Queries file '{queries_file}' not found")
        print("Please ensure test_queries.json is in the input/ folder")
        return

    try:
        results = await tracer.trace_queries_from_file(queries_file)

        # Save results
        output_file = tracer.save_results(results)

        # Print summary
        print("\n" + "=" * 50)
        print("TRACE SUMMARY")
        print("=" * 50)

        for result in results:
            query_id = result["query_id"]
            query = (
                result["query"][:50] + "..."
                if len(result["query"]) > 50
                else result["query"]
            )
            pathway = " -> ".join(result["workflow_path"])
            exec_time = result["execution_time_ms"]
            errors = len(result["errors"])
            db_ops = result.get("database_operations", [])

            print(f"\n{query_id}: {query}")
            print(f"  Pathway: {pathway}")
            print(f"  Execution time: {exec_time:.2f}ms")
            if errors > 0:
                print(f"  Errors: {errors}")
            db_ops = result.get("database_operations", [])
            if db_ops:
                print(f"  Database operations: {len(db_ops)}")
                for op in db_ops:
                    op_time = op.get("execution_time_ms", 0)
                    result_count = op.get("result_count", 0)
                    error = op.get("error")
                    status = f"ERROR: {error}" if error else f"OK ({result_count} rows)"
                    print(
                        f"    {op['operation']} {op['table']}: {status} ({op_time:.2f}ms)"
                    )
            else:
                print(f"  Database operations: DISABLED (tracing turned off)")

            # Show LLM calls
            llm_calls = result.get("llm_calls", [])
            if llm_calls:
                # Separate real LLM calls from error logs
                real_calls = [c for c in llm_calls if c.get("call_type") == "llm_call"]
                error_logs = [c for c in llm_calls if c.get("call_type") == "error_log"]

                print(
                    f"  LLM calls: {len(real_calls)} real calls, {len(error_logs)} error logs"
                )

                for call in real_calls:
                    node_name = call.get("node_name", "unknown")
                    exec_time = call.get("execution_time_ms", 0)
                    error = call.get("error")
                    response_preview = (
                        call.get("response", "")[:50] + "..."
                        if len(call.get("response", "")) > 50
                        else call.get("response", "")
                    )
                    status = f"ERROR: {error}" if error else f"OK: {response_preview}"
                    print(f"    {node_name}: {status} ({exec_time:.2f}ms)")

                for call in error_logs:
                    node_name = call.get("node_name", "unknown")
                    error = call.get("error", "Unknown error")
                    print(f"    {node_name} (error log): {error}")
            else:
                print(f"  LLM calls: None captured")

        print(f"\nDetailed results saved to: {output_file}")

    except Exception as e:
        print(f"Error during tracing: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
