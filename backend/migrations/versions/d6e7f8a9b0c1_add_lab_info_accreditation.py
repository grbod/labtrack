"""Add accreditation fields to lab_info

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-09
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lab_info", sa.Column("accreditation_body", sa.String(200), nullable=True)
    )
    op.add_column(
        "lab_info", sa.Column("accreditation_number", sa.String(100), nullable=True)
    )
    op.add_column(
        "lab_info", sa.Column("accreditation_statement", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("lab_info", "accreditation_statement")
    op.drop_column("lab_info", "accreditation_number")
    op.drop_column("lab_info", "accreditation_body")
