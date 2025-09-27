"""
Database connection utility for Supabase PostgreSQL
"""

import os
from typing import Optional

import httpx
from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from supabase import Client, create_client, ClientOptions


class DatabaseSettings(BaseSettings):
    """Database configuration settings"""

    supabase_url: str
    supabase_key: str
    supabase_service_role_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    model_config = ConfigDict(
        env_file=".env",  # Look for .env in current directory
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra environment variables
    )


class DatabaseConnection:
    """Supabase database connection manager"""

    def __init__(self):
        self.settings = DatabaseSettings()
        self._client: Optional[Client] = None
        self._service_client: Optional[Client] = None

        # Load OpenAI API key into environment for tests
        if hasattr(self.settings, "openai_api_key") and self.settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.settings.openai_api_key

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
                self.settings.supabase_url, self.settings.supabase_key, options=options
            )
        return self._client

    @property
    def service_client(self) -> Client:
        """Get the service role Supabase client (bypasses RLS)"""
        if self._service_client is None:
            if not self.settings.supabase_service_role_key:
                raise ValueError("SUPABASE_SERVICE_ROLE_KEY not configured")
            # Configure httpx client with proper timeout and verify settings
            httpx_client = httpx.Client(
                timeout=30.0,  # 30 second timeout
                verify=True,  # SSL verification enabled
            )
            options = ClientOptions(httpx_client=httpx_client)
            self._service_client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_service_role_key,
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
