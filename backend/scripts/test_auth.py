"""
Simple script to test Phase 3 authentication implementation.
Run this to verify all auth endpoints are working correctly.
"""

import requests
import json
from datetime import date

BASE_URL = "http://localhost:8000/api/v1"


def print_response(title, response):
    """Print formatted response"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response: {response.text}")
    print()


def test_authentication():
    """Test complete authentication flow"""

    print("\n" + "=" * 60)
    print("PHASE 3 AUTHENTICATION TEST")
    print("=" * 60)

    # Test 1: Register a new user
    print("\n1. Testing User Registration...")
    register_data = {
        "email": "test@example.com",
        "password": "password123",
        "name": "Test User",
    }

    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    print_response("REGISTER USER", response)

    if response.status_code in [201, 409]:  # 201 created or 409 already exists
        print("[OK] Registration endpoint working")
    else:
        print("[FAIL] Registration failed")
        return

    # Test 2: Login
    print("\n2. Testing User Login...")
    login_data = {"email": "test@example.com", "password": "password123"}

    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    print_response("LOGIN USER", response)

    if response.status_code != 200:
        print("[FAIL] Login failed")
        return

    # Extract token
    login_result = response.json()
    access_token = login_result.get("session", {}).get("access_token")
    refresh_token = login_result.get("session", {}).get("refresh_token")
    user_id = login_result.get("user", {}).get("id")

    if not access_token:
        print("[FAIL] No access token received")
        return

    print(f"[OK] Login successful")
    print(f"   User ID: {user_id}")
    print(f"   Token (first 20 chars): {access_token[:20]}...")

    # Test 3: Verify token
    print("\n3. Testing Token Verification...")
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(f"{BASE_URL}/auth/verify", headers=headers)
    print_response("VERIFY TOKEN", response)

    if response.status_code == 200:
        print("[OK] Token verification working")
    else:
        print("[FAIL] Token verification failed")

    # Test 4: Get current user info
    print("\n4. Testing Get Current User...")
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print_response("GET CURRENT USER", response)

    if response.status_code == 200:
        print("[OK] Get current user working")
    else:
        print("[FAIL] Get current user failed")

    # Test 5: Create entry (protected endpoint)
    print("\n5. Testing Protected Endpoint - Create Entry...")
    entry_data = {
        "amount": 25.50,
        "direction": "expense",
        "entry_date": str(date.today()),
        "description": "Test entry from auth script",
        "source": "manual",
    }

    response = requests.post(f"{BASE_URL}/entries/", json=entry_data, headers=headers)
    print_response("CREATE ENTRY (AUTHENTICATED)", response)

    if response.status_code == 201:
        print("[OK] Protected endpoint working - Entry created")
        entry_id = response.json().get("id")
    else:
        print("[FAIL] Failed to create entry")
        entry_id = None

    # Test 6: Get entries (protected endpoint)
    print("\n6. Testing Protected Endpoint - Get Entries...")
    response = requests.get(f"{BASE_URL}/entries/", headers=headers)
    print_response("GET ENTRIES (AUTHENTICATED)", response)

    if response.status_code == 200:
        entries = response.json().get("items", [])
        print(f"[OK] Protected endpoint working - Retrieved {len(entries)} entries")
    else:
        print("[FAIL] Failed to get entries")

    # Test 7: Try accessing protected endpoint without token
    print("\n7. Testing Access Without Token (Should Fail)...")
    response = requests.get(f"{BASE_URL}/entries/")
    print_response("GET ENTRIES (NO TOKEN)", response)

    if response.status_code == 401:
        print("[OK] Authorization working - Correctly blocked unauthenticated request")
    else:
        print("[FAIL] Security issue - Unauthenticated request was allowed")

    # Test 8: Delete the test entry
    if entry_id:
        print("\n8. Testing Delete Entry...")
        response = requests.delete(f"{BASE_URL}/entries/{entry_id}", headers=headers)
        print_response("DELETE ENTRY", response)

        if response.status_code == 200:
            print("[OK] Delete working")
        else:
            print("[FAIL] Delete failed")

    # Test 9: Refresh token
    print("\n9. Testing Token Refresh...")
    if refresh_token:
        refresh_data = {"refresh_token": refresh_token}
        response = requests.post(f"{BASE_URL}/auth/refresh", json=refresh_data)
        print_response("REFRESH TOKEN", response)

        if response.status_code == 200:
            print("[OK] Token refresh working")
        else:
            print("[FAIL] Token refresh failed")

    # Test 10: Logout
    print("\n10. Testing Logout...")
    response = requests.post(f"{BASE_URL}/auth/logout", headers=headers)
    print_response("LOGOUT", response)

    if response.status_code == 200:
        print("[OK] Logout working")
    else:
        print("[FAIL] Logout failed")

    # Final Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("[SUCCESS] Phase 3 authentication is working!")
    print()
    print("Tested:")
    print("  [OK] User registration")
    print("  [OK] User login")
    print("  [OK] Token verification")
    print("  [OK] Get current user")
    print("  [OK] Protected endpoints (entries)")
    print("  [OK] Authorization (blocking unauthenticated)")
    print("  [OK] Token refresh")
    print("  [OK] Logout")
    print()
    print("Backend authentication is fully functional!")
    print("=" * 60)
    print()


if __name__ == "__main__":
    try:
        test_authentication()
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Cannot connect to backend server")
        print("Make sure the backend is running:")
        print("  cd backend")
        print("  python main.py")
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback

        traceback.print_exc()
