"""Audit log and annotation models for tracking all system changes."""

import gzip
import json
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Enum, Index, LargeBinary
from sqlalchemy.orm import relationship, validates
from app.models.base import BaseModel
from app.models.enums import AuditAction


# Constants for attachment limits
MAX_ATTACHMENTS_PER_ENTRY = 5
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10MB uncompressed


class AuditLog(BaseModel):
    """
    Audit log model for maintaining complete history of system changes.

    Attributes:
        table_name: Name of the table where change occurred
        record_id: ID of the record that was changed
        action: Type of action performed
        old_values: JSON string of values before change
        new_values: JSON string of values after change
        user_id: User who made the change
        timestamp: When the change occurred
        ip_address: IP address of the user (if available)
        user_agent: Browser/client information
        reason: Optional reason for the change (required for certain actions)
    """

    __tablename__ = "audit_logs"

    # Override base model to use custom id and timestamp
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = None  # We use timestamp instead
    updated_at = None  # Audit logs should never be updated

    # Core fields
    table_name = Column(String(50), nullable=False)
    record_id = Column(Integer, nullable=False)
    action = Column(Enum(AuditAction), nullable=False)
    old_values = Column(Text, nullable=True)  # JSON format
    new_values = Column(Text, nullable=True)  # JSON format
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(45), nullable=True)  # Support IPv6
    user_agent = Column(String(255), nullable=True)
    reason = Column(Text, nullable=True)  # Required for rejections/overrides

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    # Indexes for performance
    __table_args__ = (
        Index("idx_audit_table_record", "table_name", "record_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_table_action_timestamp", "table_name", "action", "timestamp"),
    )

    @validates("table_name")
    def validate_table_name(self, key, value):
        """Validate table name is not empty."""
        if not value or not value.strip():
            raise ValueError("Table name cannot be empty")
        return value.strip().lower()

    @validates("record_id")
    def validate_record_id(self, key, value):
        """Validate record ID is non-negative.

        Note: record_id=0 is reserved for bulk operation summary entries.
        Regular audit entries must have a positive record_id.
        """
        if value is None or value < 0:
            raise ValueError("Record ID must be non-negative (0 is reserved for bulk summaries)")
        return value

    @validates("old_values", "new_values")
    def validate_json_values(self, key, value):
        """Validate JSON format of value fields."""
        if value is None:
            return value

        # If it's already a string, validate it's valid JSON
        if isinstance(value, str):
            try:
                json.loads(value)
            except json.JSONDecodeError:
                raise ValueError(f"{key} must be valid JSON")
            return value

        # If it's a dict, convert to JSON string
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Cannot serialize {key} to JSON: {e}")

    @validates("reason")
    def validate_reason(self, key, value):
        """Validate reason is provided for certain actions."""
        if self.action in [AuditAction.REJECT, AuditAction.DELETE] and not value:
            raise ValueError(f"Reason is required for {self.action.value} actions")
        return value

    def get_old_values_dict(self):
        """Get old values as dictionary."""
        if not self.old_values:
            return {}
        try:
            return json.loads(self.old_values)
        except json.JSONDecodeError:
            return {}

    def get_new_values_dict(self):
        """Get new values as dictionary."""
        if not self.new_values:
            return {}
        try:
            return json.loads(self.new_values)
        except json.JSONDecodeError:
            return {}

    def get_changes(self):
        """Get a summary of what changed."""
        old = self.get_old_values_dict()
        new = self.get_new_values_dict()

        if self.action == AuditAction.INSERT:
            return {"created": new}
        elif self.action == AuditAction.DELETE:
            return {"deleted": old}
        else:
            changes = {}
            all_keys = set(old.keys()) | set(new.keys())
            for key in all_keys:
                old_val = old.get(key)
                new_val = new.get(key)
                if old_val != new_val:
                    changes[key] = {"from": old_val, "to": new_val}
            return changes

    @classmethod
    def log_change(
        cls,
        session,
        table_name,
        record_id,
        action,
        old_values=None,
        new_values=None,
        user=None,
        ip_address=None,
        user_agent=None,
        reason=None,
    ):
        """
        Create an audit log entry.

        Args:
            session: Database session
            table_name: Name of the table
            record_id: ID of the record
            action: Action performed
            old_values: Dictionary of old values
            new_values: Dictionary of new values
            user: User object or user_id
            ip_address: Client IP address
            user_agent: Client user agent
            reason: Reason for the action
        """
        user_id = user.id if hasattr(user, "id") else user

        audit_log = cls(
            table_name=table_name,
            record_id=record_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=reason,
        )

        session.add(audit_log)
        return audit_log

    def __repr__(self):
        """String representation of AuditLog."""
        return (
            f"<AuditLog(id={self.id}, table='{self.table_name}', "
            f"record={self.record_id}, action='{self.action.value}', "
            f"timestamp='{self.timestamp}')>"
        )


