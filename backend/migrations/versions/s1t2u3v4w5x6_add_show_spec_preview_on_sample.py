"""add show_spec_preview_on_sample

Revision ID: s1t2u3v4w5x6
Revises: r1s2t3u4v5w6
Create Date: 2026-02-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "s1t2u3v4w5x6"
down_revision = "r1s2t3u4v5w6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lab_info",
        sa.Column(
            "show_spec_preview_on_sample",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )


def downgrade() -> None:
    op.drop_column("lab_info", "show_spec_preview_on_sample")
