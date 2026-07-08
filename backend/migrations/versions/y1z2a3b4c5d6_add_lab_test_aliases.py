"""Add lab test aliases

Revision ID: y1z2a3b4c5d6
Revises: x1y2z3a4b5c6
Create Date: 2026-06-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "y1z2a3b4c5d6"
down_revision = "x1y2z3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_test_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("raw_phrase", sa.String(length=255), nullable=False),
        sa.Column("normalized_key", sa.String(length=255), nullable=False),
        sa.Column("lab_name", sa.String(length=255), nullable=True),
        sa.Column("lab_test_type_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("suggestion_count", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_result_import_id", sa.Integer(), nullable=True),
        sa.Column("last_lot_id", sa.Integer(), nullable=True),
        sa.Column("last_filename", sa.String(length=255), nullable=True),
        sa.Column("last_suggested_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("disabled_by_id", sa.Integer(), nullable=True),
        sa.Column("disabled_at", sa.DateTime(), nullable=True),
        sa.Column("disable_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["disabled_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["lab_test_type_id"], ["lab_test_types.id"]),
        sa.ForeignKeyConstraint(["last_lot_id"], ["lots.id"]),
        sa.ForeignKeyConstraint(["last_result_import_id"], ["result_imports.id"]),
        sa.ForeignKeyConstraint(["last_suggested_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_lab_test_alias_key_lab_status",
        "lab_test_aliases",
        ["normalized_key", "lab_name", "status"],
    )
    op.create_index(
        "idx_lab_test_alias_status_updated",
        "lab_test_aliases",
        ["status", "updated_at"],
    )
    op.create_index(
        "idx_lab_test_alias_type",
        "lab_test_aliases",
        ["lab_test_type_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_lab_test_alias_type", table_name="lab_test_aliases")
    op.drop_index("idx_lab_test_alias_status_updated", table_name="lab_test_aliases")
    op.drop_index("idx_lab_test_alias_key_lab_status", table_name="lab_test_aliases")
    op.drop_table("lab_test_aliases")
