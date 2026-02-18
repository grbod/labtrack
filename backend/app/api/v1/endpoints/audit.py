"""Audit trail endpoints with annotation and export support."""

import csv
import io
import hashlib
import uuid
from datetime import datetime, date, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse, RedirectResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.dependencies import DbSession, QCManagerOrAdmin
from app.config import settings
from app.models.audit import AuditLog, AuditAnnotation, MAX_ATTACHMENTS_PER_ENTRY, MAX_ATTACHMENT_SIZE_BYTES
from app.models.enums import AuditAction
from app.models.test_result import TestResult
from app.models.coa_release import COARelease
from app.models.retest_request import RetestRequest
from app.schemas.audit import (
    AuditLogResponse,
    AuditLogListResponse,
    AuditAnnotationCreate,
    AuditAnnotationResponse,
    AuditAnnotationListResponse,
    AuditTrailResponse,
    AuditEntryDisplay,
    FieldChange,
)
from app.services.storage_service import get_storage_service

router = APIRouter()


def format_action_display(action: AuditAction) -> str:
    """Format action for display."""
    action_map = {
        AuditAction.INSERT: "Created",
        AuditAction.UPDATE: "Updated",
        AuditAction.DELETE: "Deleted",
        AuditAction.APPROVE: "Approved",
        AuditAction.REJECT: "Rejected",
        AuditAction.VALIDATION_FAILED: "Validation Failed",
    }
    return action_map.get(action, action.value.title())


def format_timestamp(dt: datetime) -> str:
    """Format timestamp for display (absolute time)."""
    return dt.strftime("%b %d, %Y %I:%M %p")


