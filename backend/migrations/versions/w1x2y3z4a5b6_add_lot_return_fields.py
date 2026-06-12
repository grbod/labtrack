"""Add return_reason and return_response_note to lots

Revision ID: w1x2y3z4a5b6
Revises: v1w2x3y4z5a6
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "w1x2y3z4a5b6"
down_revision = "v1w2x3y4z5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lots", sa.Column("return_reason", sa.Text(), nullable=True))
    op.add_column("lots", sa.Column("return_response_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("lots", "return_response_note")
    op.drop_column("lots", "return_reason")
