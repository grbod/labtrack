"""Tests for immutable COA snapshot infrastructure."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.config import settings
from app.models.coa_release import COARelease
from app.models.coa_snapshot import COASerialCounter, COASnapshot
from app.models.enums import COAReleaseStatus
from app.services.coa_generation_service import COAGenerationService
from app.services.coa_snapshot_service import (
    create_snapshot,
    get_snapshot_context,
    issue_serial,
    void_snapshot,
)
from app.services.storage_service import get_storage_service, reset_storage_service
from scripts.backfill_coa_snapshots import run_backfill


@pytest.fixture(autouse=True)
def local_snapshot_storage(tmp_path, monkeypatch):
    old_upload_path = settings.upload_path
    old_storage_backend = settings.storage_backend
    monkeypatch.setattr(settings, "upload_path", tmp_path)
    monkeypatch.setattr(settings, "storage_backend", "local")
    reset_storage_service()
    yield
    reset_storage_service()
    monkeypatch.setattr(settings, "upload_path", old_upload_path)
    monkeypatch.setattr(settings, "storage_backend", old_storage_backend)


@pytest.fixture(autouse=True)
def fast_pdf_renderer(monkeypatch):
    def _write_pdf(self, context, output_path):
        Path(output_path).write_bytes(
            f"PDF for {context.document.document_id}".encode("utf-8")
        )

    monkeypatch.setattr(COAGenerationService, "_generate_pdf_reportlab", _write_pdf)


@pytest.fixture
def released_coa(test_db, sample_lot, sample_product, sample_user, sample_test_results):
    sample_user.full_name = "Jane QC"
    sample_user.title = "QC Manager"
    sample_user.signature_path = "signatures/jane.png"
    get_storage_service().upload(b"signature-bytes", sample_user.signature_path)

    release = COARelease(
        lot_id=sample_lot.id,
        product_id=sample_product.id,
        status=COAReleaseStatus.RELEASED,
        released_at=datetime(2026, 2, 1, 9, 30, 0),
        released_by_id=sample_user.id,
    )
    test_db.add(release)
    test_db.commit()
    return release


def test_issue_serial_is_sequential_and_rolls_over_by_year(test_db):
    assert issue_serial(test_db, 2026) == "COA-2026-000001"
    assert issue_serial(test_db, 2026) == "COA-2026-000002"
    assert issue_serial(test_db, 2027) == "COA-2027-000001"


def test_issue_serial_sequential_double_claim_is_unique(test_db):
    first = issue_serial(test_db, 2026)
    second = issue_serial(test_db, 2026)

    assert first != second
    counter = test_db.get(COASerialCounter, 2026)
    assert counter.last_value == 2


def test_create_snapshot_freezes_context_after_source_mutates(
    test_db, released_coa, sample_product
):
    snapshot = create_snapshot(test_db, released_coa)
    test_db.commit()

    assert snapshot.coa_serial == "COA-2026-000001"
    assert snapshot.content_hash
    assert snapshot.signature_storage_key == (
        "coa-snapshots/COA-2026-000001/signature.png"
    )
    assert get_storage_service().exists(snapshot.pdf_storage_key)
    assert get_storage_service().exists(snapshot.signature_storage_key)

    sample_product.display_name = "Mutated Product Name"
    test_db.commit()

    frozen = get_snapshot_context(test_db, released_coa.id)
    assert frozen is not None
    assert frozen.source == "snapshot"
    assert frozen.document.document_id == "COA-2026-000001"
    assert (
        frozen.product.product_name == "Test Brand Test Product - Vanilla (20 serving)"
    )
    assert frozen.approver.signature_path == snapshot.signature_storage_key


def test_create_snapshot_rejects_duplicate_non_voided_snapshot(test_db, released_coa):
    create_snapshot(test_db, released_coa)
    test_db.commit()

    with pytest.raises(ValueError, match="Non-voided COA snapshot already exists"):
        create_snapshot(test_db, released_coa)


def test_reconstructed_snapshot_has_no_serial(test_db, released_coa):
    snapshot = create_snapshot(test_db, released_coa, reconstructed=True)
    test_db.commit()

    assert snapshot.coa_serial is None
    assert snapshot.reconstructed is True
    assert snapshot.pdf_storage_key.startswith("coa-snapshots/241101-001-release-")


def test_void_snapshot_keeps_row(test_db, released_coa):
    snapshot = create_snapshot(test_db, released_coa)
    test_db.commit()

    void_snapshot(test_db, snapshot, "Issued in error")
    test_db.commit()

    rows = test_db.query(COASnapshot).filter_by(coa_release_id=released_coa.id).all()
    assert len(rows) == 1
    assert rows[0].voided is True
    assert rows[0].void_reason == "Issued in error"
    assert get_snapshot_context(test_db, released_coa.id) is None


def test_backfill_dry_run_commit_and_idempotence(test_db, released_coa):
    dry_run = run_backfill(test_db, commit=False)
    assert dry_run["mode"] == "dry-run"
    assert dry_run["releases_seen"] == 1
    assert dry_run["would_create"] == 1
    assert dry_run["snapshots_created"] == 0
    assert test_db.query(COASnapshot).count() == 0

    committed = run_backfill(test_db, commit=True)
    assert committed["mode"] == "commit"
    assert committed["releases_seen"] == 1
    assert committed["snapshots_created"] == 1, committed
    assert committed["would_create"] == 0
    snapshot = test_db.query(COASnapshot).one()
    assert snapshot.reconstructed is True
    assert snapshot.coa_serial is None

    second = run_backfill(test_db, commit=True)
    assert second["releases_seen"] == 1
    assert second["snapshots_created"] == 0
    assert second["skipped"] == [
        {"release_id": released_coa.id, "reason": "snapshot already exists"}
    ]