def format_field_value(value, field_name: str = None) -> str:
    """Format a field value for display."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, dict)):
        # Don't display complex structures inline
        return f"[{type(value).__name__}]"
    return str(value)


# Field display name overrides
FIELD_DISPLAY_NAMES = {
    "notes": "Reason",
}


def format_field_name(field: str) -> str:
    """Format field name from snake_case to Title Case."""
    # Check for explicit overrides first
    if field in FIELD_DISPLAY_NAMES:
        return FIELD_DISPLAY_NAMES[field]
    return field.replace("_", " ").title()


def build_field_changes(old_values: dict, new_values: dict, context_prefix: str = None) -> List[FieldChange]:
    """Build list of field changes from old/new values.

    Args:
        old_values: Dictionary of old field values
        new_values: Dictionary of new field values
        context_prefix: Optional prefix to add to field names (e.g., "Yeast & Mold")
    """
    changes = []

    def get_display_field(field: str) -> str:
        """Get display name for field, optionally with context prefix."""
        formatted = format_field_name(field)
        if context_prefix:
            return f"{context_prefix} › {formatted}"
        return formatted

    # Handle INSERT (no old values)
    if not old_values and new_values:
        # Filter out metadata
        for field, value in new_values.items():
            if field.startswith("_"):
                continue
            changes.append(FieldChange(
                field=get_display_field(field),
                old_value=None,
                new_value=value,
                display_old=None,
                display_new=format_field_value(value, field),
            ))
        return changes

    # Handle DELETE (no new values)
    if old_values and not new_values:
        for field, value in old_values.items():
            if field.startswith("_"):
                continue
            changes.append(FieldChange(
                field=get_display_field(field),
                old_value=value,
                new_value=None,
                display_old=format_field_value(value, field),
                display_new=None,
            ))
        return changes

    # Handle UPDATE
    all_fields = set((old_values or {}).keys()) | set((new_values or {}).keys())
    for field in sorted(all_fields):
        if field.startswith("_"):
            continue
        old_val = (old_values or {}).get(field)
        new_val = (new_values or {}).get(field)
        if old_val != new_val:
            changes.append(FieldChange(
                field=get_display_field(field),
                old_value=old_val,
                new_value=new_val,
                display_old=format_field_value(old_val, field),
                display_new=format_field_value(new_val, field),
            ))

    return changes


# ============================================================================
# Audit Log Endpoints
# ============================================================================


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    db: DbSession,
    current_user: QCManagerOrAdmin,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    table_name: Optional[str] = None,
    record_id: Optional[int] = None,
    action: Optional[AuditAction] = None,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> AuditLogListResponse:
    """
    List audit logs with filtering (QC Manager or Admin only).

    Filters:
    - table_name: Filter by table (e.g., "test_results", "lots")
    - record_id: Filter by specific record ID
    - action: Filter by action type
    - user_id: Filter by user who made the change
    - date_from/date_to: Filter by date range
    """
    query = db.query(AuditLog).options(joinedload(AuditLog.user))

    # Apply filters
    if table_name:
        query = query.filter(AuditLog.table_name == table_name.lower())

    if record_id is not None:
        query = query.filter(AuditLog.record_id == record_id)

    if action:
        query = query.filter(AuditLog.action == action)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    if date_from:
        query = query.filter(AuditLog.timestamp >= datetime.combine(date_from, datetime.min.time()))

    if date_to:
        # Include the entire day
        query = query.filter(AuditLog.timestamp < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    logs = (
        query.order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    # Build responses with annotation counts
    items = []
    for log in logs:
        annotation_count = db.query(func.count(AuditAnnotation.id)).filter(
            AuditAnnotation.audit_log_id == log.id
        ).scalar()

        items.append(AuditLogResponse(
            id=log.id,
            table_name=log.table_name,
            record_id=log.record_id,
            action=log.action,
            old_values=log.get_old_values_dict(),
            new_values=log.get_new_values_dict(),
            user_id=log.user_id,
            username=log.user.username if log.user else "System",
            timestamp=log.timestamp,
            ip_address=log.ip_address,
            reason=log.reason,
            annotation_count=annotation_count,
        ))

    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def build_audit_entry(log: AuditLog, db, context_prefix: str = None) -> AuditEntryDisplay:
    """Build an audit entry display object from an audit log.

    Args:
        log: The audit log entry
        db: Database session for annotation count query
        context_prefix: Optional prefix for field names (e.g., test_type)
    """
    old_values = log.get_old_values_dict()
    new_values = log.get_new_values_dict()

    # Check if this is a bulk operation
    is_bulk = new_values.get("_bulk_operation", False) if new_values else False
    bulk_summary = new_values.get("_summary") if is_bulk else None

    # Get annotation count
    annotation_count = db.query(func.count(AuditAnnotation.id)).filter(
        AuditAnnotation.audit_log_id == log.id
    ).scalar()

    return AuditEntryDisplay(
        id=log.id,
        action=log.action.value,
        action_display=format_action_display(log.action),
        timestamp=log.timestamp,
        timestamp_display=format_timestamp(log.timestamp),
        username=log.user.username if log.user else "System",
        changes=build_field_changes(old_values, new_values, context_prefix),
        reason=log.reason,
        is_bulk_operation=is_bulk,
        bulk_summary=bulk_summary,
        annotation_count=annotation_count,
    )


def _get_comprehensive_audit_logs(
    db,
    table_name: str,
    record_id: int,
) -> List[tuple]:
    """
    Get all audit logs for a record, including related records.

    For lots, this includes:
    - Direct lot audit logs (context_prefix=None)
    - Related test_results audit logs (context_prefix=test_type)
    - Related COA releases audit logs (context_prefix="COA Release")

    Returns:
        List of (AuditLog, context_prefix) tuples sorted by timestamp descending.
    """
    results = []

    # Get direct audit entries for the record
    logs = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.user))
        .filter(
            AuditLog.table_name == table_name.lower(),
            AuditLog.record_id == record_id,
        )
        .all()
    )

    # Add direct logs with no context prefix
    for log in logs:
        results.append((log, None))

    # If viewing a lot, also get related test result entries
    if table_name.lower() == "lots":
        # Find test result IDs for this lot
        test_results = (
            db.query(TestResult.id, TestResult.test_type)
            .filter(TestResult.lot_id == record_id)
            .all()
        )

        if test_results:
            # Build a mapping of test_result_id -> test_type for context
            test_type_map = {tr.id: tr.test_type for tr in test_results}
            test_result_ids = list(test_type_map.keys())

            # Get audit entries for those test results
            test_logs = (
                db.query(AuditLog)
                .options(joinedload(AuditLog.user))
                .filter(
                    AuditLog.table_name == "test_results",
                    AuditLog.record_id.in_(test_result_ids),
                )
                .all()
            )

            # Add with test_type as context prefix
            for log in test_logs:
                context_prefix = test_type_map.get(log.record_id)
                results.append((log, context_prefix))

        # Also get COA release entries for this lot
        coa_releases = (
            db.query(COARelease.id, COARelease.product_id)
            .filter(COARelease.lot_id == record_id)
            .all()
        )

        if coa_releases:
            coa_release_ids = [cr.id for cr in coa_releases]

            # Get audit entries for those COA releases
            coa_logs = (
                db.query(AuditLog)
                .options(joinedload(AuditLog.user))
                .filter(
                    AuditLog.table_name == "coa_releases",
                    AuditLog.record_id.in_(coa_release_ids),
                )
                .all()
            )

            # Add with "COA Release" as context prefix
            for log in coa_logs:
                results.append((log, "COA Release"))

        # Also get retest request entries for this lot
        retest_requests = (
            db.query(RetestRequest.id, RetestRequest.reference_number)
            .filter(RetestRequest.lot_id == record_id)
            .all()
        )

        if retest_requests:
            # Build a mapping of retest_request_id -> reference_number for context
            retest_ref_map = {rr.id: rr.reference_number for rr in retest_requests}
            retest_request_ids = list(retest_ref_map.keys())

            # Get audit entries for those retest requests
            retest_logs = (
                db.query(AuditLog)
                .options(joinedload(AuditLog.user))
                .filter(
                    AuditLog.table_name == "retest_requests",
                    AuditLog.record_id.in_(retest_request_ids),
                )
                .all()
            )

            # Add with retest reference as context prefix
            for log in retest_logs:
                context_prefix = f"Retest: {retest_ref_map.get(log.record_id, 'Unknown')}"
                results.append((log, context_prefix))

    # Sort all entries by timestamp descending
    results.sort(key=lambda x: x[0].timestamp, reverse=True)

    return results


@router.get("/{table_name}/{record_id}/trail", response_model=AuditTrailResponse)
async def get_audit_trail(
    table_name: str,
    record_id: int,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> AuditTrailResponse:
    """
    Get complete audit trail for a specific record (QC Manager or Admin only).

    Returns all audit entries for the specified table/record, formatted
    for frontend display.

    For lots, this also includes audit entries for related test results,
    with the test_type shown as context in field names.
    """
    # Use helper to get all related audit logs
    log_tuples = _get_comprehensive_audit_logs(db, table_name, record_id)

    # Build display entries from log tuples
    entries = [
        build_audit_entry(log, db, context_prefix=context_prefix)
        for log, context_prefix in log_tuples
    ]

    return AuditTrailResponse(
        table_name=table_name,
        record_id=record_id,
        entries=entries,
        total=len(entries),
    )


# ============================================================================
# Annotation Endpoints
# ============================================================================


@router.get("/{audit_id}/annotations", response_model=AuditAnnotationListResponse)
async def list_annotations(
    audit_id: int,
    db: DbSession,
    current_user: QCManagerOrAdmin,
) -> AuditAnnotationListResponse:
    """List all annotations for an audit log entry (QC Manager or Admin only)."""
    # Verify audit log exists
    audit_log = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
    if not audit_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found",
        )

    annotations = (
        db.query(AuditAnnotation)
        .options(joinedload(AuditAnnotation.user))
        .filter(AuditAnnotation.audit_log_id == audit_id)
        .order_by(AuditAnnotation.created_at.desc())
        .all()
    )

    items = [
        AuditAnnotationResponse(
            id=ann.id,
            audit_log_id=ann.audit_log_id,
            user_id=ann.user_id,
            username=ann.user.username if ann.user else None,
            comment=ann.comment,
            attachment_filename=ann.attachment_filename,
            attachment_size=ann.attachment_size,
            attachment_hash=ann.attachment_hash,
            created_at=ann.created_at,
        )
        for ann in annotations
    ]

    return AuditAnnotationListResponse(items=items, total=len(items))


@router.post("/{audit_id}/annotations", response_model=AuditAnnotationResponse, status_code=status.HTTP_201_CREATED)
async def create_annotation(
    audit_id: int,
    db: DbSession,
    current_user: QCManagerOrAdmin,
    comment: Optional[str] = None,
    file: Optional[UploadFile] = File(None),
) -> AuditAnnotationResponse:
    """
    Add a comment or attachment to an audit log entry (QC Manager or Admin only).

    Either comment or file must be provided (or both).
    Max 5 attachments per audit entry. Max 10MB per attachment.
    Attachments are stored in R2 (production) or local storage (development).
    """
    # Verify audit log exists
    audit_log = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
    if not audit_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found",
        )

    # Validate that at least one of comment or file is provided
    if not comment and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either comment or file attachment must be provided",
        )

    # Check attachment limit if file provided
    if file:
        existing_attachments = (
            db.query(func.count(AuditAnnotation.id))
            .filter(
                AuditAnnotation.audit_log_id == audit_id,
                AuditAnnotation.attachment_filename.isnot(None),
            )
            .scalar()
        )

        if existing_attachments >= MAX_ATTACHMENTS_PER_ENTRY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum {MAX_ATTACHMENTS_PER_ENTRY} attachments per audit entry",
            )

    # Create annotation
    annotation = AuditAnnotation(
        audit_log_id=audit_id,
        user_id=current_user.id,
        comment=comment.strip() if comment else None,
    )

    # Handle file upload to storage
    if file:
        file_content = await file.read()

        if len(file_content) > MAX_ATTACHMENT_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum of {MAX_ATTACHMENT_SIZE_BYTES // (1024*1024)}MB",
            )

        file_hash = hashlib.sha256(file_content).hexdigest()

        # Generate unique storage key
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        safe_name = "".join(
            c if c.isalnum() or c in ".-_" else "_"
            for c in (file.filename or "attachment")
        )
        storage_key = f"attachments/{timestamp}_{unique_id}_{safe_name}"

        # Determine content type
        content_type = file.content_type or "application/octet-stream"

        # Upload to storage
        storage = get_storage_service()
        storage.upload(file_content, storage_key, content_type=content_type)

        # Set metadata on annotation
        annotation.set_attachment_metadata(
            filename=file.filename or "attachment",
            storage_key=storage_key,
            file_size=len(file_content),
            file_hash=file_hash,
        )

    db.add(annotation)
    db.commit()
    db.refresh(annotation)

    return AuditAnnotationResponse(
        id=annotation.id,
        audit_log_id=annotation.audit_log_id,
        user_id=annotation.user_id,
        username=current_user.username,
        comment=annotation.comment,
        attachment_filename=annotation.attachment_filename,
        attachment_size=annotation.attachment_size,
        attachment_hash=annotation.attachment_hash,
        created_at=annotation.created_at,
    )


@router.get("/{audit_id}/annotations/{annotation_id}/download")
async def download_attachment(
    audit_id: int,
    annotation_id: int,
    db: DbSession,
    current_user: QCManagerOrAdmin,
):
    """
    Download an attachment from an annotation (QC Manager or Admin only).

    For R2 storage: Returns a redirect to a presigned URL (1-hour expiry).
    For local storage: Returns the file content directly.
    """
    annotation = (
        db.query(AuditAnnotation)
        .filter(
            AuditAnnotation.id == annotation_id,
            AuditAnnotation.audit_log_id == audit_id,
        )
        .first()
    )

    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotation not found",
        )

    if not annotation.attachment_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No attachment found",
        )

    storage = get_storage_service()

    # For R2 storage, redirect to presigned URL
    if settings.storage_backend == "r2":
        presigned_url = storage.get_presigned_url(annotation.attachment_key)
        return RedirectResponse(url=presigned_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # For local storage, download and return directly
    try:
        file_content = storage.download(annotation.attachment_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file not found in storage",
        )

    return Response(
        content=file_content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{annotation.attachment_filename}"'
        },
    )


# ============================================================================
# Export Endpoints
# ============================================================================


def _get_annotations_for_log(db, audit_log_id: int) -> tuple:
    """
    Get annotation count and concatenated text for an audit log entry.

    Returns:
        Tuple of (count, concatenated_text) where concatenated_text is
        "user1: comment1 | user2: comment2" format, or empty string if none.
    """
    annotations = (
        db.query(AuditAnnotation)
        .options(joinedload(AuditAnnotation.user))
        .filter(AuditAnnotation.audit_log_id == audit_log_id)
        .order_by(AuditAnnotation.created_at.asc())
        .all()
    )

    if not annotations:
        return (0, "")

    annotation_texts = []
    for ann in annotations:
        if ann.comment:
            username = ann.user.username if ann.user else "Unknown"
            annotation_texts.append(f"{username}: {ann.comment}")

    return (len(annotations), " | ".join(annotation_texts))


@router.get("/export/csv")
async def export_audit_csv(
    db: DbSession,
    current_user: QCManagerOrAdmin,
    table_name: Optional[str] = None,
    record_id: Optional[int] = None,
    action: Optional[AuditAction] = None,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> StreamingResponse:
    """
    Export filtered audit logs as CSV (QC Manager or Admin only).

    When table_name AND record_id are provided, exports detailed view
    with one row per field change (matching UI's Detailed tab) including
    related records (test results, COA releases for lots).

    Otherwise, exports summary view for global/filtered exports.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # When exporting for a specific record, use comprehensive detailed view
    if table_name and record_id is not None:
        # Use comprehensive helper to get all related logs
        log_tuples = _get_comprehensive_audit_logs(db, table_name, record_id)

        # Detailed view header - one row per field change
        writer.writerow([
            "Timestamp",
            "User",
            "Action",
            "Context",
            "Field",
            "Old",
            "New",
            "Reason",
            "Annotation Count",
            "Annotations",
        ])

        # Data rows - flatten each log's changes into individual rows
        for log, context_prefix in log_tuples:
            old_values = log.get_old_values_dict()
            new_values = log.get_new_values_dict()
            # Pass context_prefix=None so Field column doesn't include prefix
            # (Context column already shows the context separately)
            field_changes = build_field_changes(old_values, new_values, context_prefix=None)
            annotation_count, annotations_text = _get_annotations_for_log(db, log.id)

            # If no field changes (e.g., bulk operation), still output one row
            if not field_changes:
                writer.writerow([
                    log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    log.user.username if log.user else "System",
                    format_action_display(log.action),
                    context_prefix or "",
                    "",  # No specific field
                    "",
                    "",
                    log.reason or "",
                    annotation_count,
                    annotations_text,
                ])
            else:
                # One row per field change
                for change in field_changes:
                    writer.writerow([
                        log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        log.user.username if log.user else "System",
                        format_action_display(log.action),
                        context_prefix or "",
                        change.field,
                        change.display_old or "",
                        change.display_new or "",
                        log.reason or "",
                        annotation_count,
                        annotations_text,
                    ])

        filename = f"audit_export_{table_name}_{record_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    else:
        # Global/filtered export - use existing summary format
        query = db.query(AuditLog).options(joinedload(AuditLog.user))

        # Apply filters
        if table_name:
            query = query.filter(AuditLog.table_name == table_name.lower())
        if action:
            query = query.filter(AuditLog.action == action)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if date_from:
            query = query.filter(AuditLog.timestamp >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            query = query.filter(AuditLog.timestamp < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))

        logs = query.order_by(AuditLog.timestamp.desc()).all()

        # Summary header
        writer.writerow([
            "ID",
            "Timestamp",
            "Table",
            "Record ID",
            "Action",
            "Username",
            "Changes",
            "Reason",
            "IP Address",
        ])

        # Data rows
        for log in logs:
            changes = log.get_changes()
            changes_str = "; ".join(
                f"{k}: {v.get('from', 'N/A')} → {v.get('to', 'N/A')}"
                for k, v in changes.items()
                if isinstance(v, dict) and "from" in v
            ) if changes else ""

            writer.writerow([
                log.id,
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                log.table_name,
                log.record_id,
                format_action_display(log.action),
                log.user.username if log.user else "System",
                changes_str,
                log.reason or "",
                log.ip_address or "",
            ])

        filename = f"audit_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        },
    )


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


