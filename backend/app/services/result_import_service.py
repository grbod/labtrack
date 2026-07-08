"""Service layer for the results importer workflow."""

from __future__ import annotations

import hashlib
import io
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, Optional

from PyPDF2 import PdfReader
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import (
    AuditAction,
    AuditLog,
    LabTestType,
    Lot,
    LotStatus,
    ResultImport,
    ResultImportLedger,
    ResultImportStatus,
    Sublot,
    TestResult,
    TestResultStatus,
    UserRole,
)
from app.models.lot import LotProduct
from app.models.product_test_spec import ProductTestSpecification
from app.services.base import BaseService
from app.services.lab_test_alias_service import LabTestAliasService, normalize_alias_key
from app.services.lot_service import LotService
from app.services.result_extraction_provider import (
    ExtractionConfigurationError,
    get_extraction_provider,
)
from app.services.retest_service import retest_service
from app.services.storage_service import get_storage_service
from app.utils.logger import logger

ACTIVE_MATCH_STATUSES = [
    LotStatus.AWAITING_RESULTS,
    LotStatus.PARTIAL_RESULTS,
    LotStatus.NEEDS_ATTENTION,
    LotStatus.UNDER_REVIEW,
    LotStatus.AWAITING_RELEASE,
]
ACTIVE_IMPORT_DEDUP_STATUSES = [
    ResultImportStatus.PROCESSING,
    ResultImportStatus.NEEDS_CONFIRMATION,
    ResultImportStatus.CONFIRMED,
]

TEST_NAME_NORMALIZATION = {
    "total yeast & mold count": "Yeast & Mold",
    "total yeast and mold count": "Yeast & Mold",
    "total yeast mold count": "Yeast & Mold",
    "yeast/mold": "Yeast & Mold",
    "yeast and mold": "Yeast & Mold",
    "e. coli": "Escherichia coli",
    "e coli": "Escherichia coli",
    "ecoli": "Escherichia coli",
    "salmonella": "Salmonella spp.",
    "salmonella spp": "Salmonella spp.",
    "pb": "Lead",
    "pb lead": "Lead",
    "lead pb": "Lead",
    "as": "Arsenic",
    "as arsenic": "Arsenic",
    "arsenic as": "Arsenic",
    "cd": "Cadmium",
    "cd cadmium": "Cadmium",
    "cadmium cd": "Cadmium",
    "hg": "Mercury",
    "hg mercury": "Mercury",
    "mercury hg": "Mercury",
}
METALS = {
    "lead": "Lead",
    "arsenic": "Arsenic",
    "cadmium": "Cadmium",
    "mercury": "Mercury",
}

# Unit label for metal results reported on the per-serving basis.
PER_SERVING_UNIT = "µg/serving"


