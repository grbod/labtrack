"""Tests for the unauthenticated intake webhook (Cloudflare Email Worker)."""

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import result_imports as endpoint_module
from app.config import settings
from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models import User
from app.models.enums import UserRole
from tests.test_api_endpoints import TestingSessionLocal, engine, override_get_db

TOKEN = "test-intake-token"
PDF = ("report.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(settings, "intake_webhook_token", TOKEN)
    monkeypatch.setattr(
        settings, "email_intake_allowed_senders", "@bodynutrition.com,@daanelabs.com"
    )
    monkeypatch.setattr(settings, "email_intake_upload_username", "admin")
    monkeypatch.setattr(endpoint_module.service, "_page_count", lambda content: 1)

    async def fake_enqueue(import_id):
        fake_enqueue.enqueued.append(import_id)

    fake_enqueue.enqueued = []
    monkeypatch.setattr(endpoint_module, "enqueue_result_import", fake_enqueue)

    user = User(username="admin", email="admin@x.com", role=UserRole.ADMIN, active=True)
    user.set_password("pw12345678")
    db.add(user)
    db.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), fake_enqueue
    finally:
        app.dependency_overrides.clear()


def _post(client, token=TOKEN, sender="greg@bodynutrition.com", files=None):
    return client.post(
        "/api/v1/result-imports/intake",
        headers={"X-Intake-Token": token},
        data={"sender": sender},
        files=[("files", files or PDF)],
    )


def test_intake_disabled_when_token_unset(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr(settings, "intake_webhook_token", None)
    assert _post(test_client).status_code == 404


def test_intake_rejects_bad_token(client):
    test_client, _ = client
    assert _post(test_client, token="wrong").status_code == 401


def test_intake_rejects_disallowed_sender(client):
    test_client, _ = client
    response = _post(test_client, sender="spoof@evil.com")
    assert response.status_code == 403
    assert "spoof@evil.com" in response.json()["detail"]


def test_intake_ingests_pdf_and_enqueues(client):
    test_client, fake_enqueue = client
    response = _post(test_client)
    assert response.status_code == 201
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["original_filename"] == "report.pdf"
    assert body["duplicates"] == []
    assert fake_enqueue.enqueued == [body["items"][0]["id"]]


def test_intake_reports_duplicates_without_reenqueue(client):
    test_client, fake_enqueue = client
    first = _post(test_client)
    assert first.status_code == 201
    second = _post(test_client)
    assert second.status_code == 201
    body = second.json()
    assert body["items"] == []
    assert len(body["duplicates"]) == 1
    assert fake_enqueue.enqueued == [first.json()["items"][0]["id"]]


def test_intake_rejects_non_pdf(client):
    test_client, _ = client
    response = _post(test_client, files=("photo.png", b"not a pdf", "image/png"))
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_intake_503_when_upload_user_missing(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr(settings, "email_intake_upload_username", "ghost")
    assert _post(test_client).status_code == 503
