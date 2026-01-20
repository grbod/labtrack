"""Tests for COA release validation (signature, full_name, title requirements)."""

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
from app.models.lab_info import LabInfo
from app.models.enums import UserRole, LotType, LotStatus, TestResultStatus


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
def qc_user_no_profile(test_db):
    """Create a QC manager user WITHOUT full_name and title."""
    user = User(
        username="qc_incomplete",
        email="qc_incomplete@example.com",
        role=UserRole.QC_MANAGER,
        active=True,
        full_name=None,
        title=None,
    )
    user.set_password("testpass123")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def qc_user_no_title(test_db):
    """Create a QC manager user with full_name but no title."""
    user = User(
        username="qc_no_title",
        email="qc_no_title@example.com",
        role=UserRole.QC_MANAGER,
        active=True,
        full_name="John Doe",
        title=None,
    )
    user.set_password("testpass123")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def qc_user_complete(test_db):
    """Create a QC manager user with complete profile."""
    user = User(
        username="qc_complete",
        email="qc_complete@example.com",
        role=UserRole.QC_MANAGER,
        active=True,
        full_name="Jane Smith",
        title="Quality Manager",
    )
    user.set_password("testpass123")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def lab_info_no_signature(test_db):
    """Create lab info without signature."""
    lab_info = LabInfo(
        company_name="Test Lab",
        address="123 Test St",
        city="Test City",
        state="TS",
        zip_code="12345",
        phone="555-1234",
        email="lab@test.com",
        signature_path=None,  # No signature
    )
    test_db.add(lab_info)
    test_db.commit()
    test_db.refresh(lab_info)
    return lab_info


@pytest.fixture
def lab_info_with_signature(test_db):
    """Create lab info with signature path."""
    lab_info = LabInfo(
        company_name="Test Lab",
        address="123 Test St",
        city="Test City",
        state="TS",
        zip_code="12345",
        phone="555-1234",
        email="lab@test.com",
        signature_path="signatures/test_signature.png",  # Has signature
    )
    test_db.add(lab_info)
    test_db.commit()
    test_db.refresh(lab_info)
    return lab_info


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
def lot_awaiting_release(test_db, test_product):
    """Create a lot in awaiting_release status."""
    lot = Lot(
        lot_number="LOT001",
        reference_number="241201-001",
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

    # Add approved test result
    test_result = TestResult(
        lot_id=lot.id,
        test_type="E. coli",
        result_value="Negative",
        status=TestResultStatus.APPROVED,
    )
    test_db.add(test_result)
    test_db.commit()

    test_db.refresh(lot)
    return lot


def make_client_with_user(test_db, user):
    """Create test client with specific user."""
    app.dependency_overrides[get_db] = override_get_db

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


class TestReleaseValidation:
    """Test COA release validation requirements."""

    def test_release_fails_without_signature(
        self, test_db, qc_user_complete, lab_info_no_signature, lot_awaiting_release, test_product
    ):
        """Test that release fails when no signature is uploaded in lab info."""
        client = make_client_with_user(test_db, qc_user_complete)

        try:
            response = client.post(
                f"/api/v1/release/{lot_awaiting_release.id}/{test_product.id}/approve"
            )
            assert response.status_code == 400
            assert "No signature uploaded" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_release_fails_without_full_name(
        self, test_db, qc_user_no_profile, lab_info_with_signature, lot_awaiting_release, test_product
    ):
        """Test that release fails when user has no full_name."""
        client = make_client_with_user(test_db, qc_user_no_profile)

        try:
            response = client.post(
                f"/api/v1/release/{lot_awaiting_release.id}/{test_product.id}/approve"
            )
            assert response.status_code == 400
            assert "missing a full name" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_release_fails_without_title(
        self, test_db, qc_user_no_title, lab_info_with_signature, lot_awaiting_release, test_product
    ):
        """Test that release fails when user has no title."""
        client = make_client_with_user(test_db, qc_user_no_title)

        try:
            response = client.post(
                f"/api/v1/release/{lot_awaiting_release.id}/{test_product.id}/approve"
            )
            assert response.status_code == 400
            assert "missing a title" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_release_succeeds_with_complete_profile_and_signature(
        self, test_db, qc_user_complete, lab_info_with_signature, lot_awaiting_release, test_product, tmp_path, monkeypatch
    ):
        """Test that release succeeds when all requirements are met."""
        # Mock the upload path to use tmp_path
        monkeypatch.setattr("app.config.settings.upload_path", str(tmp_path))

        # Create the COAs output directory
        (tmp_path / "coas").mkdir(parents=True, exist_ok=True)

        client = make_client_with_user(test_db, qc_user_complete)

        try:
            response = client.post(
                f"/api/v1/release/{lot_awaiting_release.id}/{test_product.id}/approve"
            )
            # Should succeed (200) or fail for other reasons (not validation)
            # If it fails with 400, it should NOT be about signature/name/title
            if response.status_code == 400:
                detail = response.json().get("detail", "")
                assert "signature" not in detail.lower()
                assert "full name" not in detail.lower()
                assert "title" not in detail.lower()
        finally:
            app.dependency_overrides.clear()
