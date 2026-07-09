"""Wave 5a hardening: read-only middleware, critical-audit raises, row locking."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models import Lot, LotProduct, Product, User
from app.models.audit import AuditLog
from app.models.enums import AuditAction, LotStatus, LotType, UserRole
from app.services.lot_service import LotService
from app.workflow.lot_workflow_service import LotWorkflowService

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


def _user(db, username, role):
    u = User(username=username, email=f"{username}@x.com", role=role, active=True)
    u.set_password("pw12345678")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ---------------------------------------------------------------------------
# 1. read-only enforcement middleware
# ---------------------------------------------------------------------------
_READONLY_DETAIL = "Read-only users cannot perform this action."


@pytest.fixture
def mw_client(test_db, monkeypatch):
    # Both the middleware (SessionLocal) and the endpoints (get_db) must see the
    # same in-memory DB.
    import app.middleware as mw

    monkeypatch.setattr(mw, "SessionLocal", TestingSessionLocal)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _token(user):
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def test_readonly_post_is_blocked(mw_client, test_db):
    ro = _user(test_db, "ro", UserRole.READ_ONLY)
    resp = mw_client.post("/api/v1/lots", headers=_token(ro), json={})
    assert resp.status_code == 403
    assert resp.json()["detail"] == _READONLY_DETAIL


def test_readonly_get_passes_through(mw_client, test_db):
    ro = _user(test_db, "ro", UserRole.READ_ONLY)
    resp = mw_client.get("/api/v1/lots", headers=_token(ro))
    assert resp.status_code == 200  # read-only may read


def test_lab_tech_post_unaffected(mw_client, test_db):
    tech = _user(test_db, "tech", UserRole.LAB_TECH)
    resp = mw_client.post("/api/v1/lots", headers=_token(tech), json={})
    # Passes the middleware; the route itself validates the (empty) body.
    assert resp.status_code != 403
    assert resp.json().get("detail") != _READONLY_DETAIL


def test_anonymous_request_unaffected(mw_client):
    # No token -> middleware fails open -> auth layer answers (401), not 403.
    resp = mw_client.post("/api/v1/lots", json={})
    assert resp.status_code == 401
    assert resp.json().get("detail") != _READONLY_DETAIL


def test_auth_paths_exempt_for_readonly(mw_client, test_db):
    ro = _user(test_db, "ro", UserRole.READ_ONLY)
    # A mutating auth request is exempt: reaches the endpoint (422 empty body),
    # never the read-only 403.
    resp = mw_client.post("/api/v1/auth/login", headers=_token(ro), json={})
    assert resp.status_code != 403
    assert resp.json().get("detail") != _READONLY_DETAIL


def test_invalid_token_fails_open(mw_client, test_db):
    resp = mw_client.post(
        "/api/v1/lots", headers={"Authorization": "Bearer not-a-jwt"}, json={}
    )
    # Invalid token is the auth layer's problem (401), not a 403.
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. critical audit failures raise
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "action",
    [AuditAction.APPROVE, AuditAction.REJECT, AuditAction.VOID, AuditAction.DELETE],
)
def test_critical_audit_failure_raises(test_db, monkeypatch, action):
    def _boom(*args, **kwargs):
        raise RuntimeError("audit table unavailable")

    monkeypatch.setattr(AuditLog, "log_change", staticmethod(_boom))
    with pytest.raises(RuntimeError):
        LotService()._log_audit(test_db, action=action, record_id=1)


def test_non_critical_audit_failure_is_swallowed(test_db, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("audit table unavailable")

    monkeypatch.setattr(AuditLog, "log_change", staticmethod(_boom))
    # UPDATE is routine -> log-only, no raise.
    LotService()._log_audit(test_db, action=AuditAction.UPDATE, record_id=1)


def test_explicit_critical_false_overrides(test_db, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("audit table unavailable")

    monkeypatch.setattr(AuditLog, "log_change", staticmethod(_boom))
    # Force a critical action to be non-critical for this call.
    LotService()._log_audit(
        test_db, action=AuditAction.APPROVE, record_id=1, critical=False
    )


# ---------------------------------------------------------------------------
# 3. row locking (no-op on SQLite, path still works)
# ---------------------------------------------------------------------------
def _lot_with_product(db, status):
    product = Product(brand="B", product_name="P", display_name="B P")
    db.add(product)
    db.commit()
    lot = Lot(
        lot_number="LK1",
        reference_number="260709-900",
        lot_type=LotType.STANDARD,
        status=status,
        mfg_date=date.today(),
        exp_date=date(2027, 1, 1),
    )
    db.add(lot)
    db.commit()
    db.add(LotProduct(lot_id=lot.id, product_id=product.id))
    db.commit()
    return lot


def test_lock_lot_row_is_noop_on_sqlite(test_db):
    lot = _lot_with_product(test_db, LotStatus.UNDER_REVIEW)
    # Must not raise on SQLite (which has no SELECT ... FOR UPDATE).
    LotWorkflowService._lock_lot_row(test_db, lot)


def test_transition_still_works_with_locking(test_db):
    lot = _lot_with_product(test_db, LotStatus.UNDER_REVIEW)
    user = _user(test_db, "qc", UserRole.QC_MANAGER)
    LotWorkflowService().transition(
        test_db, lot, LotStatus.AWAITING_RELEASE, user, trigger="manual"
    )
    assert lot.status == LotStatus.AWAITING_RELEASE
