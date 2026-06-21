"""Endpoint auth tests for upload/importer routes."""

import pytest
from fastapi.testclient import TestClient

from app.database import Base
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import User
from app.models.enums import UserRole
from tests.test_api_endpoints import (
    TestingSessionLocal,
    engine,
    override_get_db,
)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _make_user(db, role):
    user = User(
        username=f"u_{role.value}",
        email=f"{role.value}@x.com",
        role=role,
        active=True,
    )
    user.set_password("pw12345678")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _client_as(user):
    app.dependency_overrides[get_db] = override_get_db

    async def _override_user():
        return user

    app.dependency_overrides[get_current_user] = _override_user
    return TestClient(app)


def test_delete_upload_forbidden_for_read_only(db):
    read_only = _make_user(db, UserRole.READ_ONLY)
    client = _client_as(read_only)
    try:
        response = client.delete("/api/v1/uploads/pdfs/anything.pdf")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_delete_upload_allowed_for_lab_tech_returns_404_when_missing(db):
    lab_tech = _make_user(db, UserRole.LAB_TECH)
    client = _client_as(lab_tech)
    try:
        response = client.delete("/api/v1/uploads/pdfs/does-not-exist.pdf")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_delete_upload_allowed_for_lab_tech_deletes_and_logs(
    db,
    monkeypatch,
):
    class DummyStorage:
        def __init__(self):
            self.deleted = []

        def exists(self, key):
            return key == "pdfs/delete-me.pdf"

        def delete(self, key):
            self.deleted.append(key)

    storage = DummyStorage()
    warnings = []
    monkeypatch.setattr(
        "app.api.v1.endpoints.uploads.get_storage_service",
        lambda: storage,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.uploads.logger.warning",
        lambda message, *args: warnings.append((message, args)),
    )
    lab_tech = _make_user(db, UserRole.LAB_TECH)
    client = _client_as(lab_tech)
    try:
        response = client.delete("/api/v1/uploads/pdfs/delete-me.pdf")
        assert response.status_code == 200
        assert storage.deleted == ["pdfs/delete-me.pdf"]
        assert warnings == [
            (
                "Upload deleted: key=%s by user_id=%s",
                ("pdfs/delete-me.pdf", lab_tech.id),
            )
        ]
    finally:
        app.dependency_overrides.clear()
