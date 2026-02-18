"""Add audit_annotations table

Revision ID: n1o2p3q4r5s6
Revises: m1n2o3p4q5r6
Create Date: 2026-01-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'n1o2p3q4r5s6'
down_revision: Union[str, None] = 'm1n2o3p4q5r6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create audit_annotations table for comments and attachments on audit entries."""
    op.create_table(
        'audit_annotations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('audit_log_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('attachment_filename', sa.String(length=255), nullable=True),
        sa.Column('attachment_key', sa.String(length=500), nullable=True),  # R2/storage key
        sa.Column('attachment_size', sa.Integer(), nullable=True),
        sa.Column('attachment_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['audit_log_id'], ['audit_logs.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('idx_audit_annotation_log', 'audit_annotations', ['audit_log_id'])
    op.create_index('idx_audit_annotation_user', 'audit_annotations', ['user_id'])
    op.create_index('idx_audit_annotation_created', 'audit_annotations', ['created_at'])


def downgrade() -> None:
    """Remove audit_annotations table."""
    op.drop_index('idx_audit_annotation_created', table_name='audit_annotations')
    op.drop_index('idx_audit_annotation_user', table_name='audit_annotations')
    op.drop_index('idx_audit_annotation_log', table_name='audit_annotations')
    op.drop_table('audit_annotations')
