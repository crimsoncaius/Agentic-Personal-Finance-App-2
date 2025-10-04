"""
Langfuse service V2 for NLP Service V2 observability and tracing.
Optimized for the simplified V2 workflow: parse → response nodes.
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from contextlib import asynccontextmanager

from langfuse import Langfuse

# Try both import paths to handle running from different directories
try:
    from config.settings import settings
except ImportError:
    from backend.config.settings import settings


class LangfuseServiceV3:
    """Langfuse service optimized for NLP Service V2's simplified workflow."""

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
                yield span.id
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
        operation_type: str = "unified_parse",
    ) -> tuple:
        """
        Track a unified LLM call for V2's parse node.
        This handles both operation detection and data extraction in one call.
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
                "workflow_version": "v2",
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
                        "workflow_version": "v2",
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
                        "workflow_version": "v2",
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
        temperature: float = 0.7,
        response_type: str = "user_friendly",
    ) -> tuple:
        """
        Track LLM call for response generation in V2 workflow.
        Higher temperature for more natural responses.
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
                "workflow_version": "v2",
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
                        "workflow_version": "v2",
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
                        "workflow_version": "v2",
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
        """Track database operations with performance metrics."""
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
            "workflow_version": "v2",
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
                "workflow_version": "v2",
            },
        ) as span:
            return span.id

    def track_workflow_node_v2(
        self,
        node_name: str,
        trace_id: str = None,
        parent_id: str = None,
        input_data: Any = None,
        output_data: Any = None,
        duration: float = None,
        error: str = None,
        operation_type: str = None,
    ):
        """
        Track LangGraph workflow node execution for V2.
        Optimized for parse → response node structure.
        """
        if not self.enabled:
            return None

        # Wrap provided output in a richer payload so the span preview is useful
        workflow_output = {
            "node_name": node_name,
            "node_type": "workflow_v2",
            "operation_type": operation_type,
            "input_data": input_data,
            "output_data": output_data,
            "duration": duration,
            "error": error,
            "status": "success" if error is None else "error",
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "v2",
        }

        with self.langfuse.start_as_current_span(
            name=f"workflow_v2_{node_name}",
            input=input_data,
            output=workflow_output,
            metadata={
                "node_type": "workflow_v2",
                "node_name": node_name,
                "operation_type": operation_type,
                "duration": duration,
                "error": error,
                "workflow_version": "v2",
            },
        ) as span:
            return span.id

    def track_performance_metrics_v2(
        self, operation: str, trace_id: str = None, metrics: Dict = None
    ):
        """Track custom performance metrics for V2 workflow."""
        if not self.enabled:
            return None

        # Add V2-specific metadata
        v2_metrics = metrics or {}
        v2_metrics["workflow_version"] = "v2"

        self.langfuse.create_score(
            name=f"performance_v2_{operation}",
            trace_id=trace_id,
            value=v2_metrics.get("score", 0),
            metadata=v2_metrics,
        )

    def track_cost_metrics_v2(
        self, operation: str, trace_id: str = None, cost_data: Dict = None
    ):
        """Track cost-related metrics for V2 workflow."""
        if not self.enabled:
            return None

        # Add V2-specific metadata
        v2_cost_data = cost_data or {}
        v2_cost_data["workflow_version"] = "v2"

        self.langfuse.create_score(
            name=f"cost_v2_{operation}",
            trace_id=trace_id,
            value=v2_cost_data.get("total_cost", 0),
            metadata=v2_cost_data,
        )

    def track_parse_operation(
        self,
        trace_id: str = None,
        parent_id: str = None,
        input_text: str = None,
        parsed_data: Dict = None,
        operation: str = None,
        duration: float = None,
        error: str = None,
    ):
        """Specialized tracking for V2's unified parse operation."""
        if not self.enabled:
            return None

        parse_output = {
            "operation": operation,
            "parsed_data": parsed_data,
            "input_text": input_text,
            "duration": duration,
            "error": error,
            "status": "success" if error is None else "error",
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "v2",
        }

        with self.langfuse.start_as_current_span(
            name="unified_parse",
            input={"text": input_text},
            output=parse_output,
            metadata={
                "operation_type": "unified_parse",
                "parsed_operation": operation,
                "duration": duration,
                "error": error,
                "workflow_version": "v2",
            },
        ) as span:
            return span.id

    def track_response_operation(
        self,
        response_type: str,
        trace_id: str = None,
        parent_id: str = None,
        input_data: Any = None,
        response_message: str = None,
        duration: float = None,
        error: str = None,
    ):
        """Specialized tracking for V2's response generation operations."""
        if not self.enabled:
            return None

        response_output = {
            "response_type": response_type,
            "response_message": response_message,
            "input_data": input_data,
            "duration": duration,
            "error": error,
            "status": "success" if error is None else "error",
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "v2",
        }

        with self.langfuse.start_as_current_span(
            name=f"response_{response_type}",
            input=input_data,
            output=response_output,
            metadata={
                "operation_type": "response_generation",
                "response_type": response_type,
                "duration": duration,
                "error": error,
                "workflow_version": "v2",
            },
        ) as span:
            return span.id


# Global Langfuse service instance for V2
langfuse_service_v3 = LangfuseServiceV3()
