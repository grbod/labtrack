"""Tests for the production secrets startup guard in app.config.Settings."""

import pytest
from pydantic import ValidationError

from app.config import (
    Settings,
    _DEFAULT_SECRET_KEY,
    _DEFAULT_JWT_SECRET_KEY,
)


def test_production_with_default_secrets_raises():
    """Production env + shipped default secrets must fail loudly at startup."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="production",
            secret_key=_DEFAULT_SECRET_KEY,
            jwt_secret_key=_DEFAULT_JWT_SECRET_KEY,
        )
    msg = str(exc_info.value)
    assert "SECRET_KEY" in msg
    assert "JWT_SECRET_KEY" in msg


def test_production_with_default_jwt_only_raises():
    """A single lingering default secret is enough to block production startup."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="production",
            secret_key="a-real-strong-secret",
            jwt_secret_key=_DEFAULT_JWT_SECRET_KEY,
        )
    msg = str(exc_info.value)
    # Isolate the offender list so "SECRET_KEY" ⊂ "JWT_SECRET_KEY" doesn't confuse us.
    offenders = msg.split("default secret(s):", 1)[1].split(".", 1)[0]
    assert "JWT_SECRET_KEY" in offenders
    assert offenders.strip() == "JWT_SECRET_KEY"


def test_production_with_real_secrets_ok():
    """Production env with overridden secrets must construct fine."""
    settings = Settings(
        app_env="production",
        secret_key="a-real-strong-secret",
        jwt_secret_key="another-real-strong-secret",
    )
    assert settings.environment == "production"


def test_development_with_default_secrets_ok():
    """Development env is allowed to keep the shipped defaults."""
    settings = Settings(
        app_env="development",
        secret_key=_DEFAULT_SECRET_KEY,
        jwt_secret_key=_DEFAULT_JWT_SECRET_KEY,
    )
    assert settings.environment == "development"
