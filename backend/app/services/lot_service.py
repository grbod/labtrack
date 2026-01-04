"""Lot service for managing lots and sublots."""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.lot import Lot, Sublot, LotProduct
from app.models.test_result import TestResult
from app.models.enums import LotType, LotStatus, TestResultStatus
from app.services.base import BaseService
from app.utils.logger import logger


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
            LotStatus.AWAITING_RESULTS: [LotStatus.PARTIAL_RESULTS, LotStatus.UNDER_REVIEW, LotStatus.REJECTED],
            LotStatus.PARTIAL_RESULTS: [LotStatus.UNDER_REVIEW, LotStatus.REJECTED],
            LotStatus.UNDER_REVIEW: [LotStatus.APPROVED, LotStatus.REJECTED, LotStatus.AWAITING_RESULTS],
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
        self, 
        db: Session, 
        lot_id: int, 
        completed_test_types: List[str]
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
                db, 
                lot_product.product_id, 
                completed_test_types
            )
            
            # Add to list if not already there
            for spec in product_missing:
                if not any(s.lab_test_type_id == spec.lab_test_type_id for s in missing_specs):
                    missing_specs.append(spec)
        
        return missing_specs


    def recalculate_lot_status(
        self,
        db: Session,
        lot_id: int,
        user_id: Optional[int] = None,
    ) -> Lot:
        """
        Auto-calculate lot status based on test results completion.

        Called after each test result save to update lot status automatically.

        Status transitions:
        - awaiting_results: No test results entered yet
        - partial_results: Some results entered, not all required tests complete
        - under_review: All required test results entered, ready for QC

        Note: approved/rejected are set manually by QC manager.

        Args:
            db: Database session
            lot_id: ID of the lot to recalculate
            user_id: ID of user making the change

        Returns:
            Updated lot
        """
        from app.models import ProductTestSpecification

        lot = self.get(db, lot_id)
        if not lot:
            raise ValueError(f"Lot with ID {lot_id} not found")

        # Don't auto-update status if already approved, released, or rejected
        if lot.status in [LotStatus.APPROVED, LotStatus.RELEASED, LotStatus.REJECTED]:
            return lot

        # Get all required test types from all products in this lot
        required_test_type_ids = set()
        for lot_product in lot.lot_products:
            if not lot_product.product:
                continue
            for spec in lot_product.product.test_specifications:
                if spec.is_required:
                    required_test_type_ids.add(spec.lab_test_type_id)

        # If no required tests, status depends on whether any tests exist
        if not required_test_type_ids:
            # No required tests defined - just check if there are any test results
            test_results = db.query(TestResult).filter(TestResult.lot_id == lot_id).all()
            if test_results:
                # Has some test results, consider ready for review
                new_status = LotStatus.UNDER_REVIEW
            else:
                new_status = LotStatus.AWAITING_RESULTS
        else:
            # Get test results for this lot
            test_results = db.query(TestResult).filter(TestResult.lot_id == lot_id).all()

            # Count results with values by test type
            completed_test_type_ids = set()
            for result in test_results:
                if result.result_value is not None and result.result_value.strip() != "":
                    # Need to match test_type name to lab_test_type_id
                    # For simplicity, we'll check by test_type name
                    completed_test_type_ids.add(result.test_type)

            # Match completed test types to required specs
            # We need to check if the test_type name matches any required test
            completed_required = 0
            for lot_product in lot.lot_products:
                if not lot_product.product:
                    continue
                for spec in lot_product.product.test_specifications:
                    if spec.is_required and spec.test_name in completed_test_type_ids:
                        completed_required += 1

            total_required = len(required_test_type_ids)

            if completed_required == 0:
                new_status = LotStatus.AWAITING_RESULTS
            elif completed_required < total_required:
                new_status = LotStatus.PARTIAL_RESULTS
            else:
                # All required tests completed
                new_status = LotStatus.UNDER_REVIEW

        # Only update if status changed
        if lot.status != new_status:
            old_status = lot.status
            lot.status = new_status

            self._log_audit(
                db=db,
                action="update",
                record_id=lot.id,
                old_values={"status": old_status.value},
                new_values={"status": new_status.value},
                user_id=user_id,
                reason="Auto-calculated based on test results",
            )

            db.commit()
            db.refresh(lot)

            logger.info(
                f"Auto-updated lot {lot.lot_number} status from {old_status.value} to {new_status.value}"
            )

        return lot


# Add missing import
from datetime import timedelta
