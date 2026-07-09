"""Lot service for managing lots and sublots."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.enums import AuditAction, LotStatus, LotType, TestResultStatus
from app.models.lot import Lot, LotProduct, Sublot
from app.models.product import Product
from app.models.product_test_spec import ProductTestSpecification
from app.models.test_result import TestResult
from app.services.base import BaseService
from app.utils.logger import logger


@dataclass
class LotStatusCalculation:
    """Calculated status and explanation for a lot."""

    lot: Lot
    old_status: LotStatus
    new_status: LotStatus
    reason: str
    missing_tests: List[str]
    failing_tests: List[str]

    @property
    def changed(self) -> bool:
        """Whether the calculated status differs from the current status."""
        return self.old_status != self.new_status

    def to_change_dict(self) -> Dict[str, Any]:
        """Return API-safe change details."""
        return {
            "lot_id": self.lot.id,
            "reference_number": self.lot.reference_number,
            "lot_number": self.lot.lot_number,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "reason": self.reason,
            "missing_tests": self.missing_tests,
            "failing_tests": self.failing_tests,
        }


class LotService(BaseService[Lot]):
    """
    Service for managing lots and sublots.

    Provides functionality for:
    - Creating standard lots, parent lots, and multi-SKU composites
    - Managing sublots under parent lots
    - Reference number generation
    - Lot status transitions
    """

    def __init__(self):
        """Initialize lot service."""
        super().__init__(Lot)

    AUTO_RECALCULATION_STATUSES = [
        LotStatus.AWAITING_RESULTS,
        LotStatus.PARTIAL_RESULTS,
        LotStatus.NEEDS_ATTENTION,
        LotStatus.UNDER_REVIEW,
    ]

    def generate_reference_number(self, db: Session) -> str:
        """
        Generate unique reference number in format YYMMDD-XXX.

        Args:
            db: Database session

        Returns:
            Generated reference number
        """
        today = datetime.now()
        date_prefix = today.strftime("%y%m%d")

        # Find the highest sequence number for today
        latest_ref = (
            db.query(Lot.reference_number)
            .filter(Lot.reference_number.like(f"{date_prefix}-%"))
            .order_by(Lot.reference_number.desc())
            .first()
        )

        if latest_ref and latest_ref[0]:
            # Extract sequence number and increment
            sequence = int(latest_ref[0].split("-")[1]) + 1
        else:
            sequence = 1

        return f"{date_prefix}-{sequence:03d}"

    def create_lot(
        self,
        db: Session,
        lot_data: Dict[str, Any],
        product_ids: Optional[List[int]] = None,
        product_percentages: Optional[Dict[int, float]] = None,
        user_id: Optional[int] = None,
    ) -> Lot:
        """
        Create a new lot with associated products.

        Args:
            db: Database session
            lot_data: Lot data dictionary
            product_ids: List of product IDs to associate
            product_percentages: Dictionary of product_id -> percentage for composites
            user_id: ID of user creating the lot

        Returns:
            Created lot

        Raises:
            ValueError: If validation fails
        """
        # Validate lot data
        validated_data = self._validate_lot_data(lot_data)

        # Generate reference number if not provided
        if "reference_number" not in validated_data:
            validated_data["reference_number"] = self.generate_reference_number(db)

        # Validate product associations
        # Multi-SKU composite lots can have multiple products without requiring percentages

        try:
            # Create lot
            lot = Lot(**validated_data)
            db.add(lot)
            db.flush()

            # Associate products
            if product_ids:
                for product_id in product_ids:
                    percentage = (
                        product_percentages.get(product_id)
                        if product_percentages
                        else None
                    )
                    lot_product = LotProduct(
                        lot_id=lot.id, product_id=product_id, percentage=percentage
                    )
                    db.add(lot_product)

            # Create audit log
            self._log_audit(
                db=db,
                action="insert",
                record_id=lot.id,
                new_values=lot.to_dict(),
                user_id=user_id,
            )

            db.commit()
            db.refresh(lot)

            logger.info(
                f"Created lot {lot.lot_number} with reference {lot.reference_number}"
            )
            return lot

        except IntegrityError as e:
            db.rollback()
            if "reference_number" in str(e):
                raise ValueError("Reference number already exists")
            elif "lot_number" in str(e):
                raise ValueError("Lot number already exists")
            else:
                raise

    def create_sublot(
        self,
        db: Session,
        parent_lot_id: int,
        sublot_data: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> Sublot:
        """
        Create a sublot under a parent lot.

        Args:
            db: Database session
            parent_lot_id: ID of the parent lot
            sublot_data: Sublot data dictionary
            user_id: ID of user creating the sublot

        Returns:
            Created sublot

        Raises:
            ValueError: If parent lot is not found or not a parent lot type
        """
        # Verify parent lot exists and is correct type
        parent_lot = self.get(db, parent_lot_id)
        if not parent_lot:
            raise ValueError(f"Parent lot with ID {parent_lot_id} not found")

        if parent_lot.lot_type != LotType.PARENT_LOT:
            raise ValueError(f"Lot {parent_lot.lot_number} is not a parent lot")

        # Generate sublot number if not provided
        if "sublot_number" not in sublot_data:
            sublot_count = (
                db.query(Sublot).filter(Sublot.parent_lot_id == parent_lot_id).count()
            )
            sublot_data["sublot_number"] = f"{parent_lot.lot_number}-{sublot_count + 1}"

        sublot_data["parent_lot_id"] = parent_lot_id

        try:
            sublot = Sublot(**sublot_data)
            db.add(sublot)
            db.commit()
            db.refresh(sublot)

            logger.info(
                f"Created sublot {sublot.sublot_number} under lot {parent_lot.lot_number}"
            )
            return sublot

        except IntegrityError as e:
            db.rollback()
            if "sublot_number" in str(e):
                raise ValueError("Sublot number already exists")
            else:
                raise

    def update_lot_status(
        self,
        db: Session,
        lot_id: int,
        new_status: LotStatus,
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> Lot:
        """
        Update lot status with validation.

        Args:
            db: Database session
            lot_id: ID of the lot
            new_status: New status to set
            user_id: ID of user making the change
            reason: Reason for status change

        Returns:
            Updated lot

        Raises:
            ValueError: If status transition is invalid
        """
        lot = self.get(db, lot_id)
        if not lot:
            raise ValueError(f"Lot with ID {lot_id} not found")

        # Validate status transition
        valid_transitions = {
            LotStatus.AWAITING_RESULTS: [
                LotStatus.PARTIAL_RESULTS,
                LotStatus.UNDER_REVIEW,
                LotStatus.REJECTED,
            ],
            LotStatus.PARTIAL_RESULTS: [LotStatus.UNDER_REVIEW, LotStatus.REJECTED],
            LotStatus.UNDER_REVIEW: [
                LotStatus.APPROVED,
                LotStatus.REJECTED,
                LotStatus.AWAITING_RESULTS,
            ],
            LotStatus.APPROVED: [LotStatus.RELEASED, LotStatus.UNDER_REVIEW],
            LotStatus.RELEASED: [],  # Released is final
            LotStatus.REJECTED: [LotStatus.AWAITING_RESULTS],  # Can retry
        }

        if new_status not in valid_transitions.get(lot.status, []):
            raise ValueError(
                f"Invalid status transition from {lot.status.value} to {new_status.value}"
            )

        # Additional validation for specific transitions
        if new_status == LotStatus.APPROVED:
            # Check all test results are approved
            unapproved_tests = [
                tr for tr in lot.test_results if tr.status != TestResultStatus.APPROVED
            ]
            if unapproved_tests:
                raise ValueError(
                    f"Cannot approve lot with {len(unapproved_tests)} unapproved test results"
                )

        old_status = lot.status
        # This legacy generic setter validates against its own transition table
        # above; route the assignment through the workflow guard token so the
        # enforcement guard permits it without a second (divergent) validation.
        from app.workflow.lot_workflow_service import _allow_lot_status_assignment

        with _allow_lot_status_assignment(lot):
            lot.status = new_status

        # Log the change
        self._log_audit(
            db=db,
            action="update",
            record_id=lot.id,
            old_values={"status": old_status.value},
            new_values={"status": new_status.value},
            user_id=user_id,
            reason=reason,
        )

        db.commit()
        db.refresh(lot)

        logger.info(
            f"Updated lot {lot.lot_number} status from {old_status.value} to {new_status.value}"
        )
        return lot

    def get_lots_by_status(
        self, db: Session, status: LotStatus, skip: int = 0, limit: int = 100
    ) -> List[Lot]:
        """
        Get lots filtered by status.

        Args:
            db: Database session
            status: Lot status to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of lots
        """
        return (
            db.query(Lot).filter(Lot.status == status).offset(skip).limit(limit).all()
        )

    def get_lots_by_product(
        self, db: Session, product_id: int, skip: int = 0, limit: int = 100
    ) -> List[Lot]:
        """
        Get lots associated with a specific product.

        Args:
            db: Database session
            product_id: Product ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of lots
        """
        return (
            db.query(Lot)
            .join(LotProduct)
            .filter(LotProduct.product_id == product_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_expiring_lots(
        self, db: Session, days_ahead: int = 90, skip: int = 0, limit: int = 100
    ) -> List[Lot]:
        """
        Get lots expiring within specified days.

        Args:
            db: Database session
            days_ahead: Number of days to look ahead
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of expiring lots
        """
        expiry_date = date.today() + timedelta(days=days_ahead)

        return (
            db.query(Lot)
            .filter(
                Lot.exp_date.isnot(None),
                Lot.exp_date <= expiry_date,
                Lot.exp_date >= date.today(),
            )
            .order_by(Lot.exp_date)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def _validate_lot_data(self, lot_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean lot data.

        Args:
            lot_data: Raw lot data

        Returns:
            Validated lot data

        Raises:
            ValueError: If validation fails
        """
        # Required fields
        if not lot_data.get("lot_number"):
            raise ValueError("Lot number is required")

        # Clean data
        validated_data = {
            "lot_number": lot_data["lot_number"].strip().upper(),
            "lot_type": lot_data.get("lot_type", LotType.STANDARD),
            "status": lot_data.get("status", LotStatus.AWAITING_RESULTS),
            "generate_coa": lot_data.get("generate_coa", True),
        }

        # Optional fields
        if lot_data.get("reference_number"):
            validated_data["reference_number"] = lot_data["reference_number"].strip()

        if lot_data.get("mfg_date"):
            validated_data["mfg_date"] = lot_data["mfg_date"]

        if lot_data.get("exp_date"):
            validated_data["exp_date"] = lot_data["exp_date"]

            # Validate expiration after manufacturing
            if (
                validated_data.get("mfg_date")
                and validated_data["exp_date"] < validated_data["mfg_date"]
            ):
                raise ValueError("Expiration date must be after manufacturing date")

        return validated_data

    def get_sublots(self, db: Session, parent_lot_id: int) -> List[Sublot]:
        """
        Get all sublots for a parent lot.

        Args:
            db: Database session
            parent_lot_id: Parent lot ID

        Returns:
            List of sublots
        """
        return (
            db.query(Sublot)
            .filter(Sublot.parent_lot_id == parent_lot_id)
            .order_by(Sublot.sublot_number)
            .all()
        )

    def get_missing_required_tests_for_lot(
        self, db: Session, lot_id: int, completed_test_types: List[str]
    ) -> List["ProductTestSpecification"]:
        """
        Get list of required tests that haven't been completed for a lot.

        Args:
            db: Database session
            lot_id: Lot ID
            completed_test_types: List of test type names already completed

        Returns:
            List of missing required test specifications
        """
        from app.models import ProductTestSpecification
        from app.services.product_service import ProductService

        lot = self.get(db, lot_id)
        if not lot:
            return []

        product_service = ProductService()
        missing_specs = []

        # Get missing tests for each product in the lot
        for lot_product in lot.lot_products:
            product_missing = product_service.get_missing_required_tests(
                db, lot_product.product_id, completed_test_types
            )

            # Add to list if not already there
            for spec in product_missing:
                if not any(
                    s.lab_test_type_id == spec.lab_test_type_id for s in missing_specs
                ):
                    missing_specs.append(spec)

        return missing_specs

    def calculate_lot_status(
        self,
        db: Session,
        lot: Lot,
    ) -> LotStatusCalculation:
        """
        Calculate a lot's workflow status without mutating it.

        This is the shared source of truth for normal auto-recalculation,
        admin preview, and admin apply.
        """
        old_status = lot.status

        if old_status not in self.AUTO_RECALCULATION_STATUSES:
            return LotStatusCalculation(
                lot=lot,
                old_status=old_status,
                new_status=old_status,
                reason="Status is excluded from automatic recalculation",
                missing_tests=[],
                failing_tests=[],
            )

        # A lot returned from the release queue stays in NEEDS_ATTENTION until
        # the return is answered with a response note (resolved at submit time).
        if (
            old_status == LotStatus.NEEDS_ATTENTION
            and lot.return_reason
            and not lot.return_response_note
        ):
            return LotStatusCalculation(
                lot=lot,
                old_status=old_status,
                new_status=LotStatus.NEEDS_ATTENTION,
                reason="Returned for review; awaiting response note",
                missing_tests=[],
                failing_tests=[],
            )

        required_specs: Dict[str, ProductTestSpecification] = {}
        for lot_product in lot.lot_products:
            if not lot_product.product:
                continue
            for spec in lot_product.product.test_specifications:
                test_name = spec.test_name
                if spec.is_required and test_name and test_name not in required_specs:
                    required_specs[test_name] = spec

        test_results = db.query(TestResult).filter(TestResult.lot_id == lot.id).all()
        completed_results: Dict[str, str] = {}
        for result in test_results:
            if result.result_value is not None and result.result_value.strip() != "":
                completed_results[result.test_type] = result.result_value

        # No required specs AND no results at all → awaiting. If ad-hoc results
        # exist, fall through to the combined logic below (required_specs empty)
        # so ad-hoc gating still applies.
        if not required_specs and not test_results:
            return LotStatusCalculation(
                lot=lot,
                old_status=old_status,
                new_status=LotStatus.AWAITING_RESULTS,
                reason="No required tests configured and no results entered",
                missing_tests=[],
                failing_tests=[],
            )

        missing_tests = [
            test_name
            for test_name in required_specs
            if test_name not in completed_results
        ]
        failing_tests = [
            test_name
            for test_name, spec in required_specs.items()
            if test_name in completed_results
            and not spec.matches_result(completed_results[test_name])
        ]

        from app.utils.spec_matcher import specification_matches

        # Ad-hoc tests (not part of required product specs) are binding too:
        # empty result blocks review; failing own spec flags the lot.
        adhoc_results = [r for r in test_results if r.test_type not in required_specs]
        adhoc_missing = [
            r.test_type
            for r in adhoc_results
            if r.result_value is None or not str(r.result_value).strip()
        ]
        adhoc_failing = [
            r.test_type
            for r in adhoc_results
            if r.test_type not in adhoc_missing
            and not specification_matches(r.specification, r.unit, r.result_value)
        ]
        missing_tests = missing_tests + adhoc_missing
        failing_tests = failing_tests + adhoc_failing

        total_required = len(required_specs) + len(adhoc_results)
        completed_required = total_required - len(missing_tests)

        if completed_required == 0:
            # No completed tests. If any result rows exist at all (e.g. an
            # ad-hoc test was added but left blank), the lot is in progress
            # → PARTIAL_RESULTS; otherwise nothing has started → AWAITING.
            if test_results:
                return LotStatusCalculation(
                    lot=lot,
                    old_status=old_status,
                    new_status=LotStatus.PARTIAL_RESULTS,
                    reason=f"Missing tests: {', '.join(missing_tests)}",
                    missing_tests=missing_tests,
                    failing_tests=[],
                )
            return LotStatusCalculation(
                lot=lot,
                old_status=old_status,
                new_status=LotStatus.AWAITING_RESULTS,
                reason="Missing tests: all required tests are missing",
                missing_tests=missing_tests,
                failing_tests=[],
            )

        if completed_required < total_required:
            if old_status == LotStatus.NEEDS_ATTENTION:
                return LotStatusCalculation(
                    lot=lot,
                    old_status=old_status,
                    new_status=LotStatus.NEEDS_ATTENTION,
                    reason="Missing tests; needs attention stays until all required tests pass",
                    missing_tests=missing_tests,
                    failing_tests=[],
                )
            return LotStatusCalculation(
                lot=lot,
                old_status=old_status,
                new_status=LotStatus.PARTIAL_RESULTS,
                reason=f"Missing tests: {', '.join(missing_tests)}",
                missing_tests=missing_tests,
                failing_tests=[],
            )

        if failing_tests:
            return LotStatusCalculation(
                lot=lot,
                old_status=old_status,
                new_status=LotStatus.NEEDS_ATTENTION,
                reason=f"Failing specs: {', '.join(failing_tests)}",
                missing_tests=[],
                failing_tests=failing_tests,
            )

        return LotStatusCalculation(
            lot=lot,
            old_status=old_status,
            new_status=LotStatus.UNDER_REVIEW,
            reason="All tests pass",
            missing_tests=[],
            failing_tests=[],
        )

    def _apply_lot_status_calculation(
        self,
        db: Session,
        calculation: LotStatusCalculation,
        user_id: Optional[int] = None,
        reason_prefix: str = "Auto-calculated",
    ) -> bool:
        """Apply a calculated status change and write its audit entry."""
        if not calculation.changed:
            return False

        lot = calculation.lot
        from app.workflow.lot_workflow_service import LotWorkflowService

        LotWorkflowService().apply_auto(
            db,
            lot,
            calculation.new_status,
            actor_id=user_id,
            reason=f"{reason_prefix}: {calculation.reason}",
        )
        logger.info(
            "Auto-updated lot {} status from {} to {}",
            lot.lot_number,
            calculation.old_status.value,
            calculation.new_status.value,
        )
        return True

    def recalculate_lot_status(
        self,
        db: Session,
        lot_id: int,
        user_id: Optional[int] = None,
    ) -> Lot:
        """
        Auto-calculate and update one lot status based on current test results.
        """
        lot = self.get(db, lot_id)
        if not lot:
            raise ValueError(f"Lot with ID {lot_id} not found")

        calculation = self.calculate_lot_status(db, lot)
        if self._apply_lot_status_calculation(db, calculation, user_id=user_id):
            db.commit()
            db.refresh(lot)

        return lot

    def preview_status_recalculation(self, db: Session) -> Dict[str, Any]:
        """Preview active lot status recalculation without mutating data."""
        calculations = self._bulk_status_recalculation_calculations(db)
        changes = [
            calculation.to_change_dict()
            for calculation in calculations
            if calculation.changed
        ]
        return {
            "mode": "preview",
            "scanned_count": len(calculations),
            "changed_count": len(changes),
            "changes": changes,
        }

    def apply_status_recalculation(
        self,
        db: Session,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Apply active lot status recalculation and return changed rows."""
        calculations = self._bulk_status_recalculation_calculations(db)
        changes = []
        for calculation in calculations:
            if self._apply_lot_status_calculation(
                db,
                calculation,
                user_id=user_id,
                reason_prefix="Admin bulk status recalculation",
            ):
                changes.append(calculation.to_change_dict())

        db.commit()
        return {
            "mode": "apply",
            "scanned_count": len(calculations),
            "changed_count": len(changes),
            "changes": changes,
        }

    COC_RETENTION_DAYS = 7

    def cleanup_expired_coc_archives(self, db: Session) -> int:
        """Delete archived COC PDFs for lots released/rejected > 7 days ago."""
        from app.services.storage_service import get_storage_service

        cutoff = datetime.utcnow() - timedelta(days=self.COC_RETENTION_DAYS)
        lots = (
            db.query(Lot)
            .filter(
                Lot.coc_storage_key.isnot(None),
                Lot.status.in_([LotStatus.RELEASED, LotStatus.REJECTED]),
                Lot.updated_at < cutoff,
            )
            .all()
        )
        storage = get_storage_service()
        purged = 0
        for lot in lots:
            try:
                storage.delete(lot.coc_storage_key)
            except Exception:
                logger.opt(exception=True).warning(
                    f"Failed to delete COC archive {lot.coc_storage_key}"
                )
            lot.coc_storage_key = None
            purged += 1
        if purged:
            db.commit()
            logger.info(f"Purged {purged} expired COC archives")
        return purged

    def _bulk_status_recalculation_calculations(
        self,
        db: Session,
    ) -> List[LotStatusCalculation]:
        """Calculate current status for all active tracker lots."""
        lots = (
            db.query(Lot)
            .options(
                joinedload(Lot.lot_products)
                .joinedload(LotProduct.product)
                .joinedload(Product.test_specifications)
                .joinedload(ProductTestSpecification.lab_test_type)
            )
            .filter(Lot.status.in_(self.AUTO_RECALCULATION_STATUSES))
            .order_by(Lot.created_at.desc())
            .all()
        )
        return [self.calculate_lot_status(db, lot) for lot in lots]
