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

    AWAITING_RESULTS = "awaiting_results"
    PARTIAL_RESULTS = "partial_results"  # Some results in, missing required tests
    NEEDS_ATTENTION = "needs_attention"  # All required tests complete but some fail specs
    UNDER_REVIEW = "under_review"  # All required tests complete and pass
    AWAITING_RELEASE = "awaiting_release"  # Lab Tech submitted, awaiting QC Manager approval
    APPROVED = "approved"
    RELEASED = "released"
    REJECTED = "rejected"


class TestResultStatus(str, enum.Enum):
    """Test result status enumeration."""

    DRAFT = "draft"
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
    OVERRIDE = "override"
    VALIDATION_FAILED = "validation_failed"


class COAReleaseStatus(str, enum.Enum):
    """COA release status enumeration."""

    AWAITING_RELEASE = "awaiting_release"
    RELEASED = "released"


class RetestStatus(str, enum.Enum):
    """Retest request status enumeration."""

    PENDING = "pending"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"
