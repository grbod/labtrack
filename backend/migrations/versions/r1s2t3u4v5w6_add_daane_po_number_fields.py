"""Add Daane PO number fields to lots and retest requests.

Revision ID: r1s2t3u4v5w6
Revises: q1r2s3t4u5v6
Create Date: 2026-02-02
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "r1s2t3u4v5w6"
down_revision = "q1r2s3t4u5v6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("lots", sa.Column("daane_po_number", sa.String(length=20), nullable=True))
    op.add_column("retest_requests", sa.Column("daane_po_number", sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column("retest_requests", "daane_po_number")
    op.drop_column("lots", "daane_po_number")
