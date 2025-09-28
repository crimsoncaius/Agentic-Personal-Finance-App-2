"""
Database configuration and connection settings.
"""

from .settings import settings


class DatabaseConfig:
    """Database configuration class."""

    @property
    def supabase_url(self) -> str:
        """Supabase project URL."""
        return settings.supabase_url

    @property
    def supabase_key(self) -> str:
        """Supabase anon key for client operations."""
        return settings.supabase_key

    @property
    def supabase_service_key(self) -> str:
        """Supabase service role key for admin operations."""
        return settings.supabase_service_role_key

    @property
    def connection_params(self) -> dict:
        """Database connection parameters."""
        return {
            "url": self.supabase_url,
            "key": self.supabase_key,
            "service_key": self.supabase_service_key,
        }


# Global database config instance
db_config = DatabaseConfig()
