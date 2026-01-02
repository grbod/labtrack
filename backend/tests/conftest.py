"""Pytest configuration and fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date

from app.database import Base
from app.models import Product, Lot, User, TestResult, LotProduct, LabTestType, ProductTestSpecification
from app.models.enums import UserRole, LotType, LotStatus, TestResultStatus


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
    from app.services.user_service import UserService
    
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


@pytest.fixture
def sample_lab_test_types(test_db):
    """Create sample lab test types."""
    test_types = [
        LabTestType(
            test_name="Total Plate Count",
            test_category="Microbiological",
            default_unit="CFU/g",
            test_method="AOAC 990.12",
            abbreviations='["TPC", "Aerobic Plate Count", "APC"]',
            is_active=True
        ),
        LabTestType(
            test_name="E. coli",
            test_category="Microbiological",
            default_unit="Positive/Negative",
            test_method="AOAC 991.14",
            abbreviations='["E.coli", "Escherichia coli"]',
            is_active=True
        ),
        LabTestType(
            test_name="Lead",
            test_category="Heavy Metals",
            default_unit="ppm",
            test_method="USP <2232>",
            abbreviations='["Pb", "Lead (Pb)"]',
            is_active=True
        ),
        LabTestType(
            test_name="Arsenic",
            test_category="Heavy Metals",
            default_unit="ppm",
            test_method="USP <2232>",
            abbreviations='["As", "Arsenic (As)"]',
            is_active=True
        ),
        LabTestType(
            test_name="Protein",
            test_category="Nutritional",
            default_unit="g/100g",
            test_method="AOAC 992.15",
            abbreviations='["Crude Protein", "Total Protein"]',
            is_active=True
        ),
        LabTestType(
            test_name="Gluten",
            test_category="Allergens",
            default_unit="ppm",
            test_method="ELISA",
            abbreviations='["Gluten-Free Test"]',
            is_active=True
        )
    ]
    
    for test_type in test_types:
        test_db.add(test_type)
    
    test_db.commit()
    return test_types


@pytest.fixture
def sample_product_with_specs(test_db, sample_product, sample_lab_test_types):
    """Create a product with test specifications."""
    # Add test specifications to the product
    specifications = [
        ProductTestSpecification(
            product_id=sample_product.id,
            lab_test_type_id=sample_lab_test_types[0].id,  # Total Plate Count
            specification="< 10000",
            is_required=True,
            notes="Critical microbiological test"
        ),
        ProductTestSpecification(
            product_id=sample_product.id,
            lab_test_type_id=sample_lab_test_types[1].id,  # E. coli
            specification="Negative",
            is_required=True,
            notes="Must be negative for release"
        ),
        ProductTestSpecification(
            product_id=sample_product.id,
            lab_test_type_id=sample_lab_test_types[2].id,  # Lead
            specification="< 0.5",
            is_required=True,
            min_value="0",
            max_value="0.5"
        ),
        ProductTestSpecification(
            product_id=sample_product.id,
            lab_test_type_id=sample_lab_test_types[3].id,  # Arsenic
            specification="< 0.2",
            is_required=False,  # Optional test
            min_value="0",
            max_value="0.2"
        ),
        ProductTestSpecification(
            product_id=sample_product.id,
            lab_test_type_id=sample_lab_test_types[4].id,  # Protein
            specification="20-25",
            is_required=True,
            min_value="20",
            max_value="25",
            notes="Protein content range"
        )
    ]
    
    for spec in specifications:
        test_db.add(spec)
    
    test_db.commit()
    test_db.refresh(sample_product)
    
    return sample_product


@pytest.fixture
def sample_test_specifications(test_db, sample_product_with_specs):
    """Return the test specifications from sample_product_with_specs."""
    return sample_product_with_specs.test_specifications