@router.get("/export/pdf")
async def export_audit_pdf(
    db: DbSession,
    current_user: QCManagerOrAdmin,
    table_name: Optional[str] = None,
    record_id: Optional[int] = None,
    action: Optional[AuditAction] = None,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> StreamingResponse:
    """
    Export filtered audit logs as PDF (QC Manager or Admin only).

    When table_name AND record_id are provided, exports detailed view
    with one row per field change (matching UI's Detailed tab) including
    related records (test results, COA releases for lots).

    Otherwise, exports summary view for global/filtered exports.
    """
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import inch

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), leftMargin=0.5*inch, rightMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()

    # Custom styles for table cells
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=7,
        leading=9,
        wordWrap='CJK',
    )

    def wrap_text(text: str, max_len: int = 40) -> str:
        """Wrap long text for table cells."""
        if not text:
            return ""
        text = str(text)
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."

    # When exporting for a specific record, use comprehensive detailed view
    if table_name and record_id is not None:
        log_tuples = _get_comprehensive_audit_logs(db, table_name, record_id)

        title = f"Audit Trail Export - {table_name.title()} #{record_id}"
        filename = f"audit_export_{table_name}_{record_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # Header
        elements.append(Paragraph(title, styles['Heading1']))
        elements.append(Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}",
            styles['Normal']
        ))
        elements.append(Spacer(1, 0.25*inch))

        # Table data
        table_data = [["Timestamp", "User", "Action", "Context", "Field", "Old", "New", "Reason"]]

        for log, context_prefix in log_tuples:
            old_values = log.get_old_values_dict()
            new_values = log.get_new_values_dict()
            field_changes = build_field_changes(old_values, new_values, context_prefix=None)

            if not field_changes:
                table_data.append([
                    log.timestamp.strftime("%Y-%m-%d %H:%M"),
                    log.user.username if log.user else "System",
                    format_action_display(log.action),
                    context_prefix or "",
                    "",
                    "",
                    "",
                    wrap_text(log.reason or ""),
                ])
            else:
                for change in field_changes:
                    table_data.append([
                        log.timestamp.strftime("%Y-%m-%d %H:%M"),
                        log.user.username if log.user else "System",
                        format_action_display(log.action),
                        context_prefix or "",
                        wrap_text(change.field),
                        wrap_text(change.display_old or ""),
                        wrap_text(change.display_new or ""),
                        wrap_text(log.reason or ""),
                    ])

        # Column widths for detailed view
        col_widths = [1.1*inch, 0.8*inch, 0.7*inch, 0.9*inch, 1.2*inch, 1.5*inch, 1.5*inch, 1.3*inch]

    else:
        # Global/filtered export
        query = db.query(AuditLog).options(joinedload(AuditLog.user))

        if table_name:
            query = query.filter(AuditLog.table_name == table_name.lower())
        if action:
            query = query.filter(AuditLog.action == action)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if date_from:
            query = query.filter(AuditLog.timestamp >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            query = query.filter(AuditLog.timestamp < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))

        logs = query.order_by(AuditLog.timestamp.desc()).all()

        title = "Audit Trail Export"
        filename = f"audit_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # Header
        elements.append(Paragraph(title, styles['Heading1']))
        elements.append(Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y %I:%M %p')} | Total: {len(logs)} entries",
            styles['Normal']
        ))
        elements.append(Spacer(1, 0.25*inch))

        # Table data
        table_data = [["Timestamp", "Table", "Record", "Action", "User", "Changes", "Reason"]]

        for log in logs:
            changes = log.get_changes()
            changes_str = "; ".join(
                f"{k}: {v.get('from', 'N/A')} → {v.get('to', 'N/A')}"
                for k, v in (changes or {}).items()
                if isinstance(v, dict) and "from" in v
            )

            table_data.append([
                log.timestamp.strftime("%Y-%m-%d %H:%M"),
                log.table_name,
                str(log.record_id),
                format_action_display(log.action),
                log.user.username if log.user else "System",
                wrap_text(changes_str, 50),
                wrap_text(log.reason or ""),
            ])

        # Column widths for summary view
        col_widths = [1.1*inch, 0.9*inch, 0.6*inch, 0.8*inch, 0.8*inch, 3.5*inch, 1.3*inch]

    # Create table with styling
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.2, 0.2)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        # Data rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.Color(0.7, 0.7, 0.7)),
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        },
    )
