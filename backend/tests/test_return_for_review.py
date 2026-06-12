"""Tests for the Return-for-Review lot workflow.

A QC manager can send an AWAITING_RELEASE lot back to NEEDS_ATTENTION with a
return_reason.  The lot stays in NEEDS_ATTENTION (even when all tests pass)
until return_response_note is set.
"""

from datetime import date

import pytest

from app.models import Lot, LotProduct, TestResult
from app.models.enums import LotStatus, LotType, TestResultStatus
from app.services.lot_service import LotService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lot_with_all_passing(test_db, product, ref: str, status: LotStatus) -> Lot:
    """Create a lot linked to *product* with all required tests passing."""
    lot = Lot(
        lot_number="RFR-" + ref,
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

    # All four required specs from sample_product_with_specs, all passing
    results = [
        TestResult(
            lot_id=lot.id,
            test_type="Total Plate Count",
            result_value="500",
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
    for r in results:
        test_db.add(r)
    test_db.commit()

    return lot


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReturnForReview:
    def test_awaiting_release_can_return_to_needs_attention(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """Transition from AWAITING_RELEASE to NEEDS_ATTENTION must succeed."""
        lot = _lot_with_all_passing(
            test_db,
            sample_product_with_specs,
            ref="260101-801",
            status=LotStatus.AWAITING_RELEASE,
        )

        # This transition should not raise
        lot.update_status(LotStatus.NEEDS_ATTENTION)
        test_db.commit()

        test_db.refresh(lot)
        assert lot.status == LotStatus.NEEDS_ATTENTION

    def test_returned_lot_holds_needs_attention_despite_passing_tests(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """A lot with return_reason and no response stays NEEDS_ATTENTION even
        when all required tests are passing."""
        lot = _lot_with_all_passing(
            test_db,
            sample_product_with_specs,
            ref="260101-802",
            status=LotStatus.NEEDS_ATTENTION,
        )
        lot.return_reason = "Wrong lot number on COC"
        lot.return_response_note = None
        test_db.commit()

        service = LotService()
        # calculate_lot_status should hold the lot in NEEDS_ATTENTION
        calc = service.calculate_lot_status(test_db, lot)

        assert calc.new_status == LotStatus.NEEDS_ATTENTION
        assert "return" in calc.reason.lower()

    def test_resolved_return_recalculates_normally(
        self, test_db, sample_product_with_specs, sample_lab_test_types
    ):
        """Once return_response_note is filled the hold is lifted and the lot
        recalculates normally (all passing -> UNDER_REVIEW)."""
        lot = _lot_with_all_passing(
            test_db,
            sample_product_with_specs,
            ref="260101-803",
            status=LotStatus.NEEDS_ATTENTION,
        )
        lot.return_reason = "Wrong lot number on COC"
        lot.return_response_note = "Data entry mistake, corrected"
        test_db.commit()

        service = LotService()
        calc = service.calculate_lot_status(test_db, lot)

        assert calc.new_status == LotStatus.UNDER_REVIEW
