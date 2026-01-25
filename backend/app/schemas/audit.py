"""Audit trail schemas for API responses and requests."""

from datetime import datetime, date
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, Field, field_validator

from app.models.enums import AuditAction


# ============================================================================
# Audit Log Schemas
# ============================================================================


class AuditLogResponse(BaseModel):
    """Response schema for an audit log entry."""

    id: int
    table_name: str
    record_id: int
    action: AuditAction
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    timestamp: datetime
    ip_address: Optional[str] = None
    reason: Optional[str] = None
    annotation_count: int = 0

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""

    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditLogFilters(BaseModel):
    """Filters for audit log queries."""

    table_name: Optional[str] = None
    record_id: Optional[int] = None
    action: Optional[AuditAction] = None
    user_id: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


# ============================================================================
# Audit Annotation Schemas
# ============================================================================


class AuditAnnotationCreate(BaseModel):
    """Schema for creating an audit annotation."""

    comment: Optional[str] = Field(None, max_length=10000)

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, v):
        if v is not None and v.strip() == "":
            return None
        return v


class AuditAnnotationResponse(BaseModel):
    """Response schema for an audit annotation."""

    id: int
    audit_log_id: int
    user_id: int
    username: Optional[str] = None
    comment: Optional[str] = None
    attachment_filename: Optional[str] = None
    attachment_size: Optional[int] = None
    attachment_hash: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditAnnotationListResponse(BaseModel):
    """List of audit annotations."""

    items: List[AuditAnnotationResponse]
    total: int


# ============================================================================
# Audit Export Schemas
# ============================================================================


class AuditExportRequest(BaseModel):
    """Request schema for exporting audit logs."""

    table_name: Optional[str] = None
    record_id: Optional[int] = None
    action: Optional[AuditAction] = None
    user_id: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    format: str = Field("csv", pattern="^(csv|pdf)$")


# ============================================================================
# Audit Trail Display Schemas (for frontend)
# ============================================================================


class FieldChange(BaseModel):
    """Schema for a single field change."""

    field: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    display_old: Optional[str] = None
    display_new: Optional[str] = None


class AuditEntryDisplay(BaseModel):
    """Display-ready audit entry for frontend."""

    id: int
    action: str
    action_display: str
    timestamp: datetime
    timestamp_display: str
    username: str
    changes: List[FieldChange]
    reason: Optional[str] = None
    is_bulk_operation: bool = False
    bulk_summary: Optional[str] = None
    annotation_count: int = 0


class AuditTrailResponse(BaseModel):
    """Full audit trail for a record."""

    table_name: str
    record_id: int
    entries: List[AuditEntryDisplay]
    total: int


# ============================================================================
# Archive Schemas (kept for backwards compatibility)
# ============================================================================


class ArchivedLotResponse(BaseModel):
    """Archived (completed) lot response for list view."""

    lot_id: int
    product_id: int
    reference_number: str
    lot_number: str
    product_name: str
    brand: str
    flavor: Optional[str] = None
    size: Optional[str] = None
    status: str  # "released" or "rejected"
    completed_at: datetime  # Released or rejected date
    customer_name: Optional[str] = None
    rejection_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class ArchivedLotsListResponse(BaseModel):
    """Paginated list of archived lots."""

    items: List[ArchivedLotResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
