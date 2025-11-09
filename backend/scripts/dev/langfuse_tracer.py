"""
Langfuse-Based Workflow Tracer for Agent Service
Fetches traces from Langfuse cloud and validates against expected behavior
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Load environment variables
try:
    from dotenv import load_dotenv

    script_dir = os.path.dirname(__file__)
    possible_env_paths = [
        os.path.join(script_dir, "..", "..", "..", ".env"),
        os.path.join(script_dir, "..", "..", ".env"),
        os.path.join(script_dir, "..", ".env"),
        ".env",
    ]

    env_loaded = False
    for env_path in possible_env_paths:
        env_path = os.path.abspath(env_path)
        if os.path.exists(env_path):
            load_dotenv(env_path)
            env_loaded = True
            print(f"[OK] Loaded .env from: {env_path}")
            break

    if not env_loaded:
        print("[WARN] No .env file found in expected locations")

except ImportError:
    print("[WARN] python-dotenv not available, skipping .env loading")

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

# Import required services
try:
    from services.agent_service import AgentService
    from langfuse import Langfuse
except ImportError:
    from backend.services.agent_service import AgentService
    from langfuse import Langfuse


def load_tracer_config(config_path: str = None) -> Dict[str, Any]:
    """Load tracer configuration from JSON file with defaults"""
    default_config = {
        "timing": {
            "initial_sync_wait_seconds": 120,
            "delay_between_fetches_seconds": 3,
            "delay_between_multi_turn_fetches_seconds": 3,
        },
        "retries": {
            "batch_fetch_max_retries": 5,
            "batch_fetch_retry_delay_seconds": 15,
            "individual_trace_max_retries": 3,
        },
    }

    if config_path is None:
        config_path = Path(__file__).parent / "config" / "tracer_config.json"

    try:
        if Path(config_path).exists():
            with open(config_path, "r") as f:
                user_config = json.load(f)
                # Merge with defaults (user config overrides defaults)
                return {**default_config, **user_config}
        else:
            print(f"[INFO] Config file not found at {config_path}, using defaults")
            return default_config
    except Exception as e:
        print(f"[WARN] Error loading config: {e}, using defaults")
        return default_config


class LangfuseTracerV3:
    """Tracer that uses Langfuse cloud to validate Agent Service behavior"""

    def __init__(
        self, user_id: str, openai_api_key: str = None, config_path: str = None
    ):
        """Initialize tracer with user_id and API keys"""
        self.user_id = user_id
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        # Load configuration
        self.config = load_tracer_config(config_path)
        print(f"[INFO] Loaded tracer config: {json.dumps(self.config, indent=2)}")

        # Initialize NLP service
        self.nlp_service = AgentService(self.openai_api_key)

        # Initialize Langfuse client
        langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

        if not langfuse_public_key or not langfuse_secret_key:
            raise ValueError(
                "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set in .env"
            )

        self.langfuse = Langfuse(
            public_key=langfuse_public_key,
            secret_key=langfuse_secret_key,
            host=langfuse_host,
        )

        # Generate unique batch tag for this test run
        self.batch_tag = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"[INFO] Using batch tag: {self.batch_tag}")

        # Track trace IDs for later fetching
        self.trace_ids = []
        self.query_results = []

    async def run_query(
        self, query_data: Dict[str, Any], session_id: str = None
    ) -> Dict[str, Any]:
        """
        Execute a single query through NLP service

        Args:
            query_data: Query data from test file
            session_id: Optional session ID for grouping

        Returns:
            Dictionary with query result and metadata
        """
        query_id = query_data.get("id", "unknown")

        # Check if this is a multi-turn query (has "messages" array)
        if "messages" in query_data:
            return await self._run_multi_turn_query(query_data, session_id)

        # Single query case
        query_text = query_data.get("query", "")

        print(f"  Running query: {query_id}")
        print(f"    Text: {query_text}")

        start_time = time.time()

        try:
            # Execute query through NLP service
            result = await self.nlp_service.process_query(
                text=query_text,
                user_id=self.user_id,
                session_id=session_id or query_id,
                tags=[self.batch_tag],
            )

            execution_time = time.time() - start_time

            # Extract chat_id and trace_id
            chat_id = result.get("chat_id")
            trace_id = result.get("trace_id")
            print(f"    [DEBUG] Query {query_id} returned chat_id: {chat_id}")
            print(f"    [DEBUG] Query {query_id} returned trace_id: {trace_id}")

            # Store result with metadata
            query_result = {
                "query_id": query_id,
                "query_text": query_text,
                "chat_id": chat_id,
                "trace_id": trace_id,
                "execution_time_ms": execution_time * 1000,
                "result": result,
                "expected": {
                    "tool_calls": query_data.get("expected_tool_calls", []),
                    "has_entries": query_data.get("expected_has_entries", False),
                    "category": query_data.get("expected_category"),
                },
                "timestamp": datetime.now().isoformat(),
                "error": None,
            }

            print(f"    [OK] Completed in {execution_time:.2f}s")

            return query_result

        except Exception as e:
            execution_time = time.time() - start_time
            print(f"    [ERROR] {str(e)}")

            return {
                "query_id": query_id,
                "query_text": query_text,
                "chat_id": None,
                "trace_id": None,
                "execution_time_ms": execution_time * 1000,
                "result": None,
                "expected": {
                    "tool_calls": query_data.get("expected_tool_calls", []),
                    "has_entries": query_data.get("expected_has_entries", False),
                },
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    async def _run_multi_turn_query(
        self, query_data: Dict[str, Any], session_id: str = None
    ) -> Dict[str, Any]:
        """
        Execute a multi-turn conversation query

        Args:
            query_data: Query data with "messages" array
            session_id: Optional session ID

        Returns:
            Dictionary with final result and all turns
        """
        query_id = query_data.get("id", "unknown")
        messages = query_data.get("messages", [])

        print(f"  Running multi-turn query: {query_id} ({len(messages)} turns)")

        start_time = time.time()
        chat_id = None
        turns = []
        trace_ids = []  # Track all trace IDs from all turns

        try:
            for i, msg in enumerate(messages):
                turn_text = msg.get("content", "")
                print(f"    Turn {i+1}: {turn_text}")

                # Execute turn
                result = await self.nlp_service.process_query(
                    text=turn_text,
                    user_id=self.user_id,
                    session_id=session_id or query_id,
                    chat_id=chat_id,  # Maintain conversation
                    tags=[self.batch_tag],
                )

                # Update chat_id for next turn
                chat_id = result.get("chat_id")

                # Store trace_id from this turn
                turn_trace_id = result.get("trace_id")
                if turn_trace_id:
                    trace_ids.append(turn_trace_id)

                turns.append(
                    {
                        "turn": i + 1,
                        "text": turn_text,
                        "result": result,
                        "trace_id": turn_trace_id,  # Add trace_id to turn info
                    }
                )

            execution_time = time.time() - start_time

            # Use the final turn's result
            final_result = turns[-1]["result"] if turns else None

            query_result = {
                "query_id": query_id,
                "query_text": f"Multi-turn ({len(messages)} messages)",
                "chat_id": chat_id,
                "trace_id": (
                    trace_ids[-1] if trace_ids else None
                ),  # Keep last trace_id for compatibility
                "trace_ids": trace_ids,  # All trace IDs from all turns
                "is_multi_turn": True,  # Flag for special handling
                "execution_time_ms": execution_time * 1000,
                "result": final_result,
                "turns": turns,
                "expected": {
                    "tool_calls": query_data.get("expected_tool_calls", []),
                    "has_entries": query_data.get("expected_has_entries", False),
                },
                "timestamp": datetime.now().isoformat(),
                "error": None,
            }

            print(f"    [OK] Completed {len(messages)} turns in {execution_time:.2f}s")

            return query_result

        except Exception as e:
            execution_time = time.time() - start_time
            print(f"    [ERROR] Error on turn {len(turns)+1}: {str(e)}")

            return {
                "query_id": query_id,
                "query_text": f"Multi-turn ({len(messages)} messages)",
                "chat_id": chat_id,
                "trace_id": None,
                "trace_ids": trace_ids if "trace_ids" in locals() else [],
                "is_multi_turn": True,
                "execution_time_ms": execution_time * 1000,
                "result": None,
                "turns": turns,
                "expected": {
                    "tool_calls": query_data.get("expected_tool_calls", []),
                    "has_entries": query_data.get("expected_has_entries", False),
                },
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    async def run_all_queries(
        self, queries: List[Dict[str, Any]], session_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Execute all queries in batch mode

        Args:
            queries: List of query data from test file
            session_id: Optional session ID for grouping

        Returns:
            List of query results
        """
        print(f"\n{'='*60}")
        print(f"Running {len(queries)} queries in batch mode...")
        print(f"{'='*60}\n")

        results = []

        # Execute all queries
        for i, query_data in enumerate(queries):
            print(f"[{i+1}/{len(queries)}]")
            result = await self.run_query(query_data, session_id)
            results.append(result)
            print()

        # Wait for Langfuse to sync traces
        print(f"{'='*60}")
        wait_mins = self.config["timing"]["initial_sync_wait_seconds"] / 60
        print(f"Waiting {wait_mins:.1f} minutes for Langfuse to sync traces...")
        print(f"{'='*60}\n")

        await asyncio.sleep(self.config["timing"]["initial_sync_wait_seconds"])

        print("Fetching traces from Langfuse with rate limit protection...\n")

        # Fetch traces one by one with delays to avoid rate limiting
        for i, result in enumerate(results):
            if result.get("chat_id"):
                search_session_id = session_id or result["query_id"]

                print(
                    f"  [{i+1}/{len(results)}] Fetching trace for: {search_session_id}"
                )

                # Add delay between fetches (skip first one)
                if i > 0:
                    time.sleep(self.config["timing"]["delay_between_fetches_seconds"])

                # Handle multi-turn queries differently
                if result.get("is_multi_turn"):
                    trace_summaries = self.fetch_all_traces_by_session(
                        search_session_id
                    )
                    if trace_summaries:
                        result["trace_summary"] = self._aggregate_multi_turn_traces(
                            trace_summaries
                        )
                        result["trace_summaries_individual"] = trace_summaries
                        validation = self.validate_query_result(result)
                        result["validation"] = validation
                    else:
                        print(
                            f"    [WARN] No traces found for multi-turn session: {search_session_id}"
                        )
                else:
                    # Single-turn query
                    trace_summary = self.fetch_trace_by_session(search_session_id)
                    if trace_summary:
                        result["trace_summary"] = trace_summary
                        validation = self.validate_query_result(result)
                        result["validation"] = validation
                    else:
                        print(
                            f"    [WARN] No trace found for session_id: {search_session_id}"
                        )

        return results

    def _extract_trace_summary(self, trace) -> Dict[str, Any]:
        """
        Extract trace summary from a detailed trace object

        Args:
            trace: Detailed trace object from Langfuse API

        Returns:
            Dictionary with trace summary
        """
        # Extract relevant information
        trace_summary = {
            "trace_id": trace.id,
            "duration_seconds": None,
            "llm_calls": 0,
            "tool_calls": [],
            "tool_call_details": [],  # Added to store detailed tool call info
            "total_tokens": 0,
            "total_cost": 0,
            "observations": [],
        }

        # Process observations
        if hasattr(trace, "observations") and trace.observations:
            print(f"    [DEBUG] Found {len(trace.observations)} observations in trace")
            for obs in trace.observations:
                obs_type = obs.type if hasattr(obs, "type") else None
                obs_name = obs.name if hasattr(obs, "name") else "unknown"

                # Count LLM generations
                if obs_type == "GENERATION":
                    trace_summary["llm_calls"] += 1

                    # Sum tokens
                    if hasattr(obs, "usage"):
                        usage = obs.usage
                        if usage and hasattr(usage, "total"):
                            trace_summary["total_tokens"] += usage.total
                        elif usage and isinstance(usage, dict):
                            trace_summary["total_tokens"] += usage.get(
                                "total_tokens", 0
                            )

                    # Sum cost
                    if (
                        hasattr(obs, "calculated_total_cost")
                        and obs.calculated_total_cost
                    ):
                        trace_summary["total_cost"] += obs.calculated_total_cost

                # Detect tool calls (spans with tool names)
                elif obs_type == "SPAN":
                    tool_names = [
                        "fetch_entries",
                        "create_entry",
                        "update_entry",
                        "aggregate_entries",
                    ]

                    # Debug: print observation name to see what we're matching against
                    print(f"    [DEBUG] Checking SPAN observation: '{obs_name}'")

                    if any(tool_name in obs_name for tool_name in tool_names):
                        # Extract tool name - use exact matching to avoid false positives
                        matched_tool = None
                        for tool_name in tool_names:
                            if obs_name == tool_name or obs_name.startswith(
                                f"tool_{tool_name}"
                            ):
                                matched_tool = tool_name
                                break

                        if matched_tool:
                            print(
                                f"    [DEBUG] Matched tool: {matched_tool} for observation: {obs_name}"
                            )
                            trace_summary["tool_calls"].append(matched_tool)

                            # Extract tool call details (input/output)
                            tool_detail = {
                                "tool_name": matched_tool,
                                "observation_name": obs_name,
                                "input": None,
                                "output": None,
                            }

                            # Get input
                            if hasattr(obs, "input"):
                                tool_detail["input"] = obs.input

                            # Get output
                            if hasattr(obs, "output"):
                                tool_detail["output"] = obs.output

                            trace_summary["tool_call_details"].append(tool_detail)
                        else:
                            print(
                                f"    [DEBUG] No exact match found for observation: {obs_name}"
                            )

                # Store observation summary
                trace_summary["observations"].append(
                    {
                        "type": obs_type,
                        "name": obs_name,
                    }
                )
        else:
            print(
                f"    [WARN] No observations found in detailed trace {trace.id[:8] if hasattr(trace, 'id') else 'unknown'}..."
            )

        # Get trace duration
        if hasattr(trace, "timestamp") and hasattr(trace, "updated_at"):
            try:
                start = datetime.fromisoformat(
                    str(trace.timestamp).replace("Z", "+00:00")
                )
                end = datetime.fromisoformat(
                    str(trace.updated_at).replace("Z", "+00:00")
                )
                duration = (end - start).total_seconds()
                trace_summary["duration_seconds"] = duration
            except (ValueError, TypeError):
                pass

        print(
            f"    [OK] Processed trace {trace.id[:8] if hasattr(trace, 'id') else 'unknown'}... ({trace_summary['llm_calls']} LLM calls, {len(trace_summary['tool_calls'])} tool calls with details)"
        )

        return trace_summary

    def fetch_trace_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch trace from Langfuse by session ID

        Args:
            session_id: Session ID used in the query

        Returns:
            Dictionary with trace summary or None if not found
        """
        try:
            # Step 1: Fetch basic traces for this session using the Langfuse API
            print(
                f"    [DEBUG] Langfuse API call: list(session_id='{session_id}', tags=['{self.batch_tag}'], limit=1)"
            )
            traces_response = self.langfuse.api.trace.list(
                session_id=session_id, tags=[self.batch_tag], limit=1
            )

            if not traces_response or not traces_response.data:
                print(f"    [WARN] No trace found for session {session_id}")
                return None

            basic_trace = traces_response.data[0]
            trace_id = basic_trace.id

            # Step 2: Fetch detailed trace with observations
            print(f"    [DEBUG] Fetching detailed trace: {trace_id[:8]}...")
            try:
                trace = self.langfuse.api.trace.get(trace_id)
            except Exception as e:
                print(f"    [ERROR] Failed to get detailed trace: {str(e)}")
                return None

            # Extract trace summary using helper method
            trace_summary = self._extract_trace_summary(trace)
            return trace_summary

        except Exception as e:
            print(f"    [ERROR] Error fetching trace for {session_id}: {str(e)}")
            return None

    def fetch_all_traces_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Fetch ALL traces for a session (important for multi-turn conversations)

        Args:
            session_id: Session ID used in the query

        Returns:
            List of trace summaries (one per turn in multi-turn conversations)
        """
        try:
            # Fetch ALL traces for this session (no limit)
            print(
                f"    [DEBUG] Fetching ALL traces for session: {session_id} (batch: {self.batch_tag})"
            )
            traces_response = self.langfuse.api.trace.list(
                session_id=session_id,  # No limit - get all traces
                tags=[self.batch_tag],  # Filter to current batch only
            )

            if not traces_response or not traces_response.data:
                print(f"    [WARN] No traces found for session {session_id}")
                return []

            print(
                f"    [DEBUG] Found {len(traces_response.data)} traces for session {session_id}"
            )

            # Fetch detailed info for each trace
            trace_summaries = []
            for i, basic_trace in enumerate(traces_response.data):
                try:
                    # Add delay between fetches (skip first one)
                    if i > 0:
                        time.sleep(
                            self.config["timing"][
                                "delay_between_multi_turn_fetches_seconds"
                            ]
                        )

                    trace_id = basic_trace.id
                    print(
                        f"    [DEBUG] Fetching trace {i+1}/{len(traces_response.data)}: {trace_id[:8]}..."
                    )
                    trace = self.langfuse.api.trace.get(trace_id)
                    trace_summary = self._extract_trace_summary(trace)
                    trace_summaries.append(trace_summary)
                except Exception as e:
                    print(
                        f"    [ERROR] Failed to fetch trace {basic_trace.id[:8]}...: {str(e)}"
                    )
                    continue

            return trace_summaries

        except Exception as e:
            print(f"    [ERROR] Error fetching traces for {session_id}: {str(e)}")
            return []

    def _aggregate_multi_turn_traces(
        self, trace_summaries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Combine tool calls and metrics from multiple traces (multi-turn conversations)

        Args:
            trace_summaries: List of trace summaries from all turns

        Returns:
            Aggregated trace summary with combined metrics
        """
        if not trace_summaries:
            return {
                "trace_ids": [],
                "tool_calls": [],
                "tool_call_details": [],
                "llm_calls": 0,
                "total_tokens": 0,
                "total_cost": 0,
                "duration_seconds": 0,
                "observations": [],
            }

        aggregated = {
            "trace_ids": [t["trace_id"] for t in trace_summaries],
            "tool_calls": [],
            "tool_call_details": [],
            "llm_calls": 0,
            "total_tokens": 0,
            "total_cost": 0,
            "duration_seconds": 0,
            "observations": [],
        }

        # Combine metrics from all traces
        for trace in trace_summaries:
            aggregated["tool_calls"].extend(trace.get("tool_calls", []))
            aggregated["tool_call_details"].extend(trace.get("tool_call_details", []))
            aggregated["llm_calls"] += trace.get("llm_calls", 0)
            aggregated["total_tokens"] += trace.get("total_tokens", 0)
            aggregated["total_cost"] += trace.get("total_cost", 0)
            if trace.get("duration_seconds"):
                aggregated["duration_seconds"] += trace.get("duration_seconds", 0)
            aggregated["observations"].extend(trace.get("observations", []))

        print(
            f"    [OK] Aggregated {len(trace_summaries)} traces: "
            f"{len(aggregated['tool_calls'])} total tool calls, "
            f"{aggregated['llm_calls']} LLM calls"
        )

        return aggregated

    def fetch_traces_batch(self, session_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Fetch all traces for this batch with retry logic

        Args:
            session_ids: List of session IDs to match traces

        Returns:
            Dictionary mapping session_id -> trace_summary
        """
        max_retries = self.config["retries"]["batch_fetch_max_retries"]
        retry_delay = self.config["retries"]["batch_fetch_retry_delay_seconds"]

        for attempt in range(max_retries):
            try:
                print(
                    f"    [DEBUG] Fetch attempt {attempt + 1}/{max_retries} - Fetching traces with tag: {self.batch_tag}"
                )

                # Fetch all traces with batch tag (with pagination support)
                all_traces = []
                page = 1
                while True:
                    traces_response = self.langfuse.api.trace.list(
                        tags=[self.batch_tag],
                        user_id=self.user_id,
                        limit=100,
                        page=page,
                    )

                    if not traces_response or not traces_response.data:
                        break

                    all_traces.extend(traces_response.data)

                    if len(traces_response.data) < 100:
                        break

                    page += 1

                if not all_traces:
                    if attempt < max_retries - 1:
                        sleep_time = retry_delay * (2**attempt)
                        print(
                            f"    [WARN] No traces found on attempt {attempt + 1}, retrying in {sleep_time}s..."
                        )
                        time.sleep(sleep_time)
                        continue
                    else:
                        print(
                            f"    [ERROR] No traces found after {max_retries} attempts for batch tag {self.batch_tag}"
                        )
                        return {}

                print(
                    f"    [OK] Fetched {len(all_traces)} basic traces across {page} page(s)"
                )

                # Build mapping of session_id -> trace
                trace_map = {}
                missing_sessions = set(session_ids)

                for i, basic_trace in enumerate(all_traces):
                    # Get detailed trace with observations using retry logic
                    detail_retries = 0
                    max_detail_retries = self.config["retries"][
                        "individual_trace_max_retries"
                    ]

                    while detail_retries < max_detail_retries:
                        try:
                            print(
                                f"    [DEBUG] Processing trace {i+1}/{len(all_traces)}: {basic_trace.id[:8]}..."
                            )
                            trace = self.langfuse.api.trace.get(basic_trace.id)
                            trace_summary = self._extract_trace_summary(trace)

                            # Map by session_id for lookup
                            if hasattr(trace, "session_id") and trace.session_id:
                                trace_map[trace.session_id] = trace_summary
                                missing_sessions.discard(trace.session_id)
                            else:
                                print(
                                    f"    [WARN] Trace {basic_trace.id[:8]}... has no session_id"
                                )
                            break

                        except Exception as e:
                            detail_retries += 1
                            if "429" in str(e) and detail_retries < max_detail_retries:
                                sleep_time = 2**detail_retries
                                print(
                                    f"    [WARN] Rate limit on trace detail. Sleeping {sleep_time}s..."
                                )
                                time.sleep(sleep_time)
                            else:
                                print(
                                    f"    [ERROR] Failed to fetch detailed trace {basic_trace.id[:8]}...: {str(e)}"
                                )
                                break

                print(
                    f"    [OK] Successfully mapped {len(trace_map)} traces by session_id"
                )

                # Check if we're missing any expected traces
                if missing_sessions and attempt < max_retries - 1:
                    sleep_time = retry_delay * (2**attempt)
                    print(
                        f"    [WARN] Missing {len(missing_sessions)} traces, retrying in {sleep_time}s..."
                    )
                    print(
                        f"    [WARN] Missing sessions: {list(missing_sessions)[:5]}..."
                    )
                    time.sleep(sleep_time)
                    continue
                elif missing_sessions:
                    print(
                        f"    [ERROR] Still missing {len(missing_sessions)} traces after {max_retries} attempts"
                    )
                    print(
                        f"    [ERROR] Missing sessions: {list(missing_sessions)[:10]}"
                    )

                return trace_map

            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    sleep_time = 2 ** (attempt + 1)
                    print(f"    [ERROR] Rate limit hit. Sleeping for {sleep_time}s...")
                    time.sleep(sleep_time)
                elif attempt >= max_retries - 1:
                    print(f"    [ERROR] Max retries reached: {str(e)}")
                    return {}
                else:
                    print(f"    [ERROR] Non-recoverable error: {str(e)}")
                    return {}

        return {}

    def validate_query_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate query result against expected behavior

        Args:
            result: Query result with expected values

        Returns:
            Validation summary dictionary
        """
        expected = result.get("expected", {})
        query_result = result.get("result", {})
        trace_summary = result.get("trace_summary", {})

        # Extract actual values
        actual_entries = query_result.get("entries", []) if query_result else []
        actual_has_entries = len(actual_entries) > 0
        actual_tool_calls = trace_summary.get("tool_calls", []) if trace_summary else []

        # Expected values
        expected_tool_calls = expected.get("tool_calls")
        expected_tool_calls_by_turn = expected.get("tool_calls_by_turn")
        expected_has_entries = expected.get("has_entries", False)

        # Validate tool calls
        if expected_tool_calls is not None:
            tool_calls_match = set(expected_tool_calls) == set(actual_tool_calls)
        else:
            tool_calls_match = True

        # Validate tool calls by turn (for multi-turn conversations)
        actual_tool_calls_by_turn = None
        tool_calls_by_turn_match = True
        if expected_tool_calls_by_turn is not None:
            trace_summaries_individual = result.get("trace_summaries_individual", [])
            actual_tool_calls_by_turn = [
                summary.get("tool_calls", []) if summary else []
                for summary in trace_summaries_individual
            ]

            if len(actual_tool_calls_by_turn) != len(expected_tool_calls_by_turn):
                tool_calls_by_turn_match = False
            else:
                for expected_turn_tools, actual_turn_tools in zip(
                    expected_tool_calls_by_turn, actual_tool_calls_by_turn
                ):
                    if set(expected_turn_tools) != set(actual_turn_tools):
                        tool_calls_by_turn_match = False
                        break

        # Validate entries
        has_entries_match = expected_has_entries == actual_has_entries

        # Overall pass/fail
        passed = (
            tool_calls_match
            and tool_calls_by_turn_match
            and has_entries_match
            and not result.get("error")
        )

        validation = {
            "passed": passed,
            "tool_calls_match": tool_calls_match,
            "tool_calls_by_turn_match": tool_calls_by_turn_match
            if expected_tool_calls_by_turn is not None
            else None,
            "has_entries_match": has_entries_match,
            "expected_tool_calls": expected_tool_calls,
            "actual_tool_calls": actual_tool_calls,
            "expected_tool_calls_by_turn": expected_tool_calls_by_turn,
            "actual_tool_calls_by_turn": actual_tool_calls_by_turn,
            "expected_has_entries": expected_has_entries,
            "actual_has_entries": actual_has_entries,
            "entry_count": len(actual_entries),
            "error": result.get("error"),
        }

        return validation

    def save_results(
        self, results: List[Dict[str, Any]], output_file: str = None
    ) -> str:
        """
        Save results to JSON file with summary statistics

        Args:
            results: List of query results
            output_file: Optional output file path

        Returns:
            Path to saved file
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            script_dir = Path(__file__).parent
            output_file = (
                script_dir / "data" / f"langfuse_trace_results_{timestamp}.json"
            )

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Calculate summary statistics
        total_queries = len(results)
        passed = sum(1 for r in results if r.get("validation", {}).get("passed", False))
        failed = total_queries - passed

        total_execution_time = sum(r.get("execution_time_ms", 0) for r in results)
        total_llm_calls = sum(
            (
                r.get("trace_summary", {}).get("llm_calls", 0)
                if r.get("trace_summary")
                else 0
            )
            for r in results
        )
        total_tool_calls = sum(
            (
                len(r.get("trace_summary", {}).get("tool_calls", []))
                if r.get("trace_summary")
                else 0
            )
            for r in results
        )
        total_tokens = sum(
            (
                r.get("trace_summary", {}).get("total_tokens", 0)
                if r.get("trace_summary")
                else 0
            )
            for r in results
        )
        total_cost = sum(
            (
                r.get("trace_summary", {}).get("total_cost", 0)
                if r.get("trace_summary")
                else 0
            )
            for r in results
        )

        # Build output data
        output_data = {
            "metadata": {
                "batch_tag": self.batch_tag,
                "total_queries": total_queries,
                "passed": passed,
                "failed": failed,
                "success_rate": (
                    f"{(passed/total_queries*100):.1f}%" if total_queries > 0 else "0%"
                ),
                "generated_at": datetime.now().isoformat(),
                "user_id": self.user_id,
                "wait_time_seconds": self.config["timing"]["initial_sync_wait_seconds"],
                "total_execution_time_ms": total_execution_time,
                "total_llm_calls": total_llm_calls,
                "total_tool_calls": total_tool_calls,
                "total_tokens": total_tokens,
                "total_cost_usd": f"${total_cost:.4f}",
            },
            "results": results,
        }

        # Save to file
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"{'='*60}")
        print(f"Results saved to: {output_path}")
        print(f"{'='*60}\n")

        # Generate minimal report
        minimal_file = output_path.parent / output_path.name.replace(
            "langfuse_trace_", "minimal_"
        )
        self.save_minimal_report(results, str(minimal_file))

        # Generate failures report if there are any failures
        if failed > 0:
            # Create failures filename based on the main output file
            failures_file = output_path.parent / output_path.name.replace(
                "langfuse_trace_", "failures_"
            )
            self.save_failures_report(results, str(failures_file))

        # Print summary
        print("SUMMARY:")
        print(f"  Total queries: {total_queries}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Success rate: {output_data['metadata']['success_rate']}")
        print(f"  Total execution time: {total_execution_time/1000:.2f}s")
        print(f"  Total LLM calls: {total_llm_calls}")
        print(f"  Total tool calls: {total_tool_calls}")
        print(f"  Total tokens: {total_tokens}")
        print(f"  Total cost: ${total_cost:.4f}")
        print()

        # Print failures
        if failed > 0:
            print("FAILURES:")
            for result in results:
                validation = result.get("validation", {})
                if not validation.get("passed", False):
                    query_id = result.get("query_id", "unknown")
                    query_text = result.get("query_text", "")
                    print(f"  [FAIL] {query_id}: {query_text}")

                    if result.get("error"):
                        print(f"    Error: {result['error']}")

                    if not validation.get("tool_calls_match"):
                        print(
                            f"    Expected tools: {validation.get('expected_tool_calls', [])}"
                        )
                        print(
                            f"    Actual tools: {validation.get('actual_tool_calls', [])}"
                        )

                    if not validation.get("has_entries_match"):
                        print(
                            f"    Expected has_entries: {validation.get('expected_has_entries')}"
                        )
                        print(
                            f"    Actual has_entries: {validation.get('actual_has_entries')}"
                        )

                    print()

        return str(output_path)

    def save_minimal_report(
        self, results: List[Dict[str, Any]], output_file: str = None
    ) -> str:
        """
        Save a minimal report with just query_id, query_text, trace_id, and message

        Args:
            results: List of query results
            output_file: Optional output file path

        Returns:
            Path to saved file
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            script_dir = Path(__file__).parent
            output_file = script_dir / "data" / f"minimal_report_{timestamp}.json"

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Extract minimal info from each result
        minimal_results = []
        for result in results:
            query_result = result.get("result", {})

            minimal_entry = {
                "query_id": result.get("query_id"),
                "query_text": result.get("query_text"),
                "trace_id": result.get("trace_id"),
                "message": query_result.get("message") if query_result else None,
            }
            minimal_results.append(minimal_entry)

        # Build output data
        output_data = {
            "metadata": {
                "batch_tag": self.batch_tag,
                "total_queries": len(results),
                "generated_at": datetime.now().isoformat(),
                "user_id": self.user_id,
            },
            "results": minimal_results,
        }

        # Save to file
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"{'='*60}")
        print(f"Minimal report saved to: {output_path}")
        print(f"{'='*60}\n")

        return str(output_path)

    def save_failures_report(
        self, results: List[Dict[str, Any]], output_file: str = None
    ) -> Optional[str]:
        """
        Generate a separate failures report with detailed failure information

        Args:
            results: List of query results
            output_file: Optional output file path (will auto-generate if None)

        Returns:
            Path to saved failures file, or None if no failures
        """
        # Filter failed results
        failures = [
            r for r in results if not r.get("validation", {}).get("passed", False)
        ]

        # Return None if no failures
        if not failures:
            return None

        # Extract failure details
        failure_details = []
        for result in failures:
            query_result = result.get("result", {})
            trace_summary = result.get("trace_summary", {})
            validation = result.get("validation", {})

            # Extract tool call details (only tool_name and input)
            tool_call_details = []
            if trace_summary:
                for tool_detail in trace_summary.get("tool_call_details", []):
                    # Extract just the input from the nested structure
                    tool_input = tool_detail.get("input", {})
                    if isinstance(tool_input, dict) and "input" in tool_input:
                        # Handle nested input structure
                        tool_input = tool_input.get("input")

                    tool_call_details.append(
                        {
                            "tool_name": tool_detail.get("tool_name"),
                            "input": tool_input,
                        }
                    )

            failure_detail = {
                "query_id": result.get("query_id"),
                "query_text": result.get("query_text"),
                "chat_id": result.get("chat_id"),
                "trace_id": result.get("trace_id"),
                "execution_time_ms": result.get("execution_time_ms"),
                "message": query_result.get("message") if query_result else None,
                "has_entries": (
                    len(query_result.get("entries", [])) > 0 if query_result else False
                ),
                "tool_call_details": tool_call_details,
                "expected_vs_actual": {
                    "expected_tool_calls": validation.get("expected_tool_calls", []),
                    "actual_tool_calls": validation.get("actual_tool_calls", []),
                    "expected_has_entries": validation.get(
                        "expected_has_entries", False
                    ),
                    "actual_has_entries": validation.get("actual_has_entries", False),
                },
            }

            failure_details.append(failure_detail)

        # Generate output file path if not provided
        if output_file is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            script_dir = Path(__file__).parent
            output_file = script_dir / "data" / f"failures_{timestamp}.json"

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build output data
        output_data = {
            "metadata": {
                "batch_tag": self.batch_tag,
                "total_failures": len(failures),
                "generated_at": datetime.now().isoformat(),
                "user_id": self.user_id,
            },
            "failures": failure_details,
        }

        # Save to file
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"{'='*60}")
        print(f"Failures report saved to: {output_path}")
        print(f"  Total failures: {len(failures)}")
        print(f"{'='*60}\n")

        return str(output_path)


async def main():
    """Main function to run the Langfuse tracer"""

    print("=" * 60)
    print("Langfuse-Based Tracer for Agent Service")
    print("=" * 60)
    print()

    # Check for required environment variables
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("[ERROR] OPENAI_API_KEY environment variable not set")
        return

    test_user_id = os.getenv("TEST_USER_ID")
    if not test_user_id:
        print("[ERROR] TEST_USER_ID environment variable not set")
        print("  Please add TEST_USER_ID to your .env file")
        print("  Get the user ID from Supabase dashboard > Authentication > Users")
        return

    print(f"[OK] Using test user ID: {test_user_id[:8]}...")
    print()

    # Initialize tracer
    tracer = LangfuseTracerV3(user_id=test_user_id, openai_api_key=openai_api_key)

    # Find input directory
    script_dir = Path(__file__).parent
    input_dir = script_dir / "input"

    if not input_dir.exists():
        print(f"[ERROR] Input directory '{input_dir}' not found")
        return

    # Find all JSON files in input directory
    json_files = list(input_dir.glob("*.json"))

    if not json_files:
        print(f"[ERROR] No JSON files found in '{input_dir}'")
        return

    print(f"Found {len(json_files)} test file(s) to process:")
    for i, json_file in enumerate(json_files):
        print(f"  {i+1}. {json_file.name}")
    print()

    # Process each file
    for json_file in json_files:
        print(f"\n{'='*60}")
        print(f"Processing: {json_file.name}")
        print(f"{'='*60}\n")

        try:
            # Load queries
            with open(json_file, "r") as f:
                data = json.load(f)

            queries = data.get("queries", [])

            if not queries:
                print(f"[WARN] Skipping: No queries found in {json_file.name}")
                continue

            # Run queries - don't pass a session_id so each query uses its own query_id
            results = await tracer.run_all_queries(queries, session_id=None)

            # Save results
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_file = (
                script_dir
                / "data"
                / f"langfuse_trace_{json_file.stem}_{timestamp}.json"
            )

            tracer.save_results(results, str(output_file))

        except Exception as e:
            print(f"[ERROR] Error processing {json_file.name}: {str(e)}")
            import traceback

            traceback.print_exc()
            continue

    print(f"\n{'='*60}")
    print("PROCESSING COMPLETE")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
