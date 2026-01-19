"""Add require_pdf_for_submission to lab_info

Revision ID: m1n2o3p4q5r6
Revises: l1m2n3o4p5q6
Create Date: 2026-01-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm1n2o3p4q5r6'
down_revision: Union[str, None] = 'l1m2n3o4p5q6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add require_pdf_for_submission column with default True."""
    op.add_column(
        'lab_info',
        sa.Column('require_pdf_for_submission', sa.Boolean(), nullable=False, server_default='true')
    )


def downgrade() -> None:
    """Remove require_pdf_for_submission column."""
    op.drop_column('lab_info', 'require_pdf_for_submission')
