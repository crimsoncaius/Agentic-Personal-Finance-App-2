"""
Database connection utility for Supabase PostgreSQL
"""

import os
from typing import Optional

import httpx
from supabase import Client, create_client, ClientOptions

# Import configuration
from config.settings import settings


class DatabaseConnection:
    """Supabase database connection manager"""

    def __init__(self):
        self._client: Optional[Client] = None
        self._service_client: Optional[Client] = None

        # Load OpenAI API key into environment for tests
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
                settings.supabase_url, settings.supabase_key, options=options
            )
        return self._client

    @property
    def service_client(self) -> Client:
        """Get the service role Supabase client (bypasses RLS)"""
        if self._service_client is None:
            if not settings.supabase_service_role_key:
                raise ValueError("SUPABASE_SERVICE_ROLE_KEY not configured")
            # Configure httpx client with proper timeout and verify settings
            httpx_client = httpx.Client(
                timeout=30.0,  # 30 second timeout
                verify=True,  # SSL verification enabled
            )
            options = ClientOptions(httpx_client=httpx_client)
            self._service_client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key,
                options=options,
            )
        return self._service_client

    def get_authenticated_client(self, token: str) -> Client:
        """Get a Supabase client with JWT token for RLS

        Args:
            token: JWT token from Supabase Auth

        Returns:
            Supabase client configured with the JWT token
        """
        # Create a new client instance
        options = ClientOptions(
            httpx_client=httpx.Client(
                timeout=30.0,
                verify=True,
            )
        )

        client = create_client(
            settings.supabase_url, settings.supabase_key, options=options
        )

        # Set the session with the JWT token
        # This makes auth.uid() available in RLS policies
        try:
            client.auth.set_session(
                {
                    "access_token": token,
                    "refresh_token": "",  # Not needed for RLS
                }
            )
        except Exception as e:
            print(f"Warning: Could not set session on authenticated client: {e}")
            # Fallback: try to set the token directly in headers
            client.auth._client.headers.update({"Authorization": f"Bearer {token}"})

        return client

    async def test_connection(self) -> bool:
        """Test database connection"""
        try:
            # Simple query to test connection
            self.client.table("category").select("id").limit(1).execute()
            return True
        except Exception as e:
            print(f"Database connection test failed: {e}")
            return False


# Global database connection instance
db_connection = DatabaseConnection()
