"""
Database connection utility for Supabase PostgreSQL
"""

import os
from typing import Optional

import httpx
from supabase import Client, create_client, ClientOptions

# Import configuration
try:
    from config.database import db_config
except ImportError:
    from backend.config.database import db_config


class DatabaseConnection:
    """Supabase database connection manager"""

    def __init__(self):
        self._client: Optional[Client] = None
        self._service_client: Optional[Client] = None

        # Load OpenAI API key into environment for tests
        try:
            from config.settings import settings
        except ImportError:
            from backend.config.settings import settings

        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

    @property
    def client(self) -> Client:
        """Get the standard Supabase client (uses anon key)"""
        if self._client is None:
            # Configure httpx client with proper timeout and verify settings
            httpx_client = httpx.Client(
                timeout=30.0,  # 30 second timeout
                verify=True,  # SSL verification enabled
            )
            options = ClientOptions(httpx_client=httpx_client)
            self._client = create_client(
                db_config.supabase_url, db_config.supabase_key, options=options
            )
        return self._client

    @property
    def service_client(self) -> Client:
        """Get the service role Supabase client (bypasses RLS)"""
        if self._service_client is None:
            if not db_config.supabase_service_key:
                raise ValueError("SUPABASE_SERVICE_ROLE_KEY not configured")
            # Configure httpx client with proper timeout and verify settings
            httpx_client = httpx.Client(
                timeout=30.0,  # 30 second timeout
                verify=True,  # SSL verification enabled
            )
            options = ClientOptions(httpx_client=httpx_client)
            self._service_client = create_client(
                db_config.supabase_url,
                db_config.supabase_service_key,
                options=options,
            )
        return self._service_client

    async def test_connection(self) -> bool:
        """Test database connection"""
        try:
            # Simple query to test connection
            result = self.client.table("category").select("id").limit(1).execute()
            return True
        except Exception as e:
            print(f"Database connection test failed: {e}")
            return False


# Global database connection instance
db_connection = DatabaseConnection()
