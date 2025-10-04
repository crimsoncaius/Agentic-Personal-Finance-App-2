"""
Simplified Langfuse service for observability and tracing in the Expense Tracker MVP.
Uses the correct Langfuse API patterns based on the official documentation.
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


class LangfuseServiceV2:
    """Simplified service for managing Langfuse observability and tracing."""

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

    async def track_llm_call(
        self,
        name: str,
        model: str,
        messages: List[Dict],
        trace_id: str = None,
        parent_id: str = None,
        temperature: float = 0.1,
    ) -> tuple:
        """Track an LLM call with comprehensive metrics."""
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
            metadata={"temperature": temperature},
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
            },
        ) as span:
            return span.id

    def track_workflow_node(
        self,
        node_name: str,
        trace_id: str = None,
        parent_id: str = None,
        input_data: Any = None,
        output_data: Any = None,
        duration: float = None,
        error: str = None,
    ):
        """Track LangGraph workflow node execution."""
        if not self.enabled:
            return None

        # Wrap provided output in a richer payload so the span preview is useful
        workflow_output = {
            "node_name": node_name,
            "node_type": "workflow",
            "input_data": input_data,
            "output_data": output_data,
            "duration": duration,
            "error": error,
            "status": "success" if error is None else "error",
            "timestamp": datetime.now().isoformat(),
        }

        with self.langfuse.start_as_current_span(
            name=f"workflow_{node_name}",
            input=input_data,
            output=workflow_output,
            metadata={
                "node_type": "workflow",
                "node_name": node_name,
                "duration": duration,
                "error": error,
            },
        ) as span:
            return span.id

    def track_performance_metrics(
        self, operation: str, trace_id: str = None, metrics: Dict = None
    ):
        """Track custom performance metrics."""
        if not self.enabled:
            return None

        self.langfuse.create_score(
            name=f"performance_{operation}",
            trace_id=trace_id,
            value=metrics.get("score", 0) if metrics else 0,
            metadata=metrics or {},
        )

    def track_cost_metrics(
        self, operation: str, trace_id: str = None, cost_data: Dict = None
    ):
        """Track cost-related metrics."""
        if not self.enabled:
            return None

        self.langfuse.create_score(
            name=f"cost_{operation}",
            trace_id=trace_id,
            value=cost_data.get("total_cost", 0) if cost_data else 0,
            metadata=cost_data or {},
        )


# Global Langfuse service instance
langfuse_service_v2 = LangfuseServiceV2()
