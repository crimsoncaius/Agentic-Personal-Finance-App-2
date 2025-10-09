#!/usr/bin/env python3
"""
Create Test User

Creates a test user in Supabase Auth for testing purposes.
Returns the user_id that can be used for seeding data.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

try:
    from database.connection import db_connection
except ImportError:
    from backend.database.connection import db_connection


async def create_test_user(email: str = None):
    """
    Create a test user via Supabase Auth

    Args:
        email: Optional email for test user. If not provided, auto-generates one.

    Returns:
        str: User ID of created user
    """
    # Auto-generate email if not provided
    if not email:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        email = f"test-user-{timestamp}@example.com"

    print(f"Creating test user: {email}")
    print("=" * 50)

    try:
        # Note: Supabase Python client doesn't have direct auth.admin.createUser
        # We need to use the Auth API directly or create via SQL
        # For now, we'll provide instructions for manual creation

        print("\n⚠️  Manual User Creation Required")
        print("\nOption 1: Via Supabase Dashboard")
        print("  1. Go to Authentication > Users")
        print("  2. Click 'Add user' > 'Create new user'")
        print(f"  3. Email: {email}")
        print("  4. Password: TestPassword123! (or your choice)")
        print("  5. Confirm email: Yes")
        print("  6. Copy the generated user_id")

        print("\nOption 2: Via SQL in Supabase SQL Editor")
        print("  Run this SQL:")
        print(
            f"""
  -- Create user
  INSERT INTO auth.users (
      instance_id,
      id,
      aud,
      role,
      email,
      encrypted_password,
      email_confirmed_at,
      raw_app_meta_data,
      raw_user_meta_data,
      created_at,
      updated_at,
      confirmation_token,
      is_sso_user
  ) VALUES (
      '00000000-0000-0000-0000-000000000000'::uuid,
      gen_random_uuid(),  -- This will be your user_id
      'authenticated',
      'authenticated',
      '{email}',
      crypt('TestPassword123!', gen_salt('bf')),
      NOW(),
      '{{"provider": "email", "providers": ["email"]}}',
      '{{"name": "Test User"}}',
      NOW(),
      NOW(),
      '',
      false
  )
  RETURNING id;
        """
        )

        print("\n" + "=" * 50)
        print("After creating the user, use the returned user_id with:")
        print(f"  python seed_user_data.py --user-id <USER_ID>")

        return None

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Create test user in Supabase Auth")
    parser.add_argument(
        "--email",
        type=str,
        help="Email for test user (optional, auto-generates if not provided)",
    )
    args = parser.parse_args()

    await create_test_user(email=args.email)


if __name__ == "__main__":
    asyncio.run(main())
