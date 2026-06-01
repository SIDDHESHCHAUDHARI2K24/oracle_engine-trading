"""User logout endpoint."""

from fastapi import Request, Response

from app.features.core.dependencies import DbDep

from .. import models


async def logout(request: Request, response: Response, conn=DbDep) -> dict[str, str]:
    """Invalidate the current session and clear the cookie."""
    session_id = request.cookies.get("session_id")
    if session_id:
        await models.ensure_auth_schema(conn)
        await models.delete_session(conn, session_token=session_id)

    response.delete_cookie("session_id")
    return {"detail": "Logged out"}
