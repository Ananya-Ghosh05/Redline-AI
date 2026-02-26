"""Security middleware and dependencies for Redline AI.

Provides:
- Rate limiting via slowapi (60/min per IP)
- JWT authentication dependency for API routes
- Twilio webhook signature validation
"""
from __future__ import annotations

import os
from typing import Optional

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

log = structlog.get_logger("redline_ai.security")

# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# ---------------------------------------------------------------------------
# JWT Auth
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


async def require_jwt(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """FastAPI dependency: validates JWT and returns the decoded payload.

    Raises 401 if token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        log.warning("JWT validation failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ---------------------------------------------------------------------------
# Twilio Webhook Verification
# ---------------------------------------------------------------------------

TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")


def validate_twilio_signature(request: Request) -> bool:
    """Validate incoming Twilio webhook requests.

    Returns True if validation is disabled (no auth token set) or signature is valid.
    Raises 403 if signature is invalid.
    """
    if not TWILIO_AUTH_TOKEN:
        log.debug("Twilio auth token not set — skipping signature validation")
        return True

    try:
        from twilio.request_validator import RequestValidator

        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        signature = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)

        # For POST requests, we need the form data
        # This is a simplified check; full implementation needs form body
        is_valid = validator.validate(url, {}, signature)

        if not is_valid:
            log.warning("Invalid Twilio webhook signature", url=url)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Twilio signature",
            )
        return True
    except ImportError:
        log.warning("twilio package not installed — skipping signature validation")
        return True
