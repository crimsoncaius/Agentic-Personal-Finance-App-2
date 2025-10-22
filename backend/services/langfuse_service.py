"""
Langfuse service V3 for NLP Service V3 observability and tracing.
Optimized for the multi-turn orchestration workflow with QuerySpec execution.
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple
from contextlib import asynccontextmanager

from langfuse import Langfuse

# Try both import paths to handle running from different directories
try:
    from config.settings import settings
except ImportError:
    from backend.config.settings import settings


class LangfuseService:
    """Langfuse service optimized for agent's multi-turn orchestration workflow."""

    def __init__(self, openai_api_key: str = None):
        """Initialize Langfuse service with configuration."""
        self.openai_api_key = openai_api_key or settings.openai_api_key

        # Initialize Langfuse client
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            self.langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            self.enabled = True
        else:
            self.langfuse = None
            self.enabled = False

        # Initialize OpenAI client
        from openai import OpenAI as OpenAIClient

        self.openai_client = OpenAIClient(api_key=self.openai_api_key)

    def flush(self):
        """Flush all pending events to Langfuse."""
        if self.enabled:
            self.langfuse.flush()

    @asynccontextmanager
    async def trace_operation(
        self,
        name: str,
        user_id: str = None,
        session_id: str = None,
        input_data: Any = None,
        tags: List[str] = None,
    ):
        """Context manager for tracing operations with automatic timing."""
        if not self.enabled:
            yield None
            return

        # Start a trace using the correct Langfuse API
        with self.langfuse.start_as_current_span(name=name, input=input_data) as span:
            # Update the trace with metadata
            self.langfuse.update_current_trace(
                name=name,
                user_id=user_id,
                session_id=session_id,
                input=input_data,
                tags=tags or [],
            )

            start_time = time.time()
            try:
                # Get the actual trace ID from the current observability context
                trace_id = self.langfuse.get_current_trace_id()
                yield trace_id
            finally:
                duration = time.time() - start_time
                # Update the span with completion info
                span.update(
                    output={
                        "duration_seconds": duration,
                        "completed_at": datetime.now().isoformat(),
                    },
                    metadata={"duration": duration},
                )
                self.flush()

    @asynccontextmanager
    async def span_operation(
        self,
        name: str,
        trace_id: str = None,
        parent_id: str = None,
        input_data: Any = None,
    ):
        """Context manager for spanning operations with automatic timing."""
        if not self.enabled:
            yield None
            return

        # Start a span using the correct Langfuse API
        with self.langfuse.start_as_current_span(name=name, input=input_data) as span:
            start_time = time.time()
            try:
                yield span.id
            finally:
                duration = time.time() - start_time
                span.update(
                    output={
                        "duration_seconds": duration,
                        "completed_at": datetime.now().isoformat(),
                    },
                    metadata={"duration": duration},
                )

    async def track_unified_llm_call(
        self,
        name: str,
        model: str,
        messages: List[Dict],
        trace_id: str = None,
        parent_id: str = None,
        temperature: float = 0.1,
        operation_type: str = "v3_plan",
    ) -> tuple:
        """
        Track a unified LLM call for V3's planning and orchestration.
        This handles the main planning loop with optional QuerySpec generation.
        """
        if not self.enabled:
            # Fallback to regular OpenAI call
            response = self.openai_client.chat.completions.create(
                model=model, messages=messages, temperature=temperature
            )
            return response, None

        # Start a generation using the correct Langfuse API
        with self.langfuse.start_as_current_generation(
            name=name,
            model=model,
            input=messages,
            metadata={
                "temperature": temperature,
                "operation_type": operation_type,
                "workflow_version": "v3",
            },
        ) as generation:
            start_time = time.time()

            try:
                # Make the LLM call
                response = self.openai_client.chat.completions.create(
                    model=model, messages=messages, temperature=temperature
                )

                # Calculate metrics
                duration = time.time() - start_time
                usage = {
                    "prompt_tokens": (
                        response.usage.prompt_tokens if response.usage else 0
                    ),
                    "completion_tokens": (
                        response.usage.completion_tokens if response.usage else 0
                    ),
                    "total_tokens": (
                        response.usage.total_tokens if response.usage else 0
                    ),
                }

                # Update generation with results
                generation.update(
                    output=(
                        response.choices[0].message.content
                        if response.choices
                        else None
                    ),
                    usage=usage,
                    metadata={
                        "duration": duration,
                        "model": model,
                        "temperature": temperature,
                        "operation_type": operation_type,
                        "workflow_version": "v3",
                        "response_id": response.id,
                        "finish_reason": (
                            response.choices[0].finish_reason
                            if response.choices
                            else None
                        ),
                    },
                )

                return response, generation.id

            except Exception as e:
                # Update generation with error
                generation.update(
                    output=None,
                    metadata={
                        "error": str(e),
                        "duration": time.time() - start_time,
                        "model": model,
                        "temperature": temperature,
                        "operation_type": operation_type,
                        "workflow_version": "v3",
                    },
                )
                raise

    async def track_response_llm_call(
        self,
        name: str,
        model: str,
        messages: List[Dict],
        trace_id: str = None,
        parent_id: str = None,
        temperature: float = 0.3,
        response_type: str = "user_friendly",
    ) -> tuple:
        """
        Track LLM call for response generation in V3 workflow.
        Used for finalizing responses with accumulated facts.
        """
        if not self.enabled:
            # Fallback to regular OpenAI call
            response = self.openai_client.chat.completions.create(
                model=model, messages=messages, temperature=temperature
            )
            return response, None

        # Start a generation using the correct Langfuse API
        with self.langfuse.start_as_current_generation(
            name=name,
            model=model,
            input=messages,
            metadata={
                "temperature": temperature,
                "response_type": response_type,
                "workflow_version": "v3",
            },
        ) as generation:
            start_time = time.time()

            try:
                # Make the LLM call
                response = self.openai_client.chat.completions.create(
                    model=model, messages=messages, temperature=temperature
                )

                # Calculate metrics
                duration = time.time() - start_time
                usage = {
                    "prompt_tokens": (
                        response.usage.prompt_tokens if response.usage else 0
                    ),
                    "completion_tokens": (
                        response.usage.completion_tokens if response.usage else 0
                    ),
                    "total_tokens": (
                        response.usage.total_tokens if response.usage else 0
                    ),
                }

                # Update generation with results
                generation.update(
                    output=(
                        response.choices[0].message.content
                        if response.choices
                        else None
                    ),
                    usage=usage,
                    metadata={
                        "duration": duration,
                        "model": model,
                        "temperature": temperature,
                        "response_type": response_type,
                        "workflow_version": "v3",
                        "response_id": response.id,
                        "finish_reason": (
                            response.choices[0].finish_reason
                            if response.choices
                            else None
                        ),
                    },
                )

                return response, generation.id

            except Exception as e:
                # Update generation with error
                generation.update(
                    output=None,
                    metadata={
                        "error": str(e),
                        "duration": time.time() - start_time,
                        "model": model,
                        "temperature": temperature,
                        "response_type": response_type,
                        "workflow_version": "v3",
                    },
                )
                raise

    def track_database_operation(
        self,
        operation: str,
        table: str,
        trace_id: str = None,
        parent_id: str = None,
        query_params: Dict = None,
        result_count: int = None,
        duration: float = None,
    ):
        """Track database operations with performance metrics for V3 workflow."""
        if not self.enabled:
            return None

        # Safely serialize query params (supports Pydantic v1/v2 and plain dicts)
        safe_query_params = query_params
        try:
            if hasattr(query_params, "model_dump"):
                safe_query_params = query_params.model_dump()
            elif hasattr(query_params, "dict"):
                safe_query_params = query_params.dict()
            elif not isinstance(query_params, dict):
                safe_query_params = str(query_params)
        except Exception:
            safe_query_params = str(query_params)

        # Provide explicit output so the span is never null in Langfuse
        output_data = {
            "operation": operation,
            "table": table,
            "query_params": safe_query_params,
            "result_count": result_count,
            "duration": duration,
            "status": "success" if result_count is not None else "unknown",
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "v3",
        }

        with self.langfuse.start_as_current_span(
            name=f"db_{operation}",
            input={
                "operation": operation,
                "table": table,
                "query_params": safe_query_params,
            },
            output=output_data,
            metadata={
                "operation_type": "database",
                "table": table,
                "result_count": result_count,
                "duration": duration,
                "workflow_version": "v3",
            },
        ) as span:
            return span.id

    def track_planning_turn(
        self,
        turn_number: int,
        trace_id: str = None,
        parent_id: str = None,
        action: str = None,
        facts: Dict = None,
        duration: float = None,
        error: str = None,
    ):
        """Track individual planning turns in the V3 orchestration loop."""
        if not self.enabled:
            return None

        turn_output = {
            "turn_number": turn_number,
            "action": action,
            "facts_count": len(facts) if facts else 0,
            "duration": duration,
            "error": error,
            "status": "success" if error is None else "error",
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "v3",
        }

        with self.langfuse.start_as_current_span(
            name=f"planning_turn_{turn_number}",
            input={"turn_number": turn_number, "action": action},
            output=turn_output,
            metadata={
                "operation_type": "planning_turn",
                "turn_number": turn_number,
                "action": action,
                "duration": duration,
                "error": error,
                "workflow_version": "v3",
            },
        ) as span:
            return span.id

    def track_query_spec_execution(
        self,
        trace_id: str = None,
        parent_id: str = None,
        query_spec: Dict = None,
        execution_result: Dict = None,
        duration: float = None,
        error: str = None,
    ):
        """Track QuerySpec execution in V3 workflow."""
        if not self.enabled:
            return None

        execution_output = {
            "query_spec": query_spec,
            "execution_result": execution_result,
            "duration": duration,
            "error": error,
            "status": "success" if error is None else "error",
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "v3",
        }

        with self.langfuse.start_as_current_span(
            name="query_spec_execution",
            input={"query_spec": query_spec},
            output=execution_output,
            metadata={
                "operation_type": "query_spec_execution",
                "duration": duration,
                "error": error,
                "workflow_version": "v3",
            },
        ) as span:
            return span.id

    def track_fact_accumulation(
        self,
        trace_id: str = None,
        parent_id: str = None,
        prior_facts: Dict = None,
        new_data: List = None,
        accumulated_facts: Dict = None,
        duration: float = None,
    ):
        """Track fact accumulation across multiple turns in V3 workflow."""
        if not self.enabled:
            return None

        accumulation_output = {
            "prior_facts_count": len(prior_facts) if prior_facts else 0,
            "new_data_count": len(new_data) if new_data else 0,
            "accumulated_facts_count": (
                len(accumulated_facts) if accumulated_facts else 0
            ),
            "duration": duration,
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "v3",
        }

        with self.langfuse.start_as_current_span(
            name="fact_accumulation",
            input={
                "prior_facts_count": len(prior_facts) if prior_facts else 0,
                "new_data_count": len(new_data) if new_data else 0,
            },
            output=accumulation_output,
            metadata={
                "operation_type": "fact_accumulation",
                "duration": duration,
                "workflow_version": "v3",
            },
        ) as span:
            return span.id

    def track_multi_turn_workflow(
        self,
        trace_id: str = None,
        total_turns: int = None,
        total_fetches: int = None,
        final_operation: str = None,
        duration: float = None,
        error: str = None,
    ):
        """Track overall multi-turn workflow performance for V3."""
        if not self.enabled:
            return None

        workflow_output = {
            "total_turns": total_turns,
            "total_fetches": total_fetches,
            "final_operation": final_operation,
            "duration": duration,
            "error": error,
            "status": "success" if error is None else "error",
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "v3",
        }

        with self.langfuse.start_as_current_span(
            name="multi_turn_workflow",
            input={
                "total_turns": total_turns,
                "total_fetches": total_fetches,
                "final_operation": final_operation,
            },
            output=workflow_output,
            metadata={
                "operation_type": "multi_turn_workflow",
                "total_turns": total_turns,
                "total_fetches": total_fetches,
                "duration": duration,
                "error": error,
                "workflow_version": "v3",
            },
        ) as span:
            return span.id

    def track_performance_metrics_v3(
        self, operation: str, trace_id: str = None, metrics: Dict = None
    ):
        """Track custom performance metrics for V3 workflow."""
        if not self.enabled:
            return None

        # Add V3-specific metadata
        v3_metrics = metrics or {}
        v3_metrics["workflow_version"] = "v3"

        self.langfuse.create_score(
            name=f"performance_v3_{operation}",
            trace_id=trace_id,
            value=v3_metrics.get("score", 0),
            metadata=v3_metrics,
        )

    def track_cost_metrics_v3(
        self, operation: str, trace_id: str = None, cost_data: Dict = None
    ):
        """Track cost-related metrics for V3 workflow."""
        if not self.enabled:
            return None

        # Add V3-specific metadata
        v3_cost_data = cost_data or {}
        v3_cost_data["workflow_version"] = "v3"

        self.langfuse.create_score(
            name=f"cost_v3_{operation}",
            trace_id=trace_id,
            value=v3_cost_data.get("total_cost", 0),
            metadata=v3_cost_data,
        )

    def track_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any] = None,
        tool_output: Any = None,
        trace_id: str = None,
        duration: float = None,
        error: str = None,
    ):
        """Track tool call execution for LangGraph ReAct agent."""
        if not self.enabled:
            return None

        tool_output_data = {
            "tool_name": tool_name,
            "input": tool_input,
            "output": tool_output,
            "duration": duration,
            "error": error,
            "status": "success" if error is None else "error",
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "v3",
        }

        with self.langfuse.start_as_current_span(
            name=f"tool_{tool_name}",
            input={"tool_name": tool_name, "input": tool_input},
            output=tool_output_data,
            metadata={
                "operation_type": "tool_call",
                "tool_name": tool_name,
                "duration": duration,
                "error": error,
                "workflow_version": "v3",
            },
        ) as span:
            return span.id


# Global Langfuse service instance
langfuse_service = LangfuseService()
