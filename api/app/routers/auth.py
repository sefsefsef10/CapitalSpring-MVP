"""Authentication API router using Firebase Auth."""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, EmailStr

logger = structlog.get_logger(__name__)

router = APIRouter()


class UserInfo(BaseModel):
    """User information from Firebase token."""
    uid: str
    email: Optional[str] = None
    email_verified: bool = False
    name: Optional[str] = None
    picture: Optional[str] = None
    provider: Optional[str] = None


class TokenVerifyRequest(BaseModel):
    """Request to verify a Firebase ID token."""
    id_token: str


class TokenVerifyResponse(BaseModel):
    """Response from token verification."""
    valid: bool
    user: Optional[UserInfo] = None
    error: Optional[str] = None


async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> Optional[UserInfo]:
    """
    Dependency to get the current authenticated user from Firebase token.

    In production, this verifies the Firebase ID token.
    In development, it can be bypassed for testing.
    """
    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    try:
        # In production, verify with Firebase Admin SDK
        # For now, return a mock user for development
        from app.config import settings

        if settings.environment == "development":
            # Development mode - accept any token and return mock user
            return UserInfo(
                uid="dev-user-123",
                email="dev@capitalspring.com",
                email_verified=True,
                name="Development User",
                provider="password",
            )

        # Production mode - verify with Firebase
        import firebase_admin
        from firebase_admin import auth as firebase_auth

        # Initialize Firebase Admin if not already done
        if not firebase_admin._apps:
            firebase_admin.initialize_app()

        decoded_token = firebase_auth.verify_id_token(token)

        return UserInfo(
            uid=decoded_token["uid"],
            email=decoded_token.get("email"),
            email_verified=decoded_token.get("email_verified", False),
            name=decoded_token.get("name"),
            picture=decoded_token.get("picture"),
            provider=decoded_token.get("firebase", {}).get("sign_in_provider"),
        )

    except Exception as e:
        logger.warning("Token verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def require_auth(user: Optional[UserInfo] = Depends(get_current_user)) -> UserInfo:
    """Dependency that requires authentication."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


@router.post("/verify", response_model=TokenVerifyResponse)
async def verify_token(request: TokenVerifyRequest) -> TokenVerifyResponse:
    """
    Verify a Firebase ID token and return user information.
    """
    try:
        from app.config import settings

        if settings.environment == "development":
            return TokenVerifyResponse(
                valid=True,
                user=UserInfo(
                    uid="dev-user-123",
                    email="dev@capitalspring.com",
                    email_verified=True,
                    name="Development User",
                    provider="password",
                ),
            )

        import firebase_admin
        from firebase_admin import auth as firebase_auth

        if not firebase_admin._apps:
            firebase_admin.initialize_app()

        decoded_token = firebase_auth.verify_id_token(request.id_token)

        return TokenVerifyResponse(
            valid=True,
            user=UserInfo(
                uid=decoded_token["uid"],
                email=decoded_token.get("email"),
                email_verified=decoded_token.get("email_verified", False),
                name=decoded_token.get("name"),
                picture=decoded_token.get("picture"),
                provider=decoded_token.get("firebase", {}).get("sign_in_provider"),
            ),
        )

    except Exception as e:
        logger.warning("Token verification failed", error=str(e))
        return TokenVerifyResponse(
            valid=False,
            error=str(e),
        )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    user: UserInfo = Depends(require_auth),
) -> UserInfo:
    """
    Get information about the currently authenticated user.
    """
    return user


@router.post("/logout")
async def logout(
    user: UserInfo = Depends(require_auth),
) -> dict:
    """
    Log out the current user.

    Note: Firebase tokens are stateless, so this just acknowledges the logout.
    The client should discard the token.
    """
    logger.info("User logged out", uid=user.uid, email=user.email)
    return {
        "status": "success",
        "message": "Logged out successfully",
    }
