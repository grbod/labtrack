"""Pytest configuration and fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date

from src.database import Base
from src.models import Product, Lot, User, TestResult, LotProduct
from src.models.enums import UserRole, LotType, LotStatus, TestResultStatus


@pytest.fixture(scope="function")
def test_db():
    """Create a test database session."""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_product(test_db):
    """Create a sample product."""
    product = Product(
        brand="Test Brand",
        product_name="Test Product",
        flavor="Vanilla",
        size="20 serving",
        display_name="Test Brand Test Product - Vanilla (20 serving)",
    )
    test_db.add(product)
    test_db.commit()
    return product


@pytest.fixture
def sample_lot(test_db, sample_product):
    """Create a sample lot."""
    lot = Lot(
        lot_number="TEST123",
        lot_type=LotType.STANDARD,
        reference_number="241101-001",
        mfg_date=date(2024, 11, 1),
        exp_date=date(2027, 11, 1),
        status=LotStatus.PENDING,
        generate_coa=True,
    )
    test_db.add(lot)
    test_db.commit()

    # Link product to lot
    lot_product = LotProduct(lot_id=lot.id, product_id=sample_product.id)
    test_db.add(lot_product)
    test_db.commit()

    return lot


@pytest.fixture
def sample_user(test_db):
    """Create a sample user."""
    from src.services.user_service import UserService
    
    service = UserService()
    user = service.create_user(
        test_db,
        username="testuser",
        email="test@example.com",
        password="testpass123",
        role=UserRole.QC_MANAGER,
    )
    return user


@pytest.fixture
def sample_test_results(test_db, sample_lot):
    """Create sample test results."""
    test_results = [
        TestResult(
            lot_id=sample_lot.id,
            test_type="Total Plate Count",
            result_value="< 10",
            unit="CFU/g",
            test_date=date(2024, 11, 5),
            confidence_score=0.95,
            status=TestResultStatus.APPROVED,
        ),
        TestResult(
            lot_id=sample_lot.id,
            test_type="E. Coli",
            result_value="Negative",
            unit="",
            test_date=date(2024, 11, 5),
            confidence_score=0.98,
            status=TestResultStatus.APPROVED,
        ),
        TestResult(
            lot_id=sample_lot.id,
            test_type="Lead",
            result_value="0.05",
            unit="ppm",
            test_date=date(2024, 11, 5),
            confidence_score=0.90,
            status=TestResultStatus.DRAFT,
        ),
    ]

    for result in test_results:
        test_db.add(result)

    test_db.commit()
    return test_results
