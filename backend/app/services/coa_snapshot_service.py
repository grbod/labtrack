"""Immutable COA snapshot service."""

from __future__ import annotations

import hashlib
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.coa_release import COARelease
from app.models.coa_snapshot import COASerialCounter, COASnapshot
from app.models.enums import COAReleaseStatus
from app.models.lab_info import LabInfo
from app.services.coa_context_builder import (
    CONTEXT_SCHEMA_VERSION,
    COAContext,
    build_context,
)
from app.services.coa_generation_service import COAGenerationService
from app.services.storage_service import get_storage_service


def _safe_path_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip("-") or "coa"


class COASnapshotService:
    """Create and retrieve immutable COA release snapshots."""

    def issue_serial(self, db: Session, year: int) -> str:
        """Issue the next COA serial for ``year``.

        Uses an insert-if-absent counter row and a conditional UPDATE claim so
        concurrent workers cannot issue the same number.
        """
        year = int(year)
        self._ensure_counter_row(db, year)

        for _ in range(25):
            current = db.execute(
                select(COASerialCounter.last_value).where(COASerialCounter.year == year)
            ).scalar_one()
            next_value = current + 1
            claimed = (
                db.query(COASerialCounter)
                .filter(
                    COASerialCounter.year == year,
                    COASerialCounter.last_value == current,
                )
                .update(
                    {"last_value": next_value},
                    synchronize_session=False,
                )
            )
            if claimed == 1:
                db.flush()
                return f"COA-{year}-{next_value:06d}"
            db.expire_all()

        raise RuntimeError(f"Could not issue COA serial for {year}")

    def create_snapshot(
        self,
        db: Session,
        release: COARelease,
        *,
        reconstructed: bool = False,
    ) -> COASnapshot:
        """Create a frozen snapshot for a released COA.

        The generated PDF and frozen signature are uploaded first; the database
        row is then flushed into the caller's transaction.
        """
        if release.status != COAReleaseStatus.RELEASED:
            raise ValueError(f"Release {release.id} is not released")

        existing = (
            db.query(COASnapshot)
            .filter(
                COASnapshot.coa_release_id == release.id,
                COASnapshot.voided.is_(False),
            )
            .first()
        )
        if existing is not None:
            raise ValueError(
                f"Non-voided COA snapshot already exists for release {release.id}"
            )

        serial = None
        if not reconstructed:
            serial_year = (
                release.released_at.year
                if release.released_at
                else datetime.utcnow().year
            )
            serial = self.issue_serial(db, serial_year)

        self._ensure_lab_info_without_commit(db)
        context = build_context(
            db,
            release.lot_id,
            release.product_id,
            release=release,
        )
        context.source = "snapshot"
        if serial:
            context.document.document_id = serial

        storage_prefix = self._snapshot_prefix(release, serial)
        signature_storage_key = self._freeze_signature(context, storage_prefix)

        context_json = context.model_dump_json()
        content_hash = hashlib.sha256(context_json.encode("utf-8")).hexdigest()
        pdf_storage_key = f"{storage_prefix}/coa.pdf"
        self._render_pdf_to_storage(context, pdf_storage_key)

        snapshot = COASnapshot(
            coa_release_id=release.id,
            coa_serial=serial,
            revision=1,
            context_json=context_json,
            context_schema_version=CONTEXT_SCHEMA_VERSION,
            pdf_storage_key=pdf_storage_key,
            signature_storage_key=signature_storage_key,
            content_hash=content_hash,
            reconstructed=reconstructed,
            voided=False,
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    def get_snapshot_context(
        self,
        db: Session,
        release_id: int,
    ) -> Optional[COAContext]:
        """Return the frozen COA context for a release, if one exists."""
        snapshot = (
            db.query(COASnapshot)
            .filter(
                COASnapshot.coa_release_id == release_id,
                COASnapshot.voided.is_(False),
            )
            .first()
        )
        if snapshot is None:
            return None
        if snapshot.context_schema_version != CONTEXT_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported COA snapshot schema version "
                f"{snapshot.context_schema_version}"
            )

        context = COAContext.model_validate_json(snapshot.context_json)
        if context.schema_version != snapshot.context_schema_version:
            raise ValueError(
                "COA snapshot schema version does not match stored metadata"
            )
        return context

    def void_snapshot(
        self,
        db: Session,
        snapshot: COASnapshot,
        reason: str,
    ) -> None:
        """Void a snapshot without deleting any immutable data."""
        snapshot.voided = True
        snapshot.void_reason = reason
        db.flush()

    def _ensure_counter_row(self, db: Session, year: int) -> None:
        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""

        if dialect_name == "sqlite":
            stmt = (
                sqlite_insert(COASerialCounter)
                .values(year=year, last_value=0)
                .prefix_with("OR IGNORE")
            )
            db.execute(stmt)
            return

        if dialect_name == "postgresql":
            stmt = (
                pg_insert(COASerialCounter)
                .values(year=year, last_value=0)
                .on_conflict_do_nothing(index_elements=["year"])
            )
            db.execute(stmt)
            return

        existing = db.get(COASerialCounter, year)
        if existing is None:
            db.execute(
                text(
                    "INSERT INTO coa_serial_counters (year, last_value) "
                    "VALUES (:year, 0)"
                ),
                {"year": year},
            )

    def _ensure_lab_info_without_commit(self, db: Session) -> None:
        if db.query(LabInfo).first() is not None:
            return

        defaults = LabInfo.get_defaults()
        db.add(
            LabInfo(
                company_name=defaults["company_name"],
                address=defaults["address"],
                phone=defaults["phone"],
                email=defaults["email"],
                logo_path=defaults["logo_path"],
            )
        )
        db.flush()

    def _snapshot_prefix(self, release: COARelease, serial: Optional[str]) -> str:
        if serial:
            identifier = serial
        else:
            reference = release.reference_number or f"release-{release.id}"
            identifier = f"{reference}-release-{release.id}"
        return f"coa-snapshots/{_safe_path_part(identifier)}"

    def _freeze_signature(
        self,
        context: COAContext,
        storage_prefix: str,
    ) -> Optional[str]:
        signature_path = context.approver.signature_path
        if not signature_path:
            return None

        storage = get_storage_service()
        try:
            content = storage.download(signature_path)
        except FileNotFoundError:
            return None

        extension = Path(signature_path).suffix.lower() or ".bin"
        signature_storage_key = f"{storage_prefix}/signature{extension}"
        storage.upload(
            content, signature_storage_key, content_type="application/octet-stream"
        )
        context.approver.signature_path = signature_storage_key
        context.approver.signature_url = f"/uploads/{signature_storage_key}"
        return signature_storage_key

    def _render_pdf_to_storage(self, context: COAContext, storage_key: str) -> None:
        generator = COAGenerationService()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            generator._generate_pdf_reportlab(context, tmp_path)
            with open(tmp_path, "rb") as handle:
                pdf_content = handle.read()
            get_storage_service().upload(
                pdf_content,
                storage_key,
                content_type="application/pdf",
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)


coa_snapshot_service = COASnapshotService()


def issue_serial(db: Session, year: int) -> str:
    """Module-level convenience wrapper for serial issuance."""
    return coa_snapshot_service.issue_serial(db, year)


def create_snapshot(
    db: Session,
    release: COARelease,
    *,
    reconstructed: bool = False,
) -> COASnapshot:
    """Module-level convenience wrapper for snapshot creation."""
    return coa_snapshot_service.create_snapshot(
        db,
        release,
        reconstructed=reconstructed,
    )


def get_snapshot_context(db: Session, release_id: int) -> Optional[COAContext]:
    """Module-level convenience wrapper for frozen context retrieval."""
    return coa_snapshot_service.get_snapshot_context(db, release_id)


def void_snapshot(db: Session, snapshot: COASnapshot, reason: str) -> None:
    """Module-level convenience wrapper for snapshot voiding."""
    coa_snapshot_service.void_snapshot(db, snapshot, reason)
