"""
Workflow Testing Script for NLP Service V3
Tracks and logs all pathways through the n-shot orchestration workflow
"""

import asyncio
import json
import os
import sys
from datetime import datetime, date
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
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

# Try both import paths to handle running from different directories
try:
    from services.nlp_service_v3 import NLPServiceV3
    from database.connection import db_connection
    from models.schemas import ParseError, ErrorDetail
except ImportError:
    # If running from project root, try backend.services
    from backend.services.nlp_service_v3 import NLPServiceV3
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

    def __getattr__(self, name):
        """Delegate all other attributes to the original database connection"""
        return getattr(self.db, name)


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

    def __getattr__(self, name):
        """Delegate all other attributes to the original client"""
        return getattr(self.client, name)


class TracedNLPServiceV3:
    """Wrapper around NLPServiceV3 that captures LLM calls for tracing"""

    def __init__(self, nlp_service, tracer):
        self.nlp_service = nlp_service
        self.tracer = tracer

        # Preserve all original attributes and methods
        for attr_name in dir(nlp_service):
            if not attr_name.startswith("_") and not hasattr(self, attr_name):
                setattr(self, attr_name, getattr(nlp_service, attr_name))

    async def process_query(
        self, text: str, user_id: str = None, session_id: str = None
    ):
        """Override process_query to intercept LLM calls with better error handling"""
        import time
        from datetime import datetime

        try:
            async with self.nlp_service.langfuse.trace_operation(
                name="nlp_query_processing_v3",
                user_id=user_id,
                session_id=session_id,
                input_data={"text": text},
                tags=["nlp", "v3"],
            ) as trace_id:
                facts: Dict[str, Any] = {}
                fetches = 0

                for turn_num in range(self.nlp_service.MAX_TURNS):
                    try:
                        # Build and call unified main prompt with tracing
                        prompt = self.nlp_service._build_main_prompt(text, facts)
                    except Exception as e:
                        # Log the error but continue with a fallback prompt
                        self.tracer._log_llm_call(
                            f"v3_error_turn_{turn_num}",
                            f"Error building prompt: {str(e)}",
                            f"Database connection error: {str(e)}",
                            0,
                            str(e),
                        )
                        return {
                            "operation": "unsure",
                            "result": [],
                            "message": f"Database connection error: {str(e)}",
                        }

                    # Track LLM call start
                    llm_start = datetime.now()

                    try:
                        response, generation_id = (
                            await self.nlp_service.langfuse.track_unified_llm_call(
                                name="v3_main",
                                model="gpt-4.1-nano",
                                messages=[{"role": "user", "content": prompt}],
                                trace_id=trace_id,
                                temperature=0.1,
                                operation_type="v3_plan",
                            )
                        )
                    except Exception as e:
                        # Log LLM call failure
                        llm_end = datetime.now()
                        llm_time = (llm_end - llm_start).total_seconds() * 1000
                        self.tracer._log_llm_call(
                            f"v3_main_turn_{turn_num}",
                            prompt,
                            f"LLM call failed: {str(e)}",
                            llm_time,
                            str(e),
                        )
                        return {
                            "operation": "unsure",
                            "result": [],
                            "message": f"LLM service error: {str(e)}",
                        }

                    # Track LLM call completion
                    llm_end = datetime.now()
                    llm_time = (llm_end - llm_start).total_seconds() * 1000

                    response_content = response.choices[0].message.content.strip()

                    # Log the LLM call to tracer
                    self.tracer._log_llm_call(
                        f"v3_main_turn_{turn_num}", prompt, response_content, llm_time
                    )

                    try:
                        plan = json.loads(response_content)
                    except Exception as e:
                        self.tracer._log_llm_call(
                            f"v3_parse_error_turn_{turn_num}",
                            f"Failed to parse LLM response: {response_content}",
                            f"JSON parse error: {str(e)}",
                            0,
                            str(e),
                        )
                        return {
                            "operation": "unsure",
                            "result": [],
                            "message": "I couldn't interpret that. Please refine your request.",
                        }

                    action = plan.get("action")

                    # Direct reply path
                    if action == "reply":
                        msg = plan.get("reply") or "Done."
                        return {
                            "operation": plan.get("operation", "read"),
                            "result": [],
                            "message": msg,
                        }

                    # Clarify path
                    if action == "clarify":
                        question = (
                            plan.get("question") or "Could you clarify your request?"
                        )
                        return {
                            "operation": "unsure",
                            "result": [],
                            "message": question,
                        }

                    # Fetch path
                    if action == "fetch":
                        if fetches >= self.nlp_service.MAX_FETCHES:
                            return {
                                "operation": "read",
                                "result": [],
                                "message": "I reached the data access limit for this request. Please refine your filters or ask for top results.",
                            }

                        try:
                            spec = self.nlp_service.QuerySpec(
                                **plan["query_spec"]
                            )  # validates limit <= 10
                        except (ValidationError, KeyError) as e:
                            self.tracer._log_llm_call(
                                f"v3_validation_error_turn_{turn_num}",
                                f"QuerySpec validation failed for: {plan.get('query_spec', {})}",
                                f"Validation error: {str(e)}",
                                0,
                                str(e),
                            )
                            return {
                                "operation": "unsure",
                                "result": [],
                                "message": "I couldn't form a safe query. Try narrowing your request.",
                            }

                        try:
                            rows, meta = await self.nlp_service._run_query_spec(spec)
                            fetches += 1

                            facts = self.nlp_service._summarize_facts(
                                facts, rows, meta, plan.get("response_kind")
                            )

                            # Give model one more turn with updated facts
                            continue
                        except Exception as e:
                            # Log database fetch error but continue
                            self.tracer._log_llm_call(
                                f"v3_db_error_turn_{turn_num}",
                                f"Database fetch failed for query: {plan.get('query_spec', {})}",
                                f"Database error: {str(e)}",
                                0,
                                str(e),
                            )
                            # Return a helpful message about database connectivity
                            return {
                                "operation": "read",
                                "result": [],
                                "message": f"Database connection error: {str(e)}. Please check database configuration.",
                            }

                    # Unknown action fallback
                    return {
                        "operation": "unsure",
                        "result": [],
                        "message": "I'm not sure how to proceed. Please refine your request.",
                    }

                # Finalization fallback after max turns - also needs tracing
                try:
                    msg = await self._finalize_with_facts(text, facts, trace_id)
                    return {
                        "operation": "read",
                        "result": facts.get("top_entries", []),
                        "message": msg,
                    }
                except Exception as e:
                    self.tracer._log_llm_call(
                        "v3_finalize_error",
                        f"Finalization failed for query: {text}",
                        f"Finalization error: {str(e)}",
                        0,
                        str(e),
                    )
                    return {
                        "operation": "read",
                        "result": facts.get("top_entries", []),
                        "message": f"Processing completed with errors: {str(e)}",
                    }

        except Exception as e:
            # Log any top-level errors
            self.tracer._log_llm_call(
                "v3_top_level_error",
                f"Top-level error for query: {text}",
                f"Top-level error: {str(e)}",
                0,
                str(e),
            )
            return {
                "operation": "unsure",
                "result": [],
                "message": f"System error: {str(e)}",
            }

    async def _finalize_with_facts(
        self, user_text: str, facts: Dict[str, Any], trace_id: Optional[str]
    ):
        """Override finalization to capture LLM call with error handling"""
        import json
        from datetime import datetime

        prompt = (
            f"You are a finance assistant. Use ONLY these facts, do not invent data.\n"
            f"User: {user_text}\nFacts: {json.dumps(facts)}\n"
            "Write a concise 1-3 sentence answer."
        )

        # Track LLM call start
        llm_start = datetime.now()

        try:
            response, generation_id = (
                await self.nlp_service.langfuse.track_response_llm_call(
                    name="v3_finalize",
                    model="gpt-4.1-nano",
                    messages=[{"role": "user", "content": prompt}],
                    trace_id=trace_id,
                    response_type="user_friendly",
                    temperature=0.3,
                )
            )

            # Track LLM call completion
            llm_end = datetime.now()
            llm_time = (llm_end - llm_start).total_seconds() * 1000

            response_content = response.choices[0].message.content.strip()

            # Log the LLM call to tracer
            self.tracer._log_llm_call("v3_finalize", prompt, response_content, llm_time)

            return response_content
        except Exception as e:
            # Track LLM call failure
            llm_end = datetime.now()
            llm_time = (llm_end - llm_start).total_seconds() * 1000

            self.tracer._log_llm_call(
                "v3_finalize_error",
                prompt,
                f"Finalization failed: {str(e)}",
                llm_time,
                str(e),
            )
            return f"Unable to finalize response: {str(e)}"


