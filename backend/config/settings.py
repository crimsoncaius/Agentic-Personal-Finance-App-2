"""
Application settings using Pydantic for type-safe configuration management.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment Configuration
    environment: str = "development"

    # Production Database Configuration
    supabase_url_prod: str
    supabase_key_prod: str
    supabase_service_role_key_prod: str

    # Development Database Configuration
    supabase_url_dev: str
    supabase_key_dev: str
    supabase_service_role_key_dev: str

    # LLM Configuration
    openai_api_key: str

    # Optional Services
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # NLP Service Configuration
    nlp_service_version: str = "v2"

    # Application Settings
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    debug: bool = False

    # API Settings
    api_title: str = "Expense Tracker MVP"
    api_description: str = "Personal finance app with natural language processing"
    api_version: str = "1.0.0"

    model_config = SettingsConfigDict(
        env_file=os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        ),
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
    def supabase_url(self) -> str:
        """Get the appropriate Supabase URL based on environment."""
        if self.is_production:
            return self.supabase_url_prod
        return self.supabase_url_dev

    @property
    def supabase_key(self) -> str:
        """Get the appropriate Supabase key based on environment."""
        if self.is_production:
            return self.supabase_key_prod
        return self.supabase_key_dev

    @property
    def supabase_service_role_key(self) -> str:
        """Get the appropriate Supabase service role key based on environment."""
        if self.is_production:
            return self.supabase_service_role_key_prod
        return self.supabase_service_role_key_dev

    def validate_nlp_service_version(self) -> bool:
        """Validate that the NLP service version is supported."""
        valid_versions = ["v1", "v2"]
        if self.nlp_service_version not in valid_versions:
            raise ValueError(
                f"Invalid NLP service version: {self.nlp_service_version}. "
                f"Valid versions are: {', '.join(valid_versions)}"
            )
        return True


# Global settings instance
settings = Settings()
