"""Add batch_number to lot_products and backfill composites from COMP- lot numbers.

Revision ID: t1u2v3w4x5y6
Revises: s1t2u3v4w5x6
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "t1u2v3w4x5y6"
down_revision = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "lot_products", sa.Column("batch_number", sa.String(length=50), nullable=True)
    )

    # Backfill multi-SKU composites whose lot number encodes the per-SKU batch
    # numbers positionally ("COMP-" + batch numbers joined with "-"). Only assign
    # when the segment count matches the product row count; batch numbers that
    # themselves contain dashes make the parse ambiguous, so those lots stay NULL.
    conn = op.get_bind()
    composites = conn.execute(
        sa.text(
            "SELECT id, lot_number FROM lots "
            "WHERE lot_type = 'MULTI_SKU_COMPOSITE' AND lot_number LIKE 'COMP-%'"
        )
    ).fetchall()

    for lot_id, lot_number in composites:
        segments = lot_number[len("COMP-"):].split("-")
        rows = conn.execute(
            sa.text(
                "SELECT rowid, product_id FROM lot_products "
                "WHERE lot_id = :lot_id ORDER BY rowid"
            ),
            {"lot_id": lot_id},
        ).fetchall()
        if len(segments) != len(rows) or any(not s for s in segments):
            continue
        for (rowid, _product_id), batch_number in zip(rows, segments):
            conn.execute(
                sa.text(
                    "UPDATE lot_products SET batch_number = :batch_number "
                    "WHERE rowid = :rowid"
                ),
                {"batch_number": batch_number, "rowid": rowid},
            )


def downgrade():
    # batch mode required on SQLite: lot_products has a CHECK constraint
    with op.batch_alter_table("lot_products") as batch_op:
        batch_op.drop_column("batch_number")
