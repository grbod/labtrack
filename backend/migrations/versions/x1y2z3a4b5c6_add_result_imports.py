"""Add results importer tables

Revision ID: x1y2z3a4b5c6
Revises: w1x2y3z4a5b6
Create Date: 2026-06-21
"""

from __future__ import annotations

import json
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "x1y2z3a4b5c6"
down_revision = "w1x2y3z4a5b6"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(sa.Text(), "sqlite")


def _normalize_storage_key(value: str | None) -> str:
    if not value:
        return ""
    return value if value.startswith("pdfs/") else f"pdfs/{value}"


def _decode_attached_pdfs(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [value]
    return value


def _backfill_attached_pdfs_to_objects(bind) -> None:
    lots = sa.table(
        "lots",
        sa.column("id", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("attached_pdfs", sa.JSON),
    )
    rows = list(
        bind.execute(
            sa.select(lots.c.id, lots.c.created_at, lots.c.attached_pdfs).where(
                lots.c.attached_pdfs.isnot(None)
            )
        )
    )
    for lot_id, created_at, attached_pdfs in rows:
        decoded = _decode_attached_pdfs(attached_pdfs)
        if not isinstance(decoded, list):
            continue
        added_at = (created_at or datetime.utcnow()).isoformat()
        converted = []
        changed = False
        for entry in decoded:
            if isinstance(entry, str):
                storage_key = _normalize_storage_key(entry)
                converted.append(
                    {
                        "filename": storage_key.rsplit("/", 1)[-1],
                        "storage_key": storage_key,
                        "source": "legacy",
                        "import_id": None,
                        "added_at": added_at,
                    }
                )
                changed = True
            else:
                converted.append(entry)
        if changed:
            bind.execute(
                lots.update().where(lots.c.id == lot_id).values(attached_pdfs=converted)
            )


def _downgrade_attached_pdfs_to_filenames(bind) -> None:
    lots = sa.table(
        "lots",
        sa.column("id", sa.Integer),
        sa.column("attached_pdfs", sa.JSON),
    )
    rows = list(
        bind.execute(
            sa.select(lots.c.id, lots.c.attached_pdfs).where(
                lots.c.attached_pdfs.isnot(None)
            )
        )
    )
    for lot_id, attached_pdfs in rows:
        decoded = _decode_attached_pdfs(attached_pdfs)
        if not isinstance(decoded, list):
            continue
        converted = [
            (
                _normalize_storage_key(
                    entry.get("storage_key") or entry.get("filename")
                )
                if isinstance(entry, dict)
                else entry
            )
            for entry in decoded
        ]
        bind.execute(
            lots.update().where(lots.c.id == lot_id).values(attached_pdfs=converted)
        )


def upgrade() -> None:
    op.create_table(
        "result_imports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column("updated_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("extracted_data", _json_type(), nullable=True),
        sa.Column("match_candidates", _json_type(), nullable=True),
        sa.Column("warnings", _json_type(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("selected_lot_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("confirmed_by_id", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("reverted_at", sa.DateTime(), nullable=True),
        sa.Column("openrouter_model", sa.String(length=120), nullable=True),
        sa.Column("usage_metadata", _json_type(), nullable=True),
        sa.Column("duplicate_of_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["selected_lot_id"], ["lots.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["result_imports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_result_import_hash_status", "result_imports", ["file_hash", "status"]
    )
    op.create_index("idx_result_import_created", "result_imports", ["created_at"])
    op.create_index(
        op.f("ix_result_imports_file_hash"), "result_imports", ["file_hash"]
    )
    op.create_index(op.f("ix_result_imports_status"), "result_imports", ["status"])

    op.create_table(
        "result_import_ledgers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column("updated_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column("result_import_id", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("created_result_ids", _json_type(), nullable=True),
        sa.Column("updated_results", _json_type(), nullable=True),
        sa.Column("pdf_attachment", _json_type(), nullable=True),
        sa.Column("applied_rows", _json_type(), nullable=True),
        sa.Column("applied_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["result_import_id"], ["result_imports.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"]),
        sa.ForeignKeyConstraint(["applied_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_result_import_ledgers_result_import_id"),
        "result_import_ledgers",
        ["result_import_id"],
    )
    op.create_index(
        op.f("ix_result_import_ledgers_lot_id"), "result_import_ledgers", ["lot_id"]
    )

    bind = op.get_bind()
    _backfill_attached_pdfs_to_objects(bind)
    if "parsing_queue" in inspect(bind).get_table_names():
        op.drop_table("parsing_queue")


def downgrade() -> None:
    bind = op.get_bind()
    _downgrade_attached_pdfs_to_filenames(bind)

    op.drop_index(
        op.f("ix_result_import_ledgers_lot_id"), table_name="result_import_ledgers"
    )
    op.drop_index(
        op.f("ix_result_import_ledgers_result_import_id"),
        table_name="result_import_ledgers",
    )
    op.drop_table("result_import_ledgers")
    op.drop_index(op.f("ix_result_imports_status"), table_name="result_imports")
    op.drop_index(op.f("ix_result_imports_file_hash"), table_name="result_imports")
    op.drop_index("idx_result_import_created", table_name="result_imports")
    op.drop_index("idx_result_import_hash_status", table_name="result_imports")
    op.drop_table("result_imports")

    op.create_table(
        "parsing_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("pdf_filename", sa.String(length=255), nullable=False),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("reference_number", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assigned_to", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extracted_data", sa.Text(), nullable=True),
        sa.Column("confidence_scores", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
