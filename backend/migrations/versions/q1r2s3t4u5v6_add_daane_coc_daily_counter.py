"""Add Daane COC daily counter table.

Revision ID: q1r2s3t4u5v6
Revises: p1q2r3s4t5u6
Create Date: 2026-02-02
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "q1r2s3t4u5v6"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "daane_coc_daily_counters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("counter_date", sa.Date(), nullable=False),
        sa.Column("last_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("counter_date", name="uq_daane_coc_daily_counter_date"),
    )
    op.create_index(
        "idx_daane_coc_daily_counter_date",
        "daane_coc_daily_counters",
        ["counter_date"],
    )


def downgrade():
    op.drop_index("idx_daane_coc_daily_counter_date", table_name="daane_coc_daily_counters")
    op.drop_table("daane_coc_daily_counters")
