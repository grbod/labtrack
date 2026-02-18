"""Add Daane test mappings table.

Revision ID: p1q2r3s4t5u6
Revises: o1p2q3r4s5t6
Create Date: 2026-02-02
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "p1q2r3s4t5u6"
down_revision = "o1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "daane_test_mappings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("lab_test_type_id", sa.Integer(), nullable=False),
        sa.Column("daane_method", sa.String(length=255), nullable=True),
        sa.Column("match_type", sa.String(length=50), nullable=False, server_default="unmapped"),
        sa.Column("match_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["lab_test_type_id"], ["lab_test_types.id"]),
        sa.UniqueConstraint("lab_test_type_id", name="uq_daane_test_mapping_lab_test_type_id"),
    )
    op.create_index(
        "idx_daane_test_mapping_lab_test_type_id",
        "daane_test_mappings",
        ["lab_test_type_id"],
    )


def downgrade():
    op.drop_index("idx_daane_test_mapping_lab_test_type_id", table_name="daane_test_mappings")
    op.drop_table("daane_test_mappings")
