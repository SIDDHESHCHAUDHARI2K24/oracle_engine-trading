"""Router for authentication endpoints."""

from fastapi import APIRouter

from .endpoints.login import login
from .endpoints.logout import logout
from .endpoints.me import me
from .endpoints.register import register
from .endpoints.reset import reset_password


auth_router = APIRouter(prefix="/auth", tags=["auth"])

auth_router.post("/register")(register)
auth_router.post("/login")(login)
auth_router.post("/logout")(logout)
auth_router.post("/reset")(reset_password)
auth_router.get("/me")(me)

