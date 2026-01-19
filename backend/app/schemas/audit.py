"""Audit schemas for request/response validation."""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """Single audit log entry response."""

    id: int
    action: str  # AuditAction enum value (insert, update, delete, approve, reject, override)
    timestamp: datetime
    user_id: Optional[int] = None
    username: Optional[str] = None  # Denormalized for display
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    changes: Dict[str, Dict[str, Any]] = {}  # Computed diff: {"field": {"from": x, "to": y}}
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    table_name: str
    record_id: int

    model_config = {"from_attributes": True}


class AuditHistoryResponse(BaseModel):
    """Paginated audit history response."""

    items: List[AuditLogResponse]
    total: int
    table_name: str
    record_id: int


class LotAuditHistoryResponse(BaseModel):
    """Complete audit history for a lot including related records."""

    items: List[AuditLogResponse]
    total: int
    lot_id: int
    # Summary of tables audited
    tables_included: List[str] = []


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
