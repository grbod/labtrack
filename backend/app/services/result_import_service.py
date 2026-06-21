"""Service layer for the results importer workflow."""

from __future__ import annotations

import hashlib
import io
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from PyPDF2 import PdfReader
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import (
    AuditAction,
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
from app.services.lot_service import LotService
from app.services.result_extraction_provider import (
    ExtractionConfigurationError,
    get_extraction_provider,
)
from app.services.retest_service import retest_service
from app.services.storage_service import get_storage_service


ACTIVE_MATCH_STATUSES = [
    LotStatus.AWAITING_RESULTS,
    LotStatus.PARTIAL_RESULTS,
    LotStatus.NEEDS_ATTENTION,
    LotStatus.UNDER_REVIEW,
    LotStatus.AWAITING_RELEASE,
]

TEST_NAME_NORMALIZATION = {
    "total yeast & mold count": "Yeast & Mold",
    "total yeast and mold count": "Yeast & Mold",
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
METALS = {"lead": "Lead", "arsenic": "Arsenic", "cadmium": "Cadmium", "mercury": "Mercury"}


class ResultImportService(BaseService[ResultImport]):
    """Business logic for uploading, parsing, applying, and reverting imports."""

    STALE_AFTER = timedelta(minutes=20)

    def __init__(self) -> None:
        super().__init__(ResultImport)

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
            raise ValueError("OPENROUTER_API_KEY is required for results importer extraction")

        max_size = settings.max_upload_size_mb * 1024 * 1024
        validated: list[dict[str, Any]] = []

        for filename, content, content_type in files:
            if content_type != "application/pdf" and not filename.lower().endswith(".pdf"):
                raise ValueError("Only PDF files are allowed")
            if len(content) > max_size:
                raise ValueError(f"{filename} exceeds the {settings.max_upload_size_mb}MB limit")
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

        for payload in validated:
            filename = payload["filename"]
            duplicate = (
                db.query(ResultImport)
                .filter(
                    ResultImport.file_hash == payload["file_hash"],
                    ResultImport.status == ResultImportStatus.CONFIRMED,
                )
                .order_by(ResultImport.confirmed_at.desc().nullslast())
                .first()
            )
            if duplicate:
                duplicates.append(duplicate)
                continue

            safe_name = self._safe_filename(filename)
            storage_key = f"pdfs/result-imports/{datetime.utcnow():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}_{safe_name}"
            storage.upload(payload["content"], storage_key, content_type="application/pdf")

            item = ResultImport(
                original_filename=filename,
                storage_key=storage_key,
                file_hash=payload["file_hash"],
                status=ResultImportStatus.PROCESSING,
                uploaded_by_id=user_id,
                openrouter_model=settings.openrouter_model,
                warnings=[],
            )
            db.add(item)
            db.flush()
            self._log_audit(
                db,
                action=AuditAction.INSERT,
                record_id=item.id,
                new_values={"original_filename": filename, "storage_key": storage_key},
                user_id=user_id,
                reason="Result import uploaded",
            )
            created.append(item)

        db.commit()
        for item in created + duplicates:
            db.refresh(item)
        return created, duplicates

    def duplicate_summary(self, item: ResultImport) -> dict[str, Any]:
        lot = item.selected_lot
        confirmer = item.confirmed_by
        return {
            "import_id": item.id,
            "original_filename": item.original_filename,
            "confirmed_at": item.confirmed_at.isoformat() if item.confirmed_at else None,
            "confirmed_by": (confirmer.full_name or confirmer.username) if confirmer else None,
            "lot_id": lot.id if lot else None,
            "reference_number": lot.reference_number if lot else None,
            "lot_number": lot.lot_number if lot else None,
        }

    def process_import(self, db: Session, import_id: int) -> ResultImport:
        item = self.get(db, import_id)
        if not item or item.status != ResultImportStatus.PROCESSING:
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
                warning for warning in extracted.get("warnings", []) if warning.startswith("Multiple sample")
            ]
            if multi_sample_warnings:
                item.extracted_data = extracted
                item.warnings = extracted.get("warnings", [])
                item.usage_metadata = usage
                item.openrouter_model = model
                item.status = ResultImportStatus.FAILED
                item.error_message = multi_sample_warnings[0]
                db.commit()
                db.refresh(item)
                return item
            candidates = self.match_candidates(db, extracted, item.original_filename)

            item.extracted_data = extracted
            item.match_candidates = candidates
            item.warnings = extracted.get("warnings", [])
            item.usage_metadata = usage
            item.openrouter_model = model
            item.error_message = None
            item.status = ResultImportStatus.NEEDS_CONFIRMATION
        except ExtractionConfigurationError as exc:
            item.status = ResultImportStatus.FAILED
            item.error_message = str(exc)
        except Exception as exc:
            item.status = ResultImportStatus.FAILED
            item.error_message = f"Failed to process PDF: {exc}"

        db.commit()
        db.refresh(item)
        return item

    def list_imports(self, db: Session, page: int, page_size: int) -> tuple[list[ResultImport], int]:
        self.reap_stale_processing(db)
        query = db.query(ResultImport).order_by(ResultImport.created_at.desc())
        total = query.count()
        return query.offset((page - 1) * page_size).limit(page_size).all(), total

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

    def retry(self, db: Session, import_id: int) -> ResultImport:
        item = self.get(db, import_id)
        if not item:
            raise ValueError("Import not found")
        if item.status not in [ResultImportStatus.FAILED, ResultImportStatus.PROCESSING]:
            raise ValueError("Only failed or stale imports can be retried")
        if item.status == ResultImportStatus.PROCESSING and item.updated_at > datetime.utcnow() - self.STALE_AFTER:
            raise ValueError("Import is still processing")
        if not item.storage_key or not get_storage_service().exists(item.storage_key):
            raise ValueError("Stored PDF is no longer available")
        item.status = ResultImportStatus.PROCESSING
        item.error_message = None
        db.commit()
        db.refresh(item)
        return item

    def cancel(self, db: Session, import_id: int, user_id: int) -> ResultImport:
        item = self.get(db, import_id)
        if not item:
            raise ValueError("Import not found")
        if item.status not in [ResultImportStatus.PROCESSING, ResultImportStatus.NEEDS_CONFIRMATION, ResultImportStatus.FAILED]:
            raise ValueError("Only unconfirmed imports can be cancelled")
        old_status = item.status.value
        if item.storage_key:
            get_storage_service().delete(item.storage_key)
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
        item = (
            db.query(ResultImport)
            .filter(ResultImport.id == import_id)
            .with_for_update()
            .first()
        )
        if not item:
            raise ValueError("Import not found")
        if item.status != ResultImportStatus.NEEDS_CONFIRMATION:
            raise ValueError("Import is not ready for confirmation")

        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot or lot.status not in ACTIVE_MATCH_STATUSES:
            raise ValueError("Select an active lot")

        rows_by_id = {row["row_id"]: row for row in (item.extracted_data or {}).get("rows", [])}
        created_ids: list[int] = []
        updated: list[dict[str, Any]] = []
        applied_rows: list[dict[str, Any]] = []
        skipped_row_ids: list[str] = []

        for action in row_actions:
            if action.action == "skip":
                skipped_row_ids.append(action.row_id)
                continue
            row = rows_by_id.get(action.row_id)
            if not row:
                raise ValueError(f"Extracted row {action.row_id} not found")

            test_name, unit, specification, method, lab_test_type_id = self._resolve_test_fields(
                db, lot, row, action.lab_test_type_id, action.test_name
            )
            if not lab_test_type_id and action.action != "create_adhoc":
                raise ValueError(f"{test_name} is not mapped; choose a lab test type or create ad-hoc")
            if action.action == "create_adhoc" and not test_name:
                raise ValueError(f"Row {action.row_id} needs a test name for ad-hoc creation")
            result_value = row.get("result_value_raw")
            if result_value is None or str(result_value).strip() == "":
                raise ValueError(f"Row {action.row_id} has no result value")

            existing = self._find_existing_result(db, lot.id, test_name, action.test_result_id)
            if existing:
                if existing.status == TestResultStatus.APPROVED:
                    raise ValueError(f"{test_name} is already approved and cannot be modified")
                if action.action != "replace" and existing.result_value:
                    raise ValueError(f"{test_name} already has a draft value; choose replace")
                old = self._result_snapshot(existing)
                existing.result_value = str(result_value).strip()
                existing.unit = unit
                existing.test_date = self._parse_date(row.get("test_date") or (item.extracted_data or {}).get("date_tested"))
                existing.pdf_source = item.storage_key
                existing.confidence_score = row.get("confidence")
                existing.specification = specification
                existing.method = method
                existing.notes = self._row_notes(row)
                existing.lab_test_type_id = lab_test_type_id
                updated.append({"id": existing.id, "old": old, "new": self._result_snapshot(existing)})
                applied_rows.append({"row_id": action.row_id, "test_result_id": existing.id, "action": "replace"})
                retest_service.check_and_complete_retest(db, existing.id, user_id=user_id)
            else:
                if action.action not in ["apply", "create_adhoc"]:
                    raise ValueError(f"No draft row exists for {test_name}; choose apply")
                result = TestResult(
                    lot_id=lot.id,
                    test_type=test_name,
                    result_value=str(result_value).strip(),
                    unit=unit,
                    test_date=self._parse_date(row.get("test_date") or (item.extracted_data or {}).get("date_tested")),
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
                applied_rows.append({"row_id": action.row_id, "test_result_id": result.id, "action": action.action})

        if not created_ids and not updated:
            raise ValueError("Confirm requires at least one applied result row")

        attachment = {
            "filename": item.original_filename,
            "storage_key": item.storage_key,
            "source": "import",
            "import_id": item.id,
            "added_at": datetime.utcnow().isoformat(),
        }
        lot.attached_pdfs = self._append_pdf_attachment(lot.attached_pdfs, attachment)

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
            "status": item.status.value,
        }

    def revert(self, db: Session, import_id: int, user_id: int, user_role: UserRole) -> ResultImport:
        item = self.get(db, import_id)
        if not item:
            raise ValueError("Import not found")
        if item.status != ResultImportStatus.CONFIRMED:
            raise ValueError("Only confirmed imports can be reverted")
        if item.confirmed_by_id != user_id and user_role not in [UserRole.ADMIN, UserRole.QC_MANAGER]:
            raise ValueError("Only the confirmer, QC Manager, or Admin can revert this import")

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
            db.delete(result)

        for entry in ledger.updated_results or []:
            result = db.query(TestResult).filter(TestResult.id == entry["id"]).first()
            if not result:
                raise ValueError("Cannot revert because an updated row is missing")
            if result.status != TestResultStatus.DRAFT:
                raise ValueError("Cannot revert because an updated row was approved")
            expected = entry["new"]
            if any(getattr(result, key) != expected.get(key) for key in ["result_value", "unit", "pdf_source"]):
                raise ValueError("Cannot revert because an updated row changed after import")
            for key, value in entry["old"].items():
                if key == "test_date":
                    value = self._parse_date(value)
                setattr(result, key, value)

        lot = db.query(Lot).filter(Lot.id == ledger.lot_id).first()
        if lot and ledger.pdf_attachment:
            lot.attached_pdfs = [
                entry
                for entry in self._normalize_pdf_attachments(lot.attached_pdfs)
                if entry.get("storage_key") != ledger.pdf_attachment.get("storage_key")
            ]
            storage_key = ledger.pdf_attachment.get("storage_key")
            if storage_key:
                get_storage_service().delete(storage_key)

        item.status = ResultImportStatus.REVERTED
        item.reverted_at = datetime.utcnow()
        if lot:
            calculation = LotService().calculate_lot_status(db, lot)
            LotService()._apply_lot_status_calculation(
                db, calculation, user_id=user_id, reason_prefix="Results import revert"
            )
        db.commit()
        db.refresh(item)
        return item

    def preview_rows(self, db: Session, import_id: int, lot_id: int) -> dict[str, Any]:
        item = self.get(db, import_id)
        if not item:
            raise ValueError("Import not found")
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot or lot.status not in ACTIVE_MATCH_STATUSES:
            raise ValueError("Select an active lot")

        previews = []
        for row in (item.extracted_data or {}).get("rows", []):
            test_name, unit, specification, method, lab_test_type_id = self._resolve_test_fields(
                db,
                lot,
                row,
                row.get("matched_lab_test_type_id"),
                row.get("test_name_normalized") or row.get("test_name_raw"),
            )
            existing = self._find_existing_result(db, lot.id, test_name, None)
            warnings = list(row.get("warnings") or [])
            requires_mapping = not lab_test_type_id
            if requires_mapping:
                warnings.append("No active lab test type matched")

            if existing and existing.status == TestResultStatus.APPROVED:
                suggested_action = "skip"
            elif existing and existing.result_value:
                suggested_action = "skip"
            elif requires_mapping:
                suggested_action = "skip"
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
                    "existing_result": self._existing_result_payload(existing) if existing else None,
                }
            )
        return {"import_id": item.id, "lot_id": lot.id, "rows": previews}

    def link_candidates(self, db: Session, search: str, limit: int = 20) -> list[dict[str, Any]]:
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

    def match_candidates(self, db: Session, extracted: dict[str, Any], filename: str) -> list[dict[str, Any]]:
        tokens = {
            self._normalize_token(identifier.get("value"))
            for identifier in extracted.get("identifiers", [])
            if identifier.get("value")
        }
        tokens.update(self._normalize_token(part) for part in re.findall(r"[A-Z0-9][A-Z0-9-]{3,}", filename.upper()))
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
                "reference": lot.reference_number,
                "lot": lot.lot_number,
                "sublot": " ".join(s.sublot_number for s in lot.sublots),
                "batch": " ".join(lp.batch_number or "" for lp in lot.lot_products),
            }
            for label, value in values.items():
                normalized = self._normalize_token(value)
                if normalized and normalized in tokens:
                    score += 0.5 if label in ["reference", "lot"] else 0.25
                    reasons.append(f"{label} matched")
            if score:
                candidates.append(self._lot_candidate_payload(lot, min(score, 1.0), reasons))
        return sorted(candidates, key=lambda item: item["score"], reverse=True)[:10]

    def _resolve_test_fields(
        self,
        db: Session,
        lot: Lot,
        row: dict[str, Any],
        lab_test_type_id: Optional[int],
        override_name: Optional[str],
    ) -> tuple[str, Optional[str], Optional[str], Optional[str], Optional[int]]:
        test_name = override_name or row.get("test_name_normalized") or row.get("test_name_raw")
        lab_type = None
        if lab_test_type_id:
            lab_type = db.query(LabTestType).filter(LabTestType.id == lab_test_type_id, LabTestType.is_active == True).first()
            if not lab_type:
                raise ValueError("Selected lab test type not found")
            test_name = lab_type.test_name
        elif row.get("matched_lab_test_type_id"):
            lab_type = (
                db.query(LabTestType)
                .filter(LabTestType.id == row["matched_lab_test_type_id"], LabTestType.is_active == True)
                .first()
            )

        spec = self._find_lot_spec(lot, test_name)
        if spec and spec.lab_test_type:
            lab_type = spec.lab_test_type
            test_name = lab_type.test_name
        unit = spec.test_unit if spec else (lab_type.default_unit if lab_type else row.get("target_unit") or row.get("unit_raw"))
        specification = spec.specification if spec else (lab_type.default_specification if lab_type else row.get("limit_raw"))
        method = spec.lab_test_type.test_method if spec and spec.lab_test_type else (lab_type.test_method if lab_type else None)
        return test_name, unit, specification, method, lab_type.id if lab_type else None

    def _find_lot_spec(self, lot: Lot, test_name: str) -> Optional[ProductTestSpecification]:
        for lot_product in lot.lot_products:
            for spec in lot_product.product.test_specifications:
                if spec.test_name and spec.test_name.lower() == (test_name or "").lower():
                    return spec
        return None

    def _existing_result_payload(self, result: TestResult) -> dict[str, Any]:
        return {
            "id": result.id,
            "test_type": result.test_type,
            "result_value": result.result_value,
            "unit": result.unit,
            "status": result.status.value if hasattr(result.status, "value") else result.status,
            "test_date": result.test_date.isoformat() if isinstance(result.test_date, date) else result.test_date,
            "pdf_source": result.pdf_source,
        }

    def _find_existing_result(
        self, db: Session, lot_id: int, test_name: str, result_id: Optional[int]
    ) -> Optional[TestResult]:
        if result_id:
            return db.query(TestResult).filter(TestResult.id == result_id, TestResult.lot_id == lot_id).first()
        return (
            db.query(TestResult)
            .filter(TestResult.lot_id == lot_id, TestResult.test_type == test_name)
            .order_by(TestResult.created_at.desc())
            .first()
        )

    def _normalize_extraction(self, db: Session, raw: dict[str, Any]) -> dict[str, Any]:
        rows = []
        warnings = list(raw.get("warnings") or [])
        lab_types = {lt.test_name.lower(): lt for lt in db.query(LabTestType).filter(LabTestType.is_active == True).all()}
        for index, row in enumerate(raw.get("rows") or [], start=1):
            raw_name = row.get("test_name_raw") or ""
            normalized_name = self._normalize_test_name(raw_name)
            lab_type = lab_types.get(normalized_name.lower())
            unit_raw = row.get("unit_raw")
            target_unit = lab_type.default_unit if lab_type else unit_raw
            metadata = {key: row.get(key) for key in ["per_serving", "lod", "loq"] if row.get(key)}
            confidence = float(row.get("confidence") or 0)
            row_warnings = []
            if confidence < 0.7:
                row_warnings.append("Low confidence extraction")
            if row.get("per_serving") or self._looks_per_serving(unit_raw) or self._looks_per_serving(row.get("limit_raw")):
                row_warnings.append("Result appears to be per serving; verify COA basis")
            rows.append(
                {
                    "row_id": row.get("row_id") or f"row-{index}",
                    "test_name_raw": raw_name,
                    "test_name_normalized": normalized_name,
                    "result_value_raw": row.get("result_value_raw"),
                    "unit_raw": unit_raw,
                    "target_unit": target_unit,
                    "limit_raw": row.get("limit_raw"),
                    "test_date": row.get("test_date") or raw.get("date_tested") or raw.get("report_date"),
                    "received_date": row.get("received_date") or raw.get("received_date"),
                    "confidence": confidence,
                    "warnings": row_warnings,
                    "metadata": metadata,
                    "matched_lab_test_type_id": lab_type.id if lab_type else None,
                }
            )
        return {
            "identifiers": raw.get("identifiers") or [],
            "lab_name": raw.get("lab_name"),
            "date_tested": raw.get("date_tested") or raw.get("report_date") or raw.get("received_date"),
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

    def _extraction_warnings(self, raw: dict[str, Any]) -> list[str]:
        identifier_values = {
            self._normalize_token(identifier.get("value"))
            for identifier in raw.get("identifiers") or []
            if identifier.get("value")
        }
        row_refs = {
            self._normalize_token(row.get("reference_number") or row.get("lot_number") or row.get("sample_id"))
            for row in raw.get("rows") or []
        }
        identifier_values.discard("")
        row_refs.discard("")
        warnings = []
        if len(identifier_values | row_refs) > 1:
            warnings.append("Multiple sample identifiers detected; split this PDF before importing")
        return warnings

    def _looks_per_serving(self, value: Any) -> bool:
        return "serving" in str(value or "").lower()

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
        return "".join(char if char.isalnum() or char in ".-_" else "_" for char in name)

    def _normalize_token(self, value: Optional[str]) -> str:
        return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

    def _lot_candidate_payload(self, lot: Lot, score: float, reasons: list[str]) -> dict[str, Any]:
        return {
            "lot_id": lot.id,
            "reference_number": lot.reference_number,
            "lot_number": lot.lot_number,
            "status": lot.status.value,
            "score": score,
            "reasons": reasons,
            "products": [lp.product.display_name for lp in lot.lot_products if lp.product],
        }

    def _result_snapshot(self, result: TestResult) -> dict[str, Any]:
        return {
            "test_type": result.test_type,
            "result_value": result.result_value,
            "unit": result.unit,
            "test_date": result.test_date.isoformat() if isinstance(result.test_date, date) else result.test_date,
            "pdf_source": result.pdf_source,
            "confidence_score": float(result.confidence_score) if result.confidence_score is not None else None,
            "specification": result.specification,
            "method": result.method,
            "notes": result.notes,
            "lab_test_type_id": result.lab_test_type_id,
            "include_on_coa": result.include_on_coa,
        }

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

    def _append_pdf_attachment(self, existing: Any, attachment: dict[str, Any]) -> list[dict[str, Any]]:
        entries = self._normalize_pdf_attachments(existing)
        if not any(entry.get("storage_key") == attachment["storage_key"] for entry in entries):
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
                        "storage_key": entry if entry.startswith("pdfs/") else f"pdfs/{entry}",
                        "source": "legacy",
                        "import_id": None,
                        "added_at": None,
                    }
                )
        return entries
