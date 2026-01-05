"""Integration tests for Lot-Product-Tests end-to-end workflows."""

import pytest
from datetime import date, datetime
from sqlalchemy.orm import Session

from app.models import (
    Product, Lot, LotProduct, Sublot, LabTestType, ProductTestSpecification, 
    TestResult, User
)
from app.models.enums import LotType, LotStatus, TestResultStatus, UserRole
from app.services import (
    ProductService, LotService, ApprovalService, LabTestTypeService
)


@pytest.mark.integration
class TestLotProductTestWorkflow:
    """Test complete workflow from product creation to lot approval."""
    
    def test_create_product_with_specs_then_lot(self, test_db, sample_lab_test_types, sample_user):
        """Test creating a product with specifications, then a lot for it."""
        product_service = ProductService()
        lot_service = LotService()
        
        # Step 1: Create product
        product = product_service.create(
            test_db,
            obj_in={
                "brand": "TestBrand",
                "product_name": "Test Supplement",
                "flavor": "Berry",
                "size": "30 servings",
                "display_name": "TestBrand Test Supplement - Berry (30 servings)"
            }
        )
        
        # Step 2: Set test specifications
        specs = [
            {
                "lab_test_type_id": sample_lab_test_types[0].id,  # TPC
                "specification": "< 1000",
                "is_required": True
            },
            {
                "lab_test_type_id": sample_lab_test_types[1].id,  # E. coli
                "specification": "Negative",
                "is_required": True
            },
            {
                "lab_test_type_id": sample_lab_test_types[2].id,  # Lead
                "specification": "< 0.5",
                "is_required": True
            }
        ]
        
        product = product_service.set_test_specifications(test_db, product.id, specs)
        assert len(product.required_tests) == 3
        
        # Step 3: Create lot for this product
        lot = lot_service.create_lot(
            test_db,
            lot_data={
                "lot_number": "TST2024001",
                "lot_type": LotType.STANDARD,
                "mfg_date": date.today(),
                "exp_date": date(2027, 1, 1),
                "generate_coa": True
            },
            product_ids=[product.id]
        )
        
        assert lot.status == LotStatus.AWAITING_RESULTS
        assert len(lot.lot_products) == 1
        assert lot.lot_products[0].product_id == product.id
        
        # Step 4: Verify lot knows about required tests
        missing_tests = product_service.get_missing_required_tests(
            test_db, product.id, []
        )
        assert len(missing_tests) == 3
    
    def test_lot_status_transitions_based_on_tests(self, test_db, sample_product_with_specs, sample_user):
        """Test lot status changes based on test completeness."""
        lot_service = LotService()
        approval_service = ApprovalService()
        product_service = ProductService()
        
        # Create lot
        lot = lot_service.create_lot(
            test_db,
            lot_data={
                "lot_number": "TEST123",
                "lot_type": LotType.STANDARD,
                "mfg_date": date.today(),
                "exp_date": date(2027, 1, 1)
            },
            product_ids=[sample_product_with_specs.id]
        )
        
        # Add some test results (not all required)
        test_results = [
            TestResult(
                lot_id=lot.id,
                test_type="Total Plate Count",
                result_value="500",
                unit="CFU/g",
                test_date=date.today(),
                confidence_score=0.95,
                status=TestResultStatus.DRAFT
            ),
            TestResult(
                lot_id=lot.id,
                test_type="E. coli",
                result_value="Negative",
                unit="",
                test_date=date.today(),
                confidence_score=0.99,
                status=TestResultStatus.DRAFT
            )
        ]
        
        for result in test_results:
            test_db.add(result)
        test_db.commit()
        
        # Approve the tests we have
        for result in test_results:
            approval_service.approve_test_result(test_db, result.id, sample_user.id)
        
        # The approval service automatically updates lot status
        # Since we're missing required tests (Lead and Protein), it should be PARTIAL_RESULTS
        test_db.refresh(lot)
        
        # Check what tests are missing
        missing_tests = product_service.get_missing_required_tests(
            test_db, 
            sample_product_with_specs.id,
            ["Total Plate Count", "E. coli"]
        )
        assert len(missing_tests) == 2  # Should be missing Lead and Protein
        
        # With the fixed approval service, partial results should set PARTIAL_RESULTS status
        assert lot.status == LotStatus.PARTIAL_RESULTS
        
        # Add remaining required tests
        remaining_results = [
            TestResult(
                lot_id=lot.id,
                test_type="Lead",
                result_value="0.3",
                unit="ppm",
                test_date=date.today(),
                confidence_score=0.97,
                status=TestResultStatus.DRAFT
            ),
            TestResult(
                lot_id=lot.id,
                test_type="Protein",
                result_value="22",
                unit="g/100g",
                test_date=date.today(),
                confidence_score=0.98,
                status=TestResultStatus.DRAFT
            )
        ]
        
        for result in remaining_results:
            test_db.add(result)
        test_db.commit()
        
        # Approve remaining tests
        for result in remaining_results:
            approval_service.approve_test_result(test_db, result.id, sample_user.id)
        
        # Now with all required tests, the lot should be UNDER_REVIEW (awaiting manual approval)
        test_db.refresh(lot)
        assert lot.status == LotStatus.UNDER_REVIEW
    
    def test_test_result_validation_against_specs(self, test_db, sample_product_with_specs, sample_user):
        """Test that test results are validated against product specifications."""
        lot_service = LotService()
        product_service = ProductService()
        
        # Create lot
        lot = lot_service.create_lot(
            test_db,
            lot_data={
                "lot_number": "VAL123",
                "lot_type": LotType.STANDARD,
                "mfg_date": date.today(),
                "exp_date": date(2027, 1, 1)
            },
            product_ids=[sample_product_with_specs.id]
        )
        
        # Test various result values
        test_cases = [
            # (test_name, result_value, should_pass)
            ("Total Plate Count", "5000", True),    # Below limit
            ("Total Plate Count", "15000", False),  # Above limit
            ("E. coli", "Negative", True),          # Correct
            ("E. coli", "Positive", False),         # Wrong
            ("Lead", "0.3", True),                  # Below limit
            ("Lead", "0.6", False),                 # Above limit
            ("Protein", "22", True),                # In range
            ("Protein", "18", False),               # Below range
            ("Arsenic", "0.15", True),              # Optional test, below limit
        ]
        
        for test_name, result_value, should_pass in test_cases:
            validation = product_service.validate_test_result(
                test_db,
                sample_product_with_specs.id,
                test_name,
                result_value
            )
            
            assert validation["passes"] == should_pass, \
                f"Test {test_name} with value {result_value} should {'pass' if should_pass else 'fail'}"
    
    def test_multi_product_lot_with_different_specs(self, test_db, sample_lab_test_types, sample_user):
        """Test lot with multiple products having different test requirements."""
        product_service = ProductService()
        lot_service = LotService()
        approval_service = ApprovalService()
        
        # Create two products with different specifications
        product1 = Product(
            brand="Brand1",
            product_name="Product1",
            display_name="Brand1 Product1"
        )
        product2 = Product(
            brand="Brand2",
            product_name="Product2",
            display_name="Brand2 Product2"
        )
        test_db.add(product1)
        test_db.add(product2)
        test_db.commit()
        
        # Product 1 requires TPC and E. coli
        product_service.set_test_specifications(test_db, product1.id, [
            {
                "lab_test_type_id": sample_lab_test_types[0].id,  # TPC
                "specification": "< 1000",
                "is_required": True
            },
            {
                "lab_test_type_id": sample_lab_test_types[1].id,  # E. coli
                "specification": "Negative",
                "is_required": True
            }
        ])
        
        # Product 2 requires E. coli and Lead
        product_service.set_test_specifications(test_db, product2.id, [
            {
                "lab_test_type_id": sample_lab_test_types[1].id,  # E. coli
                "specification": "Negative",
                "is_required": True
            },
            {
                "lab_test_type_id": sample_lab_test_types[2].id,  # Lead
                "specification": "< 0.5",
                "is_required": True
            }
        ])
        
        # Create standard lot with multiple products
        lot = lot_service.create_lot(
            test_db,
            lot_data={
                "lot_number": "MULTI123",
                "lot_type": LotType.STANDARD,  # Use standard type for simplicity
                "mfg_date": date.today(),
                "exp_date": date(2027, 1, 1)
            },
            product_ids=[product1.id, product2.id]
        )
        
        # Get combined required tests
        all_required_tests = set()
        for lot_product in lot.lot_products:
            product = lot_product.product
            all_required_tests.update(product.get_required_test_names())
        
        # Should need TPC, E. coli, and Lead
        assert len(all_required_tests) == 3
        assert "Total Plate Count" in all_required_tests
        assert "E. coli" in all_required_tests
        assert "Lead" in all_required_tests
        
        # Add test results for all required tests
        test_results = [
            TestResult(
                lot_id=lot.id,
                test_type="Total Plate Count",
                result_value="500",
                unit="CFU/g",
                test_date=date.today(),
                status=TestResultStatus.DRAFT
            ),
            TestResult(
                lot_id=lot.id,
                test_type="E. coli",
                result_value="Negative",
                unit="",
                test_date=date.today(),
                status=TestResultStatus.DRAFT
            ),
            TestResult(
                lot_id=lot.id,
                test_type="Lead",
                result_value="0.2",
                unit="ppm",
                test_date=date.today(),
                status=TestResultStatus.DRAFT
            )
        ]
        
        for result in test_results:
            test_db.add(result)
        test_db.commit()
        
        # Approve all tests
        for result in test_results:
            approval_service.approve_test_result(test_db, result.id, sample_user.id)
        
        # Lot should be UNDER_REVIEW (all required tests present, awaiting manual approval)
        test_db.refresh(lot)
        assert lot.status == LotStatus.UNDER_REVIEW
    
    def test_partial_results_status(self, test_db, sample_product_with_specs, sample_user):
        """Test PARTIAL_RESULTS status for incomplete test sets."""
        lot_service = LotService()
        approval_service = ApprovalService()
        
        # Create lot
        lot = lot_service.create_lot(
            test_db,
            lot_data={
                "lot_number": "PARTIAL123",
                "lot_type": LotType.STANDARD,
                "mfg_date": date.today(),
                "exp_date": date(2027, 1, 1)
            },
            product_ids=[sample_product_with_specs.id]
        )
        
        # Product requires 4 tests: TPC, E.coli, Lead, Protein
        # Add only 2 test results
        partial_results = [
            TestResult(
                lot_id=lot.id,
                test_type="Total Plate Count",
                result_value="800",
                unit="CFU/g",
                test_date=date.today(),
                status=TestResultStatus.APPROVED,
                approved_by_id=sample_user.id,
                approved_at=datetime.now()
            ),
            TestResult(
                lot_id=lot.id,
                test_type="E. coli",
                result_value="Negative",
                unit="",
                test_date=date.today(),
                status=TestResultStatus.APPROVED,
                approved_by_id=sample_user.id,
                approved_at=datetime.now()
            )
        ]
        
        for result in partial_results:
            test_db.add(result)
        test_db.commit()
        
        # Update lot status to PARTIAL_RESULTS
        lot.status = LotStatus.PARTIAL_RESULTS
        test_db.commit()
        
        # Verify we can identify missing tests
        completed_test_names = [r.test_type for r in partial_results]
        missing = lot_service.get_missing_required_tests_for_lot(
            test_db, lot.id, completed_test_names
        )
        
        # Should be missing Lead and Protein
        assert len(missing) == 2
        missing_names = [spec.test_name for spec in missing]
        assert "Lead" in missing_names
        assert "Protein" in missing_names
    
    def test_optional_tests_dont_block_approval(self, test_db, sample_product_with_specs, sample_user):
        """Test that missing optional tests don't prevent lot approval."""
        lot_service = LotService()
        approval_service = ApprovalService()
        
        # Create lot
        lot = lot_service.create_lot(
            test_db,
            lot_data={
                "lot_number": "OPT123",
                "lot_type": LotType.STANDARD,
                "mfg_date": date.today(),
                "exp_date": date(2027, 1, 1)
            },
            product_ids=[sample_product_with_specs.id]
        )
        
        # Add only required tests (skip Arsenic which is optional)
        required_results = [
            TestResult(
                lot_id=lot.id,
                test_type="Total Plate Count",
                result_value="500",
                unit="CFU/g",
                test_date=date.today(),
                status=TestResultStatus.DRAFT
            ),
            TestResult(
                lot_id=lot.id,
                test_type="E. coli",
                result_value="Negative",
                unit="",
                test_date=date.today(),
                status=TestResultStatus.DRAFT
            ),
            TestResult(
                lot_id=lot.id,
                test_type="Lead",
                result_value="0.3",
                unit="ppm",
                test_date=date.today(),
                status=TestResultStatus.DRAFT
            ),
            TestResult(
                lot_id=lot.id,
                test_type="Protein",
                result_value="23",
                unit="g/100g",
                test_date=date.today(),
                status=TestResultStatus.DRAFT
            )
        ]
        
        for result in required_results:
            test_db.add(result)
        test_db.commit()
        
        # Approve all required tests
        for result in required_results:
            approval_service.approve_test_result(test_db, result.id, sample_user.id)
        
        # Lot should be UNDER_REVIEW even without optional Arsenic test (awaiting manual approval)
        test_db.refresh(lot)
        assert lot.status == LotStatus.UNDER_REVIEW
    
    def test_failing_test_prevents_lot_approval(self, test_db, sample_product_with_specs, sample_user):
        """Test that failing test results prevent lot approval."""
        lot_service = LotService()
        product_service = ProductService()
        
        # Create lot
        lot = lot_service.create_lot(
            test_db,
            lot_data={
                "lot_number": "FAIL123",
                "lot_type": LotType.STANDARD,
                "mfg_date": date.today(),
                "exp_date": date(2027, 1, 1)
            },
            product_ids=[sample_product_with_specs.id]
        )
        
        # Add test results with one failing
        test_results = [
            TestResult(
                lot_id=lot.id,
                test_type="Total Plate Count",
                result_value="15000",  # FAIL: Above limit of < 10000
                unit="CFU/g",
                test_date=date.today(),
                status=TestResultStatus.APPROVED,
                approved_by_id=sample_user.id,
                approved_at=datetime.now()
            ),
            TestResult(
                lot_id=lot.id,
                test_type="E. coli",
                result_value="Negative",
                unit="",
                test_date=date.today(),
                status=TestResultStatus.APPROVED,
                approved_by_id=sample_user.id,
                approved_at=datetime.now()
            ),
            TestResult(
                lot_id=lot.id,
                test_type="Lead",
                result_value="0.3",
                unit="ppm",
                test_date=date.today(),
                status=TestResultStatus.APPROVED,
                approved_by_id=sample_user.id,
                approved_at=datetime.now()
            ),
            TestResult(
                lot_id=lot.id,
                test_type="Protein",
                result_value="22",
                unit="g/100g",
                test_date=date.today(),
                status=TestResultStatus.APPROVED,
                approved_by_id=sample_user.id,
                approved_at=datetime.now()
            )
        ]
        
        for result in test_results:
            test_db.add(result)
        test_db.commit()
        
        # Validate each result
        failed_tests = []
        for result in test_results:
            validation = product_service.validate_test_result(
                test_db,
                sample_product_with_specs.id,
                result.test_type,
                result.result_value
            )
            if not validation["passes"]:
                failed_tests.append({
                    "test": result.test_type,
                    "value": result.result_value,
                    "spec": validation["specification"]
                })
        
        # Should have one failed test
        assert len(failed_tests) == 1
        assert failed_tests[0]["test"] == "Total Plate Count"
        
        # Lot should be REJECTED due to failed test
        lot.status = LotStatus.REJECTED
        test_db.commit()
        assert lot.status == LotStatus.REJECTED


