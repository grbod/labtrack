"""Tests for COA approval audit logging.

Verifies that:
1. approve_release_by_lot_product creates audit entries with APPROVE action
2. Lot audit trail includes coa_releases entries
3. Lot status change to RELEASED creates an audit entry
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base
from app.dependencies import get_db, get_current_user
from app.models import User, Product, Lot, LotProduct, TestResult
from app.models.audit import AuditLog
from app.models.coa_release import COARelease
from app.models.enums import (
    UserRole, LotType, LotStatus, TestResultStatus,
    AuditAction, COAReleaseStatus
)
from app.core.security import create_access_token


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_db():
    """Create test database tables."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def qc_manager_user(test_db):
    """Create a QC Manager user with signature for release."""
    user = User(
        username="qcmanager",
        email="qc@example.com",
        role=UserRole.QC_MANAGER,
        active=True,
        full_name="QC Manager",
        title="Quality Control Manager",
        signature_path="signatures/test_signature.png"
    )
    user.set_password("testpass123")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_product(test_db):
    """Create a test product."""
    product = Product(
        brand="Test Brand",
        product_name="Test Product",
        flavor="Vanilla",
        display_name="Test Brand Test Product - Vanilla",
        expiry_duration_months=24
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def awaiting_release_lot(test_db, test_product):
    """Create a lot in awaiting_release status with approved test results."""
    lot = Lot(
        lot_number="TESTLOT001",
        reference_number="260124-001",
        lot_type=LotType.STANDARD,
        status=LotStatus.AWAITING_RELEASE,
        mfg_date=date.today(),
        exp_date=date(2027, 12, 31)
    )
    test_db.add(lot)
    test_db.commit()

    # Link to product
    lot_product = LotProduct(lot_id=lot.id, product_id=test_product.id)
    test_db.add(lot_product)
    test_db.commit()

    # Add approved test results
    test_result = TestResult(
        lot_id=lot.id,
        test_type="E. Coli",
        result_value="Negative",
        unit="",
        test_date=date.today(),
        status=TestResultStatus.APPROVED,
    )
    test_db.add(test_result)
    test_db.commit()

    test_db.refresh(lot)
    return lot


@pytest.fixture
def client(test_db, qc_manager_user):
    """Create test client with QC Manager user."""
    app.dependency_overrides[get_db] = override_get_db

    async def override_get_current_user():
        return qc_manager_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# =============================================================================
# COA APPROVAL AUDIT TESTS
# =============================================================================

class TestCOAApprovalAudit:
    """Test audit logging for COA approval."""

    def test_approve_release_creates_audit_entry(
        self, client, test_db, awaiting_release_lot, test_product
    ):
        """Test that approving a COA release creates an audit entry with APPROVE action."""
        lot_id = awaiting_release_lot.id
        product_id = test_product.id

        # Approve the release
        response = client.post(
            f"/api/v1/release/{lot_id}/{product_id}/approve",
            json={}
        )
        assert response.status_code == 200

        # Check audit log for coa_releases entry with APPROVE action
        audit_entry = (
            test_db.query(AuditLog)
            .filter(
                AuditLog.table_name == "coa_releases",
                AuditLog.action == AuditAction.APPROVE
            )
            .first()
        )

        assert audit_entry is not None, "No APPROVE audit entry found for coa_releases"
        assert audit_entry.action == AuditAction.APPROVE

        # Verify new_values contains only the released status
        new_values = audit_entry.get_new_values_dict()
        assert new_values.get("status") == "released"

    def test_approve_release_creates_lot_audit_when_all_products_released(
        self, client, test_db, awaiting_release_lot, test_product
    ):
        """Test that approving the last product creates a lot status change audit."""
        lot_id = awaiting_release_lot.id
        product_id = test_product.id

        # Approve the release (this lot has only one product)
        response = client.post(
            f"/api/v1/release/{lot_id}/{product_id}/approve",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["all_products_released"] is True

        # Check audit log for lots entry with APPROVE action
        lot_audit_entry = (
            test_db.query(AuditLog)
            .filter(
                AuditLog.table_name == "lots",
                AuditLog.record_id == lot_id,
                AuditLog.action == AuditAction.APPROVE
            )
            .first()
        )

        assert lot_audit_entry is not None, "No APPROVE audit entry found for lot status change"

        # Verify the status change
        old_values = lot_audit_entry.get_old_values_dict()
        new_values = lot_audit_entry.get_new_values_dict()
        assert old_values.get("status") == "awaiting_release"
        assert new_values.get("status") == "released"

    def test_audit_entry_has_correct_reason(
        self, client, test_db, awaiting_release_lot, test_product
    ):
        """Test that audit entries have descriptive reason text."""
        lot_id = awaiting_release_lot.id
        product_id = test_product.id

        response = client.post(
            f"/api/v1/release/{lot_id}/{product_id}/approve",
            json={}
        )
        assert response.status_code == 200

        # Check coa_releases audit entry reason
        coa_audit = (
            test_db.query(AuditLog)
            .filter(
                AuditLog.table_name == "coa_releases",
                AuditLog.action == AuditAction.APPROVE
            )
            .first()
        )
        assert coa_audit is not None
        assert "COA released for" in coa_audit.reason
        assert test_product.product_name in coa_audit.reason

        # Check lot audit entry reason
        lot_audit = (
            test_db.query(AuditLog)
            .filter(
                AuditLog.table_name == "lots",
                AuditLog.action == AuditAction.APPROVE
            )
            .first()
        )
        assert lot_audit is not None
        assert "All products released" in lot_audit.reason


class TestAuditTrailAggregation:
    """Test that lot audit trail includes coa_releases entries."""

    def test_lot_audit_trail_includes_coa_releases(
        self, client, test_db, awaiting_release_lot, test_product
    ):
        """Test that viewing a lot's audit trail includes COA release entries."""
        lot_id = awaiting_release_lot.id
        product_id = test_product.id

        # First approve the release to create audit entries
        response = client.post(
            f"/api/v1/release/{lot_id}/{product_id}/approve",
            json={}
        )
        assert response.status_code == 200

        # Now get the lot's audit trail
        response = client.get(f"/api/v1/audit/lots/{lot_id}/trail")
        assert response.status_code == 200
        data = response.json()

        # Check that there are entries
        assert data["total"] > 0
        entries = data["entries"]

        # Find the COA release approval entry (should have "COA Release" prefix)
        coa_entries = [
            e for e in entries
            if any(c["field"].startswith("COA Release") for c in e.get("changes", []))
        ]

        # Should have at least one COA Release entry
        assert len(coa_entries) >= 1, "No COA Release entries found in lot audit trail"

        # Verify the entry has APPROVE action
        approve_entries = [e for e in entries if e["action"] == "approve"]
        assert len(approve_entries) >= 1, "No APPROVE action entries in audit trail"


class TestAuditTrailDisplay:
    """Test audit trail display formatting."""

    def test_approve_action_displays_correctly(
        self, client, test_db, awaiting_release_lot, test_product
    ):
        """Test that APPROVE action displays as 'Approved' in the trail."""
        lot_id = awaiting_release_lot.id
        product_id = test_product.id

        # Approve the release
        response = client.post(
            f"/api/v1/release/{lot_id}/{product_id}/approve",
            json={}
        )
        assert response.status_code == 200

        # Get audit trail
        response = client.get(f"/api/v1/audit/lots/{lot_id}/trail")
        assert response.status_code == 200
        data = response.json()

        # Find approve entries
        approve_entries = [
            e for e in data["entries"]
            if e["action"] == "approve"
        ]

        assert len(approve_entries) >= 1

        # Check action_display is "Approved"
        for entry in approve_entries:
            assert entry["action_display"] == "Approved"
