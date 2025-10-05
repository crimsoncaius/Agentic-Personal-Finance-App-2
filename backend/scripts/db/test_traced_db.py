#!/usr/bin/env python3
"""
Test the traced database connection
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

try:
    from database.connection import db_connection

    print("Database connection imported successfully")
except ImportError as e:
    print(f"Failed to import database connection: {e}")
    sys.exit(1)


class MockTracer:
    """Mock tracer for testing"""

    def __init__(self):
        self.db_operations = []
        self.llm_calls = []

    def _log_db_operation(self, operation, table, details):
        print(f"DB Operation: {operation} on {table} - {details}")
        self.db_operations.append(
            {
                "operation": operation,
                "table": table,
                "details": details,
                "start_time": datetime.now().isoformat(),
                "status": "started",
            }
        )

    def _log_db_execution(
        self, operation, table, execution_time_ms, result_count, error
    ):
        print(
            f"DB Execution: {operation} on {table} - {execution_time_ms}ms, {result_count} rows, error: {error}"
        )
        # Find and update the matching operation
        for op in reversed(self.db_operations):
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


async def test_traced_connection():
    """Test traced database connection"""
    try:
        print("Testing traced database connection...")

        # Create mock tracer
        tracer = MockTracer()

        # Create traced database connection
        traced_db = TracedDatabaseConnection(db_connection, tracer)

        # Test category table
        print("Testing traced category table...")
        result = traced_db.client.table("category").select("id").limit(1).execute()
        print(f"Traced category table test: {len(result.data)} rows returned")

        # Test entry table
        print("Testing traced entry table...")
        result = traced_db.client.table("entry").select("id").limit(1).execute()
        print(f"Traced entry table test: {len(result.data)} rows returned")

        print("Traced database connection test PASSED")
        return True

    except Exception as e:
        print(f"Traced database connection test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    import asyncio

    success = asyncio.run(test_traced_connection())
    if success:
        print("SUCCESS: Traced database is accessible")
    else:
        print("FAILURE: Traced database is not accessible")

