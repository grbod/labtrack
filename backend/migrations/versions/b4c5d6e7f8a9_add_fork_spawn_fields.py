"""Add re-sample fork/spawn lineage fields

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-09

Adds the columns that support composite individualization and the re-sample
SPAWN mechanism (D7):
  * lots.forked_from_lot_id / lots.fork_context — fork lineage on the new lot.
  * test_results.provenance_note — how an inherited result was originally tested.
  * coa_releases.superseded_by_release_id — post-release supersede link.

The new COAReleaseStatus.FORKED enum value needs no schema change: the status
column is a plain VARCHAR with no CHECK constraint.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("lots") as batch_op:
        batch_op.add_column(
            sa.Column("forked_from_lot_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("fork_context", sa.String(length=255), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_lots_forked_from_lot_id",
            "lots",
            ["forked_from_lot_id"],
            ["id"],
        )

    with op.batch_alter_table("test_results") as batch_op:
        batch_op.add_column(
            sa.Column("provenance_note", sa.String(length=255), nullable=True)
        )

    with op.batch_alter_table("coa_releases") as batch_op:
        batch_op.add_column(
            sa.Column("superseded_by_release_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_coa_releases_superseded_by_release_id",
            "coa_releases",
            ["superseded_by_release_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("coa_releases") as batch_op:
        batch_op.drop_constraint(
            "fk_coa_releases_superseded_by_release_id", type_="foreignkey"
        )
        batch_op.drop_column("superseded_by_release_id")

    with op.batch_alter_table("test_results") as batch_op:
        batch_op.drop_column("provenance_note")

    with op.batch_alter_table("lots") as batch_op:
        batch_op.drop_constraint("fk_lots_forked_from_lot_id", type_="foreignkey")
        batch_op.drop_column("fork_context")
        batch_op.drop_column("forked_from_lot_id")
