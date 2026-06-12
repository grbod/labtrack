"""Tests for the Return-for-Review lot workflow.

A QC manager can send an AWAITING_RELEASE lot back to NEEDS_ATTENTION with a
return_reason.  The lot stays in NEEDS_ATTENTION (even when all tests pass)
until return_response_note is set.
"""

from datetime import date

import pytest

from app.models import Lot, LotProduct, TestResult
from app.models.enums import LotStatus, LotType, TestResultStatus
from app.services.lot_service import LotService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lot_with_all_passing(test_db, product, ref: str, status: LotStatus) -> Lot:
    """Create a lot linked to *product* with all required tests passing."""
    lot = Lot(
        lot_number="RFR-" + ref,
        lot_type=LotType.STANDARD,
        reference_number=ref,
        status=status,
        generate_coa=True,
    )
    test_db.add(lot)
    test_db.commit()

    lot_product = LotProduct(lot_id=lot.id, product_id=product.id)
    test_db.add(lot_product)
    test_db.commit()

    # All four required specs from sample_product_with_specs, all passing
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
        test_db.add(r)
    test_db.commit()

    return lot


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReturnForReview:
    def test_awaiting_release_can_return_to_needs_attention(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """Transition from AWAITING_RELEASE to NEEDS_ATTENTION must succeed."""
        lot = _lot_with_all_passing(
            test_db,
            sample_product_with_specs,
            ref="260101-801",
            status=LotStatus.AWAITING_RELEASE,
        )

        # This transition should not raise
        lot.update_status(LotStatus.NEEDS_ATTENTION)
        test_db.commit()

        test_db.refresh(lot)
        assert lot.status == LotStatus.NEEDS_ATTENTION

    def test_returned_lot_holds_needs_attention_despite_passing_tests(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """A lot with return_reason and no response stays NEEDS_ATTENTION even
        when all required tests are passing."""
        lot = _lot_with_all_passing(
            test_db,
            sample_product_with_specs,
            ref="260101-802",
            status=LotStatus.NEEDS_ATTENTION,
        )
        lot.return_reason = "Wrong lot number on COC"
        lot.return_response_note = None
        test_db.commit()

        service = LotService()
        # calculate_lot_status should hold the lot in NEEDS_ATTENTION
        calc = service.calculate_lot_status(test_db, lot)

        assert calc.new_status == LotStatus.NEEDS_ATTENTION
        assert "return" in calc.reason.lower()

    def test_resolved_return_recalculates_normally(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """Once return_response_note is filled the hold is lifted and the lot
        recalculates normally (all passing -> UNDER_REVIEW)."""
        lot = _lot_with_all_passing(
            test_db,
            sample_product_with_specs,
            ref="260101-803",
            status=LotStatus.NEEDS_ATTENTION,
        )
        lot.return_reason = "Wrong lot number on COC"
        lot.return_response_note = "Data entry mistake, corrected"
        test_db.commit()

        service = LotService()
        calc = service.calculate_lot_status(test_db, lot)

        assert calc.new_status == LotStatus.UNDER_REVIEW


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

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
    Product,
    ProductTestSpecification,
    User,
)
from app.models.enums import UserRole

_ENDPOINT_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_EndpointSession = sessionmaker(
    autocommit=False, autoflush=False, bind=_ENDPOINT_ENGINE
)


def _override_get_db():
    db = _EndpointSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def api_db():
    """Function-scoped DB bound to the shared StaticPool engine."""
    Base.metadata.create_all(bind=_ENDPOINT_ENGINE)
    db = _EndpointSession()
    yield db
    db.close()
    Base.metadata.drop_all(bind=_ENDPOINT_ENGINE)


def _make_client(user):
    app.dependency_overrides[get_db] = _override_get_db

    async def _override_current_user():
        return user

    app.dependency_overrides[get_current_user] = _override_current_user
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _make_user(api_db, username, role):
    user = User(
        username=username,
        email=f"{username}@example.com",
        role=role,
        active=True,
        full_name="Test User",
        title="QC Manager",
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
def api_product_with_specs(api_db):
    """A product with four required passing-able specs, on the shared engine."""
    product = Product(
        brand="Test Brand",
        product_name="Test Product",
        flavor="Vanilla",
        size="20 serving",
        display_name="Test Brand Test Product - Vanilla (20 serving)",
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


def _api_lot_all_passing(api_db, product, ref, status, omit_test=None):
    lot = Lot(
        lot_number="RFR-" + ref,
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
        if omit_test and r.test_type == omit_test:
            continue
        api_db.add(r)
    api_db.commit()
    api_db.refresh(lot)
    return lot


@pytest.fixture
def awaiting_release_lot(api_db, api_product_with_specs):
    return _api_lot_all_passing(
        api_db, api_product_with_specs, "260201-801", LotStatus.AWAITING_RELEASE
    )


class TestReturnForReviewEndpoint:
    def test_return_for_review_endpoint(self, api_db, qc_user, awaiting_release_lot):
        client = _make_client(qc_user)
        resp = client.post(
            f"/api/v1/lots/{awaiting_release_lot.id}/return-for-review",
            json={"reason": "COC lot number mismatch"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "needs_attention"
        assert body["return_reason"] == "COC lot number mismatch"
        assert body["return_response_note"] is None

    def test_return_requires_reason(self, api_db, qc_user, awaiting_release_lot):
        client = _make_client(qc_user)
        resp = client.post(
            f"/api/v1/lots/{awaiting_release_lot.id}/return-for-review",
            json={"reason": "   "},
        )
        assert resp.status_code == 400

    def test_return_requires_awaiting_release(
        self, api_db, qc_user, api_product_with_specs
    ):
        lot = _api_lot_all_passing(
            api_db, api_product_with_specs, "260201-802", LotStatus.UNDER_REVIEW
        )
        client = _make_client(qc_user)
        resp = client.post(
            f"/api/v1/lots/{lot.id}/return-for-review",
            json={"reason": "Wrong COC"},
        )
        assert resp.status_code == 400

    def test_return_forbidden_for_lab_tech(
        self, api_db, labtech_user, awaiting_release_lot
    ):
        client = _make_client(labtech_user)
        resp = client.post(
            f"/api/v1/lots/{awaiting_release_lot.id}/return-for-review",
            json={"reason": "Wrong COC"},
        )
        assert resp.status_code == 403

    def test_return_creates_audit_entry(self, api_db, qc_user, awaiting_release_lot):
        client = _make_client(qc_user)
        resp = client.post(
            f"/api/v1/lots/{awaiting_release_lot.id}/return-for-review",
            json={"reason": "COC lot number mismatch"},
        )
        assert resp.status_code == 200, resp.text

        entries = (
            api_db.query(AuditLog)
            .filter(
                AuditLog.table_name == "lots",
                AuditLog.record_id == awaiting_release_lot.id,
            )
            .all()
        )
        assert any(e.reason and "COC lot number mismatch" in e.reason for e in entries)

    def test_submit_returned_lot_requires_response_note(
        self, api_db, qc_user, api_product_with_specs
    ):
        lot = _api_lot_all_passing(
            api_db, api_product_with_specs, "260201-803", LotStatus.NEEDS_ATTENTION
        )
        lot.return_reason = "Wrong lot number on COC"
        lot.return_response_note = None
        api_db.commit()

        client = _make_client(qc_user)

        # No body -> 400
        resp = client.post(f"/api/v1/lots/{lot.id}/submit-for-review")
        assert resp.status_code == 400, resp.text

        # With a response note -> 200, promoted to awaiting_release
        resp = client.post(
            f"/api/v1/lots/{lot.id}/submit-for-review",
            json={"return_response_note": "Data entry mistake; corrected"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "awaiting_release"
        assert body["return_response_note"] == "Data entry mistake; corrected"

    def test_submit_returned_lot_with_note_but_missing_test_keeps_hold(
        self, api_db, qc_user, api_product_with_specs
    ):
        """If a returned lot still can't reach UNDER_REVIEW (missing required
        test), submitting WITH a note must 400 without persisting the note or
        releasing the return hold."""
        lot = _api_lot_all_passing(
            api_db,
            api_product_with_specs,
            "260201-806",
            LotStatus.NEEDS_ATTENTION,
            omit_test="Protein",  # required test missing
        )
        lot.return_reason = "Wrong lot number on COC"
        lot.return_response_note = None
        api_db.commit()

        client = _make_client(qc_user)
        resp = client.post(
            f"/api/v1/lots/{lot.id}/submit-for-review",
            json={"return_response_note": "fixed"},
        )
        assert resp.status_code == 400, resp.text

        # The note must NOT have leaked to the DB and the hold stays intact
        api_db.expire_all()
        api_db.refresh(lot)
        assert lot.return_response_note is None
        assert lot.status == LotStatus.NEEDS_ATTENTION

    def test_submit_normal_lot_unaffected(
        self, api_db, qc_user, api_product_with_specs
    ):
        lot = _api_lot_all_passing(
            api_db, api_product_with_specs, "260201-804", LotStatus.UNDER_REVIEW
        )
        client = _make_client(qc_user)
        # No body, no return -> regression: still works
        resp = client.post(f"/api/v1/lots/{lot.id}/submit-for-review")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "awaiting_release"

    def test_re_return_clears_previous_response_note(
        self, api_db, qc_user, api_product_with_specs
    ):
        lot = _api_lot_all_passing(
            api_db, api_product_with_specs, "260201-805", LotStatus.AWAITING_RELEASE
        )
        lot.return_reason = "First issue"
        lot.return_response_note = "Resolved the first issue"
        api_db.commit()

        client = _make_client(qc_user)
        resp = client.post(
            f"/api/v1/lots/{lot.id}/return-for-review",
            json={"reason": "Second issue"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["return_reason"] == "Second issue"
        assert body["return_response_note"] is None
