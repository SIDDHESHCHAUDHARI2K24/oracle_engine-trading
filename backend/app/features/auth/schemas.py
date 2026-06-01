"""Pydantic schemas for auth requests and responses."""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    """Payload required to register a new user."""

    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    """Payload required to log a user in."""

    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Public representation of a user."""

    id: int
    email: EmailStr
    created_at: datetime


class SessionOut(BaseModel):
    """Representation of a session created for a user."""

    session_token: str
    expires_at: datetime