class WorkflowTracerV3:
    """Workflow tracer specifically for NLPServiceV3 with n-shot orchestration"""

    def __init__(self, openai_api_key: str):
        # Create the base NLP service
        base_nlp_service = NLPServiceV3(openai_api_key)

        # Create traced wrapper that captures LLM calls
        self.nlp_service = TracedNLPServiceV3(base_nlp_service, self)

        self.traced_queries = []

        # DISABLED: Database tracing causes Supabase client issues
        # self.nlp_service.nlp_service.db = TracedDatabaseConnection(
        #     self.nlp_service.nlp_service.db, self
        # )

        # Track database operations per query
        self.current_db_operations = []

        # Track LLM calls per query
        self.current_llm_calls = []

    def _log_db_operation(self, operation: str, table: str, details: Dict[str, Any]):
        """Log a database operation start"""
        db_op = {
            "operation": operation,
            "table": table,
            "details": details,
            "start_time": datetime.now().isoformat(),
            "status": "started",
        }
        self.current_db_operations.append(db_op)

    def _log_db_execution(
        self,
        operation: str,
        table: str,
        execution_time_ms: float,
        result_count: int,
        error: Optional[str],
    ):
        """Log a database operation completion"""
        # Find the matching started operation and update it
        for op in reversed(self.current_db_operations):
            if (
                op["operation"] == operation
                and op["table"] == table
                and op["status"] == "started"
            ):
                op.update(
                    {
                        "execution_time_ms": execution_time_ms,
                        "result_count": result_count,
                        "error": error,
                        "status": "completed",
                        "end_time": datetime.now().isoformat(),
                    }
                )
                break

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
        Trace a single query through the V3 n-shot orchestration workflow

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
            "turns": [],
            "execution_time_ms": 0,
            "errors": [],
            "final_result": None,
            "database_operations": [],  # Will be populated after execution
            "llm_calls": [],  # Will be populated after execution
        }

        try:
            # Execute the V3 service directly (it handles its own orchestration)
            result = await self.nlp_service.process_query(query)

            # Add "end" to workflow path since workflow completed successfully
            trace["workflow_path"].append("end")

            # Capture final result
            trace["final_result"] = result

            # Calculate execution time
            end_time = datetime.now()
            trace["execution_time_ms"] = (end_time - start_time).total_seconds() * 1000
            trace["end_time"] = end_time.isoformat()

            # Capture database operations
            trace["database_operations"] = self.current_db_operations.copy()

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
            expected_v3 = query_data.get("expected_pathway_v3")
            expected = expected_v3 or query_data.get("expected_pathway", "")
            actual = " -> ".join(trace["workflow_path"])
            trace["pathway_comparison"] = {
                "expected": expected,
                "actual": actual,
                "matches": expected.replace(" ", "").lower()
                == actual.replace(" ", "").lower(),
            }
            if expected_v3 and "expected_pathway" in query_data:
                trace["pathway_comparison"]["expected_v1"] = query_data[
                    "expected_pathway"
                ]
                trace["pathway_comparison"]["expected_v2"] = query_data.get(
                    "expected_pathway_v2", ""
                )

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

        # Check turn-level errors
        has_turn_errors = False
        if query.get("turns"):
            for turn in query["turns"]:
                if turn.get("errors") and len(turn["errors"]) > 0:
                    has_turn_errors = True
                    break

        return has_top_level_errors or has_final_result_error or has_turn_errors

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
                turn_failures = []
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
                    final_result = query.get("final_result")
                    if final_result and final_result.get("error"):
                        error = final_result["error"]
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

                    # Turn-level errors
                    if query.get("turns"):
                        for turn_idx, turn in enumerate(query["turns"]):
                            turn_errors = []

                            # Turn errors array
                            if turn.get("errors"):
                                for error in turn["errors"]:
                                    turn_errors.append(
                                        {
                                            "type": error.get("type", "unknown"),
                                            "message": error.get("message", str(error)),
                                        }
                                    )

                            if turn_errors:
                                turn_failures.append(
                                    {"turn_index": turn_idx, "errors": turn_errors}
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
                    "turns_count": len(query.get("turns", [])),
                    "turn_failures": turn_failures,
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
                "tracer_version": "3.0.0",
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
                script_dir / "data" / f"workflow_trace_results_v3_{timestamp}.json"
            )

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save main results file
        output_data = {
            "metadata": {
                "total_queries": len(results),
                "generated_at": datetime.now().isoformat(),
                "tracer_version": "3.0.0",
                "service_version": "NLPServiceV3",
            },
            "results": results,
        }

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, default=str)

        # Generate and save failure analysis
        failure_analysis = self._generate_failure_analysis(results)

        failure_name = output_path.name
        if "workflow_trace_results_v3_" in failure_name:
            failure_name = failure_name.replace(
                "workflow_trace_results_v3_", "workflow_failures_v3_", 1
            )
        else:
            failure_name = f"workflow_failures_v3_{failure_name}"
        failure_path = output_path.with_name(failure_name)

        with failure_path.open("w", encoding="utf-8") as f:
            json.dump(failure_analysis, f, indent=2, default=str)

        print(f"Results saved to: {output_path}")
        print(f"Failure analysis saved to: {failure_path}")
        return str(output_path)


async def main():
    """Main function to run the V3 workflow tracer"""

    # Check for OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        return

    # Initialize tracer
    tracer = WorkflowTracerV3(openai_api_key)

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
                / f"workflow_trace_results_v3_{input_stem}_{timestamp}.json"
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
    print("V3 PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"Successfully processed {len(all_processed_files)} files:")
    for input_name, output_file in all_processed_files:
        print(f"  {input_name} -> {output_file.name}")

    if not all_processed_files:
        print("No files were successfully processed.")


if __name__ == "__main__":
    asyncio.run(main())
