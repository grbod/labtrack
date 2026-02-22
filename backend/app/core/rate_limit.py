"""Rate limiting configuration."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_real_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For from nginx."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the chain is the real client
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_real_client_ip)