class ResultImportService(BaseService[ResultImport]):
    """Business logic for uploading, parsing, applying, and reverting imports."""

    STALE_AFTER = timedelta(minutes=20)
    PROCESSING_CLAIM_PREFIX = "Processing claim:"
    PROCESSING_CLAIM_AFTER = STALE_AFTER

    def __init__(self) -> None:
        super().__init__(ResultImport)
        self.alias_service = LabTestAliasService()

    def create_uploads(
        self,
        db: Session,
        files: Iterable[tuple[str, bytes, str]],
        user_id: int,
    ) -> tuple[list[ResultImport], list[ResultImport]]:
        files = list(files)
        if not files:
            raise ValueError("At least one PDF is required")
        if len(files) > 5:
            raise ValueError("Upload at most 5 PDFs at a time")
        if settings.ai_provider.lower() != "mock" and not settings.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required for results importer extraction"
            )
        if settings.ai_provider.lower() == "mock":
            logger.warning(
                "mock extraction provider active — results are fabricated for dev"
            )

        max_size = settings.max_upload_size_mb * 1024 * 1024
        validated: list[dict[str, Any]] = []

        for filename, content, content_type in files:
            if content_type != "application/pdf" and not filename.lower().endswith(
                ".pdf"
            ):
                raise ValueError("Only PDF files are allowed")
            if len(content) > max_size:
                raise ValueError(
                    f"{filename} exceeds the {settings.max_upload_size_mb}MB limit"
                )
            page_count = self._page_count(content)
            if page_count > 8:
                raise ValueError(f"{filename} has {page_count} pages; maximum is 8")

            file_hash = hashlib.sha256(content).hexdigest()
            validated.append(
                {
                    "filename": filename,
                    "content": content,
                    "content_type": content_type,
                    "file_hash": file_hash,
                }
            )

        created: list[ResultImport] = []
        duplicates: list[ResultImport] = []
        storage = get_storage_service()

        uploaded_keys: list[str] = []
        try:
            for payload in validated:
                filename = payload["filename"]
                duplicate = (
                    db.query(ResultImport)
                    .filter(
                        ResultImport.file_hash == payload["file_hash"],
                        ResultImport.status.in_(ACTIVE_IMPORT_DEDUP_STATUSES),
                    )
                    .order_by(ResultImport.confirmed_at.desc().nullslast())
                    .first()
                )
                if duplicate:
                    duplicates.append(duplicate)
                    continue

                safe_name = self._safe_filename(filename)
                storage_key = f"pdfs/result-imports/{datetime.utcnow():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}_{safe_name}"
                storage.upload(
                    payload["content"], storage_key, content_type="application/pdf"
                )
                uploaded_keys.append(storage_key)

                item = ResultImport(
                    original_filename=filename,
                    storage_key=storage_key,
                    file_hash=payload["file_hash"],
                    status=ResultImportStatus.PROCESSING,
                    uploaded_by_id=user_id,
                    openrouter_model=settings.openrouter_model,
                    warnings=[],
                )
                try:
                    with db.begin_nested():
                        db.add(item)
                        db.flush()
                        self._log_audit(
                            db,
                            action=AuditAction.INSERT,
                            record_id=item.id,
                            new_values={
                                "original_filename": filename,
                                "storage_key": storage_key,
                            },
                            user_id=user_id,
                            reason="Result import uploaded",
                        )
                except IntegrityError:
                    if storage_key in uploaded_keys:
                        uploaded_keys.remove(storage_key)
                    storage.delete(storage_key)
                    duplicate = self._active_duplicate_for_hash(
                        db, payload["file_hash"]
                    )
                    if not duplicate:
                        raise
                    duplicates.append(duplicate)
                    continue
                created.append(item)

            db.commit()
        except Exception:
            db.rollback()
            for storage_key in uploaded_keys:
                storage.delete(storage_key)
            raise
        for item in created + duplicates:
            db.refresh(item)
        return created, duplicates

    def _active_duplicate_for_hash(
        self, db: Session, file_hash: str
    ) -> Optional[ResultImport]:
        return (
            db.query(ResultImport)
            .filter(
                ResultImport.file_hash == file_hash,
                ResultImport.status.in_(ACTIVE_IMPORT_DEDUP_STATUSES),
            )
            .order_by(ResultImport.confirmed_at.desc().nullslast())
            .first()
        )

    def duplicate_summary(self, item: ResultImport) -> dict[str, Any]:
        lot = item.selected_lot
        confirmer = item.confirmed_by
        return {
            "import_id": item.id,
            "original_filename": item.original_filename,
            "confirmed_at": (
                item.confirmed_at.isoformat() if item.confirmed_at else None
            ),
            "confirmed_by": (
                (confirmer.full_name or confirmer.username) if confirmer else None
            ),
            "lot_id": lot.id if lot else None,
            "reference_number": lot.reference_number if lot else None,
            "lot_number": lot.lot_number if lot else None,
        }

    def process_import(
        self, db: Session, import_id: int, claim_id: Optional[str] = None
    ) -> ResultImport:
        item = self.get(db, import_id)
        if not item or item.status != ResultImportStatus.PROCESSING:
            return item
        if (
            claim_id
            and item.error_message != f"{self.PROCESSING_CLAIM_PREFIX}{claim_id}"
        ):
            return item

        try:
            pdf_bytes = get_storage_service().download(item.storage_key)
            text = self._extract_text(pdf_bytes)
            provider = get_extraction_provider()
            raw = provider.extract(pdf_bytes, text, item.original_filename)
            usage = raw.pop("_usage_metadata", None)
            model = raw.pop("_model", None) or settings.openrouter_model
            extracted = self._normalize_extraction(db, raw)
            multi_sample_warnings = [
                warning
                for warning in extracted.get("warnings", [])
                if warning.startswith("Multiple sample")
            ]
            if multi_sample_warnings:
                update_values = {
                    "extracted_data": extracted,
                    "warnings": extracted.get("warnings", []),
                    "usage_metadata": usage,
                    "openrouter_model": model,
                    "status": ResultImportStatus.FAILED,
                    "error_message": multi_sample_warnings[0],
                }
            else:
                candidates = self.match_candidates(
                    db, extracted, item.original_filename
                )
                update_values = {
                    "extracted_data": extracted,
                    "match_candidates": candidates,
                    "warnings": extracted.get("warnings", []),
                    "usage_metadata": usage,
                    "openrouter_model": model,
                    "error_message": None,
                    "status": ResultImportStatus.NEEDS_CONFIRMATION,
                }
        except ExtractionConfigurationError as exc:
            update_values = {
                "status": ResultImportStatus.FAILED,
                "error_message": str(exc),
            }
        except Exception as exc:
            update_values = {
                "status": ResultImportStatus.FAILED,
                "error_message": f"Failed to process PDF: {exc}",
            }

        return self._finish_processing_import(db, import_id, claim_id, update_values)

    def list_imports(
        self, db: Session, page: int, page_size: int
    ) -> tuple[list[ResultImport], int]:
        self.reap_stale_processing(db)
        query = db.query(ResultImport).order_by(ResultImport.created_at.desc())
        total = query.count()
        return query.offset((page - 1) * page_size).limit(page_size).all(), total

    def queued_processing_ids(self, db: Session) -> list[int]:
        """Return imports left in processing state for startup requeue."""
        return [
            import_id
            for (import_id,) in (
                db.query(ResultImport.id)
                .filter(ResultImport.status == ResultImportStatus.PROCESSING)
                .order_by(ResultImport.created_at.asc())
                .all()
            )
        ]

    def claim_processing_import(
        self, db: Session, import_id: int, claim_id: str
    ) -> bool:
        """Atomically claim a processing import before doing extraction work."""
        cutoff = datetime.utcnow() - self.PROCESSING_CLAIM_AFTER
        updated = (
            db.query(ResultImport)
            .filter(
                ResultImport.id == import_id,
                ResultImport.status == ResultImportStatus.PROCESSING,
                or_(
                    ResultImport.error_message.is_(None),
                    ~ResultImport.error_message.like(
                        f"{self.PROCESSING_CLAIM_PREFIX}%"
                    ),
                    ResultImport.updated_at < cutoff,
                ),
            )
            .update(
                {
                    "error_message": f"{self.PROCESSING_CLAIM_PREFIX}{claim_id}",
                    "updated_at": datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        db.commit()
        return updated == 1

    def _finish_processing_import(
        self,
        db: Session,
        import_id: int,
        claim_id: Optional[str],
        update_values: dict[str, Any],
    ) -> ResultImport:
        query = db.query(ResultImport).filter(
            ResultImport.id == import_id,
            ResultImport.status == ResultImportStatus.PROCESSING,
        )
        if claim_id:
            query = query.filter(
                ResultImport.error_message
                == f"{self.PROCESSING_CLAIM_PREFIX}{claim_id}"
            )
        update_values["updated_at"] = datetime.utcnow()
        query.update(update_values, synchronize_session=False)
        db.commit()
        return self.get(db, import_id)

    def reap_stale_processing(self, db: Session) -> int:
        cutoff = datetime.utcnow() - self.STALE_AFTER
        stale = (
            db.query(ResultImport)
            .filter(
                ResultImport.status == ResultImportStatus.PROCESSING,
                ResultImport.updated_at < cutoff,
            )
            .all()
        )
        for item in stale:
            item.status = ResultImportStatus.FAILED
            item.error_message = "Processing timed out; retry the stored PDF"
        if stale:
            db.commit()
        return len(stale)

    def retry(
        self, db: Session, import_id: int, user_id: Optional[int] = None
    ) -> ResultImport:
        item = self.get(db, import_id)
        if not item:
            raise ValueError("Import not found")
        if item.status not in [
            ResultImportStatus.FAILED,
            ResultImportStatus.PROCESSING,
        ]:
            raise ValueError("Only failed or stale imports can be retried")
        if (
            item.status == ResultImportStatus.PROCESSING
            and item.updated_at > datetime.utcnow() - self.STALE_AFTER
        ):
            raise ValueError("Import is still processing")
        if not item.storage_key or not get_storage_service().exists(item.storage_key):
            raise ValueError("Stored PDF is no longer available")
        old_status = item.status.value
        item.status = ResultImportStatus.PROCESSING
        item.error_message = None
        self._audit_entity(
            db,
            table_name="result_imports",
            action=AuditAction.UPDATE,
            record_id=item.id,
            old_values={"status": old_status},
            new_values={"status": ResultImportStatus.PROCESSING.value},
            user_id=user_id,
            reason="Result import retried (re-queued from stored PDF)",
        )
        db.commit()
        db.refresh(item)
        return item

    def cancel(self, db: Session, import_id: int, user_id: int) -> ResultImport:
        item = self.get(db, import_id)
        if not item:
            raise ValueError("Import not found")
        if item.status not in [
            ResultImportStatus.PROCESSING,
            ResultImportStatus.NEEDS_CONFIRMATION,
            ResultImportStatus.FAILED,
        ]:
            raise ValueError("Only unconfirmed imports can be cancelled")
        old_status = item.status.value
        storage_key = item.storage_key
        item.status = ResultImportStatus.CANCELLED
        item.cancelled_at = datetime.utcnow()
        self._log_audit(
            db,
            action=AuditAction.UPDATE,
            record_id=item.id,
            old_values={"status": old_status},
            new_values={"status": ResultImportStatus.CANCELLED.value},
            user_id=user_id,
            reason="Result import cancelled",
        )
        db.commit()
        if storage_key:
            self._delete_storage_key(
                storage_key, context=f"cancelled result import {item.id}"
            )
        db.refresh(item)
        return item

    def confirm(
        self,
        db: Session,
        import_id: int,
        lot_id: int,
        row_actions: list[Any],
        user_id: int,
    ) -> dict[str, Any]:
        claimed = (
            db.query(ResultImport)
            .filter(
                ResultImport.id == import_id,
                ResultImport.status == ResultImportStatus.NEEDS_CONFIRMATION,
            )
            .update(
                {
                    "status": ResultImportStatus.PROCESSING,
                    "updated_at": datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        if claimed != 1:
            db.rollback()
            item = self.get(db, import_id)
            if not item:
                raise ValueError("Import not found")
            raise ValueError("Import is not ready for confirmation")

        item = self.get(db, import_id)
        if not item:
            raise ValueError("Import not found")

        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot or lot.status not in ACTIVE_MATCH_STATUSES:
            raise ValueError("Select an active lot")

        rows_by_id = {
            row["row_id"]: row for row in (item.extracted_data or {}).get("rows", [])
        }
        created_ids: list[int] = []
        updated: list[dict[str, Any]] = []
        applied_rows: list[dict[str, Any]] = []
        skipped_row_ids: list[str] = []
        alias_suggestions_created = 0

        for action in row_actions:
            if action.action == "skip":
                skipped_row_ids.append(action.row_id)
                continue
            row = rows_by_id.get(action.row_id)
            if not row:
                raise ValueError(f"Extracted row {action.row_id} not found")

            test_name, unit, specification, method, lab_test_type_id = (
                self._resolve_test_fields(
                    db, lot, row, action.lab_test_type_id, action.test_name
                )
            )
            if not lab_test_type_id:
                raise ValueError(
                    f"{test_name} is not mapped; choose an active lab test type"
                )
            if action.action == "create_adhoc" and not test_name:
                raise ValueError(
                    f"Row {action.row_id} needs a test name for ad-hoc creation"
                )
            is_on_panel = self._find_lot_spec(lot, test_name) is not None
            # create_adhoc is the OFF-panel path. If a create_adhoc resolves onto
            # the lot's panel, use the product spec and ignore client-sent
            # Unit/Spec/Method (i.e. behave like a normal apply). Only a genuine
            # off-panel ad-hoc takes operator-entered Unit/Spec/Method, which are
            # all required.
            treat_as_adhoc = action.action == "create_adhoc" and not is_on_panel
            if treat_as_adhoc:
                if getattr(action, "unit", None) is not None:
                    unit = str(action.unit).strip()
                if getattr(action, "specification", None) is not None:
                    specification = str(action.specification).strip()
                if getattr(action, "method", None) is not None:
                    method = str(action.method).strip()
                missing = [
                    label
                    for label, value in [
                        ("Unit", unit),
                        ("Spec", specification),
                        ("Method", method),
                    ]
                    if value is None or str(value).strip() == ""
                ]
                if missing:
                    raise ValueError(
                        f"{test_name} needs Unit, Spec, and Method before it can be added as an ad-hoc draft"
                    )
            result_value = (
                action.result_value
                if action.result_value is not None
                else row.get("result_value_raw")
            )
            if result_value is None or str(result_value).strip() == "":
                raise ValueError(f"Row {action.row_id} has no result value")

            existing = self._find_existing_result(
                db, lot.id, test_name, action.test_result_id
            )
            if action.test_result_id:
                if not existing:
                    raise ValueError("Selected draft result was not found on this lot")
                if not self._existing_result_matches_target(
                    existing, test_name, lab_test_type_id
                ):
                    raise ValueError(
                        "Selected draft result does not match extracted test"
                    )
            if existing:
                if existing.status == TestResultStatus.APPROVED:
                    raise ValueError(
                        f"{test_name} is already approved and cannot be modified"
                    )
                if action.action != "replace" and existing.result_value:
                    raise ValueError(
                        f"{test_name} already has a draft value; choose replace"
                    )
                old = self._result_snapshot(existing)
                existing.result_value = str(result_value).strip()
                existing.unit = unit
                existing.test_date = self._parse_date(
                    row.get("test_date")
                    or (item.extracted_data or {}).get("date_tested")
                )
                existing.pdf_source = item.storage_key
                existing.confidence_score = row.get("confidence")
                existing.specification = specification
                existing.method = method
                existing.notes = self._row_notes(row)
                existing.lab_test_type_id = lab_test_type_id
                new = self._result_snapshot(existing)
                updated.append(
                    {
                        "id": existing.id,
                        "old": old,
                        "new": new,
                    }
                )
                self._audit_entity(
                    db,
                    table_name="test_results",
                    action=AuditAction.UPDATE,
                    record_id=existing.id,
                    old_values=old,
                    new_values=new,
                    user_id=user_id,
                    reason="Result import: replaced existing draft value",
                )
                applied_rows.append(
                    {
                        "row_id": action.row_id,
                        "test_result_id": existing.id,
                        "action": "replace",
                    }
                )
                if self._record_alias_suggestion_for_action(
                    db, item, lot, row, action, lab_test_type_id, user_id
                ):
                    alias_suggestions_created += 1
                retest_service.check_and_complete_retest(
                    db, existing.id, user_id=user_id
                )
            else:
                if action.action not in ["apply", "create_adhoc"]:
                    raise ValueError(
                        f"No draft row exists for {test_name}; choose apply"
                    )
                result = TestResult(
                    lot_id=lot.id,
                    test_type=test_name,
                    result_value=str(result_value).strip(),
                    unit=unit,
                    test_date=self._parse_date(
                        row.get("test_date")
                        or (item.extracted_data or {}).get("date_tested")
                    ),
                    pdf_source=item.storage_key,
                    confidence_score=row.get("confidence"),
                    specification=specification,
                    method=method,
                    notes=self._row_notes(row),
                    status=TestResultStatus.DRAFT,
                    lab_test_type_id=lab_test_type_id,
                    include_on_coa=True,
                )
                db.add(result)
                db.flush()
                created_ids.append(result.id)
                result_snapshot = self._result_snapshot(result)
                self._audit_entity(
                    db,
                    table_name="test_results",
                    action=AuditAction.INSERT,
                    record_id=result.id,
                    new_values=result_snapshot,
                    user_id=user_id,
                    reason=(
                        f"Result import: ad-hoc test '{action.test_name}' created"
                        if action.action == "create_adhoc"
                        else "Result import: draft result created"
                    ),
                )
                applied_rows.append(
                    {
                        "row_id": action.row_id,
                        "test_result_id": result.id,
                        "action": action.action,
                        "result_snapshot": result_snapshot,
                    }
                )
                if self._record_alias_suggestion_for_action(
                    db, item, lot, row, action, lab_test_type_id, user_id
                ):
                    alias_suggestions_created += 1

        if not created_ids and not updated:
            raise ValueError("Confirm requires at least one applied result row")

        attachment = {
            "filename": item.original_filename,
            "storage_key": item.storage_key,
            "source": "import",
            "import_id": item.id,
            "added_at": datetime.utcnow().isoformat(),
        }
        previous_attachments = list(lot.attached_pdfs or [])
        lot.attached_pdfs = self._append_pdf_attachment(lot.attached_pdfs, attachment)
        self._audit_entity(
            db,
            table_name="lots",
            action=AuditAction.UPDATE,
            record_id=lot.id,
            old_values={"attached_pdfs": previous_attachments},
            new_values={"attached_pdfs": lot.attached_pdfs},
            user_id=user_id,
            reason="Result import: source PDF attached",
        )

        ledger = ResultImportLedger(
            result_import_id=item.id,
            lot_id=lot.id,
            action_type="confirm",
            created_result_ids=created_ids,
            updated_results=updated,
            pdf_attachment=attachment,
            applied_rows=applied_rows,
            applied_by_id=user_id,
        )
        db.add(ledger)

        item.status = ResultImportStatus.CONFIRMED
        item.selected_lot_id = lot.id
        item.confirmed_by_id = user_id
        item.confirmed_at = datetime.utcnow()

        self._log_audit(
            db,
            action=AuditAction.UPDATE,
            record_id=item.id,
            old_values={"status": ResultImportStatus.NEEDS_CONFIRMATION.value},
            new_values={"status": ResultImportStatus.CONFIRMED.value, "lot_id": lot.id},
            user_id=user_id,
            reason="Result import confirmed",
        )

        if lot.status == LotStatus.AWAITING_RELEASE:
            lot.status = LotStatus.UNDER_REVIEW
            self._audit_entity(
                db,
                table_name="lots",
                action=AuditAction.UPDATE,
                record_id=lot.id,
                old_values={"status": LotStatus.AWAITING_RELEASE.value},
                new_values={"status": LotStatus.UNDER_REVIEW.value},
                user_id=user_id,
                reason="Result import: lot pulled back from release queue into review",
            )

        calculation = LotService().calculate_lot_status(db, lot)
        LotService()._apply_lot_status_calculation(
            db, calculation, user_id=user_id, reason_prefix="Results import"
        )
        db.commit()
        return {
            "import_id": item.id,
            "lot_id": lot.id,
            "created_result_ids": created_ids,
            "updated_result_ids": [entry["id"] for entry in updated],
            "skipped_row_ids": skipped_row_ids,
            "alias_suggestions_created": alias_suggestions_created,
            "status": item.status.value,
        }

    def revert(
        self, db: Session, import_id: int, user_id: int, user_role: UserRole
    ) -> ResultImport:
        item = self.get(db, import_id)
        if not item:
            raise ValueError("Import not found")
        if item.status != ResultImportStatus.CONFIRMED:
            raise ValueError("Only confirmed imports can be reverted")
        if item.confirmed_by_id != user_id and user_role not in [
            UserRole.ADMIN,
            UserRole.QC_MANAGER,
        ]:
            raise ValueError(
                "Only the confirmer, QC Manager, or Admin can revert this import"
            )

        ledger = (
            db.query(ResultImportLedger)
            .filter(ResultImportLedger.result_import_id == item.id)
            .order_by(ResultImportLedger.created_at.desc())
            .first()
        )
        if not ledger:
            raise ValueError("Import ledger not found")

        for result_id in ledger.created_result_ids or []:
            result = db.query(TestResult).filter(TestResult.id == result_id).first()
            if not result:
                continue
            if result.status != TestResultStatus.DRAFT:
                raise ValueError("Cannot revert because an imported row was approved")
            expected = self._created_result_snapshot(ledger, result_id)
            if not expected:
                raise ValueError(
                    "Cannot revert because an imported row snapshot is missing"
                )
            if any(
                self._snapshot_value(result, key) != expected.get(key)
                for key in expected
            ):
                raise ValueError(
                    "Cannot revert because an imported row changed after import"
                )
            self._audit_entity(
                db,
                table_name="test_results",
                action=AuditAction.DELETE,
                record_id=result.id,
                old_values=self._result_snapshot(result),
                user_id=user_id,
                reason="Result import reverted: draft result removed",
            )
            db.delete(result)

        for entry in ledger.updated_results or []:
            result = db.query(TestResult).filter(TestResult.id == entry["id"]).first()
            if not result:
                raise ValueError("Cannot revert because an updated row is missing")
            if result.status != TestResultStatus.DRAFT:
                raise ValueError("Cannot revert because an updated row was approved")
            expected = entry["new"]
            if any(
                self._snapshot_value(result, key) != expected.get(key)
                for key in expected
            ):
                raise ValueError(
                    "Cannot revert because an updated row changed after import"
                )
            for key, value in entry["old"].items():
                if key == "test_date":
                    value = self._parse_date(value)
                setattr(result, key, value)
            self._audit_entity(
                db,
                table_name="test_results",
                action=AuditAction.UPDATE,
                record_id=result.id,
                old_values=entry["new"],
                new_values=entry["old"],
                user_id=user_id,
                reason="Result import reverted: draft value restored",
            )

        lot = db.query(Lot).filter(Lot.id == ledger.lot_id).first()
        storage_key_to_delete = None
        if lot and ledger.pdf_attachment:
            previous_attachments = list(lot.attached_pdfs or [])
            lot.attached_pdfs = [
                entry
                for entry in self._normalize_pdf_attachments(lot.attached_pdfs)
                if entry.get("storage_key") != ledger.pdf_attachment.get("storage_key")
            ]
            self._audit_entity(
                db,
                table_name="lots",
                action=AuditAction.UPDATE,
                record_id=lot.id,
                old_values={"attached_pdfs": previous_attachments},
                new_values={"attached_pdfs": lot.attached_pdfs},
                user_id=user_id,
                reason="Result import reverted: source PDF detached",
            )
            storage_key = ledger.pdf_attachment.get("storage_key")
            if storage_key:
                db.flush()
                if not self._storage_key_has_references(
                    db, storage_key, exclude_import_id=item.id
                ):
                    storage_key_to_delete = storage_key

        item.status = ResultImportStatus.REVERTED
        item.reverted_at = datetime.utcnow()
        self._audit_entity(
            db,
            table_name="result_imports",
            action=AuditAction.UPDATE,
            record_id=item.id,
            old_values={"status": ResultImportStatus.CONFIRMED.value},
            new_values={"status": ResultImportStatus.REVERTED.value},
            user_id=user_id,
            reason="Result import reverted",
        )
        if lot:
            calculation = LotService().calculate_lot_status(db, lot)
            LotService()._apply_lot_status_calculation(
                db, calculation, user_id=user_id, reason_prefix="Results import revert"
            )
        db.commit()
        if storage_key_to_delete:
            self._delete_storage_key(
                storage_key_to_delete, context=f"reverted result import {item.id}"
            )
        db.refresh(item)
        return item

    def preview_rows(
        self,
        db: Session,
        import_id: int,
        lot_id: int,
        overrides: Optional[Iterable[Any]] = None,
    ) -> dict[str, Any]:
        item = self.get(db, import_id)
        if not item:
            raise ValueError("Import not found")
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot or lot.status not in ACTIVE_MATCH_STATUSES:
            raise ValueError("Select an active lot")

        override_by_row_id = self._preview_override_map(overrides)
        previews = []
        for row in (item.extracted_data or {}).get("rows", []):
            row_id = row.get("row_id")
            lab_test_type_override = override_by_row_id.get(row_id)
            test_name, unit, specification, method, lab_test_type_id = (
                self._resolve_test_fields(
                    db,
                    lot,
                    row,
                    lab_test_type_override
                    if row_id in override_by_row_id
                    else row.get("matched_lab_test_type_id"),
                    row.get("test_name_normalized") or row.get("test_name_raw"),
                )
            )
            existing = self._find_existing_result(db, lot.id, test_name, None)
            warnings = list(row.get("warnings") or [])
            requires_mapping = not lab_test_type_id
            is_on_panel = self._find_lot_spec(lot, test_name) is not None
            if requires_mapping:
                warnings.append("No active lab test type matched")

            if existing and existing.status == TestResultStatus.APPROVED:
                suggested_action = "skip"
            elif (
                existing
                and existing.result_value
                and row.get("match_source") == "fuzzy"
            ):
                suggested_action = "replace"
            elif existing and existing.result_value:
                suggested_action = "skip"
            elif requires_mapping:
                suggested_action = "skip"
            elif not is_on_panel:
                suggested_action = "create_adhoc"
            else:
                suggested_action = "apply"

            previews.append(
                {
                    "row_id": row.get("row_id"),
                    "resolved_test_name": test_name,
                    "unit": unit,
                    "specification": specification,
                    "method": method,
                    "lab_test_type_id": lab_test_type_id,
                    "requires_lab_test_mapping": requires_mapping,
                    "suggested_action": suggested_action,
                    "warnings": warnings,
                    "existing_result": (
                        self._existing_result_payload(existing) if existing else None
                    ),
                }
            )
        return {"import_id": item.id, "lot_id": lot.id, "rows": previews}

    def _preview_override_map(
        self, overrides: Optional[Iterable[Any]]
    ) -> dict[str, Optional[int]]:
        mapped: dict[str, Optional[int]] = {}
        for override in overrides or []:
            row_id = (
                override.get("row_id")
                if isinstance(override, dict)
                else getattr(override, "row_id", None)
            )
            if not row_id:
                continue
            lab_test_type_id = (
                override.get("lab_test_type_id")
                if isinstance(override, dict)
                else getattr(override, "lab_test_type_id", None)
            )
            mapped[str(row_id)] = lab_test_type_id
        return mapped

    def link_candidates(
        self, db: Session, search: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        term = f"%{search.strip()}%"
        lots = (
            db.query(Lot)
            .options(joinedload(Lot.lot_products).joinedload(LotProduct.product))
            .filter(
                Lot.status.in_(ACTIVE_MATCH_STATUSES),
                or_(
                    Lot.reference_number.ilike(term),
                    Lot.lot_number.ilike(term),
                    Lot.lot_products.any(LotProduct.batch_number.ilike(term)),
                    Lot.sublots.any(Sublot.sublot_number.ilike(term)),
                ),
            )
            .limit(limit)
            .all()
        )
        return [self._lot_candidate_payload(lot, 0, ["manual search"]) for lot in lots]

    def match_candidates(
        self, db: Session, extracted: dict[str, Any], filename: str
    ) -> list[dict[str, Any]]:
        tokens = {
            self._normalize_token(identifier.get("value"))
            for identifier in extracted.get("identifiers", [])
            if identifier.get("value")
        }
        for row in extracted.get("rows") or []:
            tokens.update(
                self._normalize_token(row.get(key))
                for key in [
                    "sample_id",
                    "reference_number",
                    "lot_number",
                    "sublot_number",
                    "batch_number",
                ]
                if row.get(key)
            )
        tokens.update(
            self._normalize_token(part)
            for part in re.findall(r"[A-Z0-9][A-Z0-9-]{3,}", filename.upper())
        )
        tokens.discard("")

        lots = (
            db.query(Lot)
            .options(
                joinedload(Lot.sublots),
                joinedload(Lot.lot_products).joinedload(LotProduct.product),
            )
            .filter(Lot.status.in_(ACTIVE_MATCH_STATUSES))
            .all()
        )
        candidates = []
        for lot in lots:
            score = 0.0
            reasons = []
            values = {
                "reference": [lot.reference_number],
                "lot": [lot.lot_number],
                "sublot": [s.sublot_number for s in lot.sublots],
                "batch": [lp.batch_number or "" for lp in lot.lot_products],
            }
            reason_labels = {
                "reference": "Reference {value} matched COA reference",
                "lot": "Lot {value} matched COA lot",
                "sublot": "Sublot {value} matched COA sublot",
                "batch": "Batch {value} matched COA batch number",
            }
            for label, value_list in values.items():
                matched_value = next(
                    (
                        value
                        for value in value_list
                        if value and self._normalize_token(value) in tokens
                    ),
                    None,
                )
                if matched_value:
                    score += 0.5 if label in ["reference", "lot"] else 0.25
                    reasons.append(reason_labels[label].format(value=matched_value))
            if score:
                candidates.append(
                    self._lot_candidate_payload(lot, min(score, 1.0), reasons)
                )
        return sorted(candidates, key=lambda item: item["score"], reverse=True)[:10]

    def _resolve_test_fields(
        self,
        db: Session,
        lot: Lot,
        row: dict[str, Any],
        lab_test_type_id: Optional[int],
        override_name: Optional[str],
    ) -> tuple[str, Optional[str], Optional[str], Optional[str], Optional[int]]:
        test_name = (
            override_name or row.get("test_name_normalized") or row.get("test_name_raw")
        )
        lab_type = None
        if lab_test_type_id:
            lab_type = (
                db.query(LabTestType)
                .filter(
                    LabTestType.id == lab_test_type_id, LabTestType.is_active == True
                )
                .first()
            )
            if not lab_type:
                raise ValueError("Selected lab test type not found")
            test_name = lab_type.test_name
        elif row.get("matched_lab_test_type_id"):
            lab_type = (
                db.query(LabTestType)
                .filter(
                    LabTestType.id == row["matched_lab_test_type_id"],
                    LabTestType.is_active == True,
                )
                .first()
            )

        spec = self._find_lot_spec(lot, test_name)
        if spec and spec.lab_test_type:
            lab_type = spec.lab_test_type
            test_name = lab_type.test_name
        unit = spec.test_unit if spec else (lab_type.default_unit if lab_type else None)
        # A metal result promoted to the per-serving basis carries a per-serving
        # unit, not the spec's mass-basis (ppm/ug-g) unit.
        if (row.get("metadata") or {}).get("serving_value") is not None:
            unit = PER_SERVING_UNIT
        specification = (
            spec.specification
            if spec
            else (
                (lab_type.default_specification or row.get("limit_raw"))
                if lab_type
                else row.get("limit_raw")
            )
        )
        method = (
            spec.lab_test_type.test_method
            if spec and spec.lab_test_type
            else (lab_type.test_method if lab_type else None)
        )
        return test_name, unit, specification, method, lab_type.id if lab_type else None

    def _find_lot_spec(
        self, lot: Lot, test_name: str
    ) -> Optional[ProductTestSpecification]:
        for lot_product in lot.lot_products:
            for spec in lot_product.product.test_specifications:
                if (
                    spec.test_name
                    and spec.test_name.lower() == (test_name or "").lower()
                ):
                    return spec
        return None

    def _existing_result_payload(self, result: TestResult) -> dict[str, Any]:
        return {
            "id": result.id,
            "test_type": result.test_type,
            "result_value": result.result_value,
            "unit": result.unit,
            "status": (
                result.status.value
                if hasattr(result.status, "value")
                else result.status
            ),
            "test_date": (
                result.test_date.isoformat()
                if isinstance(result.test_date, date)
                else result.test_date
            ),
            "pdf_source": result.pdf_source,
        }

    def _find_existing_result(
        self, db: Session, lot_id: int, test_name: str, result_id: Optional[int]
    ) -> Optional[TestResult]:
        if result_id:
            return (
                db.query(TestResult)
                .filter(TestResult.id == result_id, TestResult.lot_id == lot_id)
                .first()
            )
        return (
            db.query(TestResult)
            .filter(TestResult.lot_id == lot_id, TestResult.test_type == test_name)
            .order_by(TestResult.created_at.desc())
            .first()
        )

    def _existing_result_matches_target(
        self, result: TestResult, test_name: str, lab_test_type_id: Optional[int]
    ) -> bool:
        # A shared, non-null lab_test_type_id is authoritative: accept the
        # replacement even when the stored test_type text differs (e.g. legacy
        # naming). Otherwise fall back to matching the test name.
        if result.lab_test_type_id and lab_test_type_id:
            return result.lab_test_type_id == lab_test_type_id
        return result.test_type.strip().casefold() == test_name.strip().casefold()

    def _record_alias_suggestion_for_action(
        self,
        db: Session,
        item: ResultImport,
        lot: Lot,
        row: dict[str, Any],
        action: Any,
        final_lab_test_type_id: Optional[int],
        user_id: int,
    ) -> bool:
        if not final_lab_test_type_id:
            return False
        match_source = row.get("match_source")
        if match_source in {"exact", "builtin_alias", "approved_alias"}:
            return False
        original_fuzzy_id = row.get("matched_lab_test_type_id")
        should_suggest = match_source == "fuzzy" or (
            match_source == "unmatched" and getattr(action, "lab_test_type_id", None)
        )
        if match_source == "fuzzy" and original_fuzzy_id != final_lab_test_type_id:
            should_suggest = True
        if not should_suggest:
            return False
        raw_phrase = (row.get("metadata") or {}).get("fuzzy_source") or row.get(
            "test_name_raw"
        )
        if not raw_phrase:
            return False
        source = (
            "manual_override"
            if match_source == "unmatched"
            or (match_source == "fuzzy" and original_fuzzy_id != final_lab_test_type_id)
            else "fuzzy"
        )
        self.alias_service.record_alias_suggestion(
            db,
            raw_phrase=raw_phrase,
            lab_name=(item.extracted_data or {}).get("lab_name"),
            lab_test_type_id=final_lab_test_type_id,
            source=source,
            import_context={
                "result_import_id": item.id,
                "lot_id": lot.id,
                "filename": item.original_filename,
            },
            user_id=user_id,
        )
        return True

    def _normalize_extraction(self, db: Session, raw: dict[str, Any]) -> dict[str, Any]:
        rows = []
        warnings = list(raw.get("warnings") or [])
        active_lab_types = (
            db.query(LabTestType).filter(LabTestType.is_active == True).all()
        )
        lab_types = {lt.test_name.casefold(): lt for lt in active_lab_types}
        lab_name = raw.get("lab_name")
        for index, row in enumerate(raw.get("rows") or [], start=1):
            raw_name = row.get("test_name_raw") or ""
            normalized_name, lab_type, match_source, alias_id = (
                self._resolve_lab_type_match(
                    db, raw_name, lab_name, lab_types, active_lab_types
                )
            )
            unit_raw = row.get("unit_raw")
            target_unit = lab_type.default_unit if lab_type else unit_raw
            metadata = {
                key: row.get(key)
                for key in ["per_serving", "lod", "loq"]
                if row.get(key)
            }
            confidence = float(row.get("confidence") or 0)
            result_value = row.get("result_value_raw")
            row_warnings = []
            if confidence < 0.7:
                row_warnings.append("Low confidence extraction")
            if match_source == "fuzzy" and lab_type:
                metadata["fuzzy_source"] = raw_name
                metadata["fuzzy_target"] = lab_type.test_name
                warning = (
                    f'Fuzzy matched "{raw_name}" to "{lab_type.test_name}". '
                    "Applying will suggest this alias for QC review."
                )
                metadata["fuzzy_warning"] = warning
                row_warnings.append(warning)
            if self._is_metal(normalized_name, lab_type):
                serving_value = row.get("per_serving")
                primary_is_serving = self._looks_per_serving(unit_raw)
                if not serving_value and primary_is_serving:
                    # The extracted primary value is itself a per-serving figure.
                    serving_value = result_value
                if serving_value:
                    # Metals are reported and judged on the per-serving basis.
                    # Keep the printed value as-is (including <LOD/<LOQ/less-than).
                    if result_value and not primary_is_serving:
                        metadata["mass_basis_value"] = (
                            self._normalize_harken_metal_value(result_value, unit_raw)
                        )
                        metadata["mass_basis_unit"] = "ug/g"
                    metadata["serving_value"] = serving_value
                    metadata["serving_unit"] = (
                        unit_raw if primary_is_serving else "per serving"
                    )
                    metadata["conversion_note"] = "Reported on per-serving basis"
                    # The per-serving value is now the primary result; drop the
                    # duplicate per_serving note (provenance lives in serving_value
                    # / mass_basis_value).
                    metadata.pop("per_serving", None)
                    result_value = serving_value
                else:
                    # No per-serving column: keep the mass basis, normalized to ppm.
                    target_unit = "ug/g"
                    result_value = self._normalize_harken_metal_value(
                        result_value, unit_raw
                    )
            rows.append(
                {
                    "row_id": row.get("row_id") or f"row-{index}",
                    "test_name_raw": raw_name,
                    "test_name_normalized": normalized_name,
                    "result_value_raw": result_value,
                    "unit_raw": unit_raw,
                    "target_unit": target_unit,
                    "limit_raw": row.get("limit_raw"),
                    "sample_id": row.get("sample_id"),
                    "reference_number": row.get("reference_number"),
                    "lot_number": row.get("lot_number"),
                    "sublot_number": row.get("sublot_number"),
                    "batch_number": row.get("batch_number"),
                    "test_date": row.get("test_date")
                    or raw.get("date_tested")
                    or raw.get("report_date"),
                    "received_date": row.get("received_date")
                    or raw.get("received_date"),
                    "confidence": confidence,
                    "warnings": row_warnings,
                    "metadata": metadata,
                    "matched_lab_test_type_id": lab_type.id if lab_type else None,
                    "match_source": match_source,
                    "alias_id": alias_id,
                }
            )
        return {
            "identifiers": raw.get("identifiers") or [],
            "lab_name": lab_name,
            "date_tested": raw.get("date_tested")
            or raw.get("report_date")
            or raw.get("received_date"),
            "report_date": raw.get("report_date"),
            "received_date": raw.get("received_date"),
            "rows": rows,
            "warnings": warnings + self._extraction_warnings(raw),
        }

    def _normalize_test_name(self, value: str) -> str:
        key = re.sub(r"[^a-z0-9]+", " ", value.strip().lower()).strip()
        if key in TEST_NAME_NORMALIZATION:
            return TEST_NAME_NORMALIZATION[key]
        if key in METALS:
            return METALS[key]
        return value.strip()

    def _resolve_lab_type_match(
        self,
        db: Session,
        raw_name: str,
        lab_name: Optional[str],
        lab_types_by_name: dict[str, LabTestType],
        active_lab_types: list[LabTestType],
    ) -> tuple[str, Optional[LabTestType], str, Optional[int]]:
        raw_clean = (raw_name or "").strip()
        exact = lab_types_by_name.get(raw_clean.casefold())
        if exact:
            return exact.test_name, exact, "exact", None

        built_in_name = self._normalize_test_name(raw_clean)
        if built_in_name != raw_clean:
            built_in = lab_types_by_name.get(built_in_name.casefold())
            if not built_in:
                built_in = self._find_lab_type_by_alias_key(
                    built_in_name, active_lab_types
                )
            if built_in:
                return built_in.test_name, built_in, "builtin_alias", None
            return built_in_name, None, "builtin_alias", None

        alias_match = self.alias_service.resolve_approved_alias(db, raw_clean, lab_name)
        if alias_match:
            return (
                alias_match.lab_test_type.test_name,
                alias_match.lab_test_type,
                "approved_alias",
                alias_match.alias_id,
            )

        fuzzy = self.alias_service.find_fuzzy_lab_test_type(raw_clean, active_lab_types)
        if fuzzy:
            return fuzzy.lab_test_type.test_name, fuzzy.lab_test_type, "fuzzy", None

        return raw_clean, None, "unmatched", None

    def _find_lab_type_by_alias_key(
        self, test_name: str, active_lab_types: list[LabTestType]
    ) -> Optional[LabTestType]:
        key = normalize_alias_key(test_name)
        if not key:
            return None
        return next(
            (
                lab_type
                for lab_type in active_lab_types
                if normalize_alias_key(lab_type.test_name) == key
            ),
            None,
        )

    def _extraction_warnings(self, raw: dict[str, Any]) -> list[str]:
        row_sample_refs = set()
        row_lot_refs = set()
        for row in raw.get("rows") or []:
            refs = {
                self._normalize_token(row.get("sample_id")),
                self._normalize_token(row.get("reference_number")),
            }
            refs.discard("")
            row_sample_refs.update(refs)
            lot_ref = self._normalize_token(row.get("lot_number"))
            if lot_ref:
                row_lot_refs.add(lot_ref)

        identifiers_by_type: dict[str, set[str]] = {}
        lot_identifier_values = set()
        for identifier in raw.get("identifiers") or []:
            identifier_type = str(identifier.get("type") or "").strip().lower()
            value = self._normalize_token(identifier.get("value"))
            if not value:
                continue
            if identifier_type in {"lot", "lot_number", "batch", "batch_number"}:
                lot_identifier_values.add(value)
            elif identifier_type in {"sample", "sample_id", "reference_number"}:
                identifiers_by_type.setdefault(identifier_type, set()).add(value)

        top_level_sample_refs = (
            set().union(*identifiers_by_type.values()) if identifiers_by_type else set()
        )
        sample_refs = row_sample_refs | top_level_sample_refs
        lot_refs = row_lot_refs | lot_identifier_values

        warnings = []
        if (
            len(sample_refs) > 1
            or any(len(values) > 1 for values in identifiers_by_type.values())
            or len(lot_refs) > 1
        ):
            warnings.append(
                "Multiple sample identifiers detected; split this PDF before importing"
            )
        return warnings

    def _looks_per_serving(self, value: Any) -> bool:
        return "serving" in str(value or "").lower()

    def _is_metal(self, test_name: str, lab_type: Any) -> bool:
        """Lab-agnostic heavy-metal detection (any lab, not just Harken)."""
        if test_name in set(METALS.values()):
            return True
        return bool(lab_type is not None and getattr(lab_type, "is_heavy_metal", False))

    def _normalize_harken_metal_value(self, value: Any, unit: Any) -> Any:
        if value is None:
            return None
        unit_token = self._normalize_token(str(unit or ""))
        factor = {"PPB": 0.001, "NGG": 0.001}.get(unit_token)
        if factor is None:
            return value
        match = re.match(r"^\s*([<>]=?)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*$", str(value))
        if not match:
            return value
        prefix = match.group(1) or ""
        number = float(match.group(2).replace(",", "")) * factor
        converted = f"{number:.6f}".rstrip("0").rstrip(".")
        return f"{prefix}{converted}"

    def _page_count(self, content: bytes) -> int:
        try:
            return len(PdfReader(io.BytesIO(content)).pages)
        except Exception:
            raise ValueError("Could not read PDF page count")

    def _extract_text(self, content: bytes) -> str:
        try:
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""

    def _safe_filename(self, filename: str) -> str:
        name = filename or "result.pdf"
        return "".join(
            char if char.isalnum() or char in ".-_" else "_" for char in name
        )

    def _normalize_token(self, value: Optional[str]) -> str:
        return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

    def _lot_candidate_payload(
        self, lot: Lot, score: float, reasons: list[str]
    ) -> dict[str, Any]:
        return {
            "lot_id": lot.id,
            "reference_number": lot.reference_number,
            "lot_number": lot.lot_number,
            "status": lot.status.value,
            "score": score,
            "reasons": reasons,
            "products": [
                lp.product.display_name for lp in lot.lot_products if lp.product
            ],
        }

    def _result_snapshot(self, result: TestResult) -> dict[str, Any]:
        return {
            "test_type": result.test_type,
            "result_value": result.result_value,
            "unit": result.unit,
            "test_date": (
                result.test_date.isoformat()
                if isinstance(result.test_date, date)
                else result.test_date
            ),
            "pdf_source": result.pdf_source,
            "confidence_score": (
                float(result.confidence_score)
                if result.confidence_score is not None
                else None
            ),
            "specification": result.specification,
            "method": result.method,
            "notes": result.notes,
            "lab_test_type_id": result.lab_test_type_id,
            "include_on_coa": result.include_on_coa,
        }

    def _audit_entity(
        self,
        db: Session,
        table_name: str,
        action: AuditAction,
        record_id: int,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Write a non-fatal audit row for an arbitrary table."""
        try:
            AuditLog.log_change(
                session=db,
                table_name=table_name,
                record_id=record_id,
                action=action,
                old_values=old_values,
                new_values=new_values,
                user=user_id,
                reason=reason,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "Failed to create audit log for %s#%s: %s",
                table_name,
                record_id,
                exc,
            )

    def _snapshot_value(self, result: TestResult, key: str) -> Any:
        value = getattr(result, key)
        if key == "test_date" and isinstance(value, date):
            return value.isoformat()
        if key == "confidence_score" and value is not None:
            return float(value)
        return value

    def _created_result_snapshot(
        self, ledger: ResultImportLedger, result_id: int
    ) -> Optional[dict[str, Any]]:
        for row in ledger.applied_rows or []:
            if row.get("test_result_id") == result_id and row.get("result_snapshot"):
                return row["result_snapshot"]
        return None

    def _delete_storage_key(self, storage_key: str, context: str) -> None:
        try:
            get_storage_service().delete(storage_key)
        except Exception as exc:
            logger.warning(
                f"Failed to delete storage key {storage_key} for {context}: {exc}"
            )

    def _row_notes(self, row: dict[str, Any]) -> Optional[str]:
        metadata = row.get("metadata") or {}
        parts = []
        if row.get("unit_raw") and row.get("unit_raw") != row.get("target_unit"):
            parts.append(f"Lab unit: {row['unit_raw']}")
        if row.get("limit_raw"):
            parts.append(f"Lab limit: {row['limit_raw']}")
        for key in ["lod", "loq", "per_serving"]:
            if metadata.get(key):
                parts.append(f"{key.upper()}: {metadata[key]}")
        if metadata.get("mass_basis_value"):
            unit = metadata.get("mass_basis_unit") or "ug/g"
            parts.append(f"Mass basis: {metadata['mass_basis_value']} {unit}")
        return "; ".join(parts) or None

    def _parse_date(self, value: Any) -> Optional[date]:
        if isinstance(value, date):
            return value
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    def _append_pdf_attachment(
        self, existing: Any, attachment: dict[str, Any]
    ) -> list[dict[str, Any]]:
        entries = self._normalize_pdf_attachments(existing)
        if not any(
            entry.get("storage_key") == attachment["storage_key"] for entry in entries
        ):
            entries.append(attachment)
        return entries

    def _normalize_pdf_attachments(self, value: Any) -> list[dict[str, Any]]:
        entries = []
        for entry in value or []:
            if isinstance(entry, dict):
                entries.append(entry)
            elif isinstance(entry, str):
                entries.append(
                    {
                        "filename": entry.split("/")[-1],
                        "storage_key": (
                            entry if entry.startswith("pdfs/") else f"pdfs/{entry}"
                        ),
                        "source": "legacy",
                        "import_id": None,
                        "added_at": None,
                    }
                )
        return entries

    def _storage_key_has_references(
        self, db: Session, storage_key: str, exclude_import_id: Optional[int] = None
    ) -> bool:
        result_reference = (
            db.query(TestResult.id).filter(TestResult.pdf_source == storage_key).first()
        )
        if result_reference:
            return True

        imports = db.query(ResultImport.id).filter(
            ResultImport.storage_key == storage_key
        )
        if exclude_import_id is not None:
            imports = imports.filter(ResultImport.id != exclude_import_id)
        if imports.first():
            return True

        for lot in db.query(Lot).filter(Lot.attached_pdfs.isnot(None)).all():
            for entry in self._normalize_pdf_attachments(lot.attached_pdfs):
                if (
                    entry.get("storage_key") == storage_key
                    and entry.get("import_id") != exclude_import_id
                ):
                    return True
        return False
