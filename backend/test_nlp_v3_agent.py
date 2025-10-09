"""
Test script for NLP Service V3 with LangGraph ReAct Agent
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from services.nlp_service_v3 import NLPServiceV3
from config.settings import settings


async def test_nlp_service_v3():
    """Test the NLP Service V3 with various queries"""

    print("=" * 80)
    print("Testing NLP Service V3 with LangGraph ReAct Agent")
    print("=" * 80)

    # Initialize service
    service = NLPServiceV3()

    # Test user_id - Valid user with 930 entries in database
    test_user_id = "00000000-0000-0000-0000-000000000001"

    # Test queries
    test_queries = [
        {
            "name": "Read Query - Recent Expenses",
            "text": "Show me my recent expenses",
            "expected_operation": "read",
        },
        {
            "name": "Write Query - Create Expense",
            "text": "I spent $50 on groceries today",
            "expected_operation": "write",
        },
        {
            "name": "Read Query - Specific Category",
            "text": "What did I spend on food this month?",
            "expected_operation": "read",
        },
        {
            "name": "Update Query",
            "text": "Change the amount of my last grocery expense to $75",
            "expected_operation": "write",
        },
        {
            "name": "Ambiguous Query",
            "text": "Hello, how are you?",
            "expected_operation": "unsure",
        },
    ]

    for i, test_case in enumerate(test_queries, 1):
        print(f"\n{'=' * 80}")
        print(f"Test {i}: {test_case['name']}")
        print(f"{'=' * 80}")
        print(f"Query: {test_case['text']}")
        print(f"Expected Operation: {test_case['expected_operation']}")
        print(f"{'-' * 80}")

        try:
            # Process query
            result = await service.process_query(
                text=test_case["text"],
                user_id=test_user_id,
                session_id="test_session",
                chat_id=f"test_chat_{i}",
            )

            # Display results
            print(f"\n[OK] Response received:")
            print(f"  Operation: {result.get('operation')}")
            print(f"  Chat ID: {result.get('chat_id')}")
            print(f"  Message: {result.get('message')}")
            print(f"  Results count: {len(result.get('result', []))}")

            if result.get("result"):
                print(f"\n  Sample results:")
                for entry in result["result"][:3]:  # Show first 3
                    if isinstance(entry, dict):
                        print(
                            f"    - {entry.get('description', 'N/A')}: ${entry.get('amount', 0):.2f}"
                        )

            # Check if operation matches expected
            if result["operation"] == test_case["expected_operation"]:
                print(f"\n[PASS] Test PASSED - Operation matches expected")
            else:
                print(
                    f"\n[WARN] Test WARNING - Operation '{result['operation']}' doesn't match expected '{test_case['expected_operation']}'"
                )

        except Exception as e:
            print(f"\n[FAIL] Test FAILED with error:")
            print(f"  {type(e).__name__}: {str(e)}")
            import traceback

            traceback.print_exc()

    print(f"\n{'=' * 80}")
    print("Testing Complete")
    print(f"{'=' * 80}")


async def test_conversation_memory():
    """Test that Redis conversation memory works"""

    print("\n" + "=" * 80)
    print("Testing Conversation Memory with Redis")
    print("=" * 80)

    service = NLPServiceV3()
    test_user_id = "00000000-0000-0000-0000-000000000001"  # Valid user with data
    chat_id = "memory_test_chat"

    # First message
    print("\n[MSG] Message 1: Creating an expense...")
    result1 = await service.process_query(
        text="I spent $25 on lunch today", user_id=test_user_id, chat_id=chat_id
    )
    print(f"Response: {result1.get('message')}")

    # Second message referencing the first
    print("\n[MSG] Message 2: Following up on the previous expense...")
    result2 = await service.process_query(
        text="Actually, change that to $30", user_id=test_user_id, chat_id=chat_id
    )
    print(f"Response: {result2.get('message')}")

    if "30" in result2.get("message", ""):
        print("\n[PASS] Conversation memory is working - agent understood the context!")
    else:
        print(
            "\n[WARN] Conversation memory might not be working - agent didn't seem to understand context"
        )

    print("=" * 80)


if __name__ == "__main__":
    print("\n[*] Starting NLP Service V3 Tests\n")

    # Run basic tests
    asyncio.run(test_nlp_service_v3())

    # Run memory tests
    asyncio.run(test_conversation_memory())

    print("\n[*] All tests completed!\n")
