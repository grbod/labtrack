"""Route-level authorization matrix (Wave 5b).

Exercises a representative mutating endpoint from every router that carries
mutations, against all four roles, using *real JWTs* through the full auth
stack (get_current_user decodes the token, loads the user from the DB, then the
route's role dependency runs).

Assertion model
---------------
For each (endpoint, role):

* if the role is NOT in the endpoint's allowed set  -> HTTP 403
* if the role IS allowed                            -> anything but 403
  (authorized calls hit non-existent ids / empty state and legitimately return
  200/400/404/409 — the point is only that authorization passed)

Bodies are valid and ids are non-existent so an authorized caller never trips
422 body-validation; the role dependency runs before the handler either way.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models import User
from app.models.enums import UserRole

# ---------------------------------------------------------------------------
# In-memory DB shared by the app (via get_db override) and the test setup
# ---------------------------------------------------------------------------
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


ROLES = {
    "admin": UserRole.ADMIN,
    "qc_manager": UserRole.QC_MANAGER,
    "lab_tech": UserRole.LAB_TECH,
    "read_only": UserRole.READ_ONLY,
}


@pytest.fixture(scope="module")
def tokens():
    """Seed one active user per role and return {role_name: bearer_token}."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    out = {}
    try:
        for name, role in ROLES.items():
            user = User(
                username=name,
                email=f"{name}@example.com",
                role=role,
                active=True,
                full_name=f"{name} User",
                title="Quality Control",
                signature_path="signatures/sig.png",
            )
            user.set_password("testpass123")
            db.add(user)
            db.commit()
            db.refresh(user)
            out[name] = create_access_token(user.id)
    finally:
        db.close()
    app.dependency_overrides[get_db] = _override_get_db
    yield out
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


# Role sets
LAB = {"admin", "qc_manager", "lab_tech"}
QC = {"admin", "qc_manager"}
ADMIN = {"admin"}

# (label, method, path, json_body_or_None, query_or_None, allowed_roles)
# ids are non-existent on purpose; allowed roles get 4xx from the handler, not 403.
MATRIX = [
    # lots
    (
        "lots.submit_for_review",
        "POST",
        "/api/v1/lots/999999/submit-for-review",
        None,
        None,
        LAB,
    ),
    (
        "lots.create",
        "POST",
        "/api/v1/lots",
        {"lot_number": "AUTHZ-1", "lot_type": "standard"},
        None,
        LAB,
    ),
    (
        "lots.status_recalc_apply",
        "POST",
        "/api/v1/lots/status-recalculation/apply",
        None,
        None,
        ADMIN,
    ),
    ("lots.delete", "DELETE", "/api/v1/lots/999999", None, None, QC),
    (
        "lots.update_status",
        "PATCH",
        "/api/v1/lots/999999/status",
        {"status": "approved"},
        None,
        QC,
    ),
    ("lots.fork", "POST", "/api/v1/lots/999999/fork", {"product_id": 1}, None, QC),
    # test_results
    ("test_results.update", "PATCH", "/api/v1/test-results/999999", {}, None, LAB),
    (
        "test_results.approve",
        "PATCH",
        "/api/v1/test-results/999999/status",
        {"status": "approved"},
        None,
        QC,
    ),
    ("test_results.delete", "DELETE", "/api/v1/test-results/999999", None, None, QC),
    # release
    (
        "release.approve_by_lot_product",
        "POST",
        "/api/v1/release/999999/888888/approve",
        {},
        None,
        QC,
    ),
    ("release.approve", "POST", "/api/v1/release/999999/approve", None, None, QC),
    (
        "release.void",
        "POST",
        "/api/v1/release/999999/void",
        {"reason": "authz probe"},
        None,
        ADMIN,
    ),
    ("release.save_draft", "PUT", "/api/v1/release/999999/draft", {}, None, QC),
    # archive
    (
        "archive.resend",
        "POST",
        "/api/v1/archive/999999/resend",
        {"recipient_email": "a@b.com"},
        None,
        QC,
    ),
    # result imports
    (
        "result_imports.cancel",
        "POST",
        "/api/v1/result-imports/999999/cancel",
        None,
        None,
        LAB,
    ),
    (
        "result_imports.revert",
        "POST",
        "/api/v1/result-imports/999999/revert",
        None,
        None,
        LAB,
    ),
    # uploads
    (
        "uploads.delete",
        "DELETE",
        "/api/v1/uploads/nonexistent-authz.pdf",
        None,
        None,
        LAB,
    ),
    # retest
    (
        "retest.complete",
        "POST",
        "/api/v1/retest/retest-requests/999999/complete",
        None,
        None,
        QC,
    ),
    (
        "retest.create",
        "POST",
        "/api/v1/retest/lots/999999/retest-requests",
        {"test_result_ids": [1], "reason": "x"},
        None,
        QC,
    ),
    # lab test aliases
    (
        "aliases.approve",
        "POST",
        "/api/v1/lab-test-aliases/999999/approve",
        None,
        None,
        QC,
    ),
    # audit
    (
        "audit.annotation",
        "POST",
        "/api/v1/audit/999999/annotations",
        None,
        {"comment": "x"},
        QC,
    ),
    # admin-only config CRUD
    ("customers.delete", "DELETE", "/api/v1/customers/999999", None, None, ADMIN),
    ("products.delete", "DELETE", "/api/v1/products/999999", None, None, ADMIN),
    (
        "lab_test_types.delete",
        "DELETE",
        "/api/v1/lab-test-types/999999",
        None,
        None,
        ADMIN,
    ),
    (
        "settings.category_order_reset",
        "POST",
        "/api/v1/settings/coa-category-order/reset",
        None,
        None,
        ADMIN,
    ),
    ("users.delete", "DELETE", "/api/v1/users/999999", None, None, ADMIN),
]


def _call(client, method, path, body, query, token):
    headers = {"Authorization": f"Bearer {token}"}
    return client.request(method, path, json=body, params=query, headers=headers)


@pytest.mark.parametrize("label,method,path,body,query,allowed", MATRIX)
@pytest.mark.parametrize("role", list(ROLES.keys()))
def test_authz_matrix(tokens, role, label, method, path, body, query, allowed):
    client = TestClient(app)
    resp = _call(client, method, path, body, query, tokens[role])
    if role in allowed:
        assert (
            resp.status_code != 403
        ), f"{label}: {role} should be authorized but got 403 ({resp.text[:200]})"
    else:
        assert resp.status_code == 403, (
            f"{label}: {role} should be forbidden but got {resp.status_code} "
            f"({resp.text[:200]})"
        )


def test_unauthenticated_is_401_not_403(tokens):
    """No token at all -> 401 (authentication), distinct from 403 (authorization)."""
    client = TestClient(app)
    resp = client.post("/api/v1/lots/999999/submit-for-review")
    assert resp.status_code == 401
