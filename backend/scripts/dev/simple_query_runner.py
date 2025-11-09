"""
Simple Query Runner for NLP Service Testing
Leverages Langfuse's native tracing and session management capabilities
instead of custom workflow tracing.
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Try to import Langfuse SDK for trace fetching
try:
    from langfuse import Langfuse

    LANGFUSE_SDK_AVAILABLE = True
except ImportError:
    LANGFUSE_SDK_AVAILABLE = False
    print("Warning: Langfuse SDK not available, trace export will be limited")

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
    from services.agent_service import AgentService
except ImportError:
    # If running from project root, try backend.services
    from backend.services.agent_service import AgentService


class SimpleQueryRunner:
    """
    Simple query runner that leverages Langfuse's native capabilities.

    Instead of custom tracing, this script:
    1. Creates a session ID for the entire test run
    2. Runs queries through the NLP service (which already has Langfuse integration)
    3. Provides a summary with session ID for Langfuse cloud review
    """

    def __init__(self):
        # Check for OpenAI API key
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        # Initialize NLP service (it already has Langfuse integration)
        self.nlp_service = AgentService(self.openai_api_key)

        # Generate a session ID for this test run
        self.session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Initialize Langfuse client for trace fetching
        if LANGFUSE_SDK_AVAILABLE:
            try:
                langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
                langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
                langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

                if langfuse_public_key and langfuse_secret_key:
                    self.langfuse_client = Langfuse(
                        public_key=langfuse_public_key,
                        secret_key=langfuse_secret_key,
                        host=langfuse_host,
                    )
                    print("Langfuse trace fetcher: Available")
                else:
                    print("Warning: Langfuse credentials not found")
                    self.langfuse_client = None
            except Exception as e:
                print(f"Warning: Could not initialize Langfuse client: {e}")
                self.langfuse_client = None
        else:
            self.langfuse_client = None

        print("Initialized Simple Query Runner")
        print(f"Session ID: {self.session_id}")
        print(f"Langfuse enabled: {self.nlp_service.langfuse.enabled}")

        if not self.nlp_service.langfuse.enabled:
            print(
                "Warning: Langfuse is not enabled. Check your Langfuse configuration."
            )

    async def run_single_query(
        self, query: str, query_id: str = None
    ) -> Dict[str, Any]:
        """
        Run a single query through the NLP service.

        Args:
            query: The natural language query to process
            query_id: Optional identifier for the query

        Returns:
            Dictionary with query results and metadata
        """
        start_time = datetime.now()

        try:
            # Run the query through NLP service (already has Langfuse tracing)
            result = await self.nlp_service.process_query(
                text=query, user_id="test_user", session_id=self.session_id
            )

            end_time = datetime.now()
            execution_time_ms = (end_time - start_time).total_seconds() * 1000

            return {
                "query_id": query_id or f"query_{uuid.uuid4().hex[:8]}",
                "query": query,
                "result": result,
                "execution_time_ms": execution_time_ms,
                "success": True,
                "error": None,
                "timestamp": start_time.isoformat(),
            }

        except Exception as e:
            end_time = datetime.now()
            execution_time_ms = (end_time - start_time).total_seconds() * 1000

            return {
                "query_id": query_id or f"query_{uuid.uuid4().hex[:8]}",
                "query": query,
                "result": None,
                "execution_time_ms": execution_time_ms,
                "success": False,
                "error": str(e),
                "timestamp": start_time.isoformat(),
            }

    async def run_queries_from_file(self, queries_file: str) -> Dict[str, Any]:
        """
        Load queries from JSON file and run them all.

        Args:
            queries_file: Path to JSON file containing queries

        Returns:
            Dictionary with test run summary
        """
        with open(queries_file, "r") as f:
            data = json.load(f)

        queries = data.get("queries", [])
        if not queries:
            raise ValueError(f"No queries found in {queries_file}")

        print(f"Running {len(queries)} queries from {queries_file}...")

        results = []
        total_start_time = datetime.now()

        for i, query_data in enumerate(queries):
            query = query_data["query"]
            query_id = query_data.get("id", f"query_{i+1}")
            description = query_data.get("description", "")

            print(f"Running query {i+1}/{len(queries)}: {query_id}")
            if description:
                print(f"  Description: {description}")
            print(f"  Query: {query}")

            result = await self.run_single_query(query, query_id)
            results.append(result)

            # Print result summary
            if result["success"]:
                operation = result["result"].get("operation", "unknown")
                message = result["result"].get("message", "No message")
                print(
                    f"  [SUCCESS] ({operation}): {message[:100]}{'...' if len(message) > 100 else ''}"
                )
            else:
                print(f"  [FAILED]: {result['error']}")

            print(f"  Time: {result['execution_time_ms']:.1f}ms")
            print()

        total_end_time = datetime.now()
        total_execution_time_ms = (
            total_end_time - total_start_time
        ).total_seconds() * 1000

        # Calculate summary statistics
        successful_queries = [r for r in results if r["success"]]
        failed_queries = [r for r in results if not r["success"]]

        avg_execution_time = sum(r["execution_time_ms"] for r in results) / len(results)

        # Group by operation type
        operation_counts = {}
        for result in successful_queries:
            operation = result["result"].get("operation", "unknown")
            operation_counts[operation] = operation_counts.get(operation, 0) + 1

        summary = {
            "session_id": self.session_id,
            "test_run_metadata": {
                "queries_file": queries_file,
                "total_queries": len(queries),
                "successful_queries": len(successful_queries),
                "failed_queries": len(failed_queries),
                "success_rate": len(successful_queries) / len(queries) * 100,
                "total_execution_time_ms": total_execution_time_ms,
                "average_execution_time_ms": avg_execution_time,
                "operation_breakdown": operation_counts,
                "start_time": total_start_time.isoformat(),
                "end_time": total_end_time.isoformat(),
            },
            "results": results,
        }

        return summary

    def save_summary(self, summary: Dict[str, Any], output_file: str = None):
        """
        Save test run summary to JSON file.

        Args:
            summary: Test run summary data
            output_file: Optional output file path
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            script_dir = Path(__file__).parent
            output_file = script_dir / "data" / f"query_run_summary_{timestamp}.json"

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)

        print(f"Test summary saved to: {output_path}")
        return str(output_path)

    def save_simplified_langfuse_traces(
        self, session_id: str = None, output_file: str = None
    ):
        """
        Export simplified Langfuse traces focusing on essential debugging fields.

        Args:
            session_id: The session ID to fetch traces for (defaults to current session)
            output_file: Optional output file path

        Returns:
            Path to the exported simplified trace file, or None if failed
        """
        if not self.langfuse_client:
            print("Warning: Langfuse client not available. Cannot export traces.")
            return None

        target_session_id = session_id or self.session_id

        try:
            print(
                f"Exporting simplified Langfuse traces for session: {target_session_id}"
            )

            # Get traces using Langfuse SDK
            traces_response = self.langfuse_client.api.trace.list()
            if not (hasattr(traces_response, "data") and traces_response.data):
                print("No traces found via SDK")
                return None

            # Filter traces by session ID
            session_traces = []
            for trace in traces_response.data:
                trace_session_id = getattr(trace, "session_id", None)
                if trace_session_id == target_session_id:
                    trace_id = getattr(trace, "id", None)

                    # Get full trace details
                    try:
                        detailed_trace = self.langfuse_client.api.trace.get(trace_id)
                        simplified_trace = self._extract_simplified_trace_data(
                            detailed_trace
                        )
                        session_traces.append(simplified_trace)
                    except Exception as e:
                        print(f"Could not get detailed trace data for {trace_id}: {e}")
                        continue

            if not session_traces:
                print(f"No traces found for session: {target_session_id}")
                return None

            # Save simplified traces
            if output_file is None:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                script_dir = Path(__file__).parent
                output_file = (
                    script_dir
                    / "data"
                    / f"simplified_traces_{target_session_id}_{timestamp}.json"
                )

            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            export_data = {
                "exported_at": datetime.now().isoformat(),
                "total_traces": len(session_traces),
                "export_method": "simplified_langfuse_sdk",
                "session_id": target_session_id,
                "traces": session_traces,
            }

            with output_path.open("w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, default=str)

            print(
                f"Successfully exported {len(session_traces)} simplified traces to: {output_path}"
            )
            return str(output_path)

        except Exception as e:
            print(f"Error exporting simplified Langfuse traces: {str(e)}")
            return None

    def _extract_simplified_trace_data(self, trace):
        """Extract only essential debugging fields from trace data."""
        try:
            # Essential trace-level fields
            trace_data = {
                "id": getattr(trace, "id", None),
                "name": getattr(trace, "name", None),
                "sessionId": getattr(trace, "session_id", None),
                "timestamp": getattr(trace, "timestamp", None),
                "duration": getattr(trace, "duration", None),
                "input": getattr(trace, "input", None),
                "output": getattr(trace, "output", None),
                "totalCost": getattr(trace, "total_cost", None),
                "totalTokens": getattr(trace, "total_tokens", None),
                "observations": [],
            }

            # Extract essential observation fields
            observations = getattr(trace, "observations", None)
            if observations:
                for obs in observations:
                    obs_data = {
                        "id": getattr(obs, "id", None),
                        "name": getattr(obs, "name", None),
                        "type": getattr(obs, "type", None),
                        "startTime": getattr(obs, "start_time", None),
                        "endTime": getattr(obs, "end_time", None),
                        "duration": getattr(obs, "duration", None),
                        "input": getattr(obs, "input", None),
                        "output": getattr(obs, "output", None),
                        "parentObservationId": getattr(
                            obs, "parent_observation_id", None
                        ),
                        "traceId": getattr(obs, "trace_id", None),
                    }

                    # Add essential metadata for debugging
                    metadata = getattr(obs, "metadata", None)
                    if metadata:
                        obs_data["metadata"] = {
                            "duration": getattr(metadata, "duration", None),
                            "model": getattr(metadata, "model", None),
                            "operation_type": getattr(metadata, "operation_type", None),
                            "workflow_version": getattr(
                                metadata, "workflow_version", None
                            ),
                            "finish_reason": getattr(metadata, "finish_reason", None),
                        }

                    # Add usage info for generations
                    if getattr(obs, "type", None) == "GENERATION":
                        obs_data["usage"] = {
                            "input": getattr(obs, "input_tokens", None),
                            "output": getattr(obs, "output_tokens", None),
                            "total": getattr(obs, "total_tokens", None),
                        }
                        obs_data["cost"] = getattr(obs, "total_cost", None)
                        obs_data["model"] = getattr(obs, "model", None)

                    trace_data["observations"].append(obs_data)

            return trace_data

        except Exception as e:
            print(f"Error extracting simplified trace data: {e}")
            return {"error": str(e), "id": getattr(trace, "id", "unknown")}

    def print_summary(self, summary: Dict[str, Any]):
        """Print a human-readable summary of the test run."""
        metadata = summary["test_run_metadata"]

        print("\n" + "=" * 60)
        print("TEST RUN SUMMARY")
        print("=" * 60)
        print(f"Session ID: {summary['session_id']}")
        print(f"Total Queries: {metadata['total_queries']}")
        print(f"Successful: {metadata['successful_queries']}")
        print(f"Failed: {metadata['failed_queries']}")
        print(f"Success Rate: {metadata['success_rate']:.1f}%")
        print(f"Total Time: {metadata['total_execution_time_ms']/1000:.2f}s")
        print(f"Average Time per Query: {metadata['average_execution_time_ms']:.1f}ms")

        if metadata["operation_breakdown"]:
            print("\nOperation Breakdown:")
            for operation, count in metadata["operation_breakdown"].items():
                print(f"  {operation}: {count}")

        print(f"\nLangfuse Session: {summary['session_id']}")
        print("View traces at: https://cloud.langfuse.com")

        if metadata["failed_queries"] > 0:
            print("\nFailed Queries:")
            for result in summary["results"]:
                if not result["success"]:
                    print(f"  - {result['query_id']}: {result['error']}")

    def export_langfuse_traces(
        self, session_id: str = None, output_file: str = None, max_retries: int = 2
    ):
        """
        Export traces from Langfuse using integrated functionality.

        Args:
            session_id: The session ID to fetch traces for (defaults to current session)
            output_file: Optional output file path
            max_retries: Maximum number of retries to get all traces

        Returns:
            Path to the exported trace file, or None if failed
        """
        if not self.langfuse_client:
            print("Warning: Langfuse client not available. Cannot export traces.")
            return None

        target_session_id = session_id or self.session_id

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    print(
                        f"Retry attempt {attempt}/{max_retries} - waiting 2 more seconds..."
                    )
                    import time

                    time.sleep(2)

                print(f"Exporting Langfuse traces for session: {target_session_id}")

                # Get traces using Langfuse SDK with higher limit
                traces_response = self.langfuse_client.api.trace.list()
                if hasattr(traces_response, "data") and traces_response.data:
                    print(f"Found {len(traces_response.data)} total traces in Langfuse")

                    # Debug: Show all session IDs found
                    all_sessions = set()
                    for trace in traces_response.data:
                        session_id = getattr(trace, "session_id", None)
                        if session_id:
                            all_sessions.add(session_id)

                    print(f"All session IDs found: {list(all_sessions)}")
                    print(f"Looking for session ID: {target_session_id}")

                    # Filter traces by session ID and get full trace details
                    session_traces = []
                    for trace in traces_response.data:
                        trace_session_id = getattr(trace, "session_id", None)
                        if trace_session_id == target_session_id:
                            trace_id = getattr(trace, "id", None)
                            print(f"Fetching detailed data for trace: {trace_id}")

                            # Get full trace details including observations
                            try:
                                detailed_trace = self.langfuse_client.api.trace.get(
                                    trace_id
                                )
                                trace_dict = self._extract_full_trace_data(
                                    detailed_trace
                                )
                            except Exception as e:
                                print(f"Could not get detailed trace data: {e}")
                                # Fallback to basic trace data
                                trace_dict = self._extract_basic_trace_data(trace)

                            session_traces.append(trace_dict)

                    print(
                        f"Retrieved {len(session_traces)} traces for session {target_session_id} via SDK"
                    )

                    if session_traces:
                        # Save traces to file
                        if output_file is None:
                            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                            script_dir = Path(__file__).parent
                            output_file = (
                                script_dir
                                / "data"
                                / f"langfuse_traces_{target_session_id}_{timestamp}.json"
                            )

                        output_path = Path(output_file)
                        output_path.parent.mkdir(parents=True, exist_ok=True)

                        export_data = {
                            "exported_at": datetime.now().isoformat(),
                            "total_traces": len(session_traces),
                            "export_method": "langfuse_sdk",
                            "traces": session_traces,
                        }

                        with output_path.open("w", encoding="utf-8") as f:
                            json.dump(export_data, f, indent=2, default=str)

                        print(
                            f"Successfully exported {len(session_traces)} Langfuse traces to: {output_path}"
                        )
                        return str(output_path)
                    else:
                        print(f"No traces found for session: {target_session_id}")
                        if attempt < max_retries:
                            continue
                        return None
                else:
                    print("No traces found via SDK")
                    if attempt < max_retries:
                        continue
                    return None

            except Exception as e:
                print(
                    f"Error exporting Langfuse traces (attempt {attempt + 1}): {str(e)}"
                )
                if attempt < max_retries:
                    continue
                return None

    def _extract_full_trace_data(self, trace):
        """Extract comprehensive trace data including all observations and spans."""
        try:
            trace_data = {
                "id": getattr(trace, "id", None),
                "name": getattr(trace, "name", None),
                "userId": getattr(trace, "user_id", None),
                "sessionId": getattr(trace, "session_id", None),
                "timestamp": getattr(trace, "timestamp", None),
                "input": getattr(trace, "input", None),
                "output": getattr(trace, "output", None),
                "metadata": getattr(trace, "metadata", None),
                "tags": getattr(trace, "tags", None),
                "public": getattr(trace, "public", None),
                "release": getattr(trace, "release", None),
                "version": getattr(trace, "version", None),
                "status": getattr(trace, "status", None),
                "totalCost": getattr(trace, "total_cost", None),
                "totalTokens": getattr(trace, "total_tokens", None),
                "duration": getattr(trace, "duration", None),
                "externalId": getattr(trace, "external_id", None),
                "parentObservationId": getattr(trace, "parent_observation_id", None),
                "level": getattr(trace, "level", None),
            }

            # Get observations (spans, generations, events)
            observations = getattr(trace, "observations", None)
            if observations:
                trace_data["observations"] = []
                for obs in observations:
                    obs_data = self._extract_observation_data(obs)
                    trace_data["observations"].append(obs_data)

            # Get scores/evaluations
            scores = getattr(trace, "scores", None)
            if scores:
                trace_data["scores"] = []
                for score in scores:
                    score_data = {
                        "id": getattr(score, "id", None),
                        "name": getattr(score, "name", None),
                        "value": getattr(score, "value", None),
                        "timestamp": getattr(score, "timestamp", None),
                        "observationId": getattr(score, "observation_id", None),
                        "traceId": getattr(score, "trace_id", None),
                        "comment": getattr(score, "comment", None),
                    }
                    trace_data["scores"].append(score_data)

            return trace_data

        except Exception as e:
            print(f"Error extracting full trace data: {e}")
            return self._extract_basic_trace_data(trace)

    def _extract_observation_data(self, obs):
        """Extract detailed observation data (spans, generations, events)."""
        try:
            obs_data = {
                "id": getattr(obs, "id", None),
                "name": getattr(obs, "name", None),
                "type": getattr(obs, "type", None),
                "startTime": getattr(obs, "start_time", None),
                "endTime": getattr(obs, "end_time", None),
                "duration": getattr(obs, "duration", None),
                "status": getattr(obs, "status", None),
                "input": getattr(obs, "input", None),
                "output": getattr(obs, "output", None),
                "metadata": getattr(obs, "metadata", None),
                "level": getattr(obs, "level", None),
                "parentObservationId": getattr(obs, "parent_observation_id", None),
                "traceId": getattr(obs, "trace_id", None),
                "version": getattr(obs, "version", None),
                "externalId": getattr(obs, "external_id", None),
            }

            # For generation observations, get token and cost details
            if getattr(obs, "type", None) == "GENERATION":
                obs_data["usage"] = {
                    "input": getattr(obs, "input_tokens", None),
                    "output": getattr(obs, "output_tokens", None),
                    "total": getattr(obs, "total_tokens", None),
                    "unit": getattr(obs, "unit", None),
                }
                obs_data["cost"] = getattr(obs, "total_cost", None)
                obs_data["model"] = getattr(obs, "model", None)
                obs_data["modelParameters"] = getattr(obs, "model_parameters", None)
                obs_data["promptTokens"] = getattr(obs, "prompt_tokens", None)
                obs_data["completionTokens"] = getattr(obs, "completion_tokens", None)

            # For span observations, get nested observations
            nested_observations = getattr(obs, "observations", None)
            if nested_observations:
                obs_data["nestedObservations"] = []
                for nested_obs in nested_observations:
                    nested_data = self._extract_observation_data(nested_obs)
                    obs_data["nestedObservations"].append(nested_data)

            return obs_data

        except Exception as e:
            print(f"Error extracting observation data: {e}")
            return {"error": str(e), "type": "observation_extraction_error"}

    def _extract_basic_trace_data(self, trace):
        """Extract basic trace data as fallback."""
        return {
            "id": getattr(trace, "id", None),
            "name": getattr(trace, "name", None),
            "userId": getattr(trace, "user_id", None),
            "sessionId": getattr(trace, "session_id", None),
            "timestamp": getattr(trace, "timestamp", None),
            "input": getattr(trace, "input", None),
            "output": getattr(trace, "output", None),
            "metadata": getattr(trace, "metadata", None),
        }


async def main():
    """Main function to run queries."""

    # Initialize runner
    try:
        runner = SimpleQueryRunner()
    except ValueError as e:
        print(f"Error: {e}")
        return

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
    all_summaries = []

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

            # Run queries from this file
            summary = await runner.run_queries_from_file(str(json_file))

            # Save summary
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            input_stem = json_file.stem
            output_file = (
                script_dir / "data" / f"query_run_summary_{input_stem}_{timestamp}.json"
            )

            runner.save_summary(summary, str(output_file))
            all_summaries.append((json_file.name, summary))

            # Print summary for this file
            runner.print_summary(summary)

        except Exception as e:
            print(f"Error processing {json_file.name}: {str(e)}")
            import traceback

            traceback.print_exc()
            continue

    # Final summary
    print(f"\n{'='*60}")
    print("ALL TESTS COMPLETE")
    print(f"{'='*60}")

    if all_summaries:
        total_queries = sum(
            s[1]["test_run_metadata"]["total_queries"] for s in all_summaries
        )
        total_successful = sum(
            s[1]["test_run_metadata"]["successful_queries"] for s in all_summaries
        )
        total_failed = sum(
            s[1]["test_run_metadata"]["failed_queries"] for s in all_summaries
        )

        print(f"Processed {len(all_summaries)} files")
        print(f"Total queries across all files: {total_queries}")
        print(f"Total successful: {total_successful}")
        print(f"Total failed: {total_failed}")
        print(f"Overall success rate: {total_successful/total_queries*100:.1f}%")

        print(f"\nSession ID for Langfuse review: {runner.session_id}")
        print("View all traces at: https://cloud.langfuse.com")

        # Export Langfuse traces
        print(f"\n{'='*60}")
        print("EXPORTING LANGFUSE TRACES")
        print(f"{'='*60}")
        print("Waiting for traces to be fully processed in Langfuse...")
        await asyncio.sleep(10)  # Wait even longer for traces to be processed

        # Export full traces
        langfuse_trace_file = runner.export_langfuse_traces()
        if langfuse_trace_file:
            print(f"Full Langfuse traces exported to: {langfuse_trace_file}")
        else:
            print("Full Langfuse trace export failed or no traces found.")
            print("This is normal if traces haven't been processed yet in Langfuse.")

        # Export simplified traces
        print("\nExporting simplified traces for debugging...")
        simplified_trace_file = runner.save_simplified_langfuse_traces()
        if simplified_trace_file:
            print(f"Simplified traces exported to: {simplified_trace_file}")
        else:
            print("Simplified trace export failed or no traces found.")
    else:
        print("No files were successfully processed.")


if __name__ == "__main__":
    asyncio.run(main())
