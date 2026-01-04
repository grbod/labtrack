"""Tests for lot with specs endpoint and status recalculation."""

import pytest
from datetime import date

from app.models import Lot, LotProduct, TestResult
from app.models.enums import LotType, LotStatus, TestResultStatus
from app.services.lot_service import LotService


class TestLotService:
    """Test LotService methods."""

    def test_recalculate_lot_status_awaiting_results(
        self, test_db, sample_product_with_specs
    ):
        """Test status calculation when no results exist."""
        # Create lot with product but no test results
        lot = Lot(
            lot_number="TEST001",
            lot_type=LotType.STANDARD,
            reference_number="250101-001",
            status=LotStatus.AWAITING_RESULTS,
            generate_coa=True,
        )
        test_db.add(lot)
        test_db.commit()

        # Link product to lot
        lot_product = LotProduct(lot_id=lot.id, product_id=sample_product_with_specs.id)
        test_db.add(lot_product)
        test_db.commit()

        # Recalculate status
        service = LotService()
        updated_lot = service.recalculate_lot_status(test_db, lot.id)

        # Should remain awaiting_results with no test results
        assert updated_lot.status == LotStatus.AWAITING_RESULTS

    def test_recalculate_lot_status_partial_results(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """Test status calculation with partial results."""
        # Create lot
        lot = Lot(
            lot_number="TEST002",
            lot_type=LotType.STANDARD,
            reference_number="250101-002",
            status=LotStatus.AWAITING_RESULTS,
            generate_coa=True,
        )
        test_db.add(lot)
        test_db.commit()

        # Link product to lot
        lot_product = LotProduct(lot_id=lot.id, product_id=sample_product_with_specs.id)
        test_db.add(lot_product)
        test_db.commit()

        # Add partial test results (only 2 of 5 specs)
        test_results = [
            TestResult(
                lot_id=lot.id,
                test_type="Total Plate Count",
                result_value="< 1000",
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
        ]
        for tr in test_results:
            test_db.add(tr)
        test_db.commit()

        # Recalculate status
        service = LotService()
        updated_lot = service.recalculate_lot_status(test_db, lot.id)

        # Should be partial_results
        assert updated_lot.status == LotStatus.PARTIAL_RESULTS

    def test_recalculate_lot_status_under_review(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """Test status calculation when all required results exist."""
        # Create lot
        lot = Lot(
            lot_number="TEST003",
            lot_type=LotType.STANDARD,
            reference_number="250101-003",
            status=LotStatus.AWAITING_RESULTS,
            generate_coa=True,
        )
        test_db.add(lot)
        test_db.commit()

        # Link product to lot
        lot_product = LotProduct(lot_id=lot.id, product_id=sample_product_with_specs.id)
        test_db.add(lot_product)
        test_db.commit()

        # Add all required test results (4 required specs)
        test_results = [
            TestResult(
                lot_id=lot.id,
                test_type="Total Plate Count",
                result_value="< 1000",
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
        for tr in test_results:
            test_db.add(tr)
        test_db.commit()

        # Recalculate status
        service = LotService()
        updated_lot = service.recalculate_lot_status(test_db, lot.id)

        # Should be under_review (all required results)
        assert updated_lot.status == LotStatus.UNDER_REVIEW

    def test_recalculate_status_does_not_change_approved(
        self, test_db, sample_product_with_specs
    ):
        """Test that approved status is not changed."""
        # Create approved lot
        lot = Lot(
            lot_number="TEST004",
            lot_type=LotType.STANDARD,
            reference_number="250101-004",
            status=LotStatus.APPROVED,
            generate_coa=True,
        )
        test_db.add(lot)
        test_db.commit()

        # Link product to lot
        lot_product = LotProduct(lot_id=lot.id, product_id=sample_product_with_specs.id)
        test_db.add(lot_product)
        test_db.commit()

        # Recalculate status
        service = LotService()
        updated_lot = service.recalculate_lot_status(test_db, lot.id)

        # Should remain approved
        assert updated_lot.status == LotStatus.APPROVED

    def test_recalculate_status_does_not_change_released(
        self, test_db, sample_product_with_specs
    ):
        """Test that released status is not changed."""
        # Create released lot
        lot = Lot(
            lot_number="TEST005",
            lot_type=LotType.STANDARD,
            reference_number="250101-005",
            status=LotStatus.RELEASED,
            generate_coa=True,
        )
        test_db.add(lot)
        test_db.commit()

        # Link product to lot
        lot_product = LotProduct(lot_id=lot.id, product_id=sample_product_with_specs.id)
        test_db.add(lot_product)
        test_db.commit()

        # Recalculate status
        service = LotService()
        updated_lot = service.recalculate_lot_status(test_db, lot.id)

        # Should remain released
        assert updated_lot.status == LotStatus.RELEASED

    def test_recalculate_status_does_not_change_rejected(
        self, test_db, sample_product_with_specs
    ):
        """Test that rejected status is not changed."""
        # Create rejected lot
        lot = Lot(
            lot_number="TEST006",
            lot_type=LotType.STANDARD,
            reference_number="250101-006",
            status=LotStatus.REJECTED,
            rejection_reason="Test rejection",
            generate_coa=True,
        )
        test_db.add(lot)
        test_db.commit()

        # Link product to lot
        lot_product = LotProduct(lot_id=lot.id, product_id=sample_product_with_specs.id)
        test_db.add(lot_product)
        test_db.commit()

        # Recalculate status
        service = LotService()
        updated_lot = service.recalculate_lot_status(test_db, lot.id)

        # Should remain rejected
        assert updated_lot.status == LotStatus.REJECTED


class TestLotWithSpecs:
    """Test lot with specs functionality."""

    def test_get_lot_with_product_specs(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """Test getting lot with product specifications."""
        # Create lot with product
        lot = Lot(
            lot_number="SPEC001",
            lot_type=LotType.STANDARD,
            reference_number="250101-007",
            status=LotStatus.AWAITING_RESULTS,
            generate_coa=True,
        )
        test_db.add(lot)
        test_db.commit()

        # Link product to lot
        lot_product = LotProduct(lot_id=lot.id, product_id=sample_product_with_specs.id)
        test_db.add(lot_product)
        test_db.commit()

        # Refresh to get relationships
        test_db.refresh(lot)

        # Verify lot products
        assert len(lot.lot_products) == 1
        assert lot.lot_products[0].product.id == sample_product_with_specs.id

        # Verify product has test specifications
        product = lot.lot_products[0].product
        assert len(product.test_specifications) == 5

        # Verify spec details
        spec_names = [s.lab_test_type.test_name for s in product.test_specifications]
        assert "Total Plate Count" in spec_names
        assert "E. coli" in spec_names
        assert "Lead" in spec_names
        assert "Arsenic" in spec_names
        assert "Protein" in spec_names

    def test_multi_product_lot_specs(
        self, test_db, sample_lab_test_types
    ):
        """Test lot with multiple products having specs."""
        from app.models import Product, ProductTestSpecification

        # Create two products
        product1 = Product(
            brand="Brand A",
            product_name="Product A",
            display_name="Brand A Product A",
        )
        product2 = Product(
            brand="Brand B",
            product_name="Product B",
            display_name="Brand B Product B",
        )
        test_db.add_all([product1, product2])
        test_db.commit()

        # Add different specs to each product
        specs = [
            ProductTestSpecification(
                product_id=product1.id,
                lab_test_type_id=sample_lab_test_types[0].id,  # TPC
                specification="< 1000",
                is_required=True,
            ),
            ProductTestSpecification(
                product_id=product2.id,
                lab_test_type_id=sample_lab_test_types[2].id,  # Lead
                specification="< 0.5",
                is_required=True,
            ),
        ]
        test_db.add_all(specs)
        test_db.commit()

        # Create multi-SKU lot
        lot = Lot(
            lot_number="MULTI001",
            lot_type=LotType.MULTI_SKU_COMPOSITE,
            reference_number="250101-008",
            status=LotStatus.AWAITING_RESULTS,
            generate_coa=True,
        )
        test_db.add(lot)
        test_db.commit()

        # Link both products
        lot_product1 = LotProduct(lot_id=lot.id, product_id=product1.id, percentage=60)
        lot_product2 = LotProduct(lot_id=lot.id, product_id=product2.id, percentage=40)
        test_db.add_all([lot_product1, lot_product2])
        test_db.commit()

        # Refresh and verify
        test_db.refresh(lot)

        assert len(lot.lot_products) == 2
        assert lot.lot_type == LotType.MULTI_SKU_COMPOSITE

        # Each product should have its own specs
        for lp in lot.lot_products:
            assert len(lp.product.test_specifications) >= 1
