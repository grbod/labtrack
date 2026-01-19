"""add_lab_info

Revision ID: h1b2c3d4e5f6
Revises: g1a2b3c4d5e6
Create Date: 2026-01-10 23:00:00.000000

"""

from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "h1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "g1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create lab_info table with default values."""
    # Create lab_info table
    op.create_table(
        "lab_info",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("phone", sa.String(50), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("logo_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Insert default row with default values
    op.execute(
        sa.text(
            """
            INSERT INTO lab_info (company_name, address, phone, email, logo_path, created_at, updated_at)
            VALUES (:company_name, :address, :phone, :email, NULL, :now, :now)
            """
        ).bindparams(
            company_name="Your Company Name",
            address="123 Quality Street, Lab City, LC 12345",
            phone="(555) 123-4567",
            email="lab@company.com",
            now=datetime.utcnow(),
        )
    )


def downgrade() -> None:
    """Drop lab_info table."""
    op.drop_table("lab_info")
