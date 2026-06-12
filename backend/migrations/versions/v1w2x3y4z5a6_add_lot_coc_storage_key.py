"""Add coc_storage_key to lots

Revision ID: v1w2x3y4z5a6
Revises: u1v2w3x4y5z6
Create Date: 2026-06-12
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "v1w2x3y4z5a6"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lots", sa.Column("coc_storage_key", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("lots", "coc_storage_key")