class AuditAnnotation(BaseModel):
    """
    Model for comments and attachments on audit log entries.

    Allows QC Managers and Admins to add comments and attach files
    to audit entries for additional context.

    Attributes:
        audit_log_id: ID of the associated audit log entry
        user_id: User who created the annotation
        comment: Text comment (optional)
        attachment_filename: Original filename of attachment (optional)
        attachment_data: Compressed (gzip) file contents
        attachment_size: Original uncompressed size in bytes
        attachment_hash: SHA256 hash of original file
        created_at: When the annotation was created
    """

    __tablename__ = "audit_annotations"

    # Override base model to use custom id and timestamps
    id = Column(Integer, primary_key=True, autoincrement=True)
    updated_at = None  # Annotations should never be updated

    # Core fields
    audit_log_id = Column(Integer, ForeignKey("audit_logs.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    comment = Column(Text, nullable=True)

    # Attachment fields
    attachment_filename = Column(String(255), nullable=True)
    attachment_data = Column(LargeBinary, nullable=True)  # Gzip compressed
    attachment_size = Column(Integer, nullable=True)  # Original uncompressed size
    attachment_hash = Column(String(64), nullable=True)  # SHA256 hash

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    audit_log = relationship("AuditLog", backref="annotations")
    user = relationship("User")

    # Indexes for performance
    __table_args__ = (
        Index("idx_audit_annotation_log", "audit_log_id"),
        Index("idx_audit_annotation_user", "user_id"),
        Index("idx_audit_annotation_created", "created_at"),
    )

    @validates("comment", "attachment_data")
    def validate_has_content(self, key, value):
        """Validate that annotation has either comment or attachment."""
        # This validation happens on the field level, so we can't check both
        # We'll handle this in the endpoint
        return value

    def set_attachment(self, filename: str, file_content: bytes, file_hash: str):
        """
        Set attachment with compression.

        Args:
            filename: Original filename
            file_content: Uncompressed file bytes
            file_hash: SHA256 hash of original file
        """
        if len(file_content) > MAX_ATTACHMENT_SIZE_BYTES:
            raise ValueError(
                f"Attachment size ({len(file_content)} bytes) exceeds maximum "
                f"({MAX_ATTACHMENT_SIZE_BYTES} bytes)"
            )

        self.attachment_filename = filename
        self.attachment_size = len(file_content)
        self.attachment_hash = file_hash
        self.attachment_data = gzip.compress(file_content)

    def get_attachment(self) -> bytes:
        """
        Get decompressed attachment data.

        Returns:
            Decompressed file bytes
        """
        if not self.attachment_data:
            return None
        return gzip.decompress(self.attachment_data)

    def __repr__(self):
        """String representation of AuditAnnotation."""
        has_comment = "yes" if self.comment else "no"
        has_attachment = "yes" if self.attachment_filename else "no"
        return (
            f"<AuditAnnotation(id={self.id}, audit_log_id={self.audit_log_id}, "
            f"comment={has_comment}, attachment={has_attachment})>"
        )
