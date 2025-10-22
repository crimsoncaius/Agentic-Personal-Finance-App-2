"""
Authentication service for user registration, login, and session management.
"""

from typing import Optional
from uuid import UUID

from supabase import Client

from database.connection import db_connection


class AuthService:
    """Service for authentication operations using Supabase Auth."""

    @staticmethod
    def get_client() -> Client:
        """Get the Supabase client instance."""
        return db_connection.client

    @staticmethod
    async def register_user(
        email: str, password: str, name: Optional[str] = None
    ) -> dict:
        """
        Register a new user with email and password.

        Args:
            email: User's email address
            password: User's password (min 8 characters)
            name: Optional user's display name

        Returns:
            dict: User data and session information

        Raises:
            Exception: If registration fails
        """
        client = AuthService.get_client()

        # Prepare user metadata
        user_metadata = {}
        if name:
            user_metadata["name"] = name

        # Sign up the user
        response = client.auth.sign_up(
            {"email": email, "password": password, "options": {"data": user_metadata}}
        )

        if not response.user:
            raise Exception("Failed to create user account")

        return {
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "name": user_metadata.get("name"),
                "created_at": (
                    str(response.user.created_at) if response.user.created_at else ""
                ),
            },
            "session": (
                {
                    "access_token": (
                        response.session.access_token if response.session else None
                    ),
                    "refresh_token": (
                        response.session.refresh_token if response.session else None
                    ),
                    "expires_at": (
                        response.session.expires_at if response.session else None
                    ),
                }
                if response.session
                else None
            ),
        }

    @staticmethod
    async def login_user(email: str, password: str) -> dict:
        """
        Log in a user with email and password.

        Args:
            email: User's email address
            password: User's password

        Returns:
            dict: User data and session information

        Raises:
            Exception: If login fails
        """
        client = AuthService.get_client()

        # Sign in the user
        response = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )

        if not response.user or not response.session:
            raise Exception("Invalid email or password")

        return {
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name"),
                "created_at": (
                    str(response.user.created_at) if response.user.created_at else ""
                ),
            },
            "session": {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at,
            },
        }

    @staticmethod
    async def logout_user(access_token: str) -> bool:
        """
        Log out a user by invalidating their session.

        Args:
            access_token: User's current access token

        Returns:
            bool: True if logout successful

        Raises:
            Exception: If logout fails
        """
        client = AuthService.get_client()

        # Set the session for the current operation
        client.auth.sign_out()

        return True

    @staticmethod
    async def refresh_session(refresh_token: str) -> dict:
        """
        Refresh an expired session using a refresh token.

        Args:
            refresh_token: User's refresh token

        Returns:
            dict: New session information

        Raises:
            Exception: If refresh fails
        """
        client = AuthService.get_client()

        # Refresh the session
        response = client.auth.refresh_session(refresh_token)

        if not response.session:
            raise Exception("Failed to refresh session")

        return {
            "session": {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at,
            }
        }

    @staticmethod
    async def get_user_by_id(user_id: UUID) -> Optional[dict]:
        """
        Get user information by user ID.

        Args:
            user_id: User's UUID

        Returns:
            Optional[dict]: User information or None if not found
        """
        client = AuthService.get_client()

        try:
            # Query the users table via Supabase client
            # Note: This requires proper RLS policies or service role key
            response = (
                client.from_("auth.users").select("*").eq("id", str(user_id)).execute()
            )

            if response.data and len(response.data) > 0:
                user = response.data[0]
                return {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user.get("raw_user_meta_data", {}).get("name"),
                    "created_at": user["created_at"],
                }

            return None
        except Exception:
            return None

    @staticmethod
    async def verify_user_email(access_token: str) -> dict:
        """
        Get user information from access token.

        Args:
            access_token: User's access token

        Returns:
            dict: User information

        Raises:
            Exception: If verification fails
        """
        client = AuthService.get_client()

        # Get user from token
        response = client.auth.get_user(access_token)

        if not response.user:
            raise Exception("Invalid or expired token")

        return {
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name"),
                "email_confirmed": response.user.email_confirmed_at is not None,
                "created_at": (
                    str(response.user.created_at) if response.user.created_at else ""
                ),
            }
        }
