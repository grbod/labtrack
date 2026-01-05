"""Comprehensive unit tests for COA Management System.

This module contains 50 additional unit tests covering various gaps
in the test coverage for models, services, and business logic.
"""

import pytest
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.models import (
    Product, ProductSize, Lot, Sublot, LotProduct,
    User, TestResult, AuditLog, ParsingQueue,
    COAHistory, LabTestType, ProductTestSpecification
)
from app.models.enums import (
    UserRole, LotType, LotStatus, TestResultStatus,
    ParsingStatus, AuditAction
)
from app.services import (
    ProductService, LotService, UserService,
    ApprovalService, AuditService, LabTestTypeService
)


# =============================================================================
# PRODUCT MODEL TESTS (Tests 1-8)
# =============================================================================

class TestProductModelComprehensive:
    """Comprehensive tests for Product model."""

    # Test 1
    def test_product_brand_validation_empty_string(self, test_db):
        """Test that empty brand raises ValueError."""
        with pytest.raises(ValueError, match="brand cannot be empty"):
            Product(
                brand="   ",
                product_name="Test Product",
                display_name="Test Display"
            )

    # Test 2
    def test_product_name_validation_empty_string(self, test_db):
        """Test that empty product_name raises ValueError."""
        with pytest.raises(ValueError, match="product_name cannot be empty"):
            Product(
                brand="Test Brand",
                product_name="",
                display_name="Test Display"
            )

    # Test 3
    def test_product_display_name_validation_empty(self, test_db):
        """Test that empty display_name raises ValueError."""
        with pytest.raises(ValueError, match="display_name cannot be empty"):
            Product(
                brand="Test Brand",
                product_name="Test Product",
                display_name="   "
            )

    # Test 4
    def test_product_expiry_duration_months_validation(self, test_db):
        """Test expiry duration must be positive."""
        with pytest.raises(ValueError, match="positive"):
            Product(
                brand="Test",
                product_name="Product",
                display_name="Display",
                expiry_duration_months=0
            )

    # Test 5
    def test_product_expiry_duration_display_years_only(self, test_db):
        """Test expiry duration display for exact years."""
        product = Product(
            brand="Test",
            product_name="Product",
            display_name="Display",
            expiry_duration_months=24
        )
        assert product.expiry_duration_display == "2 years"

    # Test 6
    def test_product_expiry_duration_display_months_only(self, test_db):
        """Test expiry duration display for months only."""
        product = Product(
            brand="Test",
            product_name="Product",
            display_name="Display",
            expiry_duration_months=6
        )
        assert product.expiry_duration_display == "6 months"

    # Test 7
    def test_product_expiry_duration_display_mixed(self, test_db):
        """Test expiry duration display for years and months."""
        product = Product(
            brand="Test",
            product_name="Product",
            display_name="Display",
            expiry_duration_months=18
        )
        assert "1 year" in product.expiry_duration_display
        assert "6 months" in product.expiry_duration_display

    # Test 8
    def test_product_get_full_name(self, sample_product):
        """Test get_full_name method."""
        full_name = sample_product.get_full_name()
        assert "Test Brand" in full_name
        assert "Test Product" in full_name
        assert "Vanilla" in full_name


# =============================================================================
# PRODUCT SIZE MODEL TESTS (Tests 9-12)
# =============================================================================

class TestProductSizeModel:
    """Tests for ProductSize model."""

    # Test 9
    def test_create_product_size(self, test_db, sample_product):
        """Test creating a product size."""
        size = ProductSize(
            product_id=sample_product.id,
            size="2lb"
        )
        test_db.add(size)
        test_db.commit()

        assert size.id is not None
        assert size.size == "2lb"
        assert size.product_id == sample_product.id

    # Test 10
    def test_product_size_validation_empty(self, test_db, sample_product):
        """Test that empty size raises ValueError."""
        with pytest.raises(ValueError, match="Size cannot be empty"):
            ProductSize(
                product_id=sample_product.id,
                size="   "
            )

    # Test 11
    def test_product_multiple_sizes(self, test_db, sample_product):
        """Test product can have multiple sizes."""
        sizes = ["2lb", "5lb", "10lb"]
        for size_val in sizes:
            size = ProductSize(product_id=sample_product.id, size=size_val)
            test_db.add(size)
        test_db.commit()
        test_db.refresh(sample_product)

        assert len(sample_product.sizes) == 3

    # Test 12
    def test_product_size_unique_constraint(self, test_db, sample_product):
        """Test unique constraint on product_id + size."""
        size1 = ProductSize(product_id=sample_product.id, size="2lb")
        test_db.add(size1)
        test_db.commit()

        size2 = ProductSize(product_id=sample_product.id, size="2lb")
        test_db.add(size2)
        with pytest.raises(IntegrityError):
            test_db.commit()


