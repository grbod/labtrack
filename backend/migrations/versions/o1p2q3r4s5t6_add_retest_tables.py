"""Add retest_requests and retest_items tables

Revision ID: o1p2q3r4s5t6
Revises: n1o2p3q4r5s6
Create Date: 2026-01-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'o1p2q3r4s5t6'
down_revision: Union[str, None] = 'n1o2p3q4r5s6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create retest tables and add has_pending_retest column to lots."""
    # Create retest_requests table
    op.create_table(
        'retest_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('lot_id', sa.Integer(), nullable=False),
        sa.Column('reference_number', sa.String(length=50), nullable=False),
        sa.Column('retest_number', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'completed', name='reteststatus'), nullable=False),
        sa.Column('requested_by_id', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference_number'),
        sa.ForeignKeyConstraint(['lot_id'], ['lots.id']),
        sa.ForeignKeyConstraint(['requested_by_id'], ['users.id']),
    )
    op.create_index('idx_retest_request_lot', 'retest_requests', ['lot_id'])
    op.create_index('idx_retest_request_status', 'retest_requests', ['status'])
    op.create_index('idx_retest_request_reference', 'retest_requests', ['reference_number'])

    # Create retest_items table
    op.create_table(
        'retest_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('retest_request_id', sa.Integer(), nullable=False),
        sa.Column('test_result_id', sa.Integer(), nullable=False),
        sa.Column('original_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['retest_request_id'], ['retest_requests.id']),
        sa.ForeignKeyConstraint(['test_result_id'], ['test_results.id']),
    )
    op.create_index('idx_retest_item_request', 'retest_items', ['retest_request_id'])
    op.create_index('idx_retest_item_test_result', 'retest_items', ['test_result_id'])

    # Add has_pending_retest column to lots table
    op.add_column('lots', sa.Column('has_pending_retest', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Remove retest tables and has_pending_retest column."""
    # Remove has_pending_retest column from lots
    op.drop_column('lots', 'has_pending_retest')

    # Drop retest_items table
    op.drop_index('idx_retest_item_test_result', table_name='retest_items')
    op.drop_index('idx_retest_item_request', table_name='retest_items')
    op.drop_table('retest_items')

    # Drop retest_requests table
    op.drop_index('idx_retest_request_reference', table_name='retest_requests')
    op.drop_index('idx_retest_request_status', table_name='retest_requests')
    op.drop_index('idx_retest_request_lot', table_name='retest_requests')
    op.drop_table('retest_requests')

    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS reteststatus")
