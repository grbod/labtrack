"""Tests for deployment fixes: writable paths and global exception handler."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base
from app.dependencies import get_db, get_current_user
from app.models import User
from app.models.enums import UserRole
from app.config import settings


# ---------------------------------------------------------------------------
# Test database setup (same pattern as test_api_endpoints.py)
# ---------------------------------------------------------------------------
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_user(test_db):
    user = User(
        username="admin",
        email="admin@test.com",
        role=UserRole.ADMIN,
        active=True,
    )
    user.set_password("adminpass123")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def client(test_db, admin_user):
    app.dependency_overrides[get_db] = override_get_db

    async def override_get_current_user():
        return admin_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


# ===========================================================================
# Fix 1: Writable paths — exports/, COAs/, uploads/, data/ all configured
# ===========================================================================

class TestWritablePaths:
    """Verify all writable directories are configured in settings and systemd."""

    def test_export_path_configured(self):
        """export_path must be set in settings (used by audit CSV/PDF exports)."""
        assert hasattr(settings, "export_path")
        assert settings.export_path is not None

    def test_coa_output_folder_configured(self):
        """coa_output_folder must be set in settings (used by COA generation)."""
        assert hasattr(settings, "coa_output_folder")
        assert settings.coa_output_folder is not None

    def test_upload_path_configured(self):
        """upload_path must be set in settings (used by file uploads)."""
        assert hasattr(settings, "upload_path")
        assert settings.upload_path is not None

    def test_systemd_service_has_all_writable_paths(self):
        """The systemd service file must list ReadWritePaths for every directory the app writes to."""
        service_file = Path(__file__).parent.parent.parent / "deploy" / "labtrack-api.service"
        assert service_file.exists(), f"Service file not found at {service_file}"

        content = service_file.read_text()

        required_paths = [
            "/opt/labtrack/backend/data",
            "/opt/labtrack/backend/uploads",
            "/opt/labtrack/backend/COAs",
            "/opt/labtrack/backend/exports",
            "/var/log/labtrack",
        ]

        for path in required_paths:
            assert f"ReadWritePaths={path}" in content, (
                f"Missing ReadWritePaths={path} in systemd service file. "
                f"The app writes to this directory and ProtectSystem=strict will block it."
            )

    def test_systemd_service_has_protect_system_strict(self):
        """ProtectSystem=strict must be enabled for security hardening."""
        service_file = Path(__file__).parent.parent.parent / "deploy" / "labtrack-api.service"
        content = service_file.read_text()
        assert "ProtectSystem=strict" in content

    def test_setup_script_creates_all_directories(self):
        """setup.sh must create all writable directories."""
        setup_file = Path(__file__).parent.parent.parent / "deploy" / "setup.sh"
        assert setup_file.exists(), f"Setup script not found at {setup_file}"

        content = setup_file.read_text()

        for dirname in ["data", "uploads", "COAs", "exports"]:
            assert dirname in content, (
                f"setup.sh does not create '{dirname}' directory. "
                f"First deployment will fail with PermissionError."
            )


# ===========================================================================
# Fix 2: Global exception handler — no stack traces leaked in production
# ===========================================================================

class TestGlobalExceptionHandler:
    """Verify unhandled exceptions return clean JSON, not stack traces."""

    def test_unhandled_exception_returns_500_json(self, client):
        """An unhandled exception should return {"detail": "Internal server error"}, not a stack trace."""
        # Add a temporary route that raises an unhandled exception
        @app.get("/api/v1/test-exception")
        async def raise_exception():
            raise RuntimeError("This should not leak to the client")

        with patch.object(settings, "debug", False):
            response = client.get("/api/v1/test-exception")

        assert response.status_code == 500
        body = response.json()
        assert body == {"detail": "Internal server error"}
        # Ensure no stack trace in response
        assert "RuntimeError" not in response.text
        assert "Traceback" not in response.text

    def test_exception_handler_passes_through_in_debug(self, test_db, admin_user):
        """In debug mode, exceptions should propagate for developer visibility."""
        app.dependency_overrides[get_db] = override_get_db

        async def override_get_current_user():
            return admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        @app.get("/api/v1/test-exception-debug")
        async def raise_debug_exception():
            raise RuntimeError("Debug exception")

        with patch.object(settings, "debug", True):
            with TestClient(app, raise_server_exceptions=True) as c:
                with pytest.raises(RuntimeError, match="Debug exception"):
                    c.get("/api/v1/test-exception-debug")

        app.dependency_overrides.clear()

    def test_404_returns_clean_json(self, client):
        """A 404 should return clean JSON, not leak internal paths."""
        response = client.get("/api/v1/this-does-not-exist")
        assert response.status_code in (404, 405)
        body = response.json()
        assert "detail" in body
        assert "Traceback" not in response.text

    def test_health_endpoint_still_works(self, client):
        """Health check should not be affected by the exception handler."""
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"

    def test_exception_handler_registered_on_app(self):
        """The global exception handler must be registered on the FastAPI app."""
        # FastAPI stores exception handlers in exception_handlers dict
        assert Exception in app.exception_handlers, (
            "Global Exception handler not registered. "
            "Stack traces will leak to clients in production."
        )
