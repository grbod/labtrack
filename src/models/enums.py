"""Enum types for database models."""

import enum


class UserRole(str, enum.Enum):
    """User role enumeration."""

    ADMIN = "admin"
    QC_MANAGER = "qc_manager"
    LAB_TECH = "lab_tech"
    READ_ONLY = "read_only"


class LotType(str, enum.Enum):
    """Lot type enumeration."""

    STANDARD = "standard"
    PARENT_LOT = "parent_lot"
    MULTI_SKU_COMPOSITE = "multi_sku_composite"


class LotStatus(str, enum.Enum):
    """Lot status enumeration."""

    PENDING = "pending"
    TESTED = "tested"
    APPROVED = "approved"
    RELEASED = "released"
    REJECTED = "rejected"


class TestResultStatus(str, enum.Enum):
    """Test result status enumeration."""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"


class ParsingStatus(str, enum.Enum):
    """Parsing queue status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    RESOLVED = "resolved"
    FAILED = "failed"


class AuditAction(str, enum.Enum):
    """Audit log action enumeration."""

    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
