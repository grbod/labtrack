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
    # Isolate from the per-IP slowapi limiter and the in-process per-sender cap
    # so intake tests don't interfere with each other across the run.
    monkeypatch.setattr(endpoint_module.limiter, "enabled", False)
    endpoint_module._reset_intake_sender_window()

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
    # Fix #5: the 403 detail must be generic — no sender echo, no "allow" — so
    # it can't be used to confirm a live address or probe the allowlist.
    detail = response.json()["detail"]
    assert "spoof@evil.com" not in detail
    assert "allow" not in detail.lower()


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


def test_intake_rejects_pdf_named_non_pdf(client):
    # Fix #8: both intake paths force content_type=pdf, so only the magic-byte
    # check catches a .pdf-named payload whose bytes are not a real PDF.
    test_client, _ = client
    response = _post(
        test_client, files=("report.pdf", b"totally not a pdf", "application/pdf")
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_intake_per_sender_hourly_cap(client, monkeypatch):
    # Fix #3: a single sender exceeding the hourly PDF cap gets 429; distinct
    # file bytes each time so dedup doesn't mask the rejection.
    test_client, _ = client
    monkeypatch.setattr(settings, "email_intake_sender_hourly_cap", 2)

    def unique_pdf(n):
        return (
            "report.pdf",
            b"%PDF-1.4\n" + str(n).encode() + b"\n%%EOF",
            "application/pdf",
        )

    assert _post(test_client, files=unique_pdf(1)).status_code == 201
    assert _post(test_client, files=unique_pdf(2)).status_code == 201
    third = _post(test_client, files=unique_pdf(3))
    assert third.status_code == 429


def test_intake_rejected_upload_does_not_burn_cap(client, monkeypatch):
    # Codex #3: usage is charged only on accepted PDFs. A malformed upload (400)
    # must not consume the sender's hourly quota, so a good report still lands.
    test_client, _ = client
    monkeypatch.setattr(settings, "email_intake_sender_hourly_cap", 1)

    not_a_pdf = ("report.pdf", b"GIF89a-not-a-pdf", "application/pdf")
    assert _post(test_client, files=not_a_pdf).status_code == 400
    assert _post(test_client, files=not_a_pdf).status_code == 400
    # Two prior rejects did not count; a genuine PDF is still accepted.
    good = ("report.pdf", b"%PDF-1.4\n1\n%%EOF", "application/pdf")
    assert _post(test_client, files=good).status_code == 201


def test_intake_503_when_upload_user_missing(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr(settings, "email_intake_upload_username", "ghost")
    assert _post(test_client).status_code == 503


def test_email_intake_service_account_seeds_with_valid_username(db):
    # Regression: the seeded service-account username must satisfy the User
    # validator (letters/numbers/underscores only). A hyphenated name
    # ("email-intake") raised in the validator, so the account was never
    # created and every intake upload 503'd. It must seed as a READ_ONLY user.
    from app.models.enums import UserRole
    from app.seed import EMAIL_INTAKE_USERNAME, ensure_email_intake_user

    assert ensure_email_intake_user(db) is True
    user = db.query(User).filter(User.username == EMAIL_INTAKE_USERNAME).first()
    assert user is not None
    assert user.role == UserRole.READ_ONLY
    # Idempotent: a second call is a no-op, not a duplicate/error.
    assert ensure_email_intake_user(db) is False
