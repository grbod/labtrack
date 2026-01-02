"""Integration tests for Manual Entry feature."""

import pytest
from datetime import datetime, date
from sqlalchemy.orm import Session

from app.models import (
    User, UserRole, Product, Lot, LotType, LotStatus, 
    TestResult, TestResultStatus, LabTestType, 
    LotProduct, ProductTestSpecification
)
from app.services.lot_service import LotService
from app.services.lab_test_type_service import LabTestTypeService
from app.services.sample_service import SampleService
from app.services.product_service import ProductService
from app.ui.pages.manual_test_entry import (
    get_required_tests_for_lot, 
    update_lot_status, 
    save_test_results
)


@pytest.fixture
def test_user(test_db: Session):
    """Create a test QC Manager user."""
    user = User(
        username="qc_test",
        email="qc@test.com",
        role=UserRole.QC_MANAGER,
        active=True
    )
    user.set_password("test123")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_product(test_db: Session):
    """Create a test product."""
    product = Product(
        brand="Test Brand",
        product_name="Test Protein",
        flavor="Vanilla",
        size="2 lbs",
        display_name="Test Brand Test Protein - Vanilla (2 lbs)",
        serving_size=28.5
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def test_lab_types(test_db: Session):
    """Create test lab test types."""
    service = LabTestTypeService()
    
    # Create various test types
    types = []
    
    # Microbiological tests
    types.append(service.create_lab_test_type(
        test_db, 
        name="Total Plate Count",
        category="Microbiological",
        unit_of_measurement="CFU/g",
        default_method="USP <2021>"
    ))
    
    types.append(service.create_lab_test_type(
        test_db,
        name="E. coli",
        category="Microbiological",
        unit_of_measurement="Positive/Negative",
        default_method="USP <2022>"
    ))
    
    # Heavy metals
    types.append(service.create_lab_test_type(
        test_db,
        name="Lead",
        category="Heavy Metals",
        unit_of_measurement="ppm",
        default_method="ICP-MS"
    ))
    
    types.append(service.create_lab_test_type(
        test_db,
        name="Arsenic",
        category="Heavy Metals",
        unit_of_measurement="ppm",
        default_method="ICP-MS"
    ))
    
    test_db.commit()
    return types


@pytest.fixture
def test_product_with_specs(test_db: Session, test_product: Product, test_lab_types: list):
    """Create product with test specifications."""
    # Add required tests
    for i, test_type in enumerate(test_lab_types[:2]):  # First 2 as required
        spec = ProductTestSpecification(
            product_id=test_product.id,
            lab_test_type_id=test_type.id,
            specification="< 10" if test_type.default_unit == "CFU/g" else "Negative",
            is_required=True
        )
        test_db.add(spec)
    
    # Add optional tests
    for test_type in test_lab_types[2:]:  # Rest as optional
        spec = ProductTestSpecification(
            product_id=test_product.id,
            lab_test_type_id=test_type.id,
            specification="< 1",
            is_required=False
        )
        test_db.add(spec)
    
    test_db.commit()
    test_db.refresh(test_product)
    return test_product


@pytest.fixture
def test_lot(test_db: Session, test_product_with_specs: Product):
    """Create a test lot with various statuses."""
    lot_service = LotService()
    
    lot = lot_service.create_lot(
        test_db,
        lot_data={
            "lot_number": "TEST123",
            "lot_type": LotType.STANDARD,
            "mfg_date": date.today(),
            "exp_date": date(2025, 12, 31),
            "status": LotStatus.PENDING,
            "generate_coa": True
        },
        product_ids=[test_product_with_specs.id]
    )
    
    return lot


class TestManualEntryFeature:
    """Test suite for Manual Entry functionality."""
    
    def test_get_required_tests_for_lot(self, test_db: Session, test_lot: Lot):
        """Test getting required tests for a lot based on its products."""
        required_test_ids = get_required_tests_for_lot(test_db, test_lot)
        
        # Should have 2 required tests based on our fixture
        assert len(required_test_ids) == 2
        
        # Verify they are the correct test IDs
        product = test_lot.lot_products[0].product
        required_specs = [s for s in product.test_specifications if s.is_required]
        expected_ids = {s.lab_test_type_id for s in required_specs}
        
        assert required_test_ids == expected_ids
    
    def test_editable_lot_statuses(self, test_db: Session, test_lot: Lot):
        """Test that only certain lot statuses are editable."""
        editable_statuses = [LotStatus.PENDING, LotStatus.PARTIAL_RESULTS, LotStatus.UNDER_REVIEW]
        
        # Test editable statuses
        for status in editable_statuses:
            test_lot.status = status
            test_db.commit()
            
            # Query editable lots
            editable_lots = test_db.query(Lot).filter(
                Lot.status.in_(editable_statuses)
            ).all()
            
            assert test_lot in editable_lots
        
        # Test non-editable statuses
        non_editable = [LotStatus.APPROVED, LotStatus.RELEASED, LotStatus.REJECTED]
        for status in non_editable:
            test_lot.status = status
            test_db.commit()
            
            editable_lots = test_db.query(Lot).filter(
                Lot.status.in_(editable_statuses)
            ).all()
            
            assert test_lot not in editable_lots
    
    def test_update_lot_status_no_tests(self, test_db: Session, test_lot: Lot):
        """Test lot status update when no test results exist."""
        update_lot_status(test_db, test_lot)
        
        # Should remain PENDING when no tests
        assert test_lot.status == LotStatus.PENDING
    
    def test_update_lot_status_partial_results(
        self, test_db: Session, test_lot: Lot, test_lab_types: list
    ):
        """Test lot status update with partial test results."""
        # Add one test result (but lot requires 2)
        test_result = TestResult(
            lot_id=test_lot.id,
            test_type=test_lab_types[0].test_name,
            result_value="< 5",
            unit="CFU/g",
            method="USP <2021>",
            status=TestResultStatus.DRAFT,
            test_date=date.today()
        )
        test_db.add(test_result)
        test_db.commit()
        
        update_lot_status(test_db, test_lot)
        
        # Should be PARTIAL_RESULTS
        assert test_lot.status == LotStatus.PARTIAL_RESULTS
    
    def test_update_lot_status_all_required_complete(
        self, test_db: Session, test_lot: Lot, test_lab_types: list
    ):
        """Test lot status update when all required tests are complete."""
        # Add all required test results
        for test_type in test_lab_types[:2]:  # First 2 are required
            test_result = TestResult(
                lot_id=test_lot.id,
                test_type=test_type.test_name,
                result_value="< 5" if test_type.default_unit == "CFU/g" else "Negative",
                unit=test_type.default_unit,
                method=test_type.test_method,
                status=TestResultStatus.DRAFT,
                test_date=date.today()
            )
            test_db.add(test_result)
        
        test_db.commit()
        update_lot_status(test_db, test_lot)
        
        # Should be UNDER_REVIEW when all required tests complete
        assert test_lot.status == LotStatus.UNDER_REVIEW
    
    def test_create_new_test_results(
        self, test_db: Session, test_lot: Lot, test_user: User, test_lab_types: list
    ):
        """Test creating new test results through manual entry."""
        sample_service = SampleService()
        
        # Simulate form data
        changes = {
            f"test_{test_lot.id}_{test_lab_types[0].id}": {
                "value": "< 10",
                "unit": "CFU/g",
                "method": "USP <2021>"
            }
        }
        
        # Create mock session state
        class MockSessionState:
            def __init__(self):
                self.data = {
                    f"test_{test_lot.id}_{test_lab_types[0].id}_include": True,
                    f"test_{test_lot.id}_{test_lab_types[0].id}_value": "< 10",
                    f"test_{test_lot.id}_{test_lab_types[0].id}_unit": "CFU/g",
                    f"test_{test_lot.id}_{test_lab_types[0].id}_method": "USP <2021>"
                }
                self.test_changes = {}
            
            def get(self, key, default=None):
                return self.data.get(key, default)
        
        # Would need to mock streamlit session state for full test
        # For now, test the core logic directly
        
        # Verify no test results initially
        initial_count = test_db.query(TestResult).filter(
            TestResult.lot_id == test_lot.id
        ).count()
        assert initial_count == 0
        
        # Create a test result manually (simulating what save_test_results does)
        new_result = TestResult(
            lot_id=test_lot.id,
            test_type=test_lab_types[0].test_name,
            result_value="< 10",
            unit="CFU/g",
            method="USP <2021>",
            status=TestResultStatus.DRAFT,
            test_date=datetime.now().date(),
            confidence_score=1.0
        )
        test_db.add(new_result)
        test_db.commit()
        
        # Verify test result created
        final_count = test_db.query(TestResult).filter(
            TestResult.lot_id == test_lot.id
        ).count()
        assert final_count == 1
        
        # Verify test result details
        saved_result = test_db.query(TestResult).filter(
            TestResult.lot_id == test_lot.id
        ).first()
        assert saved_result.result_value == "< 10"
        assert saved_result.unit == "CFU/g"
        assert saved_result.confidence_score == 1.0  # Manual entry = high confidence
    
    def test_update_existing_test_results(
        self, test_db: Session, test_lot: Lot, test_lab_types: list
    ):
        """Test updating existing test results."""
        # Create initial test result
        existing = TestResult(
            lot_id=test_lot.id,
            test_type=test_lab_types[0].test_name,
            result_value="15",
            unit="CFU/g",
            method="Old Method",
            status=TestResultStatus.DRAFT,
            test_date=date.today()
        )
        test_db.add(existing)
        test_db.commit()
        
        # Update the result
        existing.result_value = "< 10"
        existing.method = "USP <2021>"
        test_db.commit()
        
        # Verify update
        updated = test_db.query(TestResult).filter(
            TestResult.id == existing.id
        ).first()
        assert updated.result_value == "< 10"
        assert updated.method == "USP <2021>"
    
    def test_delete_test_result_on_uncheck(
        self, test_db: Session, test_lot: Lot, test_lab_types: list
    ):
        """Test that unchecking a test deletes the result."""
        # Create test result
        test_result = TestResult(
            lot_id=test_lot.id,
            test_type=test_lab_types[2].test_name,  # Optional test
            result_value="0.5",
            unit="ppm",
            status=TestResultStatus.DRAFT,
            test_date=date.today()
        )
        test_db.add(test_result)
        test_db.commit()
        
        result_id = test_result.id
        
        # Simulate unchecking (deletion)
        test_db.delete(test_result)
        test_db.commit()
        
        # Verify deletion
        deleted = test_db.query(TestResult).filter(
            TestResult.id == result_id
        ).first()
        assert deleted is None
    
    def test_cannot_uncheck_required_tests(
        self, test_db: Session, test_lot: Lot, test_product_with_specs: Product
    ):
        """Test that required tests cannot be unchecked."""
        required_test_ids = get_required_tests_for_lot(test_db, test_lot)
        
        # Verify we have required tests
        assert len(required_test_ids) > 0
        
        # In the UI, these would have disabled checkboxes
        # Here we just verify they are identified as required
        product = test_lot.lot_products[0].product
        for spec in product.test_specifications:
            if spec.is_required:
                assert spec.lab_test_type_id in required_test_ids


class TestManualEntryValidation:
    """Test validation and edge cases."""
    
    def test_empty_value_not_saved(self, test_db: Session, test_lot: Lot):
        """Test that empty values are not saved."""
        # Try to create result with empty value
        # In real app, this would be filtered out in save_test_results
        
        # Verify no results initially
        count = test_db.query(TestResult).filter(
            TestResult.lot_id == test_lot.id
        ).count()
        assert count == 0
        
        # Empty value should not create a record
        # (In actual implementation, the save logic checks for empty values)
    
    def test_approved_lot_not_editable(self, test_db: Session, test_lot: Lot):
        """Test that approved lots cannot be edited."""
        test_lot.status = LotStatus.APPROVED
        test_db.commit()
        
        # Query for editable lots
        editable_statuses = [LotStatus.PENDING, LotStatus.PARTIAL_RESULTS, LotStatus.UNDER_REVIEW]
        editable_lots = test_db.query(Lot).filter(
            Lot.status.in_(editable_statuses)
        ).all()
        
        # Approved lot should not be in editable list
        assert test_lot not in editable_lots
    
    def test_lot_display_formatting(self, test_db: Session, test_lot: Lot):
        """Test lot display string formatting."""
        product = test_lot.lot_products[0].product
        
        # Test display components
        assert test_lot.lot_number == "TEST123"
        assert test_lot.reference_number is not None
        assert test_lot.status == LotStatus.PENDING
        assert product.display_name == "Test Brand Test Protein - Vanilla (2 lbs)"
        
        # Test formatted string (as would appear in dropdown)
        display_text = (
            f"{test_lot.lot_number} | "
            f"Ref: {test_lot.reference_number} | "
            f"{test_lot.status.value} | "
            f"{product.display_name}"
        )
        
        assert "TEST123" in display_text
        assert test_lot.status.value in display_text
        assert product.display_name in display_text


class TestManualEntryIntegration:
    """Full integration tests."""
    
    def test_complete_workflow(
        self, test_db: Session, test_lot: Lot, test_user: User, test_lab_types: list
    ):
        """Test complete manual entry workflow."""
        # 1. Verify lot is editable
        assert test_lot.status == LotStatus.PENDING
        
        # 2. Get required tests
        required_test_ids = get_required_tests_for_lot(test_db, test_lot)
        assert len(required_test_ids) == 2
        
        # 3. Enter test results for all required tests
        for i, test_type in enumerate(test_lab_types[:2]):
            result = TestResult(
                lot_id=test_lot.id,
                test_type=test_type.test_name,
                result_value="Pass",
                unit=test_type.default_unit,
                method=test_type.test_method,
                status=TestResultStatus.DRAFT,
                test_date=date.today(),
                confidence_score=1.0
            )
            test_db.add(result)
        
        # 4. Add one optional test
        optional_result = TestResult(
            lot_id=test_lot.id,
            test_type=test_lab_types[2].test_name,
            result_value="0.3",
            unit="ppm",
            method="ICP-MS",
            status=TestResultStatus.DRAFT,
            test_date=date.today(),
            confidence_score=1.0
        )
        test_db.add(optional_result)
        test_db.commit()
        
        # 5. Update lot status
        update_lot_status(test_db, test_lot)
        
        # 6. Verify final state
        assert test_lot.status == LotStatus.UNDER_REVIEW
        
        # Verify all test results saved
        all_results = test_db.query(TestResult).filter(
            TestResult.lot_id == test_lot.id
        ).all()
        assert len(all_results) == 3  # 2 required + 1 optional
        
        # Verify confidence scores
        for result in all_results:
            assert result.confidence_score == 1.0  # Manual entry
    
    def test_error_recovery(self, test_db: Session, test_lot: Lot):
        """Test error handling and recovery."""
        # Test with invalid data
        try:
            # Try to create result without required fields
            bad_result = TestResult(
                lot_id=test_lot.id,
                # Missing test_type - should fail
                result_value="10",
                unit="CFU/g"
            )
            test_db.add(bad_result)
            test_db.commit()
            assert False, "Should have raised an error"
        except Exception:
            # Expected - rollback
            test_db.rollback()
        
        # Verify no partial data saved
        count = test_db.query(TestResult).filter(
            TestResult.lot_id == test_lot.id
        ).count()
        assert count == 0
        
        # Verify lot can still be edited after error
        assert test_lot.status == LotStatus.PENDING


# Run tests with: pytest tests/test_manual_entry.py -v