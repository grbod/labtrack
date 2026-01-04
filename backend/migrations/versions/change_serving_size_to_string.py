"""change_serving_size_to_string

Revision ID: c8f9a2b3d4e5
Revises: bf8713feb41a
Create Date: 2025-01-03

Change serving_size from Numeric(5,2) to String(50) to support
various serving size formats like "30g", "2 capsules", "1 tsp"
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c8f9a2b3d4e5"
down_revision = "a64a3194d777"
branch_labels = None
depends_on = None


def upgrade():
    # Convert serving_size from Numeric to String
    # First, create a temporary column
    op.add_column("products", sa.Column("serving_size_new", sa.String(50), nullable=True))

    # Copy data, converting numeric to string with 'g' suffix for existing values
    op.execute("""
        UPDATE products
        SET serving_size_new = CASE
            WHEN serving_size IS NOT NULL THEN CAST(serving_size AS VARCHAR) || 'g'
            ELSE NULL
        END
    """)

    # Drop old column and rename new one
    op.drop_column("products", "serving_size")
    op.alter_column("products", "serving_size_new", new_column_name="serving_size")


def downgrade():
    # Convert back to Numeric - this will lose non-numeric values
    op.add_column("products", sa.Column("serving_size_new", sa.Numeric(5, 2), nullable=True))

    # Try to extract numeric values (strip 'g' suffix if present)
    op.execute("""
        UPDATE products
        SET serving_size_new = CASE
            WHEN serving_size ~ '^[0-9]+\\.?[0-9]*g?$'
            THEN CAST(REPLACE(serving_size, 'g', '') AS NUMERIC(5,2))
            ELSE NULL
        END
    """)

    op.drop_column("products", "serving_size")
    op.alter_column("products", "serving_size_new", new_column_name="serving_size")
