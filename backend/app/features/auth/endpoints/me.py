"""Endpoint for retrieving the current authenticated user."""

from fastapi import Depends

from ..utils import get_current_user
from ..schemas import UserOut


async def me(user=Depends(get_current_user)) -> UserOut:
    """Return the currently authenticated user."""
    return UserOut(
        id=user["id"],
        email=user["email"],
        created_at=user["created_at"],
    )

