"""Tests for ad-hoc test binding in lot status calculation.

Ad-hoc tests are TestResult rows whose ``test_type`` is NOT among the
product's required test specs. Per spec, they are binding:
- An ad-hoc test with no result blocks progression to UNDER_REVIEW.
- An ad-hoc result failing its own ``specification`` string sends the lot
  to NEEDS_ATTENTION.
"""

from datetime import date

import pytest

from app.models import Lot, LotProduct, Product, ProductTestSpecification, TestResult
from app.models.enums import LotStatus, LotType, TestResultStatus
from app.services.lot_service import LotService


def _make_lot(test_db, product, status=LotStatus.AWAITING_RESULTS, ref="250101-900"):
    lot = Lot(
        lot_number="ADHOC-" + ref,
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
    return lot


def _passing_required_results(lot_id):
    """All required specs from sample_product_with_specs passing."""
    return [
        TestResult(
            lot_id=lot_id,
            test_type="Total Plate Count",
            result_value="500",
            unit="CFU/g",
            status=TestResultStatus.DRAFT,
        ),
        TestResult(
            lot_id=lot_id,
            test_type="E. coli",
            result_value="Negative",
            unit="Positive/Negative",
            status=TestResultStatus.DRAFT,
        ),
        TestResult(
            lot_id=lot_id,
            test_type="Lead",
            result_value="0.1",
            unit="ppm",
            status=TestResultStatus.DRAFT,
        ),
        TestResult(
            lot_id=lot_id,
            test_type="Protein",
            result_value="22",
            unit="g/100g",
            status=TestResultStatus.DRAFT,
        ),
    ]


class TestAdhocTestBinding:
    def test_adhoc_without_result_blocks_under_review(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """All required passing + ad-hoc with no result -> PARTIAL_RESULTS."""
        lot = _make_lot(test_db, sample_product_with_specs, ref="250101-901")
        results = _passing_required_results(lot.id)
        results.append(
            TestResult(
                lot_id=lot.id,
                test_type="Heavy Metals Panel",  # ad-hoc, not in required specs
                result_value=None,
                unit="ppm",
                status=TestResultStatus.DRAFT,
            )
        )
        for r in results:
            test_db.add(r)
        test_db.commit()

        service = LotService()
        calc = service.calculate_lot_status(test_db, lot)
        assert calc.new_status == LotStatus.PARTIAL_RESULTS

    def test_adhoc_failing_spec_sends_needs_attention(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """All required passing + ad-hoc result '50' spec '< 10' -> NEEDS_ATTENTION."""
        lot = _make_lot(test_db, sample_product_with_specs, ref="250101-902")
        results = _passing_required_results(lot.id)
        results.append(
            TestResult(
                lot_id=lot.id,
                test_type="Cadmium",  # ad-hoc
                result_value="50",
                unit="ppm",
                specification="< 10",
                status=TestResultStatus.DRAFT,
            )
        )
        for r in results:
            test_db.add(r)
        test_db.commit()

        service = LotService()
        calc = service.calculate_lot_status(test_db, lot)
        assert calc.new_status == LotStatus.NEEDS_ATTENTION

    def test_adhoc_passing_spec_allows_under_review(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """All required passing + ad-hoc result '5' spec '< 10' -> UNDER_REVIEW."""
        lot = _make_lot(test_db, sample_product_with_specs, ref="250101-903")
        results = _passing_required_results(lot.id)
        results.append(
            TestResult(
                lot_id=lot.id,
                test_type="Cadmium",  # ad-hoc
                result_value="5",
                unit="ppm",
                specification="< 10",
                status=TestResultStatus.DRAFT,
            )
        )
        for r in results:
            test_db.add(r)
        test_db.commit()

        service = LotService()
        calc = service.calculate_lot_status(test_db, lot)
        assert calc.new_status == LotStatus.UNDER_REVIEW

    def test_adhoc_without_spec_counts_as_passing(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """Ad-hoc with result entered but no spec -> UNDER_REVIEW."""
        lot = _make_lot(test_db, sample_product_with_specs, ref="250101-904")
        results = _passing_required_results(lot.id)
        results.append(
            TestResult(
                lot_id=lot.id,
                test_type="Appearance",  # ad-hoc, no spec
                result_value="White powder",
                unit="",
                specification=None,
                status=TestResultStatus.DRAFT,
            )
        )
        for r in results:
            test_db.add(r)
        test_db.commit()

        service = LotService()
        calc = service.calculate_lot_status(test_db, lot)
        assert calc.new_status == LotStatus.UNDER_REVIEW

    def test_adhoc_only_lot_no_required_specs(self, test_db):
        """Product with NO required specs + one ad-hoc with empty result.

        Must NOT short-circuit to UNDER_REVIEW; with an incomplete ad-hoc
        result expect PARTIAL_RESULTS.
        """
        product = Product(
            brand="No Spec Brand",
            product_name="No Spec Product",
            display_name="No Spec Brand No Spec Product",
        )
        test_db.add(product)
        test_db.commit()

        lot = _make_lot(test_db, product, ref="250101-905")
        result = TestResult(
            lot_id=lot.id,
            test_type="Moisture",  # ad-hoc, no required specs at all
            result_value=None,
            unit="%",
            status=TestResultStatus.DRAFT,
        )
        test_db.add(result)
        test_db.commit()

        service = LotService()
        calc = service.calculate_lot_status(test_db, lot)
        assert calc.new_status == LotStatus.PARTIAL_RESULTS

    def test_adhoc_only_lot_no_results_awaiting(self, test_db):
        """Product with NO required specs and no results at all -> AWAITING_RESULTS."""
        product = Product(
            brand="Empty Brand",
            product_name="Empty Product",
            display_name="Empty Brand Empty Product",
        )
        test_db.add(product)
        test_db.commit()

        lot = _make_lot(test_db, product, ref="250101-906")

        service = LotService()
        calc = service.calculate_lot_status(test_db, lot)
        assert calc.new_status == LotStatus.AWAITING_RESULTS