# =============================================================================
# USER MODEL TESTS (Tests 13-18)
# =============================================================================

class TestUserModelComprehensive:
    """Comprehensive tests for User model."""

    # Test 13
    def test_user_username_validation_special_chars(self, test_db):
        """Test username with special characters fails."""
        with pytest.raises(ValueError, match="letters, numbers, and underscores"):
            User(
                username="test@user",
                email="test@example.com",
                role=UserRole.LAB_TECH
            )

    # Test 14
    def test_user_email_validation_invalid(self, test_db):
        """Test invalid email format fails."""
        with pytest.raises(ValueError, match="Invalid email format"):
            User(
                username="testuser",
                email="invalid-email",
                role=UserRole.LAB_TECH
            )

    # Test 15
    def test_user_is_admin_property(self, test_db):
        """Test is_admin property."""
        admin = User(username="admin", email="admin@test.com", role=UserRole.ADMIN)
        lab_tech = User(username="tech", email="tech@test.com", role=UserRole.LAB_TECH)

        assert admin.is_admin is True
        assert lab_tech.is_admin is False

    # Test 16
    def test_user_is_qc_manager_property(self, test_db):
        """Test is_qc_manager property."""
        admin = User(username="admin", email="admin@test.com", role=UserRole.ADMIN)
        qc = User(username="qc", email="qc@test.com", role=UserRole.QC_MANAGER)
        tech = User(username="tech", email="tech@test.com", role=UserRole.LAB_TECH)

        assert admin.is_qc_manager is True
        assert qc.is_qc_manager is True
        assert tech.is_qc_manager is False

    # Test 17
    def test_user_has_permission_view(self, test_db):
        """Test has_permission for view action."""
        read_only = User(username="ro", email="ro@test.com", role=UserRole.READ_ONLY, active=True)

        assert read_only.has_permission("view") is True
        assert read_only.has_permission("create") is False

    # Test 18
    def test_user_inactive_no_permissions(self, test_db):
        """Test inactive user has no permissions."""
        admin = User(username="admin", email="admin@test.com", role=UserRole.ADMIN, active=False)

        assert admin.has_permission("view") is False
        assert admin.has_permission("delete") is False


# =============================================================================
# LOT MODEL TESTS (Tests 19-26)
# =============================================================================

class TestLotModelComprehensive:
    """Comprehensive tests for Lot model."""

    # Test 19
    def test_lot_number_validation_empty(self, test_db):
        """Test empty lot number fails."""
        with pytest.raises(ValueError, match="lot_number cannot be empty"):
            Lot(
                lot_number="   ",
                reference_number="241101-001",
                lot_type=LotType.STANDARD
            )

    # Test 20
    def test_lot_reference_uppercase(self, test_db):
        """Test lot number and reference are uppercased."""
        lot = Lot(
            lot_number="abc123",
            reference_number="ref456",
            lot_type=LotType.STANDARD
        )

        assert lot.lot_number == "ABC123"
        assert lot.reference_number == "REF456"

    # Test 21
    def test_lot_is_composite_property(self, test_db):
        """Test is_composite property."""
        composite = Lot(
            lot_number="C1",
            reference_number="R1",
            lot_type=LotType.MULTI_SKU_COMPOSITE
        )
        standard = Lot(
            lot_number="S1",
            reference_number="R2",
            lot_type=LotType.STANDARD
        )

        assert composite.is_composite is True
        assert standard.is_composite is False

    # Test 22
    def test_lot_is_parent_lot_property(self, test_db):
        """Test is_parent_lot property."""
        parent = Lot(
            lot_number="P1",
            reference_number="R1",
            lot_type=LotType.PARENT_LOT
        )

        assert parent.is_parent_lot is True

    # Test 23
    def test_lot_update_status_rejection_requires_reason(self, test_db):
        """Test rejection requires a reason."""
        lot = Lot(
            lot_number="L1",
            reference_number="R1",
            lot_type=LotType.STANDARD,
            status=LotStatus.AWAITING_RESULTS
        )
        test_db.add(lot)
        test_db.commit()

        with pytest.raises(ValueError, match="Rejection reason is required"):
            lot.update_status(LotStatus.REJECTED)

    # Test 24
    def test_lot_update_status_rejection_with_reason(self, test_db):
        """Test rejection with valid reason."""
        lot = Lot(
            lot_number="L2",
            reference_number="R2",
            lot_type=LotType.STANDARD,
            status=LotStatus.AWAITING_RESULTS
        )
        test_db.add(lot)
        test_db.commit()

        lot.update_status(LotStatus.REJECTED, rejection_reason="Test failed")
        test_db.commit()

        assert lot.status == LotStatus.REJECTED
        assert lot.rejection_reason == "Test failed"

    # Test 25
    def test_lot_update_status_clears_rejection_on_resubmit(self, test_db):
        """Test rejection reason cleared when resubmitting."""
        lot = Lot(
            lot_number="L3",
            reference_number="R3",
            lot_type=LotType.STANDARD,
            status=LotStatus.REJECTED,
            rejection_reason="Previous rejection"
        )
        test_db.add(lot)
        test_db.commit()

        lot.update_status(LotStatus.AWAITING_RELEASE)
        test_db.commit()

        assert lot.status == LotStatus.AWAITING_RELEASE
        assert lot.rejection_reason is None

    # Test 26
    def test_lot_date_validation(self, test_db):
        """Test exp_date must be after mfg_date."""
        with pytest.raises(ValueError, match="Expiration date must be after"):
            Lot(
                lot_number="L4",
                reference_number="R4",
                lot_type=LotType.STANDARD,
                mfg_date=date(2025, 1, 1),
                exp_date=date(2024, 1, 1)
            )


