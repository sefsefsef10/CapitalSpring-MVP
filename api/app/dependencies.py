"""Shared dependencies for API routes."""

from typing import Optional

from fastapi import Depends, HTTPException, status

from app.routers.auth import get_current_user, require_auth, UserInfo

# Re-export auth dependencies for convenient imports
__all__ = [
    "get_current_user",
    "require_auth",
    "UserInfo",
    "get_optional_user",
    "require_verified_user",
]


async def get_optional_user(
    user: Optional[UserInfo] = Depends(get_current_user),
) -> Optional[UserInfo]:
    """
    Dependency for routes that can work with or without authentication.
    Returns None if no user is authenticated.
    """
    return user


def require_verified_user(
    user: UserInfo = Depends(require_auth),
) -> UserInfo:
    """
    Dependency that requires an authenticated user with verified email.
    """
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    return user
