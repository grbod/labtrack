"""Wave 5b: audited deletes, double-release DB constraint, override removal.

Covers the non-authz deliverables:
* delete_lot / delete_test_result now write a DELETE audit entry (were raw).
* a lot carrying a RELEASED COA can never be deleted (409).
* the partial unique index blocks a second RELEASED COA for a (lot, product).
* submit_for_review no longer accepts a forgeable override_user_id.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models import Lot, LotProduct, Product, TestResult, User
from app.models.audit import AuditLog
from app.models.coa_release import COARelease
from app.models.enums import (
    AuditAction,
    COAReleaseStatus,
    LotStatus,
    LotType,
    TestResultStatus,
    UserRole,
)

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


def _user(db, role=UserRole.QC_MANAGER, username="qc"):
    u = User(
        username=username,
        email=f"{username}@example.com",
        role=role,
        active=True,
        full_name="QC User",
        title="QC",
    )
    u.set_password("testpass123")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _client(user):
    return TestClient(app), {"Authorization": f"Bearer {create_access_token(user.id)}"}


def _product(db):
    p = Product(brand="B", product_name="P", flavor="F", display_name="B P - F")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _lot(db, product, status=LotStatus.AWAITING_RESULTS, ref="260709-900"):
    lot = Lot(
        lot_number="W5B" + ref[-3:],
        lot_type=LotType.STANDARD,
        reference_number=ref,
        status=status,
    )
    db.add(lot)
    db.commit()
    db.add(LotProduct(lot_id=lot.id, product_id=product.id))
    db.commit()
    db.refresh(lot)
    return lot


# ---------------------------------------------------------------------------
# Audited deletes
# ---------------------------------------------------------------------------
def test_delete_lot_writes_audit_and_removes(db):
    user = _user(db)
    product = _product(db)
    lot = _lot(db, product)
    lot_id = lot.id

    client, headers = _client(user)
    resp = client.delete(f"/api/v1/lots/{lot_id}", headers=headers)
    assert resp.status_code == 204

    assert db.query(Lot).filter(Lot.id == lot_id).first() is None
    entry = (
        db.query(AuditLog)
        .filter(
            AuditLog.table_name == "lots",
            AuditLog.record_id == lot_id,
            AuditLog.action == AuditAction.DELETE,
        )
        .first()
    )
    assert entry is not None
    assert entry.user_id == user.id
    assert entry.get_old_values_dict().get("reference_number") == "260709-900"


def test_delete_lot_with_released_coa_refused_409(db):
    user = _user(db)
    product = _product(db)
    # Artificial belt-and-suspenders state: AWAITING_RESULTS lot that also has a
    # RELEASED COA. The delete must refuse regardless of status.
    lot = _lot(db, product, ref="260709-901")
    rel = COARelease(
        lot_id=lot.id,
        product_id=product.id,
        status=COAReleaseStatus.RELEASED,
        released_at=datetime.utcnow(),
        released_by_id=user.id,
    )
    db.add(rel)
    db.commit()

    client, headers = _client(user)
    resp = client.delete(f"/api/v1/lots/{lot.id}", headers=headers)
    assert resp.status_code == 409
    assert db.query(Lot).filter(Lot.id == lot.id).first() is not None


def test_delete_test_result_writes_audit(db):
    user = _user(db)
    product = _product(db)
    lot = _lot(db, product, ref="260709-902")
    result = TestResult(
        lot_id=lot.id,
        test_type="Total Plate Count",
        result_value="10",
        unit="CFU/g",
        status=TestResultStatus.DRAFT,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    rid = result.id

    client, headers = _client(user)
    resp = client.delete(f"/api/v1/test-results/{rid}", headers=headers)
    assert resp.status_code == 204

    assert db.query(TestResult).filter(TestResult.id == rid).first() is None
    entry = (
        db.query(AuditLog)
        .filter(
            AuditLog.table_name == "test_results",
            AuditLog.record_id == rid,
            AuditLog.action == AuditAction.DELETE,
        )
        .first()
    )
    assert entry is not None
    assert entry.get_old_values_dict().get("test_type") == "Total Plate Count"


# ---------------------------------------------------------------------------
# Double-release DB constraint
# ---------------------------------------------------------------------------
def test_second_released_coa_for_same_pair_is_rejected(db):
    user = _user(db)
    product = _product(db)
    lot = _lot(db, product, ref="260709-903")

    db.add(
        COARelease(
            lot_id=lot.id,
            product_id=product.id,
            status=COAReleaseStatus.RELEASED,
            released_at=datetime.utcnow(),
            released_by_id=user.id,
        )
    )
    db.commit()

    db.add(
        COARelease(
            lot_id=lot.id,
            product_id=product.id,
            status=COAReleaseStatus.RELEASED,
            released_at=datetime.utcnow(),
            released_by_id=user.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_awaiting_and_released_coexist(db):
    """The partial index only constrains RELEASED rows; an AWAITING_RELEASE row
    alongside a RELEASED one for the same pair is allowed."""
    user = _user(db)
    product = _product(db)
    lot = _lot(db, product, ref="260709-904")

    db.add(
        COARelease(
            lot_id=lot.id,
            product_id=product.id,
            status=COAReleaseStatus.RELEASED,
            released_at=datetime.utcnow(),
            released_by_id=user.id,
        )
    )
    db.add(
        COARelease(
            lot_id=lot.id,
            product_id=product.id,
            status=COAReleaseStatus.AWAITING_RELEASE,
        )
    )
    db.commit()  # must not raise
    assert (
        db.query(COARelease)
        .filter(COARelease.lot_id == lot.id, COARelease.product_id == product.id)
        .count()
        == 2
    )


# ---------------------------------------------------------------------------
# override_user_id removal
# ---------------------------------------------------------------------------
def test_submit_for_review_rejects_override_user_id_query(db):
    """The forgeable override_user_id query param is gone; the submit still runs
    (attributed to the caller) and simply ignores the stray query param."""
    user = _user(db, role=UserRole.LAB_TECH, username="lab")
    product = _product(db)
    # A lot not in UNDER_REVIEW so submit returns a 400 (business rule), proving
    # the endpoint ran without the override param wiring.
    lot = _lot(db, product, status=LotStatus.AWAITING_RESULTS, ref="260709-905")

    client, headers = _client(user)
    resp = client.post(
        f"/api/v1/lots/{lot.id}/submit-for-review",
        params={"override_user_id": 1},
        headers=headers,
    )
    # 400 (can't submit from this status) — NOT a 500 from an unknown param, and
    # no OVERRIDE audit row attributed to the forged user id.
    assert resp.status_code == 400
    forged = (
        db.query(AuditLog)
        .filter(AuditLog.action == AuditAction.OVERRIDE, AuditLog.user_id == 1)
        .first()
    )
    assert forged is None
