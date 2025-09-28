"""
NLP service configuration.
"""

from .settings import settings


class NLPConfig:
    """NLP service configuration class."""

    @property
    def openai_api_key(self) -> str:
        """OpenAI API key."""
        return settings.openai_api_key

    @property
    def langfuse_public_key(self) -> str:
        """Langfuse public key for observability."""
        return settings.langfuse_public_key

    @property
    def langfuse_secret_key(self) -> str:
        """Langfuse secret key for observability."""
        return settings.langfuse_secret_key

    @property
    def langfuse_host(self) -> str:
        """Langfuse host URL."""
        return settings.langfuse_host

    @property
    def has_langfuse(self) -> bool:
        """Check if Langfuse is configured."""
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def observability_config(self) -> dict:
        """Observability configuration for Langfuse."""
        if not self.has_langfuse:
            return {}

        return {
            "public_key": self.langfuse_public_key,
            "secret_key": self.langfuse_secret_key,
            "host": self.langfuse_host,
        }


# Global NLP config instance
nlp_config = NLPConfig()
