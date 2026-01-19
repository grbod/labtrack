"""Authentication endpoints."""

import os
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies import DbSession, CurrentUser
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
    decode_token,
)
from app.schemas.auth import Token, RefreshRequest, UserResponse, UserProfileUpdate, VerifyOverrideResponse
from app.models import User
from app.models.enums import UserRole
from app.config import settings

router = APIRouter()


def get_signature_url(signature_path: Optional[str]) -> Optional[str]:
    """Get the full URL for a signature path."""
    if not signature_path:
        return None
    return f"/uploads/{signature_path}"


def build_user_response(user: User) -> UserResponse:
    """Build UserResponse with computed signature_url."""
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        title=user.title,
        phone=user.phone,
        signature_url=get_signature_url(user.signature_path),
        role=user.role,
        is_active=user.active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> Token:
    """Authenticate user and return JWT tokens."""
    # Find user by username
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check password using SHA256 with salt (must match UserService._hash_password)
    import hashlib
    salt = "coa_system_salt_"
    sha256_hash = hashlib.sha256(f"{salt}{form_data.password}".encode()).hexdigest()
    password_valid = sha256_hash == user.password_hash

    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Create tokens with role claim
    access_token = create_access_token(
        subject=user.id,
        additional_claims={"role": user.role.value},
    )
    refresh_token = create_refresh_token(subject=user.id)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshRequest,
    db: DbSession,
) -> Token:
    """Refresh access token using refresh token."""
    payload = decode_token(request.refresh_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new tokens
    access_token = create_access_token(
        subject=user.id,
        additional_claims={"role": user.role.value},
    )
    new_refresh_token = create_refresh_token(subject=user.id)

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current user information."""
    return build_user_response(current_user)


@router.put("/me/profile", response_model=UserResponse)
async def update_profile(
    profile_in: UserProfileUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    """Update current user's profile information."""
    # Update fields if provided
    if profile_in.full_name is not None:
        current_user.full_name = profile_in.full_name
    if profile_in.title is not None:
        current_user.title = profile_in.title
    if profile_in.phone is not None:
        current_user.phone = profile_in.phone
    if profile_in.email is not None:
        current_user.email = profile_in.email

    db.commit()
    db.refresh(current_user)
    return build_user_response(current_user)


@router.post("/me/signature", response_model=UserResponse)
async def upload_signature(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
) -> UserResponse:
    """Upload user signature image."""
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}",
        )

    # Validate file size (max 2MB)
    max_size = 2 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 2MB.",
        )

    # Delete old signature if exists
    if current_user.signature_path:
        try:
            old_path = os.path.join(settings.upload_path, current_user.signature_path)
            if os.path.exists(old_path):
                os.remove(old_path)
        except Exception:
            pass

    # Generate unique filename
    ext = os.path.splitext(file.filename or "signature.png")[1].lower()
    new_filename = f"sig_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"

    # Ensure signatures directory exists
    signatures_dir = os.path.join(settings.upload_path, "signatures")
    os.makedirs(signatures_dir, exist_ok=True)

    # Save file
    file_path = os.path.join(signatures_dir, new_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # Update database
    current_user.signature_path = f"signatures/{new_filename}"
    db.commit()
    db.refresh(current_user)

    return build_user_response(current_user)


@router.delete("/me/signature", response_model=UserResponse)
async def delete_signature(
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    """Delete user signature image."""
    if current_user.signature_path:
        try:
            old_path = os.path.join(settings.upload_path, current_user.signature_path)
            if os.path.exists(old_path):
                os.remove(old_path)
        except Exception:
            pass

        current_user.signature_path = None
        db.commit()
        db.refresh(current_user)

    return build_user_response(current_user)


@router.post("/logout")
async def logout() -> dict:
    """Logout user (client should discard tokens)."""
    return {"message": "Successfully logged out"}


@router.post("/verify-override", response_model=VerifyOverrideResponse)
async def verify_override(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> VerifyOverrideResponse:
    """
    Verify credentials for admin/QC manager override actions.

    Used when a user needs to override a restriction (e.g., submitting without PDF).
    Only admin or qc_manager roles are allowed to override.
    """
    import hashlib

    # Find user by username
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user:
        return VerifyOverrideResponse(
            valid=False,
            user_id=None,
            role=None,
            message="Invalid credentials",
        )

    # Check password using SHA256 with salt (must match UserService._hash_password)
    salt = "coa_system_salt_"
    sha256_hash = hashlib.sha256(f"{salt}{form_data.password}".encode()).hexdigest()
    password_valid = sha256_hash == user.password_hash

    if not password_valid:
        return VerifyOverrideResponse(
            valid=False,
            user_id=None,
            role=None,
            message="Invalid credentials",
        )

    if not user.active:
        return VerifyOverrideResponse(
            valid=False,
            user_id=None,
            role=None,
            message="User account is disabled",
        )

    # Check if user has override permission (admin or qc_manager)
    allowed_roles = [UserRole.ADMIN, UserRole.QC_MANAGER]
    if user.role not in allowed_roles:
        return VerifyOverrideResponse(
            valid=False,
            user_id=user.id,
            role=user.role.value,
            message="User does not have override permission. Admin or QC Manager required.",
        )

    return VerifyOverrideResponse(
        valid=True,
        user_id=user.id,
        role=user.role.value,
        message="Override authorized",
    )