# =============================================================================
# SUBLOT MODEL TESTS (Tests 27-29)
# =============================================================================

class TestSublotModel:
    """Tests for Sublot model."""

    # Test 27
    def test_sublot_number_validation(self, test_db, sample_lot):
        """Test sublot number validation."""
        sample_lot.lot_type = LotType.PARENT_LOT
        test_db.commit()

        with pytest.raises(ValueError, match="cannot be empty"):
            Sublot(
                parent_lot_id=sample_lot.id,
                sublot_number="   "
            )

    # Test 28
    def test_sublot_quantity_positive(self, test_db, sample_lot):
        """Test sublot quantity must be positive."""
        sample_lot.lot_type = LotType.PARENT_LOT
        test_db.commit()

        with pytest.raises(ValueError, match="positive"):
            Sublot(
                parent_lot_id=sample_lot.id,
                sublot_number="SUB001",
                quantity_lbs=Decimal("-100")
            )

    # Test 29
    def test_sublot_uppercase_number(self, test_db, sample_lot):
        """Test sublot number is uppercased."""
        sample_lot.lot_type = LotType.PARENT_LOT
        test_db.commit()

        sublot = Sublot(
            parent_lot_id=sample_lot.id,
            sublot_number="sub001"
        )

        assert sublot.sublot_number == "SUB001"


# =============================================================================
# LOT PRODUCT MODEL TESTS (Tests 30-31)
# =============================================================================

class TestLotProductModel:
    """Tests for LotProduct model."""

    # Test 30
    def test_lot_product_percentage_validation(self, test_db, sample_lot, sample_product):
        """Test percentage must be 0-100."""
        with pytest.raises(ValueError, match="between 0 and 100"):
            LotProduct(
                lot_id=sample_lot.id,
                product_id=sample_product.id,
                percentage=Decimal("150")
            )

    # Test 31
    def test_lot_product_percentage_valid(self, test_db):
        """Test valid percentage."""
        # Create a new lot and product to avoid conflicts with fixtures
        new_product = Product(
            brand="Test Brand2",
            product_name="Test Product2",
            display_name="Test Brand2 Test Product2"
        )
        test_db.add(new_product)
        test_db.commit()

        new_lot = Lot(
            lot_number="PERC001",
            reference_number="PERC001-REF",
            lot_type=LotType.STANDARD
        )
        test_db.add(new_lot)
        test_db.commit()

        lp = LotProduct(
            lot_id=new_lot.id,
            product_id=new_product.id,
            percentage=Decimal("75.5")
        )
        test_db.add(lp)
        test_db.commit()

        assert lp.percentage == Decimal("75.5")


# =============================================================================
# TEST RESULT MODEL TESTS (Tests 32-36)
# =============================================================================

