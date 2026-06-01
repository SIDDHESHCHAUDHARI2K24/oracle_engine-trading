"""Router for authentication endpoints — login, logout, refresh, me."""

from fastapi import APIRouter

from app.features.auth.endpoints.login import login
from app.features.auth.endpoints.logout import logout
from app.features.auth.endpoints.me import me
from app.features.auth.endpoints.refresh import refresh

auth_router = APIRouter(prefix="/auth", tags=["auth"])

auth_router.post("/login")(login)
auth_router.post("/logout")(logout)
auth_router.post("/refresh")(refresh)
auth_router.get("/me")(me)
