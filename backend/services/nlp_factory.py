"""
NLP Service Factory
Creates the appropriate NLP service instance based on configuration.
"""

from __future__ import annotations
from typing import Union, TYPE_CHECKING
from config.settings import settings
from models.schemas import ParseError

if TYPE_CHECKING:
    from services.nlp_service_v1 import NLPServiceV1
    from services.nlp_service_v2 import NLPServiceV2


def create_nlp_service(
    openai_api_key: str = None,
) -> Union[NLPServiceV1, NLPServiceV2]:
    """
    Factory function to create the appropriate NLP service instance.

    Args:
        openai_api_key: Optional OpenAI API key. If not provided, uses settings.

    Returns:
        NLPService or NLPServiceV2 instance based on configuration.

    Raises:
        ValueError: If an invalid service version is specified.
    """
    # Validate service version using settings validation
    settings.validate_nlp_service_version()

    # Create service based on version
    if settings.nlp_service_version == "v1":
        from services.nlp_service_v1 import NLPService

        return NLPService(openai_api_key)
    else:  # v2 (default)
        from services.nlp_service_v2 import NLPServiceV2

        return NLPServiceV2(openai_api_key)


def get_nlp_service_info() -> dict:
    """
    Get information about the current NLP service configuration.

    Returns:
        Dictionary with service version and class name.
    """
    if settings.nlp_service_version == "v1":
        return {
            "version": "v1",
            "class_name": "NLPServiceV1",
            "description": "Multi-node workflow with separate router, read, write, and unsure nodes",
        }
    else:
        return {
            "version": "v2",
            "class_name": "NLPServiceV2",
            "description": "Unified workflow with parse node and response generation nodes",
        }
