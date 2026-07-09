"""Tests for the release gate: completeness, verdicts, sensory attest, override,
void, and self-approval warning. Runs with the enforcement guard at its default
(True) so it also exercises the canonical transitions end to end.
"""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import (
    COARelease,
    LabTestType,
    Lot,
    LotProduct,
    Product,
    ProductTestSpecification,
    TestResult,
    User,
)
from app.models.email_history import EmailHistory
from app.models.enums import (
    COAReleaseStatus,
    LotStatus,
    LotType,
    TestResultStatus,
    UserRole,
)
from app.models.release_sensory_attest import ReleaseSensoryAttest

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


def _lab_type(db, name, category, unit=""):
    lt = LabTestType(test_name=name, test_category=category, default_unit=unit)
    db.add(lt)
    db.flush()
    return lt


def _spec(db, product_id, lab_type, specification, required=True):
    s = ProductTestSpecification(
        product_id=product_id,
        lab_test_type_id=lab_type.id,
        specification=specification,
        is_required=required,
    )
    db.add(s)
    db.flush()
    return s


def _lot(db, product_id, status=LotStatus.AWAITING_RELEASE):
    lot = Lot(
        lot_number="GATELOT1",
        reference_number="260709-001",
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


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Completeness / verdicts
# ---------------------------------------------------------------------------
def test_gate_blocks_on_missing_required_test(test_db, product, qc_user):
    tpc = _lab_type(test_db, "Total Plate Count", "Microbiological", "CFU/g")
    _spec(test_db, product.id, tpc, "< 10000")
    test_db.commit()
    lot = _lot(test_db, product.id)

    client = _client(qc_user)
    gate = client.get(f"/api/v1/release/{lot.id}/{product.id}/gate").json()
    assert "Total Plate Count" in gate["missing_tests"]
    assert gate["can_release"] is False

    resp = client.post(f"/api/v1/release/{lot.id}/{product.id}/approve", json={})
    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert body["code"] == "GATE_BLOCKED"
    assert "Total Plate Count" in body["missing_tests"]


def test_gate_blocks_on_failing_result(test_db, product, qc_user):
    tpc = _lab_type(test_db, "Total Plate Count", "Microbiological", "CFU/g")
    _spec(test_db, product.id, tpc, "< 10")
    test_db.commit()
    lot = _lot(test_db, product.id)
    test_db.add(
        TestResult(
            lot_id=lot.id,
            test_type="Total Plate Count",
            result_value="5000",
            unit="CFU/g",
            specification="< 10",
            lab_test_type_id=tpc.id,
            status=TestResultStatus.APPROVED,
        )
    )
    test_db.commit()

    client = _client(qc_user)
    gate = client.get(f"/api/v1/release/{lot.id}/{product.id}/gate").json()
    assert any(t["name"] == "Total Plate Count" for t in gate["failing_tests"])
    assert gate["can_release"] is False

    resp = client.post(f"/api/v1/release/{lot.id}/{product.id}/approve", json={})
    assert resp.status_code == 409
    assert "Total Plate Count" in resp.json()["detail"]["failing_tests"]


def test_indeterminate_is_amber_and_non_blocking(test_db, product, qc_user):
    # A JUDGMENT-style spec yields INDETERMINATE, which must not block release.
    judg = _lab_type(test_db, "Appearance Note", "Physical", "")
    # "< 500" against a "< 100" limit is not comparable -> INDETERMINATE.
    _spec(test_db, product.id, judg, "< 100")
    test_db.commit()
    lot = _lot(test_db, product.id)
    test_db.add(
        TestResult(
            lot_id=lot.id,
            test_type="Appearance Note",
            result_value="< 500",
            specification="< 100",
            lab_test_type_id=judg.id,
            status=TestResultStatus.APPROVED,
        )
    )
    test_db.commit()

    client = _client(qc_user)
    gate = client.get(f"/api/v1/release/{lot.id}/{product.id}/gate").json()
    assert any(t["name"] == "Appearance Note" for t in gate["indeterminate_tests"])
    assert gate["can_release"] is True
    resp = client.post(f"/api/v1/release/{lot.id}/{product.id}/approve", json={})
    assert resp.status_code == 200


def test_override_releases_and_records_deviation(test_db, product, qc_user):
    tpc = _lab_type(test_db, "Total Plate Count", "Microbiological", "CFU/g")
    _spec(test_db, product.id, tpc, "< 10")  # missing result -> blocked
    test_db.commit()
    lot = _lot(test_db, product.id)

    client = _client(qc_user)
    resp = client.post(
        f"/api/v1/release/{lot.id}/{product.id}/approve",
        json={"override": True, "override_reason": "QC accepted deviation"},
    )
    assert resp.status_code == 200
    release = (
        test_db.query(COARelease)
        .filter(COARelease.lot_id == lot.id, COARelease.product_id == product.id)
        .first()
    )
    assert release.status == COAReleaseStatus.RELEASED
    assert release.deviation_note == "QC accepted deviation"

    # The deviation prints on the COA context.
    from app.services.coa_context_builder import build_context

    ctx = build_context(test_db, lot.id, product.id, release=release)
    assert ctx.document.deviation_note == "QC accepted deviation"


def test_override_requires_reason(test_db, product, qc_user):
    tpc = _lab_type(test_db, "Total Plate Count", "Microbiological", "CFU/g")
    _spec(test_db, product.id, tpc, "< 10")
    test_db.commit()
    lot = _lot(test_db, product.id)
    client = _client(qc_user)
    resp = client.post(
        f"/api/v1/release/{lot.id}/{product.id}/approve",
        json={"override": True, "override_reason": "   "},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Sensory attest
# ---------------------------------------------------------------------------
def test_sensory_attest_required_then_satisfied(test_db, product, qc_user):
    appearance = _lab_type(test_db, "Appearance", "Organoleptic", "")
    _spec(test_db, product.id, appearance, "Typical")
    test_db.commit()
    lot = _lot(test_db, product.id)
    test_db.add(
        TestResult(
            lot_id=lot.id,
            test_type="Appearance",
            result_value="Typical",
            specification="Typical",
            lab_test_type_id=appearance.id,
            status=TestResultStatus.APPROVED,
        )
    )
    test_db.commit()

    client = _client(qc_user)
    gate = client.get(f"/api/v1/release/{lot.id}/{product.id}/gate").json()
    assert len(gate["sensory_rows"]) == 1
    assert gate["sensory_rows"][0]["attested"] is False
    assert gate["can_release"] is False

    # Attempt to release blocked
    assert (
        client.post(
            f"/api/v1/release/{lot.id}/{product.id}/approve", json={}
        ).status_code
        == 409
    )

    # Attest the sensory row
    updated = client.post(
        f"/api/v1/release/{lot.id}/{product.id}/attest",
        json={"lab_test_type_ids": [appearance.id]},
    ).json()
    assert updated["sensory_all_attested"] is True
    assert updated["can_release"] is True

    # Now release succeeds and the attested row prints "Pass"
    resp = client.post(f"/api/v1/release/{lot.id}/{product.id}/approve", json={})
    assert resp.status_code == 200

    release = (
        test_db.query(COARelease)
        .filter(COARelease.lot_id == lot.id, COARelease.product_id == product.id)
        .first()
    )
    from app.services.coa_context_builder import build_context

    ctx = build_context(test_db, lot.id, product.id, release=release)
    row = next(r for r in ctx.test_rows if r.name == "Appearance")
    assert row.status_display == "Pass"


# ---------------------------------------------------------------------------
# Void
# ---------------------------------------------------------------------------
def _release_lot(test_db, product, user):
    """Release a clean lot (no specs) and return its COARelease."""
    lot = _lot(test_db, product.id)
    client = _client(user)
    resp = client.post(f"/api/v1/release/{lot.id}/{product.id}/approve", json={})
    assert resp.status_code == 200
    release = (
        test_db.query(COARelease)
        .filter(COARelease.lot_id == lot.id, COARelease.product_id == product.id)
        .first()
    )
    return lot, release


def test_void_returns_lot_to_queue_and_flags_prior_email(test_db, product, admin_user):
    lot, release = _release_lot(test_db, product, admin_user)

    # Record an email having been sent for this release.
    test_db.add(
        EmailHistory(
            coa_release_id=release.id,
            recipient_email="customer@example.com",
            sent_at=datetime.utcnow(),
            sent_by_id=admin_user.id,
        )
    )
    test_db.commit()

    client = _client(admin_user)
    resp = client.post(
        f"/api/v1/release/{release.id}/void", json={"reason": "Wrong lot data"}
    )
    assert resp.status_code == 200

    test_db.refresh(lot)
    test_db.refresh(release)
    assert lot.status == LotStatus.AWAITING_RELEASE
    assert release.status == COAReleaseStatus.AWAITING_RELEASE
    assert release.voided_at is not None
    assert release.voided_note == "Wrong lot data"

    # Re-release gate flags the prior email.
    gate = client.get(f"/api/v1/release/{lot.id}/{product.id}/gate").json()
    assert "customer@example.com" in gate["prior_email_recipients"]
    assert gate["prior_email_date"] is not None


def test_void_requires_admin(test_db, product, qc_user):
    # Release with an admin-capable path first (qc can release).
    lot, release = _release_lot(test_db, product, qc_user)
    client = _client(qc_user)
    resp = client.post(f"/api/v1/release/{release.id}/void", json={"reason": "x"})
    assert resp.status_code == 403


def test_void_requires_reason(test_db, product, admin_user):
    lot, release = _release_lot(test_db, product, admin_user)
    client = _client(admin_user)
    resp = client.post(f"/api/v1/release/{release.id}/void", json={"reason": "  "})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Self-approval warning
# ---------------------------------------------------------------------------
def test_self_approval_warning(test_db, product, qc_user):
    lot = _lot(test_db, product.id, status=LotStatus.UNDER_REVIEW)
    result = TestResult(
        lot_id=lot.id,
        test_type="Total Plate Count",
        result_value="< 10",
        status=TestResultStatus.DRAFT,
        created_by_id=qc_user.id,
    )
    test_db.add(result)
    test_db.commit()

    client = _client(qc_user)
    resp = client.patch(
        f"/api/v1/test-results/{result.id}/status", json={"status": "approved"}
    )
    assert resp.status_code == 200
    assert resp.json()["self_approval_warning"] is True

    # A SELF_APPROVAL audit row exists.
    from app.models.audit import AuditLog
    from app.models.enums import AuditAction

    self_audit = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "test_results",
            AuditLog.action == AuditAction.SELF_APPROVAL,
        )
        .first()
    )
    assert self_audit is not None


def test_no_self_approval_warning_for_other_approver(test_db, product, qc_user):
    other = _make_user(test_db, "creator", UserRole.LAB_TECH)
    lot = _lot(test_db, product.id, status=LotStatus.UNDER_REVIEW)
    result = TestResult(
        lot_id=lot.id,
        test_type="Total Plate Count",
        result_value="< 10",
        status=TestResultStatus.DRAFT,
        created_by_id=other.id,
    )
    test_db.add(result)
    test_db.commit()

    client = _client(qc_user)
    resp = client.patch(
        f"/api/v1/test-results/{result.id}/status", json={"status": "approved"}
    )
    assert resp.status_code == 200
    assert resp.json()["self_approval_warning"] is False
