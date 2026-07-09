"""Custom ASGI middleware."""

from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.security import decode_token
from app.database import SessionLocal
from app.models import User, UserRole

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_AUTH_PREFIX = "/api/v1/auth/"


class ReadOnlyEnforcementMiddleware(BaseHTTPMiddleware):
    """Reject mutating requests from read-only users (server-side enforcement).

    A user whose role is ``read_only`` may only issue safe (GET/HEAD/OPTIONS)
    requests; any other method returns 403, EXCEPT under ``/api/v1/auth/`` (so
    they can still log in / refresh / change their own password).

    This is a coarse backstop in front of the per-route role dependencies, not a
    replacement for them. It decodes the JWT exactly as the auth dependency does
    and FAILS OPEN on a missing/invalid/expired token — surfacing those to the
    auth layer (401), which owns authentication — so it never turns an
    authentication problem into a 403.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        if request.url.path.startswith(_AUTH_PREFIX):
            return await call_next(request)

        role = self._role_from_request(request)
        if role == UserRole.READ_ONLY:
            return JSONResponse(
                status_code=403,
                content={"detail": "Read-only users cannot perform this action."},
            )

        return await call_next(request)

    @staticmethod
    def _role_from_request(request: Request):
        """Return the requester's role, or None when it cannot be established.

        Any ambiguity (no/!bearer/invalid/expired token, unknown user) returns
        None → the request passes through to the auth layer (fail-open).
        """
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None

        payload = decode_token(token.strip())
        if not payload or payload.get("type") != "access":
            return None

        user_id = payload.get("sub")
        if user_id is None:
            return None

        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return None

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == uid).first()
            return user.role if user is not None else None
        finally:
            db.close()
