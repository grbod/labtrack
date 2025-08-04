"""Audit service for managing audit trails and compliance logging."""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from src.models.audit import AuditLog
from src.models.user import User
from src.models.enums import AuditAction
from src.services.base import BaseService
from src.utils.logger import logger
import json


class AuditService(BaseService[AuditLog]):
    """
    Service for managing audit trails and compliance logging.

    Provides functionality for:
    - Querying audit logs with filters
    - Generating audit reports
    - Tracking data changes
    - Compliance reporting
    """

    def __init__(self):
        """Initialize audit service."""
        super().__init__(AuditLog)

    def log_action(
        self,
        db: Session,
        table_name: str,
        record_id: int,
        action: AuditAction,
        user_id: Optional[int] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """
        Create an audit log entry.

        Args:
            db: Database session
            table_name: Name of the affected table
            record_id: ID of the affected record
            action: Action performed
            user_id: ID of user performing the action
            old_values: Values before the change
            new_values: Values after the change
            reason: Reason for the action
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Created audit log entry
        """
        return AuditLog.log_change(
            session=db,
            table_name=table_name,
            record_id=record_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            user=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=reason,
        )

    def get_record_history(
        self,
        db: Session,
        table_name: str,
        record_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get complete audit history for a specific record.

        Args:
            db: Database session
            table_name: Table name
            record_id: Record ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit entries with formatted changes
        """
        audit_logs = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == table_name, AuditLog.record_id == record_id)
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        history = []
        for log in audit_logs:
            history_entry = {
                "id": log.id,
                "action": log.action.value,
                "timestamp": log.timestamp,
                "user": log.user.username if log.user else "System",
                "user_id": log.user_id,
                "changes": log.get_changes(),
                "reason": log.reason,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
            }
            history.append(history_entry)

        return history

    def get_user_activity(
        self,
        db: Session,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        actions: Optional[List[AuditAction]] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get audit logs for a specific user.

        Args:
            db: Database session
            user_id: User ID
            start_date: Filter from date
            end_date: Filter to date
            actions: Filter by specific actions
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of user activity entries
        """
        query = db.query(AuditLog).filter(AuditLog.user_id == user_id)

        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)

        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

        if actions:
            query = query.filter(AuditLog.action.in_(actions))

        audit_logs = (
            query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
        )

        activity = []
        for log in audit_logs:
            activity_entry = {
                "id": log.id,
                "timestamp": log.timestamp,
                "table": log.table_name,
                "record_id": log.record_id,
                "action": log.action.value,
                "changes": log.get_changes(),
                "reason": log.reason,
                "ip_address": log.ip_address,
            }
            activity.append(activity_entry)

        return activity

    def search_audit_logs(
        self,
        db: Session,
        table_name: Optional[str] = None,
        action: Optional[AuditAction] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_term: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Search audit logs with multiple filters.

        Args:
            db: Database session
            table_name: Filter by table name
            action: Filter by action type
            user_id: Filter by user
            start_date: Filter from date
            end_date: Filter to date
            search_term: Search in old/new values
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching audit logs
        """
        query = db.query(AuditLog)

        if table_name:
            query = query.filter(AuditLog.table_name == table_name)

        if action:
            query = query.filter(AuditLog.action == action)

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)

        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.filter(
                or_(
                    AuditLog.old_values.ilike(search_pattern),
                    AuditLog.new_values.ilike(search_pattern),
                    AuditLog.reason.ilike(search_pattern),
                )
            )

        return query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()

    def generate_compliance_report(
        self,
        db: Session,
        start_date: datetime,
        end_date: datetime,
        table_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a compliance report for audit logs.

        Args:
            db: Database session
            start_date: Report start date
            end_date: Report end date
            table_names: Optional list of tables to include

        Returns:
            Compliance report dictionary
        """
        query = db.query(AuditLog).filter(
            AuditLog.timestamp >= start_date, AuditLog.timestamp <= end_date
        )

        if table_names:
            query = query.filter(AuditLog.table_name.in_(table_names))

        # Get total counts by action
        action_counts = (
            db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
            .filter(AuditLog.timestamp >= start_date, AuditLog.timestamp <= end_date)
            .group_by(AuditLog.action)
            .all()
        )

        # Get activity by table
        table_activity = (
            db.query(AuditLog.table_name, func.count(AuditLog.id).label("count"))
            .filter(AuditLog.timestamp >= start_date, AuditLog.timestamp <= end_date)
            .group_by(AuditLog.table_name)
            .all()
        )

        # Get most active users
        user_activity = (
            db.query(User.username, func.count(AuditLog.id).label("action_count"))
            .join(AuditLog, AuditLog.user_id == User.id)
            .filter(AuditLog.timestamp >= start_date, AuditLog.timestamp <= end_date)
            .group_by(User.username)
            .order_by(func.count(AuditLog.id).desc())
            .limit(10)
            .all()
        )

        # Get critical actions (deletes and rejects)
        critical_actions = query.filter(
            AuditLog.action.in_([AuditAction.DELETE, AuditAction.REJECT])
        ).count()

        report = {
            "report_period": {
                "start_date": start_date,
                "end_date": end_date,
                "days": (end_date - start_date).days,
            },
            "summary": {
                "total_actions": query.count(),
                "critical_actions": critical_actions,
                "unique_users": db.query(func.count(func.distinct(AuditLog.user_id)))
                .filter(
                    AuditLog.timestamp >= start_date, AuditLog.timestamp <= end_date
                )
                .scalar(),
            },
            "actions_breakdown": {
                action.value: count for action, count in action_counts
            },
            "table_activity": {table: count for table, count in table_activity},
            "top_users": [
                {"username": username, "actions": count}
                for username, count in user_activity
            ],
        }

        return report

    def get_data_changes_summary(
        self,
        db: Session,
        table_name: str,
        field_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get summary of changes to a specific field.

        Args:
            db: Database session
            table_name: Table name
            field_name: Field to track changes for
            start_date: Filter from date
            end_date: Filter to date

        Returns:
            List of field change summaries
        """
        query = db.query(AuditLog).filter(
            AuditLog.table_name == table_name, AuditLog.action == AuditAction.UPDATE
        )

        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)

        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

        audit_logs = query.all()

        changes = []
        for log in audit_logs:
            old_values = log.get_old_values_dict()
            new_values = log.get_new_values_dict()

            # Check if the field changed
            if field_name in old_values and field_name in new_values:
                if old_values[field_name] != new_values[field_name]:
                    changes.append(
                        {
                            "audit_id": log.id,
                            "record_id": log.record_id,
                            "timestamp": log.timestamp,
                            "user": log.user.username if log.user else "System",
                            "old_value": old_values[field_name],
                            "new_value": new_values[field_name],
                            "reason": log.reason,
                        }
                    )

        return changes

    def cleanup_old_logs(
        self, db: Session, retention_days: int = 365, batch_size: int = 1000
    ) -> int:
        """
        Clean up old audit logs based on retention policy.

        Args:
            db: Database session
            retention_days: Number of days to retain logs
            batch_size: Number of records to delete per batch

        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        total_deleted = 0

        while True:
            # Delete in batches to avoid locking
            old_logs = (
                db.query(AuditLog)
                .filter(AuditLog.timestamp < cutoff_date)
                .limit(batch_size)
                .all()
            )

            if not old_logs:
                break

            for log in old_logs:
                db.delete(log)

            db.commit()
            total_deleted += len(old_logs)

            logger.info(f"Deleted batch of {len(old_logs)} old audit logs")

        logger.info(
            f"Cleanup complete. Deleted {total_deleted} audit logs older than {retention_days} days"
        )
        return total_deleted

    def export_audit_logs(
        self,
        db: Session,
        start_date: datetime,
        end_date: datetime,
        format: str = "json",
    ) -> str:
        """
        Export audit logs for a date range.

        Args:
            db: Database session
            start_date: Export start date
            end_date: Export end date
            format: Export format (json or csv)

        Returns:
            Exported data as string
        """
        logs = (
            db.query(AuditLog)
            .filter(AuditLog.timestamp >= start_date, AuditLog.timestamp <= end_date)
            .order_by(AuditLog.timestamp)
            .all()
        )

        if format == "json":
            export_data = []
            for log in logs:
                export_data.append(
                    {
                        "id": log.id,
                        "timestamp": log.timestamp.isoformat(),
                        "table_name": log.table_name,
                        "record_id": log.record_id,
                        "action": log.action.value,
                        "user": log.user.username if log.user else None,
                        "changes": log.get_changes(),
                        "reason": log.reason,
                        "ip_address": log.ip_address,
                        "user_agent": log.user_agent,
                    }
                )
            return json.dumps(export_data, indent=2)

        elif format == "csv":
            # Simple CSV export
            lines = ["timestamp,table,record_id,action,user,reason"]
            for log in logs:
                user = log.user.username if log.user else "System"
                reason = log.reason or ""
                lines.append(
                    f"{log.timestamp},{log.table_name},{log.record_id},"
                    f"{log.action.value},{user},{reason}"
                )
            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported export format: {format}")
