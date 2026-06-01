from fastapi import Depends

from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.auth.schemas import UserResponse


async def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)