class TestTestResultModelComprehensive:
    """Comprehensive tests for TestResult model."""

    # Test 32
    def test_test_result_confidence_validation(self, test_db, sample_lot):
        """Test confidence score must be 0-1."""
        with pytest.raises(ValueError, match="between 0 and 1"):
            TestResult(
                lot_id=sample_lot.id,
                test_type="Test",
                confidence_score=Decimal("1.5")
            )

    # Test 33
    def test_test_result_is_high_confidence(self, test_db, sample_lot):
        """Test is_high_confidence property."""
        high = TestResult(
            lot_id=sample_lot.id,
            test_type="Test",
            confidence_score=Decimal("0.85")
        )
        low = TestResult(
            lot_id=sample_lot.id,
            test_type="Test2",
            confidence_score=Decimal("0.5")
        )

        assert high.is_high_confidence is True
        assert low.is_high_confidence is False

    # Test 34
    def test_test_result_needs_review(self, test_db, sample_lot):
        """Test needs_review property."""
        needs_review = TestResult(
            lot_id=sample_lot.id,
            test_type="Test",
            confidence_score=Decimal("0.5"),
            status=TestResultStatus.DRAFT
        )
        no_review = TestResult(
            lot_id=sample_lot.id,
            test_type="Test2",
            confidence_score=Decimal("0.9"),
            status=TestResultStatus.DRAFT
        )

        assert needs_review.needs_review is True
        assert no_review.needs_review is False

    # Test 35
    def test_test_result_category_microbiological(self, test_db, sample_lot):
        """Test test category for microbiological tests."""
        result = TestResult(
            lot_id=sample_lot.id,
            test_type="Total Plate Count"
        )

        assert result.get_test_category() == "microbiological"

    # Test 36
    def test_test_result_category_heavy_metals(self, test_db, sample_lot):
        """Test test category for heavy metals tests."""
        result = TestResult(
            lot_id=sample_lot.id,
            test_type="Lead"
        )

        assert result.get_test_category() == "heavy_metals"


# =============================================================================
# COA HISTORY MODEL TESTS (Tests 37-39)
# =============================================================================

class TestCOAHistoryModel:
    """Tests for COAHistory model."""

    # Test 37
    def test_coa_history_format_validation(self, test_db, sample_lot):
        """Test format validation."""
        with pytest.raises(ValueError, match="Format must be one of"):
            COAHistory(
                lot_id=sample_lot.id,
                filename="test.xyz",
                format="XYZ"
            )

    # Test 38
    def test_coa_history_valid_formats(self, test_db, sample_lot):
        """Test valid formats."""
        for fmt in ["PDF", "DOCX", "HTML"]:
            coa = COAHistory(
                lot_id=sample_lot.id,
                filename=f"test.{fmt.lower()}",
                format=fmt
            )
            assert coa.format == fmt

    # Test 39
    def test_coa_history_file_size_positive(self, test_db, sample_lot):
        """Test file size must be positive."""
        with pytest.raises(ValueError, match="positive"):
            COAHistory(
                lot_id=sample_lot.id,
                filename="test.pdf",
                file_size_bytes=-100
            )


# =============================================================================
# PARSING QUEUE MODEL TESTS (Tests 40-44)
# =============================================================================

class TestParsingQueueModel:
    """Tests for ParsingQueue model."""

    # Test 40
    def test_parsing_queue_filename_validation(self, test_db):
        """Test filename must be PDF."""
        with pytest.raises(ValueError, match="must be a PDF"):
            ParsingQueue(
                pdf_filename="test.doc"
            )

    # Test 41
    def test_parsing_queue_retry_count_positive(self, test_db):
        """Test retry count cannot be negative."""
        with pytest.raises(ValueError, match="cannot be negative"):
            ParsingQueue(
                pdf_filename="test.pdf",
                retry_count=-1
            )

    # Test 42
    def test_parsing_queue_can_retry(self, test_db):
        """Test can_retry property."""
        can_retry = ParsingQueue(
            pdf_filename="test.pdf",
            status=ParsingStatus.PENDING,
            retry_count=1
        )
        cannot_retry = ParsingQueue(
            pdf_filename="test2.pdf",
            status=ParsingStatus.PENDING,
            retry_count=3
        )

        assert can_retry.can_retry is True
        assert cannot_retry.can_retry is False

    # Test 43
    def test_parsing_queue_mark_processing(self, test_db):
        """Test mark_processing method."""
        pq = ParsingQueue(pdf_filename="test.pdf", status=ParsingStatus.PENDING)
        test_db.add(pq)
        test_db.commit()

        pq.mark_processing()
        test_db.commit()

        assert pq.status == ParsingStatus.PROCESSING
        assert pq.retry_count == 1

    # Test 44
    def test_parsing_queue_extracted_data_json(self, test_db):
        """Test extracted data JSON conversion."""
        pq = ParsingQueue(pdf_filename="test.pdf")

        data = {"test": "value", "number": 123}
        pq.set_extracted_data(data)

        result = pq.get_extracted_data_dict()
        assert result["test"] == "value"
        assert result["number"] == 123


