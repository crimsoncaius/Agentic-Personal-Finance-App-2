"""
Application settings using Pydantic for type-safe configuration management.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database Configuration
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: str

    # LLM Configuration
    openai_api_key: str

    # Optional Services
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # Application Settings
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    debug: bool = False
    environment: str = "development"

    # API Settings
    api_title: str = "Expense Tracker MVP"
    api_description: str = "Personal finance app with natural language processing"
    api_version: str = "1.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() in ("development", "dev")

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() in ("production", "prod")

    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.environment.lower() in ("testing", "test")


# Global settings instance
settings = Settings()
