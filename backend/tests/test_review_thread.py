"""Tests for the GET /api/v1/lots/{id}/review-thread endpoint.

The endpoint derives the return/resolution conversation from the audit log
without any new storage — each round trip (QC returns, lab tech resolves)
writes audit rows that this endpoint re-reads.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import (
    AuditLog,
    LabTestType,
    Lot,
    LotProduct,
    Product,
    ProductTestSpecification,
    TestResult,
    User,
)
from app.models.enums import LotStatus, LotType, TestResultStatus, UserRole

# ---------------------------------------------------------------------------
# In-memory DB setup (isolated from other test suites)
# ---------------------------------------------------------------------------

_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def api_db():
    Base.metadata.create_all(bind=_ENGINE)
    db = _Session()
    yield db
    db.close()
    Base.metadata.drop_all(bind=_ENGINE)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _make_client(user):
    app.dependency_overrides[get_db] = _override_get_db

    async def _override_current_user():
        return user

    app.dependency_overrides[get_current_user] = _override_current_user
    return TestClient(app)


def _make_user(api_db, username, role):
    user = User(
        username=username,
        email=f"{username}@test.com",
        role=role,
        active=True,
        full_name="Test User",
        title="Test",
    )
    user.set_password("testpass123")
    api_db.add(user)
    api_db.commit()
    api_db.refresh(user)
    return user


@pytest.fixture
def qc_user(api_db):
    return _make_user(api_db, "qcmanager", UserRole.QC_MANAGER)


@pytest.fixture
def labtech_user(api_db):
    return _make_user(api_db, "labtech", UserRole.LAB_TECH)


@pytest.fixture
def product_with_specs(api_db):
    product = Product(
        brand="Thread Brand",
        product_name="Thread Product",
        flavor="Plain",
        size="30 serving",
        display_name="Thread Brand Thread Product - Plain (30 serving)",
    )
    api_db.add(product)
    api_db.commit()

    types = [
        LabTestType(
            test_name="Total Plate Count",
            test_category="Microbiological",
            default_unit="CFU/g",
            is_active=True,
        ),
        LabTestType(
            test_name="E. coli",
            test_category="Microbiological",
            default_unit="Positive/Negative",
            is_active=True,
        ),
        LabTestType(
            test_name="Lead",
            test_category="Heavy Metals",
            default_unit="ppm",
            is_active=True,
        ),
        LabTestType(
            test_name="Protein",
            test_category="Nutritional",
            default_unit="g/100g",
            is_active=True,
        ),
    ]
    for t in types:
        api_db.add(t)
    api_db.commit()

    specs = [
        ProductTestSpecification(
            product_id=product.id,
            lab_test_type_id=types[0].id,
            specification="< 10000",
            is_required=True,
        ),
        ProductTestSpecification(
            product_id=product.id,
            lab_test_type_id=types[1].id,
            specification="Negative",
            is_required=True,
        ),
        ProductTestSpecification(
            product_id=product.id,
            lab_test_type_id=types[2].id,
            specification="< 0.5",
            is_required=True,
            min_value="0",
            max_value="0.5",
        ),
        ProductTestSpecification(
            product_id=product.id,
            lab_test_type_id=types[3].id,
            specification="20-25",
            is_required=True,
            min_value="20",
            max_value="25",
        ),
    ]
    for s in specs:
        api_db.add(s)
    api_db.commit()
    api_db.refresh(product)
    return product


def _make_lot_all_passing(api_db, product, ref, status):
    lot = Lot(
        lot_number="THR-" + ref,
        lot_type=LotType.STANDARD,
        reference_number=ref,
        status=status,
        generate_coa=True,
    )
    api_db.add(lot)
    api_db.commit()
    api_db.add(LotProduct(lot_id=lot.id, product_id=product.id))
    api_db.commit()

    results = [
        TestResult(
            lot_id=lot.id,
            test_type="Total Plate Count",
            result_value="500",
            unit="CFU/g",
            status=TestResultStatus.DRAFT,
        ),
        TestResult(
            lot_id=lot.id,
            test_type="E. coli",
            result_value="Negative",
            unit="Positive/Negative",
            status=TestResultStatus.DRAFT,
        ),
        TestResult(
            lot_id=lot.id,
            test_type="Lead",
            result_value="0.1",
            unit="ppm",
            status=TestResultStatus.DRAFT,
        ),
        TestResult(
            lot_id=lot.id,
            test_type="Protein",
            result_value="22",
            unit="g/100g",
            status=TestResultStatus.DRAFT,
        ),
    ]
    for r in results:
        api_db.add(r)
    api_db.commit()
    api_db.refresh(lot)
    return lot


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_review_thread_empty(api_db, qc_user, product_with_specs):
    """A lot that was never returned should return an empty thread."""
    lot = _make_lot_all_passing(
        api_db, product_with_specs, "260301-901", LotStatus.AWAITING_RELEASE
    )
    client = _make_client(qc_user)

    resp = client.get(f"/api/v1/lots/{lot.id}/review-thread")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["events"] == []
    assert body["return_count"] == 0


def test_review_thread_multi_round(api_db, qc_user, labtech_user, product_with_specs):
    """Full two-round return/resolution conversation produces 4 events in order."""
    lot = _make_lot_all_passing(
        api_db, product_with_specs, "260301-902", LotStatus.AWAITING_RELEASE
    )

    # Round 1: QC returns with reason "A"
    resp = _make_client(qc_user).post(
        f"/api/v1/lots/{lot.id}/return-for-review",
        json={"reason": "A"},
    )
    assert resp.status_code == 200, resp.text

    # Round 1: Lab tech resolves with note "B"
    resp = _make_client(labtech_user).post(
        f"/api/v1/lots/{lot.id}/submit-for-review",
        json={"return_response_note": "B"},
    )
    assert resp.status_code == 200, resp.text

    # Round 2: QC returns again with reason "C"
    resp = _make_client(qc_user).post(
        f"/api/v1/lots/{lot.id}/return-for-review",
        json={"reason": "C"},
    )
    assert resp.status_code == 200, resp.text

    # Round 2: Lab tech resolves with note "D"
    resp = _make_client(labtech_user).post(
        f"/api/v1/lots/{lot.id}/submit-for-review",
        json={"return_response_note": "D"},
    )
    assert resp.status_code == 200, resp.text

    # Fetch the review thread (as QC)
    resp = _make_client(qc_user).get(f"/api/v1/lots/{lot.id}/review-thread")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["return_count"] == 2
    events = body["events"]
    assert len(events) == 4

    types = [e["type"] for e in events]
    assert types == ["return", "resolution", "return", "resolution"]

    messages = [e["message"] for e in events]
    assert messages == ["A", "B", "C", "D"]

    for e in events:
        assert e["at"] is not None
        assert e["author"] is not None


def test_review_thread_accessible_to_lab_tech(
    api_db, qc_user, labtech_user, product_with_specs
):
    """Lab tech (not QC) must be able to GET the review thread (200, not 403)."""
    lot = _make_lot_all_passing(
        api_db, product_with_specs, "260301-903", LotStatus.AWAITING_RELEASE
    )

    # QC returns
    resp = _make_client(qc_user).post(
        f"/api/v1/lots/{lot.id}/return-for-review",
        json={"reason": "Check COC"},
    )
    assert resp.status_code == 200, resp.text

    # Lab tech reads the thread
    resp = _make_client(labtech_user).get(f"/api/v1/lots/{lot.id}/review-thread")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["events"]) == 1
    assert body["events"][0]["type"] == "return"
    assert body["events"][0]["message"] == "Check COC"


def test_review_thread_404(api_db, qc_user):
    """GET for a nonexistent lot must return 404."""
    client = _make_client(qc_user)
    resp = client.get("/api/v1/lots/99999/review-thread")
    assert resp.status_code == 404
