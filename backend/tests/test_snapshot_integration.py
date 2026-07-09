"""Endpoint-level tests for snapshot wiring in the release lifecycle.

Proves the immutability property AT THE ENDPOINT: a released COA is served from
its frozen snapshot and does not change when the underlying lot/product/results
are mutated afterwards.
"""

from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import (
    COARelease,
    Lot,
    LotProduct,
    Product,
    TestResult,
    User,
)
from app.models.coa_snapshot import COASnapshot
from app.models.enums import (
    COAReleaseStatus,
    LotStatus,
    LotType,
    TestResultStatus,
    UserRole,
)
from app.services.coa_generation_service import COAGenerationService
from app.services.coa_snapshot_service import coa_snapshot_service
from app.services.storage_service import get_storage_service, reset_storage_service

engine = create_engine(
    "sqlite:///:memory:",
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


@pytest.fixture(autouse=True)
def local_snapshot_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_path", tmp_path)
    monkeypatch.setattr(settings, "storage_backend", "local")
    reset_storage_service()
    yield
    reset_storage_service()


@pytest.fixture(autouse=True)
def fast_pdf_renderer(monkeypatch):
    def _write_pdf(self, context, output_path):
        Path(output_path).write_bytes(
            f"PDF for {context.document.document_id}".encode("utf-8")
        )

    monkeypatch.setattr(COAGenerationService, "_generate_pdf_reportlab", _write_pdf)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _make_user(db, username, role):
    user = User(
        username=username,
        email=f"{username}@example.com",
        role=role,
        active=True,
        full_name=f"{username} Name",
        title="Quality Control",
        signature_path="signatures/sig.png",
    )
    user.set_password("testpass123")
    db.add(user)
    db.commit()
    db.refresh(user)
    get_storage_service().upload(b"sig-bytes", user.signature_path)
    return user


@pytest.fixture
def qc_user(test_db):
    return _make_user(test_db, "qcmanager", UserRole.QC_MANAGER)


@pytest.fixture
def admin_user(test_db):
    return _make_user(test_db, "admin", UserRole.ADMIN)


@pytest.fixture
def product(test_db):
    p = Product(
        brand="Test Brand",
        product_name="Test Product",
        flavor="Vanilla",
        display_name="Test Brand Test Product - Vanilla",
    )
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


def _lot(db, product_id, status=LotStatus.AWAITING_RELEASE):
    lot = Lot(
        lot_number="SNAPLOT1",
        reference_number="260709-050",
        lot_type=LotType.STANDARD,
        status=status,
        mfg_date=date.today(),
        exp_date=date(2027, 12, 31),
    )
    db.add(lot)
    db.commit()
    db.add(LotProduct(lot_id=lot.id, product_id=product_id))
    db.commit()
    return lot


def _client(user):
    app.dependency_overrides[get_db] = override_get_db

    async def _cu():
        return user

    app.dependency_overrides[get_current_user] = _cu
    return TestClient(app)


def _snapshot_for(db, release_id, voided=False):
    return (
        db.query(COASnapshot)
        .filter(
            COASnapshot.coa_release_id == release_id,
            COASnapshot.voided.is_(voided),
        )
        .first()
    )


def test_release_creates_snapshot_atomically(test_db, product, qc_user):
    lot = _lot(test_db, product.id)
    client = _client(qc_user)

    resp = client.post(f"/api/v1/release/{lot.id}/{product.id}/approve", json={})
    assert resp.status_code == 200
    release_id = resp.json()["coa_release_id"]

    snap = _snapshot_for(test_db, release_id)
    assert snap is not None
    assert snap.revision == 1
    assert snap.coa_serial and snap.coa_serial.startswith("COA-")
    assert snap.voided is False

    # coa_file_path points at the frozen snapshot PDF
    release = test_db.query(COARelease).filter(COARelease.id == release_id).first()
    assert release.coa_file_path == snap.pdf_storage_key

    # preview-data is served from the snapshot with the serial as document_id
    data = client.get(f"/api/v1/release/{lot.id}/{product.id}/preview-data").json()
    assert data["source"] == "snapshot"
    assert data["document_id"] == snap.coa_serial
    assert data["reconstructed"] is False


def test_snapshot_failure_rolls_back_release(test_db, product, qc_user, monkeypatch):
    lot = _lot(test_db, product.id)
    client = _client(qc_user)

    def _boom(*args, **kwargs):
        raise RuntimeError("render exploded")

    monkeypatch.setattr(coa_snapshot_service, "create_snapshot", _boom)

    resp = client.post(f"/api/v1/release/{lot.id}/{product.id}/approve", json={})
    assert resp.status_code == 500

    test_db.expire_all()
    # Release did not flip to RELEASED, lot stayed in the queue, no snapshot.
    release = (
        test_db.query(COARelease)
        .filter(COARelease.lot_id == lot.id, COARelease.product_id == product.id)
        .first()
    )
    if release is not None:
        assert release.status == COAReleaseStatus.AWAITING_RELEASE
    lot_row = test_db.query(Lot).filter(Lot.id == lot.id).first()
    assert lot_row.status == LotStatus.AWAITING_RELEASE
    assert test_db.query(COASnapshot).count() == 0


def test_released_preview_is_immutable_at_endpoint(test_db, product, qc_user):
    lot = _lot(test_db, product.id)
    client = _client(qc_user)
    assert (
        client.post(
            f"/api/v1/release/{lot.id}/{product.id}/approve", json={}
        ).status_code
        == 200
    )

    before = client.get(f"/api/v1/release/{lot.id}/{product.id}/preview-data").json()

    # Mutate the world after release: rename the product, add a new result.
    product.product_name = "MUTATED NAME"
    product.display_name = "MUTATED NAME"
    test_db.add(
        TestResult(
            lot_id=lot.id,
            test_type="Lead",
            result_value="9999",
            specification="< 1",
            status=TestResultStatus.APPROVED,
        )
    )
    test_db.commit()

    after = client.get(f"/api/v1/release/{lot.id}/{product.id}/preview-data").json()
    assert after == before  # frozen snapshot is unaffected
    assert after["product_name"] == "Test Brand Test Product - Vanilla"
    assert after["source"] == "snapshot"


def test_void_excludes_snapshot_from_serving(test_db, product, admin_user):
    lot = _lot(test_db, product.id)
    client = _client(admin_user)
    release_id = client.post(
        f"/api/v1/release/{lot.id}/{product.id}/approve", json={}
    ).json()["coa_release_id"]

    # Void it (admin).
    assert (
        client.post(
            f"/api/v1/release/{release_id}/void", json={"reason": "bad data"}
        ).status_code
        == 200
    )

    # The snapshot row is kept but flagged voided.
    test_db.expire_all()
    assert _snapshot_for(test_db, release_id, voided=True) is not None
    assert _snapshot_for(test_db, release_id, voided=False) is None

    # Serving now falls back to live (no non-voided snapshot).
    data = client.get(f"/api/v1/release/{lot.id}/{product.id}/preview-data").json()
    assert data["source"] == "live"

    # Download 404s (no active snapshot for a non-released row).
    dl = client.get(f"/api/v1/release/{lot.id}/{product.id}/download")
    assert dl.status_code == 404


def test_re_release_after_void_creates_revision_2_with_supersedes(
    test_db, product, admin_user
):
    lot = _lot(test_db, product.id)
    client = _client(admin_user)

    # First release -> revision 1.
    release_id = client.post(
        f"/api/v1/release/{lot.id}/{product.id}/approve", json={}
    ).json()["coa_release_id"]
    rev1 = _snapshot_for(test_db, release_id)
    assert rev1.revision == 1

    # Void, returning the lot to the queue.
    assert (
        client.post(
            f"/api/v1/release/{release_id}/void", json={"reason": "reissue"}
        ).status_code
        == 200
    )

    # Re-release the same lot/product -> revision 2 superseding revision 1.
    resp = client.post(f"/api/v1/release/{lot.id}/{product.id}/approve", json={})
    assert resp.status_code == 200

    test_db.expire_all()
    active = _snapshot_for(test_db, release_id, voided=False)
    assert active is not None
    assert active.revision == 2
    assert active.supersedes_id == rev1.id
    # The old snapshot is retained, still voided.
    old = test_db.query(COASnapshot).filter(COASnapshot.id == rev1.id).first()
    assert old.voided is True


def test_download_404_when_released_without_snapshot(test_db, product, qc_user):
    # A released COA with no snapshot (legacy pre-backfill record).
    lot = _lot(test_db, product.id, status=LotStatus.RELEASED)
    release = COARelease(
        lot_id=lot.id,
        product_id=product.id,
        status=COAReleaseStatus.RELEASED,
        released_at=datetime.utcnow(),
        released_by_id=qc_user.id,
    )
    test_db.add(release)
    test_db.commit()

    client = _client(qc_user)
    resp = client.get(f"/api/v1/release/{lot.id}/{product.id}/download")
    assert resp.status_code == 404
    assert "backfill" in resp.json()["detail"].lower()