# =============================================================================
# AUDIT LOG MODEL TESTS (Tests 45-47)
# =============================================================================

class TestAuditLogModel:
    """Tests for AuditLog model."""

    # Test 45
    def test_audit_log_table_name_validation(self, test_db):
        """Test table name validation."""
        with pytest.raises(ValueError, match="cannot be empty"):
            AuditLog(
                table_name="   ",
                record_id=1,
                action=AuditAction.INSERT
            )

    # Test 46
    def test_audit_log_record_id_positive(self, test_db):
        """Test record ID must be positive."""
        with pytest.raises(ValueError, match="must be positive"):
            AuditLog(
                table_name="test",
                record_id=0,
                action=AuditAction.INSERT
            )

    # Test 47
    def test_audit_log_get_changes(self, test_db):
        """Test get_changes method."""
        audit = AuditLog(
            table_name="test",
            record_id=1,
            action=AuditAction.UPDATE,
            old_values=json.dumps({"status": "pending"}),
            new_values=json.dumps({"status": "approved"})
        )

        changes = audit.get_changes()
        assert "status" in changes
        assert changes["status"]["from"] == "pending"
        assert changes["status"]["to"] == "approved"


# =============================================================================
# LAB TEST TYPE SERVICE TESTS (Tests 48-50)
# =============================================================================

class TestLabTestTypeServiceComprehensive:
    """Comprehensive tests for LabTestTypeService."""

    # Test 48
    def test_create_lab_test_type_duplicate_name(self, test_db, sample_lab_test_types):
        """Test duplicate name prevention."""
        service = LabTestTypeService()

        with pytest.raises(ValueError, match="already exists"):
            service.create_lab_test_type(
                test_db,
                name="Total Plate Count",  # Already exists
                category=LabTestType.CATEGORY_MICROBIOLOGICAL,
                unit_of_measurement="CFU/g"
            )

    # Test 49
    def test_create_lab_test_type_invalid_category(self, test_db):
        """Test invalid category prevention."""
        service = LabTestTypeService()

        with pytest.raises(ValueError, match="Invalid category"):
            service.create_lab_test_type(
                test_db,
                name="New Test",
                category="Invalid Category",
                unit_of_measurement="units"
            )

    # Test 50
    def test_search_by_abbreviation(self, test_db, sample_lab_test_types):
        """Test search by abbreviation."""
        service = LabTestTypeService()

        # Search by abbreviation
        result = service.search_by_name_or_abbreviation(test_db, "TPC")
        assert result is not None
        assert result.test_name == "Total Plate Count"

        # Search by alternate abbreviation
        result = service.search_by_name_or_abbreviation(test_db, "APC")
        assert result is not None
        assert result.test_name == "Total Plate Count"


# =============================================================================
# ADDITIONAL SERVICE TESTS (Bonus Tests 51-55)
# =============================================================================

class TestProductServiceComprehensive:
    """Additional ProductService tests."""

    def test_validate_product_data_missing_brand(self, test_db):
        """Test validation fails without brand."""
        service = ProductService()

        with pytest.raises(ValueError, match="Brand is required"):
            service.validate_product_data({"product_name": "Test"})

    def test_validate_product_data_missing_name(self, test_db):
        """Test validation fails without product_name."""
        service = ProductService()

        with pytest.raises(ValueError, match="Product name is required"):
            service.validate_product_data({"brand": "Test"})

    def test_standardize_display_name(self, test_db):
        """Test display name standardization."""
        service = ProductService()

        name = service.standardize_display_name(
            brand="TestBrand",
            product_name="TestProduct",
            flavor="Vanilla",
            size="1lb"
        )

        assert "TestBrand" in name
        assert "TestProduct" in name
        assert "Vanilla" in name
        assert "(1lb)" in name


class TestLotServiceComprehensive:
    """Additional LotService tests."""

    def test_get_lots_by_status(self, test_db, sample_lot):
        """Test getting lots by status."""
        service = LotService()

        lots = service.get_lots_by_status(test_db, LotStatus.AWAITING_RESULTS)
        assert len(lots) >= 1

    def test_generate_reference_number_format(self, test_db):
        """Test reference number format."""
        service = LotService()

        ref = service.generate_reference_number(test_db)

        # Should be in format YYMMDD-XXX
        assert len(ref) == 10
        assert "-" in ref
        parts = ref.split("-")
        assert len(parts[0]) == 6
        assert len(parts[1]) == 3
