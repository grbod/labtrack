"""Tests for the email intake service (mailbox -> results importer)."""

import base64

import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.services import email_intake_service as intake_module
from app.services.email_intake_service import (
    PROCESSED_FOLDER,
    REJECTED_FOLDER,
    EmailIntakeService,
)

PDF_BYTES = b"%PDF-1.4 fake"
PDF_B64 = base64.b64encode(PDF_BYTES).decode()


# -- Config guard -------------------------------------------------------


def test_email_intake_enabled_without_credentials_raises():
    with pytest.raises(ValidationError) as exc_info:
        Settings(email_intake_enabled=True)
    message = str(exc_info.value)
    assert "EMAIL_INTAKE_TENANT_ID" in message
    assert "EMAIL_INTAKE_MAILBOX" in message


def test_email_intake_enabled_with_credentials_ok():
    config = Settings(
        email_intake_enabled=True,
        email_intake_tenant_id="tenant",
        email_intake_client_id="client",
        email_intake_client_secret="secret",
        email_intake_mailbox="results@example.com",
    )
    assert config.email_intake_enabled is True


def test_email_intake_disabled_requires_nothing():
    assert Settings().email_intake_enabled is False


# -- Sender allowlist ---------------------------------------------------


def test_sender_allowlist_empty_allows_all(monkeypatch):
    monkeypatch.setattr(settings, "email_intake_allowed_senders", "")
    assert EmailIntakeService._sender_allowed("anyone@anywhere.com")


def test_sender_allowlist_matches_address_and_domain(monkeypatch):
    monkeypatch.setattr(
        settings,
        "email_intake_allowed_senders",
        "reports@daanelabs.com, @bodynutrition.com",
    )
    assert EmailIntakeService._sender_allowed("reports@daanelabs.com")
    assert EmailIntakeService._sender_allowed("Reports@DaaneLabs.com")
    assert EmailIntakeService._sender_allowed("greg@bodynutrition.com")
    assert not EmailIntakeService._sender_allowed("spoof@evil.com")
    assert not EmailIntakeService._sender_allowed("other@daanelabs.com")


# -- poll_once routing --------------------------------------------------


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class GraphStub:
    """Records Graph calls and serves canned message/attachment payloads."""

    def __init__(self, messages, attachments_by_message):
        self.messages = messages
        self.attachments = attachments_by_message
        self.moves = []  # (message_id, folder_name)
        self.patched_read = []
        self._folder_requests = []

    async def __call__(self, client, method, path, **kwargs):
        if path.startswith("/mailFolders/inbox/messages"):
            return FakeResponse({"value": self.messages})
        if "/attachments" in path:
            message_id = path.split("/")[2]
            return FakeResponse({"value": self.attachments.get(message_id, [])})
        if path.startswith("/mailFolders?"):
            # Folder lookup: pretend it exists, id == its display name.
            name = path.split("'")[1]
            self._folder_requests.append(name)
            return FakeResponse({"value": [{"id": name}]})
        if method == "PATCH" and path.startswith("/messages/"):
            self.patched_read.append(path.split("/")[2])
            return FakeResponse({})
        if method == "POST" and path.endswith("/move"):
            message_id = path.split("/")[2]
            self.moves.append((message_id, kwargs["json"]["destinationId"]))
            return FakeResponse({})
        raise AssertionError(f"Unexpected Graph call: {method} {path}")


def message(message_id, sender="reports@daanelabs.com", subject="Results"):
    return {
        "id": message_id,
        "subject": subject,
        "from": {"emailAddress": {"address": sender}},
        "receivedDateTime": "2026-07-10T12:00:00Z",
    }


def pdf_attachment(name="report.pdf", content_type="application/pdf"):
    return {
        "id": "att1",
        "name": name,
        "contentType": content_type,
        "contentBytes": PDF_B64,
    }


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(settings, "email_intake_allowed_senders", "")
    monkeypatch.setattr(settings, "email_intake_mailbox", "results@example.com")
    svc = EmailIntakeService()
    monkeypatch.setattr(svc, "_upload_user_id", lambda: 1)
    return svc


def wire(monkeypatch, svc, stub):
    monkeypatch.setattr(svc, "_graph", stub)
    enqueued = []

    async def fake_enqueue(import_id):
        enqueued.append(import_id)

    monkeypatch.setattr(intake_module, "enqueue_result_import", fake_enqueue)
    return enqueued


@pytest.mark.asyncio
async def test_pdf_message_is_ingested_and_filed(monkeypatch, service):
    stub = GraphStub([message("m1")], {"m1": [pdf_attachment()]})
    enqueued = wire(monkeypatch, service, stub)
    ingested = []

    def fake_ingest(filename, content, user_id):
        ingested.append((filename, content, user_id))
        return [42]

    monkeypatch.setattr(service, "_ingest_pdf", fake_ingest)

    stats = await service.poll_once()

    assert ingested == [("report.pdf", PDF_BYTES, 1)]
    assert enqueued == [42]
    assert stub.moves == [("m1", PROCESSED_FOLDER)]
    assert stats == {"messages": 1, "ingested": 1, "rejected": 0}


@pytest.mark.asyncio
async def test_message_without_pdf_is_rejected(monkeypatch, service):
    attachment = {
        "id": "a",
        "name": "photo.png",
        "contentType": "image/png",
        "contentBytes": PDF_B64,
    }
    stub = GraphStub([message("m1")], {"m1": [attachment]})
    wire(monkeypatch, service, stub)

    stats = await service.poll_once()

    assert stub.moves == [("m1", REJECTED_FOLDER)]
    assert stats["rejected"] == 1


@pytest.mark.asyncio
async def test_disallowed_sender_is_rejected(monkeypatch, service):
    monkeypatch.setattr(settings, "email_intake_allowed_senders", "@bodynutrition.com")
    stub = GraphStub([message("m1", sender="spoof@evil.com")], {})
    wire(monkeypatch, service, stub)

    stats = await service.poll_once()

    assert stub.moves == [("m1", REJECTED_FOLDER)]
    assert stats["rejected"] == 1


@pytest.mark.asyncio
async def test_all_pdfs_invalid_rejects_message(monkeypatch, service):
    stub = GraphStub([message("m1")], {"m1": [pdf_attachment()]})
    wire(monkeypatch, service, stub)

    def fake_ingest(filename, content, user_id):
        raise ValueError("too many pages")

    monkeypatch.setattr(service, "_ingest_pdf", fake_ingest)

    stats = await service.poll_once()

    assert stub.moves == [("m1", REJECTED_FOLDER)]
    assert stats == {"messages": 1, "ingested": 0, "rejected": 1}


@pytest.mark.asyncio
async def test_duplicate_only_message_counts_as_processed(monkeypatch, service):
    stub = GraphStub([message("m1")], {"m1": [pdf_attachment()]})
    enqueued = wire(monkeypatch, service, stub)
    # Duplicate: create_uploads returns nothing new, no error raised.
    monkeypatch.setattr(service, "_ingest_pdf", lambda *args: [])

    stats = await service.poll_once()

    assert enqueued == []
    assert stub.moves == [("m1", PROCESSED_FOLDER)]
    assert stats == {"messages": 1, "ingested": 0, "rejected": 0}


@pytest.mark.asyncio
async def test_missing_upload_user_skips_poll(monkeypatch, service):
    monkeypatch.setattr(service, "_upload_user_id", lambda: None)
    stats = await service.poll_once()
    assert stats == {"messages": 0, "ingested": 0, "rejected": 0}
