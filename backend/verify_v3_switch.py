"""
Quick verification that NLP Service V3 is properly configured
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Force reload of environment variables BEFORE importing settings
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)

from services.nlp_factory import create_nlp_service, get_nlp_service_info
from config.settings import Settings

# Create fresh settings instance to pick up new environment variables
settings = Settings()


def verify_v3_switch():
    """Verify that V3 is properly configured"""

    print("=" * 80)
    print("NLP Service V3 Switch Verification")
    print("=" * 80)

    # Check settings
    print(f"\n1. Settings Configuration:")
    print(f"   NLP Service Version: {settings.nlp_service_version}")

    # Check service info
    print(f"\n2. Service Info:")
    info = get_nlp_service_info()
    for key, value in info.items():
        print(f"   {key}: {value}")

    # Test service creation
    print(f"\n3. Service Creation Test:")
    try:
        service = create_nlp_service()
        print(f"   Service Type: {type(service).__name__}")
        print(f"   Module: {type(service).__module__}")
        print(f"   [OK] Service created successfully!")
    except Exception as e:
        print(f"   [FAIL] Error creating service: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Verify it's V3
    print(f"\n4. Verification:")
    if type(service).__name__ == "NLPServiceV3":
        print(f"   [PASS] Correctly using NLPServiceV3")
    else:
        print(f"   [FAIL] Wrong service type: {type(service).__name__}")
        return False

    # Check V3 specific attributes
    print(f"\n5. V3 Specific Features:")
    has_checkpointer = hasattr(service, "checkpointer")
    has_redis = hasattr(service, "redis")
    has_create_agent = hasattr(service, "_create_agent")

    print(f"   Has checkpointer: {'[OK]' if has_checkpointer else '[MISSING]'}")
    print(f"   Has redis: {'[OK]' if has_redis else '[MISSING]'}")
    print(f"   Has _create_agent: {'[OK]' if has_create_agent else '[MISSING]'}")

    if all([has_checkpointer, has_redis, has_create_agent]):
        print(f"\n{'=' * 80}")
        print("[SUCCESS] NLP Service V3 is properly configured and ready!")
        print(f"{'=' * 80}")
        return True
    else:
        print(f"\n{'=' * 80}")
        print("[FAILED] Some V3 features are missing")
        print(f"{'=' * 80}")
        return False


if __name__ == "__main__":
    success = verify_v3_switch()
    sys.exit(0 if success else 1)
