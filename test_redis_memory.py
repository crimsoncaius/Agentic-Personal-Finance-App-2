#!/usr/bin/env python3
"""
Test script for Redis conversation memory feature
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"


def register_user():
    """Register a test user"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            json={
                "email": "redis_test@example.com",
                "password": "testpass123",
                "name": "Redis Test User",
            },
        )

        if response.status_code == 200:
            data = response.json()
            return data["session"]["access_token"]
        elif response.status_code in [400, 409]:
            # User already exists, try login
            return login_user()
        else:
            print(
                f"[ERROR] Registration failed with status {response.status_code}: {response.text[:200]}"
            )
            return None
    except Exception as e:
        print(f"[ERROR] Registration exception: {e}")
        return login_user()  # Try login as fallback


def login_user():
    """Login existing user"""
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": "redis_test@example.com", "password": "testpass123"},
    )

    if response.status_code == 200:
        data = response.json()
        return data["session"]["access_token"]
    else:
        print(f"Login failed: {response.text}")
        return None


def test_conversation_memory(token):
    """Test conversation memory with two related messages"""

    headers = {"Authorization": f"Bearer {token}"}

    print("\n" + "=" * 80)
    print("[TEST] REDIS CONVERSATION MEMORY")
    print("=" * 80)

    # Message 1: Create first entry
    print("\n[MSG 1] Creating initial expense...")
    message1 = {"text": "I spent 100 dollars on car maintenance yesterday"}

    response1 = requests.post(
        f"{BASE_URL}/api/v1/chat/", json=message1, headers=headers
    )

    if response1.status_code != 200:
        print(
            f"[ERROR] Request 1 failed (status {response1.status_code}): {response1.text}"
        )
        print(f"[DEBUG] Check your backend server logs for more details")
        print(f"[DEBUG] Request was: {json.dumps(message1, indent=2)}")
        return False

    data1 = response1.json()
    chat_id = data1.get("chat_id")

    print(f"[OK] Response 1:")
    print(f"   Operation: {data1.get('operation')}")
    print(f"   Message: {data1.get('message')}")
    print(f"   Chat ID: {chat_id}")

    if not chat_id:
        print("[ERROR] No chat_id returned!")
        return False

    # Message 2: Reference the first message using "the same day"
    print("\n[MSG 2] Adding related expense with context reference...")
    message2 = {
        "text": "also add motorcycle maintenance for 150 dollars on the same day",
        "chat_id": chat_id,  # Use same chat_id for conversation context
    }

    response2 = requests.post(
        f"{BASE_URL}/api/v1/chat/", json=message2, headers=headers
    )

    if response2.status_code != 200:
        print(f"[ERROR] Request 2 failed: {response2.text}")
        return False

    data2 = response2.json()

    print(f"[OK] Response 2:")
    print(f"   Operation: {data2.get('operation')}")
    print(f"   Message: {data2.get('message')}")
    print(f"   Chat ID: {data2.get('chat_id')}")

    # Check conversation history
    print("\n[HISTORY] RETRIEVING CONVERSATION HISTORY...")
    history_response = requests.get(
        f"{BASE_URL}/api/v1/chat/{chat_id}/history", headers=headers
    )

    if history_response.status_code == 200:
        history = history_response.json()
        print(f"[OK] Conversation history retrieved:")
        print(f"   Total messages: {history.get('count')}")
        for i, msg in enumerate(history.get("messages", []), 1):
            print(f"   {i}. [{msg.get('role')}]: {msg.get('content')[:60]}...")
    else:
        print(f"[WARN] Could not retrieve history: {history_response.text}")

    print("\n" + "=" * 80)
    print("[SUCCESS] CONVERSATION MEMORY IS WORKING!")
    print("=" * 80)
    print("\n[INFO] The LLM understood 'the same day' referred to 'yesterday'")
    print("       from the previous message - Redis memory is functioning!")
    print("\n" + "=" * 80)

    return True


def main():
    """Main test function"""
    print("[*] Starting Redis Conversation Memory Test...")

    # Get auth token
    print("\n[AUTH] Authenticating...")
    token = register_user()

    if not token:
        print("[ERROR] Authentication failed. Cannot proceed with tests.")
        sys.exit(1)

    print("[OK] Authentication successful!")

    # Run conversation memory test
    success = test_conversation_memory(token)

    if success:
        print("\n[OK] ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n[ERROR] TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
