"""Retest service for managing retest requests and workflow."""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.models import Lot, TestResult, User
from app.models.retest_request import RetestRequest, RetestItem
from app.models.enums import RetestStatus, AuditAction, LotStatus
from app.services.base import BaseService
from app.services.lab_info_service import lab_info_service
from app.services.storage_service import get_storage_service
from app.services.daane_coc_service import daane_coc_service
from app.utils.logger import logger


class RetestService(BaseService[RetestRequest]):
    """
    Service for managing lab retest requests.

    Provides functionality for:
    - Creating retest requests with -R1, -R2 reference numbers
    - Tracking which tests are being retested
    - Auto-completing retests when values are updated
    - Generating PDF retest request forms
    """

    def __init__(self):
        """Initialize retest service."""
        super().__init__(RetestRequest)

    def generate_retest_reference(
        self, db: Session, lot_id: int
    ) -> Tuple[str, int]:
        """
        Generate next -R1, -R2, etc. reference for a lot.

        Args:
            db: Database session
            lot_id: ID of the lot

        Returns:
            Tuple of (reference_number, retest_number)

        Raises:
            ValueError: If lot not found
        """
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot:
            raise ValueError(f"Lot with ID {lot_id} not found")

        # Count existing retest requests for this lot
        existing_count = (
            db.query(RetestRequest)
            .filter(RetestRequest.lot_id == lot_id)
            .count()
        )

        retest_number = existing_count + 1
        reference_number = f"{lot.reference_number}-R{retest_number}"

        return reference_number, retest_number

    def create_retest_request(
        self,
        db: Session,
        lot_id: int,
        test_result_ids: List[int],
        reason: str,
        user_id: int,
    ) -> RetestRequest:
        """
        Create a retest request for selected tests.

        Args:
            db: Database session
            lot_id: ID of the lot
            test_result_ids: List of test result IDs to retest
            reason: Reason for requesting the retest
            user_id: ID of the user requesting the retest

        Returns:
            Created RetestRequest

        Raises:
            ValueError: If lot not found, no tests specified, or test results not found
        """
        if not test_result_ids:
            raise ValueError("At least one test result must be selected for retest")

        # Validate lot exists
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot:
            raise ValueError(f"Lot with ID {lot_id} not found")

        # Generate reference number
        reference_number, retest_number = self.generate_retest_reference(db, lot_id)

        try:
            # Create the retest request
            retest_request = RetestRequest(
                lot_id=lot_id,
                reference_number=reference_number,
                retest_number=retest_number,
                reason=reason,
                requested_by_id=user_id,
                daane_po_number=daane_coc_service.generate_po_number(db),
            )
            db.add(retest_request)
            db.flush()

            # Create retest items and snapshot original values
            for test_result_id in test_result_ids:
                test_result = (
                    db.query(TestResult)
                    .filter(TestResult.id == test_result_id)
                    .first()
                )
                if not test_result:
                    raise ValueError(f"Test result with ID {test_result_id} not found")

                if test_result.lot_id != lot_id:
                    raise ValueError(
                        f"Test result {test_result_id} does not belong to lot {lot_id}"
                    )

                retest_item = RetestItem(
                    retest_request_id=retest_request.id,
                    test_result_id=test_result_id,
                    original_value=test_result.result_value,
                )
                db.add(retest_item)

            # Update lot flag
            lot.has_pending_retest = True

            # Move lot to Partial Results if it was in Needs Attention (failing tests need re-entry)
            if lot.status == LotStatus.NEEDS_ATTENTION:
                lot.status = LotStatus.PARTIAL_RESULTS

            db.flush()

            # Log audit
            self._log_audit(
                db=db,
                action=AuditAction.INSERT,
                record_id=retest_request.id,
                new_values={
                    "reference_number": reference_number,
                    "reason": reason,
                    "test_result_ids": test_result_ids,
                },
                user_id=user_id,
                reason=f"Retest requested: {reason}",
            )

            db.commit()
            db.refresh(retest_request)

            logger.info(
                f"Created retest request {reference_number} for lot {lot.lot_number} "
                f"with {len(test_result_ids)} tests"
            )

            return retest_request

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Error creating retest request: {e}")
            raise

    def get_retest_request(
        self, db: Session, retest_request_id: int
    ) -> Optional[RetestRequest]:
        """
        Get a retest request with related data.

        Args:
            db: Database session
            retest_request_id: ID of the retest request

        Returns:
            RetestRequest or None if not found
        """
        return (
            db.query(RetestRequest)
            .options(
                joinedload(RetestRequest.lot),
                joinedload(RetestRequest.requested_by),
                joinedload(RetestRequest.items).joinedload(RetestItem.test_result),
            )
            .filter(RetestRequest.id == retest_request_id)
            .first()
        )

    def get_retests_for_lot(
        self, db: Session, lot_id: int
    ) -> List[RetestRequest]:
        """
        Get all retest requests for a lot.

        Args:
            db: Database session
            lot_id: ID of the lot

        Returns:
            List of RetestRequest objects
        """
        return (
            db.query(RetestRequest)
            .options(
                joinedload(RetestRequest.requested_by),
                joinedload(RetestRequest.items).joinedload(RetestItem.test_result),
            )
            .filter(RetestRequest.lot_id == lot_id)
            .order_by(RetestRequest.created_at.desc())
            .all()
        )

    def get_pending_retests_for_lot(
        self, db: Session, lot_id: int
    ) -> List[RetestRequest]:
        """
        Get pending retest requests for a lot.

        Args:
            db: Database session
            lot_id: ID of the lot

        Returns:
            List of pending RetestRequest objects
        """
        return (
            db.query(RetestRequest)
            .options(
                joinedload(RetestRequest.items).joinedload(RetestItem.test_result),
            )
            .filter(
                RetestRequest.lot_id == lot_id,
                RetestRequest.status == RetestStatus.PENDING,
            )
            .order_by(RetestRequest.created_at.desc())
            .all()
        )

    def get_retest_items_for_test_result(
        self, db: Session, test_result_id: int
    ) -> List[RetestItem]:
        """
        Get all retest items for a specific test result.

        Args:
            db: Database session
            test_result_id: ID of the test result

        Returns:
            List of RetestItem objects
        """
        return (
            db.query(RetestItem)
            .options(joinedload(RetestItem.retest_request))
            .filter(RetestItem.test_result_id == test_result_id)
            .all()
        )

    def check_and_complete_retest(
        self, db: Session, test_result_id: int, user_id: Optional[int] = None
    ) -> Optional[RetestRequest]:
        """
        Check if updating a test result completes any pending retests.

        This should be called after a test result value is updated.
        If new value matches original value, sets status to REVIEW_REQUIRED.
        If new value differs from original, auto-completes the retest.

        Args:
            db: Database session
            test_result_id: ID of the test result that was updated

        Returns:
            The completed/review_required RetestRequest if one was updated, None otherwise
        """
        # Find pending retest items for this test result
        items = (
            db.query(RetestItem)
            .join(RetestRequest)
            .filter(
                RetestItem.test_result_id == test_result_id,
                RetestRequest.status == RetestStatus.PENDING,
            )
            .all()
        )

        updated_request = None

        for item in items:
            retest_request = item.retest_request

            # Check status of ALL items in this request
            all_updated = True
            any_same_as_original = False

            for req_item in retest_request.items:
                test_result = (
                    db.query(TestResult)
                    .filter(TestResult.id == req_item.test_result_id)
                    .first()
                )
                if test_result:
                    if test_result.result_value == req_item.original_value:
                        # Value unchanged from original - either not updated or same value
                        # Check if this is the item we just updated
                        if req_item.test_result_id == test_result_id:
                            # User entered same value as original - needs review
                            any_same_as_original = True
                        else:
                            # Other items still need updating
                            all_updated = False
                            break

            if all_updated:
                if any_same_as_original:
                    # At least one value matches original - needs QC review
                    retest_request.status = RetestStatus.REVIEW_REQUIRED
                    # Log audit for auto status change
                    self._log_audit(
                        db=db,
                        action=AuditAction.UPDATE,
                        record_id=retest_request.id,
                        old_values={"status": RetestStatus.PENDING.value},
                        new_values={"status": RetestStatus.REVIEW_REQUIRED.value},
                        user_id=user_id,
                        reason=f"Retest requires review: value unchanged for {item.test_result.test_type}",
                    )
                    logger.info(
                        f"Retest {retest_request.reference_number} requires review "
                        f"(new value matches original)"
                    )
                else:
                    # All values differ from original - auto-complete
                    retest_request.status = RetestStatus.COMPLETED
                    retest_request.completed_at = datetime.utcnow()
                    # Log audit for auto-completion
                    self._log_audit(
                        db=db,
                        action=AuditAction.UPDATE,
                        record_id=retest_request.id,
                        old_values={"status": RetestStatus.PENDING.value},
                        new_values={
                            "status": RetestStatus.COMPLETED.value,
                            "completed_at": retest_request.completed_at.isoformat(),
                        },
                        user_id=user_id,
                        reason="Retest auto-completed: all values differ from original",
                    )
                    logger.info(
                        f"Retest {retest_request.reference_number} auto-completed"
                    )

                updated_request = retest_request

                # Check if lot has any OTHER pending retests
                pending_count = (
                    db.query(RetestRequest)
                    .filter(
                        RetestRequest.lot_id == retest_request.lot_id,
                        RetestRequest.status == RetestStatus.PENDING,
                        RetestRequest.id != retest_request.id,
                    )
                    .count()
                )

                # Also check for review_required retests - lot should still show pending
                review_required_count = (
                    db.query(RetestRequest)
                    .filter(
                        RetestRequest.lot_id == retest_request.lot_id,
                        RetestRequest.status == RetestStatus.REVIEW_REQUIRED,
                    )
                    .count()
                )

                if pending_count == 0 and review_required_count == 0:
                    retest_request.lot.has_pending_retest = False
                elif retest_request.status == RetestStatus.REVIEW_REQUIRED:
                    # Keep flag true if review required
                    retest_request.lot.has_pending_retest = True

        if updated_request:
            db.commit()

        return updated_request

    def complete_retest(
        self, db: Session, retest_request_id: int, user_id: int
    ) -> RetestRequest:
        """
        Manually mark a retest as completed.

        Args:
            db: Database session
            retest_request_id: ID of the retest request
            user_id: ID of the user completing the retest

        Returns:
            Updated RetestRequest

        Raises:
            ValueError: If retest not found or already completed
        """
        retest_request = self.get_retest_request(db, retest_request_id)
        if not retest_request:
            raise ValueError(f"Retest request with ID {retest_request_id} not found")

        if retest_request.status == RetestStatus.COMPLETED:
            raise ValueError("Retest request is already completed")

        old_values = {
            "status": retest_request.status.value,
        }

        retest_request.status = RetestStatus.COMPLETED
        retest_request.completed_at = datetime.utcnow()

        # Update lot flag if no other pending retests
        pending_count = (
            db.query(RetestRequest)
            .filter(
                RetestRequest.lot_id == retest_request.lot_id,
                RetestRequest.status == RetestStatus.PENDING,
                RetestRequest.id != retest_request.id,
            )
            .count()
        )

        if pending_count == 0:
            retest_request.lot.has_pending_retest = False

        db.flush()

        self._log_audit(
            db=db,
            action=AuditAction.UPDATE,
            record_id=retest_request.id,
            old_values=old_values,
            new_values={
                "status": RetestStatus.COMPLETED.value,
                "completed_at": retest_request.completed_at.isoformat(),
            },
            user_id=user_id,
            reason="Retest manually completed",
        )

        db.commit()
        db.refresh(retest_request)

        logger.info(f"Retest {retest_request.reference_number} manually completed")

        return retest_request

    def generate_retest_pdf(
        self, db: Session, retest_request_id: int
    ) -> bytes:
        """
        Generate a PDF retest request form.

        Args:
            db: Database session
            retest_request_id: ID of the retest request

        Returns:
            PDF content as bytes

        Raises:
            ValueError: If retest request not found
        """
        retest_request = self.get_retest_request(db, retest_request_id)
        if not retest_request:
            raise ValueError(f"Retest request with ID {retest_request_id} not found")

        # Generate PDF to temporary file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            self._generate_pdf_reportlab(db, retest_request, tmp_path)

            with open(tmp_path, "rb") as f:
                pdf_content = f.read()

            return pdf_content

        finally:
            import os
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _generate_pdf_reportlab(
        self, db: Session, retest_request: RetestRequest, output_path: str
    ) -> None:
        """
        Generate retest PDF using ReportLab.

        Args:
            db: Database session
            retest_request: RetestRequest object
            output_path: Path to write the PDF file
        """
        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )

        # Setup styles
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="RetestTitle",
                parent=styles["Title"],
                fontSize=18,
                textColor=colors.HexColor("#b45309"),  # Amber/warning color
                alignment=TA_CENTER,
                spaceAfter=10,
            )
        )
        styles.add(
            ParagraphStyle(
                name="RetestHeader",
                parent=styles["Heading2"],
                fontSize=11,
                textColor=colors.HexColor("#b45309"),
                alignment=TA_LEFT,
                spaceBefore=12,
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="RetestNormal",
                parent=styles["Normal"],
                fontSize=9,
                alignment=TA_LEFT,
                leading=11,
            )
        )

        # Build story (content)
        story = []

        # Get lab info
        lab_info = lab_info_service.get_or_create_default(db)

        # Company header
        company_header = [
            [lab_info.company_name, "", ""],
            [lab_info.full_address, "", ""],
        ]
        header_table = Table(company_header, colWidths=[3.5 * inch, 1 * inch, 3 * inch])
        header_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (0, 0), 14),
                    ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#1a5f2a")),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.grey),
                ]
            )
        )
        story.append(header_table)
        story.append(Spacer(1, 0.2 * inch))

        # Title
        story.append(Paragraph("RETEST REQUEST FORM", styles["RetestTitle"]))
        story.append(Spacer(1, 0.15 * inch))

        # Reference and date
        doc_info = [
            [
                f"Reference: {retest_request.reference_number}",
                f"Date: {retest_request.created_at.strftime('%B %d, %Y')}",
            ]
        ]
        doc_table = Table(doc_info, colWidths=[3.75 * inch, 3.75 * inch])
        doc_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, 0), "LEFT"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ]
            )
        )
        story.append(doc_table)
        story.append(Spacer(1, 0.15 * inch))

        # Sample Information section
        story.append(Paragraph("SAMPLE INFORMATION", styles["RetestHeader"]))

        lot = retest_request.lot

        # Get product name
        product_name = "Unknown Product"
        if lot.lot_products:
            products = [lp.product for lp in lot.lot_products if lp.product]
            if len(products) == 1:
                product_name = products[0].display_name
            elif len(products) > 1:
                product_name = "Multi-SKU: " + ", ".join(p.display_name for p in products[:3])
                if len(products) > 3:
                    product_name += f" +{len(products) - 3} more"

        sample_data = [
            ["Product:", product_name],
            ["Lot Number:", lot.lot_number],
            [
                "Mfg Date:",
                lot.mfg_date.strftime("%B %d, %Y") if lot.mfg_date else "N/A",
            ],
            [
                "Exp Date:",
                lot.exp_date.strftime("%B %d, %Y") if lot.exp_date else "N/A",
            ],
        ]
        sample_table = Table(sample_data, colWidths=[1.5 * inch, 6 * inch])
        sample_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                ]
            )
        )
        story.append(sample_table)
        story.append(Spacer(1, 0.15 * inch))

        # Tests to Retest section
        story.append(Paragraph("TESTS TO RETEST", styles["RetestHeader"]))

        test_data = [["Test", "Specification"]]
        for item in retest_request.items:
            test_result = item.test_result
            test_data.append(
                [
                    test_result.test_type,
                    test_result.specification or "N/A",
                ]
            )

        test_table = Table(test_data, colWidths=[3.75 * inch, 3.75 * inch])
        test_table.setStyle(
            TableStyle(
                [
                    # Header
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b45309")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    # Data
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    # Grid
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
                    # Padding
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    # Alternating row colors
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f8f9fa")],
                    ),
                ]
            )
        )
        story.append(test_table)
        story.append(Spacer(1, 0.15 * inch))

        # Reason section
        story.append(Paragraph("REASON FOR RETEST", styles["RetestHeader"]))

        reason_table = Table([[retest_request.reason]], colWidths=[7.5 * inch])
        reason_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fbbf24")),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(reason_table)
        story.append(Spacer(1, 0.2 * inch))

        # Requested by section
        requested_by = retest_request.requested_by
        requested_by_name = (
            requested_by.full_name or requested_by.username
            if requested_by
            else "Unknown"
        )

        story.append(
            Paragraph(
                f"<b>Requested by:</b> {requested_by_name}",
                styles["RetestNormal"],
            )
        )
        story.append(
            Paragraph(
                f"<b>Date:</b> {retest_request.created_at.strftime('%B %d, %Y')}",
                styles["RetestNormal"],
            )
        )

        # Build PDF
        doc.build(story)


# Singleton instance
retest_service = RetestService()
