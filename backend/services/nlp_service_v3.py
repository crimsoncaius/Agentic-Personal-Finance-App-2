"""
NLP Service V3 - Unified n-shot orchestrator with a single QuerySpec tool and 10-row cap.
This implementation does not modify V1/V2; it's an additive alternative.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from pydantic import ValidationError


class NLPServiceV3:
    """Unified orchestrator that plans, optionally fetches via QuerySpec, then finalizes reply."""

    def __init__(self, openai_api_key: str = None):
        # Import configuration and services with flexible paths
        try:
            from config.settings import settings
            from services.langfuse_service_v3 import (
                langfuse_service_v3 as langfuse_service,
            )
            from services.prompt_manager import PromptManager
            from database.connection import db_connection
            from models.query_spec import QuerySpec
        except ImportError:
            from backend.config.settings import settings
            from backend.services.langfuse_service_v3 import (
                langfuse_service_v3 as langfuse_service,
            )
            from backend.services.prompt_manager import PromptManager
            from backend.database.connection import db_connection
            from backend.models.query_spec import QuerySpec

        # Set up services
        import os

        if openai_api_key:
            os.environ["OPENAI_API_KEY"] = openai_api_key
        elif getattr(settings, "openai_api_key", None):
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

        self.langfuse = langfuse_service
        self.db = db_connection
        self.prompt_manager = PromptManager()
        self.QuerySpec = QuerySpec

        # Orchestration limits
        self.MAX_TURNS = 3
        self.MAX_FETCHES = 2
        self.ROW_CAP = 10

    async def process_query(
        self, text: str, user_id: str = None, session_id: str = None
    ) -> Dict[str, Any]:
        """Process a natural language query using unified prompt with optional fetch steps."""
        async with self.langfuse.trace_operation(
            name="nlp_query_processing_v3",
            user_id=user_id,
            session_id=session_id,
            input_data={"text": text},
            tags=["nlp", "v3"],
        ) as trace_id:
            facts: Dict[str, Any] = {}
            fetches = 0

            for _ in range(self.MAX_TURNS):
                # Build and call unified main prompt
                prompt = self._build_main_prompt(text, facts)
                response, generation_id = await self.langfuse.track_unified_llm_call(
                    name="v3_main",
                    model="gpt-4.1-nano",
                    messages=[{"role": "user", "content": prompt}],
                    trace_id=trace_id,
                    temperature=0.1,
                    operation_type="v3_plan",
                )

                try:
                    plan = json.loads(response.choices[0].message.content.strip())
                except Exception:
                    return {
                        "operation": "unsure",
                        "result": [],
                        "message": "I couldn't interpret that. Please refine your request.",
                    }

                action = plan.get("action")

                # Direct reply path
                if action == "reply":
                    msg = plan.get("reply") or "Done."
                    result_rows = self._extract_result_rows(facts)
                    return {
                        "operation": plan.get("operation", "read"),
                        "result": result_rows,
                        "message": msg,
                    }

                # Clarify path
                if action == "clarify":
                    question = plan.get("question") or "Could you clarify your request?"
                    return {"operation": "unsure", "result": [], "message": question}

                # Get data path (fetch existing entries)
                if action == "get":
                    if fetches >= self.MAX_FETCHES:
                        return {
                            "operation": "read",
                            "result": [],
                            "message": "I reached the data access limit for this request. Please refine your filters or ask for top results.",
                        }

                    try:
                        # Normalize the query spec to convert category names to UUIDs
                        normalized_spec_dict = self._normalize_query_spec_filters(
                            plan["query_spec"]
                        )
                        spec = self.QuerySpec(
                            **normalized_spec_dict
                        )  # validates limit <= 10
                    except (ValidationError, KeyError):
                        return {
                            "operation": "unsure",
                            "result": [],
                            "message": "I couldn't form a safe query. Try narrowing your request.",
                        }

                    rows, meta = await self._run_query_spec(spec, trace_id=trace_id)
                    fetches += 1

                    facts = self._summarize_facts(
                        facts, rows, meta, plan.get("query_spec")
                    )

                    # Give model one more turn with updated facts
                    continue

                # Create new entry path
                if action == "create":
                    try:
                        entry_data = plan["entry_data"]
                        # Here you would typically validate and save the entry
                        # For now, return success message
                        return {
                            "operation": "create",
                            "result": [entry_data],
                            "message": f"Created {entry_data.get('description', 'entry')} for ${entry_data.get('amount_cents', 0)/100:.2f}",
                        }
                    except (KeyError, ValueError) as e:
                        return {
                            "operation": "unsure",
                            "result": [],
                            "message": "I couldn't create that entry. Please check the details.",
                        }

                # Unknown action fallback
                return {
                    "operation": "unsure",
                    "result": [],
                    "message": "I'm not sure how to proceed. Please refine your request.",
                }

            # Finalization fallback after max turns
            msg = await self._finalize_with_facts(text, facts, trace_id)
            result_rows = self._extract_result_rows(facts)
            return {
                "operation": "read",
                "result": result_rows,
                "message": msg,
            }

    def _build_main_prompt(self, user_text: str, facts: Dict[str, Any]) -> str:
        categories = self._get_categories_sync()
        # Pass only category names to the LLM, not UUIDs
        category_names = [cat.get("name") for cat in categories if cat.get("name")]
        return self.prompt_manager.generate_unified_prompt_v3(
            user_input=user_text,
            facts=facts,
            current_date=date.today(),
            categories=category_names,
        )

    async def _run_query_spec(
        self, spec, trace_id: str = None, parent_id: str = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Translate QuerySpec to Supabase builder calls and execute (10-row cap enforced)."""
        import time

        start_time = time.time()

        try:
            # Start with base query
            query = self.db.client.table(spec.from_)

            # Apply select (columns)
            if spec.select:
                query = query.select(",".join(spec.select))

            # Apply where conditions
            if spec.where:
                for column, condition in spec.where.items():
                    if isinstance(condition, dict):
                        # Handle range conditions like {"gte": "2024-01-01", "lte": "2024-12-31"}
                        for op, value in condition.items():
                            if op == ">=":
                                query = query.gte(column, value)
                            elif op == "<=":
                                query = query.lte(column, value)
                            elif op == ">":
                                query = query.gt(column, value)
                            elif op == "<":
                                query = query.lt(column, value)
                            elif op == "!=":
                                query = query.neq(column, value)
                            elif op == "=":
                                query = query.eq(column, value)
                    else:
                        # Handle simple equality
                        query = query.eq(column, condition)

            # Apply group_by
            if spec.group_by:
                for group_col in spec.group_by:
                    query = query.select(f"{group_col}")

            # Apply order_by
            if spec.order_by:
                for order_spec in spec.order_by:
                    for column, direction in order_spec.items():
                        if direction.lower() == "desc":
                            query = query.order(column, desc=True)
                        else:
                            query = query.order(column, desc=False)

            # Apply limit (enforce 10-row cap)
            limit = min(spec.limit or 10, self.ROW_CAP)
            query = query.limit(limit)

            # Apply offset
            if spec.offset:
                query = query.range(spec.offset, spec.offset + limit - 1)

            # Execute query
            result = query.execute()

            duration = time.time() - start_time

            # Track query execution
            self.langfuse.track_query_spec_execution(
                trace_id=trace_id,
                parent_id=parent_id,
                query_spec=spec.model_dump(),
                execution_result={"rows": len(result.data), "data": result.data},
                duration=duration,
            )

            return result.data or [], {
                "returned": len(result.data or []),
                "duration": duration,
            }

        except Exception as e:
            duration = time.time() - start_time
            self.langfuse.track_query_spec_execution(
                trace_id=trace_id,
                parent_id=parent_id,
                query_spec=spec.model_dump(),
                execution_result=None,
                duration=duration,
                error=str(e),
            )
            raise

    def _summarize_facts(
        self,
        prior: Dict[str, Any],
        rows: List[Dict[str, Any]],
        meta: Dict[str, Any],
        query_spec: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Update facts structure to match new v3 format with queries array."""
        # Initialize facts structure if empty
        if not prior:
            prior = {"queries": []}

        new = dict(prior)

        # Convert category IDs back to names in query_spec for better readability
        readable_query_spec = self._convert_category_ids_to_names_in_spec(
            query_spec or {}
        )

        # Add new query result to queries array
        query_result = {
            "query_spec": readable_query_spec,
            "results": rows[: self.ROW_CAP] if rows else [],
        }

        if "queries" not in new:
            new["queries"] = []

        new["queries"].append(query_result)

        # Keep track of total rows for reference
        new["total_rows"] = prior.get("total_rows", 0) + meta.get("returned", 0)

        return new

    def _extract_result_rows(self, facts: Dict[str, Any]) -> List[Any]:
        """Extract result rows from new v3 facts structure."""
        if not facts or not facts.get("queries"):
            return []

        # Get the most recent query results
        queries = facts.get("queries", [])
        if not queries:
            return []

        # Return results from the latest query
        latest_results = queries[-1].get("results", [])
        if not isinstance(latest_results, list):
            return []

        return [self._coerce_json_value(row) for row in latest_results]

    def _coerce_json_value(self, value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, dict):
            return {k: self._coerce_json_value(v) for k, v in value.items()}
        return value

    async def _finalize_with_facts(
        self, user_text: str, facts: Dict[str, Any], trace_id: Optional[str]
    ) -> str:
        safe_facts = self._coerce_json_value(facts or {})
        prompt = (
            f"You are a finance assistant. Use ONLY these facts, do not invent data.\n"
            f"User: {user_text}\nFacts: {json.dumps(safe_facts)}\n"
            "Write a concise 1-3 sentence answer."
        )
        response, generation_id = await self.langfuse.track_response_llm_call(
            name="v3_finalize",
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}],
            trace_id=trace_id,
            response_type="user_friendly",
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    def _get_categories_sync(self) -> List[Dict[str, Any]]:
        """Get categories synchronously for prompt context."""
        try:
            result = self.db.client.table("category").select("id, name, type").execute()
            return result.data or []
        except Exception:
            return []

    def _resolve_category_name_to_id(self, category_name: str) -> Optional[str]:
        """Resolve category name to category_id."""
        try:
            result = (
                self.db.client.table("category")
                .select("id")
                .eq("name", category_name)
                .execute()
            )
            if result.data:
                return result.data[0]["id"]
        except Exception:
            pass
        return None

    def _resolve_category_id_to_name(self, category_id: str) -> Optional[str]:
        """Resolve category_id to category name."""
        try:
            result = (
                self.db.client.table("category")
                .select("name")
                .eq("id", category_id)
                .execute()
            )
            if result.data:
                return result.data[0]["name"]
        except Exception:
            pass
        return None

    def _convert_category_ids_to_names_in_spec(
        self, query_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert category IDs back to names in query spec for better readability in facts."""
        if not query_spec:
            return query_spec

        # Create a copy to avoid modifying the original
        readable_spec = query_spec.copy()

        # Convert category_id in where clause if present
        if "where" in readable_spec and isinstance(readable_spec["where"], dict):
            where_clause = readable_spec["where"].copy()
            if "category_id" in where_clause:
                category_id = where_clause["category_id"]
                if (
                    isinstance(category_id, str) and len(category_id) == 36
                ):  # UUID length check
                    category_name = self._resolve_category_id_to_name(category_id)
                    if category_name:
                        # Replace category_id with category_name for readability
                        del where_clause["category_id"]
                        where_clause["category_name"] = category_name
            readable_spec["where"] = where_clause

        return readable_spec

    def _normalize_category_filter_value(self, value: Any):
        if value is None:
            return None
        if isinstance(value, str):
            # Try to resolve category name to ID
            category_id = self._resolve_category_name_to_id(value)
            if category_id:
                return category_id
        return value

    def _normalize_query_spec_filters(
        self, spec_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize QuerySpec filters, converting category names to IDs where needed."""
        if "where" in spec_dict and isinstance(spec_dict["where"], dict):
            normalized_where = {}
            for key, value in spec_dict["where"].items():
                if key == "category_id" and isinstance(value, str):
                    # Try to resolve category name to ID
                    category_id = self._resolve_category_name_to_id(value)
                    if category_id:
                        normalized_where[key] = category_id
                    else:
                        normalized_where[key] = value
                else:
                    normalized_where[key] = value
            spec_dict["where"] = normalized_where
        return spec_dict

    async def _run_query_spec_with_normalization(
        self, spec, trace_id: str = None, parent_id: str = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Run QuerySpec with category name normalization."""
        # Normalize the spec to convert category names to IDs
        normalized_spec_dict = self._normalize_query_spec_filters(spec.model_dump())
        normalized_spec = self.QuerySpec(**normalized_spec_dict)
        return await self._run_query_spec(normalized_spec, trace_id, parent_id)