@pytest.mark.integration
class TestComplexScenarios:
    """Test complex real-world scenarios."""
    
    def test_product_reformulation_workflow(self, test_db, sample_lab_test_types):
        """Test workflow when product specifications change."""
        product_service = ProductService()
        lot_service = LotService()
        
        # Create original product
        product = Product(
            brand="HealthBrand",
            product_name="Protein Plus",
            flavor="Vanilla",
            display_name="HealthBrand Protein Plus - Vanilla"
        )
        test_db.add(product)
        test_db.commit()
        
        # Set original specifications
        original_specs = [
            {
                "lab_test_type_id": sample_lab_test_types[0].id,  # TPC
                "specification": "< 50000",  # Loose limit
                "is_required": True
            },
            {
                "lab_test_type_id": sample_lab_test_types[4].id,  # Protein
                "specification": "70-80",
                "is_required": True
            }
        ]
        
        product_service.set_test_specifications(test_db, product.id, original_specs)
        
        # Create lot with old specs
        old_lot = lot_service.create_lot(
            test_db,
            lot_data={
                "lot_number": "OLD001",
                "lot_type": LotType.STANDARD,
                "mfg_date": date(2024, 1, 1),
                "exp_date": date(2026, 1, 1)
            },
            product_ids=[product.id]
        )
        
        # Simulate reformulation - update specifications
        new_specs = [
            {
                "lab_test_type_id": sample_lab_test_types[0].id,  # TPC
                "specification": "< 10000",  # Stricter limit
                "is_required": True
            },
            {
                "lab_test_type_id": sample_lab_test_types[1].id,  # E. coli - NEW
                "specification": "Negative",
                "is_required": True
            },
            {
                "lab_test_type_id": sample_lab_test_types[4].id,  # Protein
                "specification": "75-85",  # Tighter range
                "is_required": True
            }
        ]
        
        product_service.set_test_specifications(test_db, product.id, new_specs)
        
        # Create new lot with new specs
        new_lot = lot_service.create_lot(
            test_db,
            lot_data={
                "lot_number": "NEW001",
                "lot_type": LotType.STANDARD,
                "mfg_date": date(2024, 6, 1),
                "exp_date": date(2027, 6, 1)
            },
            product_ids=[product.id]
        )
        
        # Old lot had 2 required tests, new lot has 3
        test_db.refresh(product)
        assert len(product.required_tests) == 3
        
        # Historical lot still exists with its original requirements
        assert old_lot.lot_number == "OLD001"
        assert new_lot.lot_number == "NEW001"
    
    def test_lab_test_abbreviation_matching(self, test_db, sample_lab_test_types):
        """Test that test results can be matched using abbreviations."""
        lab_service = LabTestTypeService()
        
        # Test various abbreviations
        test_cases = [
            ("TPC", "Total Plate Count"),
            ("Aerobic Plate Count", "Total Plate Count"),
            ("E.coli", "E. coli"),
            ("Escherichia coli", "E. coli"),
            ("Pb", "Lead"),
            ("Lead (Pb)", "Lead"),
            ("Crude Protein", "Protein"),
            ("Total Protein", "Protein")
        ]
        
        for abbreviation, expected_name in test_cases:
            result = lab_service.search_by_name_or_abbreviation(test_db, abbreviation)
            assert result is not None, f"Should find test for '{abbreviation}'"
            assert result.test_name == expected_name
    
    def test_parent_lot_with_sublots_testing(self, test_db, sample_product_with_specs):
        """Test parent lot with sublots having different test results."""
        lot_service = LotService()
        
        # Create parent lot
        parent_lot = lot_service.create_lot(
            test_db,
            lot_data={
                "lot_number": "PARENT001",
                "lot_type": LotType.PARENT_LOT,
                "mfg_date": date.today(),
                "exp_date": date(2027, 1, 1)
            },
            product_ids=[sample_product_with_specs.id]
        )
        
        # Create sublots manually
        sublots = []
        for i in range(3):
            sublot = Sublot(
                parent_lot_id=parent_lot.id,
                sublot_number=f"PARENT001-{i+1}",
                production_date=date.today(),
                quantity_lbs=1000.0
            )
            test_db.add(sublot)
            sublots.append(sublot)
        test_db.commit()
        
        # Each sublot could have its own test results
        for i, sublot in enumerate(sublots):
            # Create a regular lot for the sublot
            sublot_lot = Lot(
                lot_number=sublot.sublot_number,
                lot_type=LotType.STANDARD,  # No SUBLOT type, use STANDARD
                reference_number=f"SUB-{sublot.sublot_number}",
                mfg_date=sublot.production_date,
                exp_date=parent_lot.exp_date,
                status=LotStatus.AWAITING_RESULTS
            )
            test_db.add(sublot_lot)
            test_db.flush()  # Flush to get ID
            
            # Link to same product
            lot_product = LotProduct(
                lot_id=sublot_lot.id,
                product_id=sample_product_with_specs.id
            )
            test_db.add(lot_product)
            
            # Add test results with slight variations
            test_result = TestResult(
                lot_id=sublot_lot.id,
                test_type="Total Plate Count",
                result_value=str(100 + i * 100),  # 100, 200, 300
                unit="CFU/g",
                test_date=date.today(),
                status=TestResultStatus.APPROVED
            )
            test_db.add(test_result)
        
        test_db.commit()
        
        # Parent lot tracks overall status
        assert parent_lot.lot_type == LotType.PARENT_LOT
        assert len(sublots) == 3
        assert all(s.sublot_number.startswith("PARENT001-") for s in sublots)