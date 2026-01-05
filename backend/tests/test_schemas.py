"""Schema validation tests for Pydantic models."""

import pytest
from datetime import datetime, date
from pydantic import ValidationError

from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductSizeCreate,
    TestSpecificationCreate,
)
from app.schemas.lot import (
    LotCreate,
    LotUpdate,
    SublotCreate,
    LotStatusUpdate,
)
from app.schemas.test_result import (
    TestResultCreate,
    TestResultUpdate,
)
from app.schemas.lab_test_type import (
    LabTestTypeCreate,
    LabTestTypeUpdate,
)
from app.schemas.auth import (
    UserCreate,
    UserUpdate,
    Token,
)


# =============================================================================
# PRODUCT SCHEMA TESTS
# =============================================================================

class TestProductSchemas:
    """Test product schema validation."""

    def test_product_create_valid(self):
        """Test valid product creation."""
        data = {
            "brand": "Test Brand",
            "product_name": "Test Product",
            "display_name": "Test Brand Test Product",
            "flavor": "Vanilla",
            "expiry_duration_months": 24
        }
        product = ProductCreate(**data)
        assert product.brand == "Test Brand"
        assert product.expiry_duration_months == 24

    def test_product_create_missing_required(self):
        """Test product creation with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ProductCreate(brand="Test")  # Missing product_name and display_name

        errors = exc_info.value.errors()
        assert len(errors) >= 2  # At least product_name and display_name

    def test_product_create_empty_brand(self):
        """Test product creation with empty brand."""
        with pytest.raises(ValidationError):
            ProductCreate(
                brand="",  # Empty string invalid
                product_name="Test",
                display_name="Test"
            )

    def test_product_create_brand_too_long(self):
        """Test product creation with brand exceeding max length."""
        with pytest.raises(ValidationError):
            ProductCreate(
                brand="x" * 101,  # Max is 100
                product_name="Test",
                display_name="Test"
            )

    def test_product_create_negative_expiry(self):
        """Test product creation with negative expiry duration."""
        with pytest.raises(ValidationError):
            ProductCreate(
                brand="Test",
                product_name="Test",
                display_name="Test",
                expiry_duration_months=0  # Must be > 0
            )

    def test_product_update_partial(self):
        """Test partial product update."""
        update = ProductUpdate(brand="Updated Brand")
        assert update.brand == "Updated Brand"
        assert update.product_name is None

    def test_product_update_all_optional(self):
        """Test product update with no fields."""
        update = ProductUpdate()
        assert update.brand is None
        assert update.product_name is None

    def test_product_size_create(self):
        """Test product size creation."""
        size = ProductSizeCreate(size="2lb")
        assert size.size == "2lb"

    def test_product_size_empty(self):
        """Test product size with empty string."""
        with pytest.raises(ValidationError):
            ProductSizeCreate(size="")

    def test_test_spec_create(self):
        """Test specification creation."""
        spec = TestSpecificationCreate(
            lab_test_type_id=1,
            specification="< 10 CFU/g",
            is_required=True
        )
        assert spec.specification == "< 10 CFU/g"
        assert spec.is_required is True


# =============================================================================
# LOT SCHEMA TESTS
# =============================================================================

class TestLotSchemas:
    """Test lot schema validation."""

    def test_lot_create_valid(self):
        """Test valid lot creation."""
        data = {
            "lot_number": "LOT001",
            "lot_type": "standard",
            "mfg_date": "2024-01-01",
            "exp_date": "2027-01-01",
        }
        lot = LotCreate(**data)
        assert lot.lot_number == "LOT001"
        assert lot.lot_type == "standard"

    def test_lot_create_missing_lot_number(self):
        """Test lot creation without lot number."""
        with pytest.raises(ValidationError):
            LotCreate(
                lot_type="standard",
            )

    def test_lot_create_with_products(self):
        """Test lot creation with products field."""
        lot = LotCreate(
            lot_number="LOT001",
            lot_type="standard",
        )
        # products field may be optional
        assert lot.lot_number == "LOT001"

    def test_lot_update_partial(self):
        """Test partial lot update."""
        update = LotUpdate(generate_coa=False)
        assert update.generate_coa is False
        assert update.lot_number is None

    def test_sublot_create(self):
        """Test sublot creation."""
        sublot = SublotCreate(
            sublot_number="SUB001",
            quantity_lbs=500.0
        )
        assert sublot.sublot_number == "SUB001"
        assert sublot.quantity_lbs == 500.0

    def test_sublot_negative_quantity(self):
        """Test sublot with negative quantity."""
        with pytest.raises(ValidationError):
            SublotCreate(
                sublot_number="SUB001",
                quantity_lbs=-100.0
            )

    def test_lot_status_update(self):
        """Test lot status update."""
        update = LotStatusUpdate(status="under_review")
        assert update.status == "under_review"

    def test_lot_status_update_with_reason(self):
        """Test lot status update with rejection reason."""
        update = LotStatusUpdate(
            status="rejected",
            rejection_reason="Failed quality check"
        )
        assert update.rejection_reason == "Failed quality check"


# =============================================================================
# TEST RESULT SCHEMA TESTS
# =============================================================================

class TestTestResultSchemas:
    """Test test result schema validation."""

    def test_test_result_create(self):
        """Test valid test result creation."""
        result = TestResultCreate(
            lot_id=1,
            test_type="Total Plate Count",
            result_value="< 10",
            unit="CFU/g"
        )
        assert result.test_type == "Total Plate Count"
        assert result.result_value == "< 10"

    def test_test_result_create_with_date(self):
        """Test test result with test date."""
        result = TestResultCreate(
            lot_id=1,
            test_type="E. coli",
            result_value="Negative",
            unit="",
            test_date="2024-01-15"
        )
        # test_date is converted to date object
        assert result.test_date is not None

    def test_test_result_update(self):
        """Test test result update."""
        update = TestResultUpdate(
            result_value="< 5",
            notes="Retest performed"
        )
        assert update.result_value == "< 5"
        assert update.notes == "Retest performed"


# =============================================================================
# LAB TEST TYPE SCHEMA TESTS
# =============================================================================

class TestLabTestTypeSchemas:
    """Test lab test type schema validation."""

    def test_lab_test_type_create(self):
        """Test valid lab test type creation."""
        lab_type = LabTestTypeCreate(
            test_name="Lead",
            test_category="Heavy Metals",
            default_unit="ppm"
        )
        assert lab_type.test_name == "Lead"
        assert lab_type.test_category == "Heavy Metals"

    def test_lab_test_type_with_abbreviations(self):
        """Test lab test type with abbreviations."""
        lab_type = LabTestTypeCreate(
            test_name="Total Plate Count",
            abbreviations="TPC,APC",  # Comma-separated string
            test_category="Microbiological",
            default_unit="CFU/g"
        )
        assert "TPC" in lab_type.abbreviations

    def test_lab_test_type_update(self):
        """Test lab test type update."""
        update = LabTestTypeUpdate(
            default_specification="< 10,000 CFU/g"
        )
        assert update.default_specification == "< 10,000 CFU/g"


# =============================================================================
# AUTH SCHEMA TESTS
# =============================================================================

class TestAuthSchemas:
    """Test authentication schema validation."""

    def test_user_create(self):
        """Test valid user creation."""
        user = UserCreate(
            username="newuser",
            email="new@example.com",
            password="securepass123",
            role="lab_tech"
        )
        assert user.username == "newuser"
        assert user.email == "new@example.com"

    def test_user_create_invalid_email(self):
        """Test user creation with invalid email."""
        with pytest.raises(ValidationError):
            UserCreate(
                username="testuser",
                email="invalid-email",
                password="pass123",
                role="lab_tech"
            )

    def test_user_create_short_password(self):
        """Test user creation with short password."""
        with pytest.raises(ValidationError):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="123",  # Too short
                role="lab_tech"
            )

    def test_user_update(self):
        """Test user update."""
        update = UserUpdate(
            email="updated@example.com",
            is_active=False
        )
        assert update.email == "updated@example.com"
        assert update.is_active is False

    def test_token_schema(self):
        """Test token schema."""
        token = Token(
            access_token="abc123",
            refresh_token="refresh123",
            token_type="bearer"
        )
        assert token.access_token == "abc123"
        assert token.token_type == "bearer"
