"""
Authentication routes for user registration, login, and session management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from middleware.auth import get_current_user
from models.schemas import (
    AuthResponse,
    RefreshTokenRequest,
    SessionResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    VerifyTokenResponse,
)
from services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
security = HTTPBearer()


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(user_data: UserRegister):
    """
    Register a new user with email and password.

    **Requires:**
    - Email address
    - Password (minimum 8 characters)
    - Optional: Display name

    **Returns:**
    - User information
    - Session tokens (access_token, refresh_token)
    """
    try:
        result = await AuthService.register_user(
            email=user_data.email,
            password=user_data.password,
            name=user_data.name,
        )

        # Format response
        user_response = UserResponse(**result["user"])
        session_response = (
            SessionResponse(**result["session"]) if result.get("session") else None
        )

        return AuthResponse(
            user=user_response,
            session=session_response,
            message=(
                "User registered successfully. Please check your email to confirm your account."
                if not session_response
                else "User registered and logged in successfully."
            ),
        )

    except Exception as e:
        error_msg = str(e)

        # Handle common errors
        if (
            "already registered" in error_msg.lower()
            or "already exists" in error_msg.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )
        elif "password" in error_msg.lower() and "short" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Registration failed: {error_msg}",
            )


@router.post("/login", response_model=AuthResponse)
async def login(credentials: UserLogin):
    """
    Log in a user with email and password.

    **Requires:**
    - Email address
    - Password

    **Returns:**
    - User information
    - Session tokens (access_token, refresh_token)
    """
    try:
        result = await AuthService.login_user(
            email=credentials.email,
            password=credentials.password,
        )

        # Format response
        user_response = UserResponse(**result["user"])
        session_response = SessionResponse(**result["session"])

        return AuthResponse(
            user=user_response, session=session_response, message="Login successful"
        )

    except Exception as e:
        error_msg = str(e)

        # Handle authentication errors
        if "invalid" in error_msg.lower() or "password" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
            )


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Log out the current user.

    **Requires:**
    - Valid access token in Authorization header

    **Returns:**
    - Success message
    """
    try:
        await AuthService.logout_user(credentials.credentials)
        return {"message": "Logout successful"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed"
        )


@router.post("/refresh", response_model=SessionResponse)
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh an expired access token using a refresh token.

    **Requires:**
    - Valid refresh token

    **Returns:**
    - New session tokens (access_token, refresh_token)
    """
    try:
        result = await AuthService.refresh_session(request.refresh_token)
        return SessionResponse(**result["session"])

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/verify", response_model=VerifyTokenResponse)
async def verify_token(current_user: dict = Depends(get_current_user)):
    """
    Verify the current access token and get user information.

    **Requires:**
    - Valid access token in Authorization header

    **Returns:**
    - User information
    - Email confirmation status
    """
    try:
        # The token is already verified by the get_current_user dependency
        # Just return the user information
        user_response = UserResponse(
            id=current_user["user_id"],
            email=current_user["email"],
            name=current_user.get("metadata", {}).get("name"),
            created_at=current_user.get("created_at", ""),
        )

        return VerifyTokenResponse(
            user=user_response,
            email_confirmed=True,  # If we got here, the token is valid
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get the current authenticated user's information.

    **Requires:**
    - Valid access token in Authorization header

    **Returns:**
    - User information
    """
    return UserResponse(
        id=current_user["user_id"],
        email=current_user["email"],
        name=current_user.get("metadata", {}).get("name"),
        created_at=current_user.get("created_at", ""),
    )
