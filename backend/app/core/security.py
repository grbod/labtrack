"""Security utilities for authentication and authorization."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

import bcrypt as _bcrypt
from jose import jwt, JWTError

from app.config import settings

# Token settings
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = 7


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return _bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


# Legacy SHA256 salt — used only for migration from old hashes
_SHA256_SALT = "labtrack_salt_"


def verify_password_with_migration(plain_password: str, hashed_password: str, user, db) -> bool:
    """Check bcrypt first, then SHA256 fallback. Re-hash on SHA256 match."""
    # bcrypt hashes always start with $2b$ (or $2a$)
    if hashed_password.startswith(("$2b$", "$2a$")):
        return _bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    # SHA256 fallback for unmigrated passwords
    sha256_hash = hashlib.sha256(f"{_SHA256_SALT}{plain_password}".encode()).hexdigest()
    if sha256_hash == hashed_password:
        # Transparently upgrade to bcrypt
        user.password_hash = get_password_hash(plain_password)
        db.commit()
        return True
    return False


def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
    }
    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def create_refresh_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "refresh",
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None
