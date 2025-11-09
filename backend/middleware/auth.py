"""
Authentication middleware for JWT validation and user context extraction.
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from database.connection import db_connection

# Security scheme for bearer token
security = HTTPBearer()


class AuthMiddleware:
    """Middleware for handling JWT authentication with Supabase."""

    @staticmethod
    def get_supabase_client() -> Client:
        """Get the Supabase client instance."""
        return db_connection.client

    @staticmethod
    async def verify_token(token: str) -> dict:
        """
        Verify JWT token and extract user information.

        Args:
            token: JWT token from Authorization header

        Returns:
            dict: User information from the token

        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            client = AuthMiddleware.get_supabase_client()

            # Verify the token with Supabase
            # The client will validate the JWT signature and expiry
            user_response = client.auth.get_user(token)

            if not user_response or not user_response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user_info = {
                "user_id": user_response.user.id,
                "email": user_response.user.email,
                "role": user_response.user.role,
                "metadata": user_response.user.user_metadata,
            }

            # Store the JWT token in the user info for RLS
            user_info["jwt_token"] = token

            return user_info

        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @staticmethod
    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = security,
    ) -> dict:
        """
        Dependency to get the current authenticated user.

        Args:
            credentials: HTTP authorization credentials from the request

        Returns:
            dict: Current user information

        Raises:
            HTTPException: If authentication fails
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await AuthMiddleware.verify_token(credentials.credentials)

    @staticmethod
    async def get_current_user_id(
        credentials: HTTPAuthorizationCredentials = security,
    ) -> UUID:
        """
        Dependency to get the current user's UUID.

        Args:
            credentials: HTTP authorization credentials from the request

        Returns:
            UUID: Current user's ID

        Raises:
            HTTPException: If authentication fails
        """
        user = await AuthMiddleware.get_current_user(credentials)
        return UUID(user["user_id"])

    @staticmethod
    async def optional_auth(request: Request) -> Optional[dict]:
        """
        Optional authentication - returns user if authenticated, None otherwise.
        Useful for endpoints that can work with or without authentication.

        Args:
            request: FastAPI request object

        Returns:
            Optional[dict]: User information if authenticated, None otherwise
        """
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.replace("Bearer ", "")

        try:
            return await AuthMiddleware.verify_token(token)
        except HTTPException:
            return None


# Convenience functions for route dependencies
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Get current authenticated user (dependency)."""
    return await AuthMiddleware.get_current_user(credentials)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UUID:
    """Get current user ID (dependency)."""
    return await AuthMiddleware.get_current_user_id(credentials)
