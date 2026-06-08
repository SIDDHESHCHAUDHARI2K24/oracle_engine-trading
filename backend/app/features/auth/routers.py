"""Router for authentication endpoints — login, logout, refresh, me, account management."""

from fastapi import APIRouter

from app.features.auth.endpoints.change_password import change_password
from app.features.auth.endpoints.login import login
from app.features.auth.endpoints.logout import logout
from app.features.auth.endpoints.logout_everywhere import logout_everywhere
from app.features.auth.endpoints.me import me
from app.features.auth.endpoints.refresh import refresh
from app.features.auth.endpoints.reset_password import reset_password
from app.features.auth.endpoints.sessions import list_sessions

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

auth_router.post("/login")(login)
auth_router.post("/logout")(logout)
auth_router.post("/refresh")(refresh)
auth_router.get("/me")(me)
auth_router.post("/change-password")(change_password)
auth_router.get("/sessions")(list_sessions)
auth_router.post("/logout-everywhere")(logout_everywhere)
auth_router.post("/reset-password")(reset_password)
