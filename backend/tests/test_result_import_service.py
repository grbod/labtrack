"""Tests for the results importer service."""

from datetime import date, datetime, timedelta

import pytest
import requests

from app.models import (
    AuditAction,
    AuditLog,
    LabTestAlias,
    LabTestType,
    Lot,
    ResultImport,
    ResultImportLedger,
    ResultImportStatus,
    TestResult,
    TestResultStatus,
    UserRole,
)
from app.models.enums import LotStatus, LotType
from app.schemas.result_import import RowAction
from app.services.lab_test_alias_service import normalize_alias_key
from app.services.release_service import ReleaseService
from app.services.result_extraction_provider import (
    MockExtractionProvider,
    OpenRouterExtractionProvider,
)
from app.services.result_import_service import ResultImportService


def _audit_row(row_id: str = "row-1", value: str = "Negative") -> dict:
    return {
        "row_id": row_id,
        "test_name_raw": "Total Plate Count",
        "test_name_normalized": "Total Plate Count",
        "result_value_raw": value,
        "unit_raw": "CFU/g",
        "target_unit": "CFU/g",
        "limit_raw": None,
        "confidence": 0.9,
        "warnings": [],
        "metadata": {},
        "matched_lab_test_type_id": None,
    }


def test_audit_entity_writes_row_for_arbitrary_table(test_db, sample_user):
    service = ResultImportService()
    service._audit_entity(
        test_db,
        table_name="test_results",
        action=AuditAction.INSERT,
        record_id=12345,
        new_values={"result_value": "Negative"},
        user_id=sample_user.id,
    )
    test_db.commit()

    entry = (
        test_db.query(AuditLog)
        .filter(AuditLog.table_name == "test_results", AuditLog.record_id == 12345)
        .first()
    )
    assert entry is not None
    assert entry.action == AuditAction.INSERT
    assert entry.user_id == sample_user.id
    assert entry.get_new_values_dict().get("result_value") == "Negative"


def test_audit_entity_swallows_failures(test_db, sample_user):
    service = ResultImportService()
    service._audit_entity(
        test_db,
        table_name="test_results",
        action=AuditAction.DELETE,
        record_id=999,
        old_values={"result_value": "x"},
        user_id=sample_user.id,
        reason=None,
    )
    test_db.commit()

    entry = (
        test_db.query(AuditLog)
        .filter(AuditLog.table_name == "test_results", AuditLog.record_id == 999)
        .first()
    )
    assert entry is None


def test_mock_provider_does_not_invent_rows():
    provider = MockExtractionProvider()
    extracted = provider.extract(b"%PDF", "No known tests here", "unknown.pdf")
    assert extracted["rows"] == []
    assert extracted["warnings"]


def test_openrouter_retries_text_only_for_pdf_input_rejection(monkeypatch):
    monkeypatch.setattr(
        "app.services.result_extraction_provider.settings.openrouter_api_key",
        "test-key",
    )
    calls = []

    class FakeResponse:
        status_code = 400
        text = "unsupported pdf file input"

        def raise_for_status(self):
            if len(calls) == 1:
                raise requests.HTTPError(response=self)

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"identifiers":[],"lab_name":"Lab","rows":[],"warnings":[]}'
                        }
                    }
                ],
                "model": "test-model",
            }

    def fake_post(*args, **kwargs):
        calls.append(kwargs["json"]["messages"][0]["content"])
        return FakeResponse()

    monkeypatch.setattr(
        "app.services.result_extraction_provider.requests.post", fake_post
    )

    result = OpenRouterExtractionProvider().extract(
        b"%PDF", "extracted text", "coa.pdf"
    )

    assert result["lab_name"] == "Lab"
    assert len(calls) == 2
    assert any(part["type"] == "file" for part in calls[0])
    assert all(part["type"] != "file" for part in calls[1])


def test_openrouter_does_not_retry_text_only_for_auth_error(monkeypatch):
    monkeypatch.setattr(
        "app.services.result_extraction_provider.settings.openrouter_api_key",
        "test-key",
    )

    class FakeResponse:
        status_code = 401
        text = "invalid api key"

        def raise_for_status(self):
            raise requests.HTTPError(response=self)

    monkeypatch.setattr(
        "app.services.result_extraction_provider.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(requests.HTTPError):
        OpenRouterExtractionProvider().extract(b"%PDF", "extracted text", "coa.pdf")


def test_candidate_matching_uses_lot_identifiers(test_db, sample_lot):
    service = ResultImportService()
    extracted = {"identifiers": [{"type": "reference_number", "value": "241101-001"}]}
    candidates = service.match_candidates(test_db, extracted, "result.pdf")
    assert candidates[0]["lot_id"] == sample_lot.id
    assert any(
        "matched COA reference" in reason and sample_lot.reference_number in reason
        for reason in candidates[0]["reasons"]
    )


def test_candidate_matching_uses_row_level_identifiers(test_db, sample_lot):
    service = ResultImportService()
    extracted = service._normalize_extraction(
        test_db,
        {
            "identifiers": [],
            "rows": [
                {
                    "row_id": "row-1",
                    "reference_number": sample_lot.reference_number,
                    "test_name_raw": "Lead",
                    "result_value_raw": "0.1",
                    "confidence": 0.9,
                }
            ],
        },
    )

    candidates = service.match_candidates(test_db, extracted, "result.pdf")

    assert candidates[0]["lot_id"] == sample_lot.id
    assert any(
        "matched COA reference" in reason and sample_lot.reference_number in reason
        for reason in candidates[0]["reasons"]
    )


def test_candidate_matching_uses_row_level_batch_identifier(test_db, sample_lot):
    sample_lot.lot_products[0].batch_number = "BATCH-123"
    test_db.commit()
    service = ResultImportService()
    extracted = service._normalize_extraction(
        test_db,
        {
            "identifiers": [],
            "rows": [
                {
                    "row_id": "row-1",
                    "batch_number": "BATCH-123",
                    "test_name_raw": "Lead",
                    "result_value_raw": "0.1",
                    "confidence": 0.9,
                }
            ],
        },
    )

    candidates = service.match_candidates(test_db, extracted, "result.pdf")

    assert candidates[0]["lot_id"] == sample_lot.id
    assert "Batch BATCH-123 matched COA batch number" in candidates[0]["reasons"]


def test_upload_fails_without_openrouter_key_when_live_provider(
    test_db, sample_user, monkeypatch
):
    monkeypatch.setattr(
        "app.services.result_import_service.settings.ai_provider", "openrouter"
    )
    monkeypatch.setattr(
        "app.services.result_import_service.settings.openrouter_api_key", None
    )

    try:
        ResultImportService().create_uploads(
            test_db,
            [("coa.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")],
            sample_user.id,
        )
    except ValueError as exc:
        assert "OPENROUTER_API_KEY" in str(exc)
    else:
        raise AssertionError("upload should fail without OpenRouter configuration")


def test_confirm_creates_draft_results_and_attachment(
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="a" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data={
            "date_tested": "2026-06-20",
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Total Plate Count",
                    "test_name_normalized": "Total Plate Count",
                    "result_value_raw": "< 10",
                    "unit_raw": "CFU/g",
                    "target_unit": "CFU/g",
                    "limit_raw": "< 10000",
                    "confidence": 0.9,
                    "warnings": [],
                    "metadata": {},
                    "matched_lab_test_type_id": None,
                }
            ],
        },
    )
    test_db.add(import_row)
    test_db.commit()

    result = ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="apply")],
        sample_user.id,
    )

    assert result["created_result_ids"]
    created = (
        test_db.query(TestResult)
        .filter(TestResult.id == result["created_result_ids"][0])
        .one()
    )
    assert created.status == TestResultStatus.DRAFT
    assert created.result_value == "< 10"
    assert created.pdf_source == "pdfs/result-imports/coa.pdf"
    test_db.refresh(sample_lot)
    assert sample_lot.attached_pdfs[0]["source"] == "import"


def test_confirm_persists_corrected_result_value(
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="b" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data={
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Total Plate Count",
                    "test_name_normalized": "Total Plate Count",
                    "result_value_raw": "15,000",
                    "unit_raw": "CFU/g",
                    "target_unit": "CFU/g",
                    "limit_raw": "< 10000",
                    "confidence": 0.9,
                    "warnings": [],
                    "metadata": {},
                    "matched_lab_test_type_id": None,
                }
            ],
        },
    )
    test_db.add(import_row)
    test_db.commit()

    result = ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="apply", result_value="8,000")],
        sample_user.id,
    )

    created = (
        test_db.query(TestResult)
        .filter(TestResult.id == result["created_result_ids"][0])
        .one()
    )
    assert created.result_value == "8,000"


def test_confirm_rejects_mismatched_test_result_id(
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    existing = TestResult(
        lot_id=sample_lot.id,
        test_type="Lead",
        result_value="0.1",
        unit="ppm",
        status=TestResultStatus.DRAFT,
    )
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="z" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data={
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Total Plate Count",
                    "test_name_normalized": "Total Plate Count",
                    "result_value_raw": "< 10",
                    "unit_raw": "CFU/g",
                    "target_unit": "CFU/g",
                    "limit_raw": "< 10000",
                    "confidence": 0.9,
                    "warnings": [],
                    "metadata": {},
                    "matched_lab_test_type_id": None,
                }
            ],
        },
    )
    test_db.add_all([existing, import_row])
    test_db.commit()

    with pytest.raises(ValueError, match="does not match extracted test"):
        ResultImportService().confirm(
            test_db,
            import_row.id,
            sample_lot.id,
            [
                RowAction(
                    row_id="row-1",
                    action="replace",
                    test_result_id=existing.id,
                )
            ],
            sample_user.id,
        )

    test_db.refresh(existing)
    assert existing.test_type == "Lead"
    assert existing.result_value == "0.1"


def test_confirm_audits_created_result(
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa.pdf",
        file_hash="hash-create-audit",
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        extracted_data={"rows": [_audit_row(value="< 10,000 CFU/g")]},
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    result = ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="apply")],
        sample_user.id,
    )
    created_id = result["created_result_ids"][0]

    entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "test_results",
            AuditLog.record_id == created_id,
            AuditLog.action == AuditAction.INSERT,
        )
        .first()
    )
    assert entry is not None
    assert entry.user_id == sample_user.id
    assert entry.get_new_values_dict().get("result_value") == "< 10,000 CFU/g"


def test_confirm_audits_replaced_result(
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    existing = TestResult(
        lot_id=sample_lot.id,
        test_type="Total Plate Count",
        result_value="old value",
        status=TestResultStatus.DRAFT,
    )
    test_db.add(existing)
    test_db.commit()

    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa2.pdf",
        file_hash="hash-replace-audit",
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        extracted_data={"rows": [_audit_row(value="new value")]},
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="replace")],
        sample_user.id,
    )

    entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "test_results",
            AuditLog.record_id == existing.id,
            AuditLog.action == AuditAction.UPDATE,
        )
        .first()
    )
    assert entry is not None
    assert entry.get_old_values_dict().get("result_value") == "old value"
    assert entry.get_new_values_dict().get("result_value") == "new value"


def test_confirm_audits_pdf_attachment_on_lot(
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa3.pdf",
        file_hash="hash-pdf-audit",
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        extracted_data={"rows": [_audit_row()]},
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="apply")],
        sample_user.id,
    )

    entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "lots",
            AuditLog.record_id == sample_lot.id,
            AuditLog.action == AuditAction.UPDATE,
            AuditLog.reason == "Result import: source PDF attached",
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert entry is not None
    assert "attached_pdfs" in entry.get_new_values_dict()


def test_confirm_audits_awaiting_release_pullback(
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    sample_lot.status = LotStatus.AWAITING_RELEASE
    test_db.commit()

    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa-pullback.pdf",
        file_hash="hash-pullback-audit",
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        extracted_data={"rows": [_audit_row()]},
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="apply")],
        sample_user.id,
    )

    lot_audits = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "lots",
            AuditLog.record_id == sample_lot.id,
            AuditLog.action == AuditAction.UPDATE,
        )
        .all()
    )
    pullback = [
        entry
        for entry in lot_audits
        if entry.get_old_values_dict().get("status") == "awaiting_release"
        and entry.get_new_values_dict().get("status") == "under_review"
    ]
    assert pullback


def test_confirm_rejects_zero_applied_rows(test_db, sample_lot, sample_user):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="b" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data={"rows": []},
    )
    test_db.add(import_row)
    test_db.commit()

    try:
        ResultImportService().confirm(
            test_db,
            import_row.id,
            sample_lot.id,
            [RowAction(row_id="missing", action="skip")],
            sample_user.id,
        )
    except ValueError as exc:
        assert "at least one applied" in str(exc)
    else:
        raise AssertionError("confirm should fail with zero applied rows")


def test_confirm_rejects_unmapped_apply(test_db, sample_lot, sample_user):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="c" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data={
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Unknown Marker",
                    "test_name_normalized": "Unknown Marker",
                    "result_value_raw": "12",
                    "unit_raw": "ppm",
                    "target_unit": "ppm",
                    "limit_raw": None,
                    "confidence": 0.9,
                    "warnings": [],
                    "metadata": {},
                    "matched_lab_test_type_id": None,
                }
            ]
        },
    )
    test_db.add(import_row)
    test_db.commit()

    try:
        ResultImportService().confirm(
            test_db,
            import_row.id,
            sample_lot.id,
            [RowAction(row_id="row-1", action="apply")],
            sample_user.id,
        )
    except ValueError as exc:
        assert "not mapped" in str(exc)
    else:
        raise AssertionError("unmapped apply should be rejected")


def test_confirm_rejects_unmapped_adhoc(test_db, sample_lot, sample_user):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="j" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data={
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Unknown Marker",
                    "test_name_normalized": "Unknown Marker",
                    "result_value_raw": "12",
                    "unit_raw": "lab unit",
                    "target_unit": "lab unit",
                    "limit_raw": "< 20",
                    "confidence": 0.9,
                    "warnings": [],
                    "metadata": {},
                    "matched_lab_test_type_id": None,
                }
            ]
        },
    )
    test_db.add(import_row)
    test_db.commit()

    try:
        ResultImportService().confirm(
            test_db,
            import_row.id,
            sample_lot.id,
            [
                RowAction(
                    row_id="row-1", action="create_adhoc", test_name="Unknown Marker"
                )
            ],
            sample_user.id,
        )
    except ValueError as exc:
        assert "active lab test type" in str(exc)
    else:
        raise AssertionError("unmapped ad-hoc row should be rejected")


def test_confirm_adhoc_uses_lab_type_defaults(
    test_db, sample_lot, sample_user, sample_lab_test_types
):
    gluten = next(
        test_type
        for test_type in sample_lab_test_types
        if test_type.test_name == "Gluten"
    )
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="k" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data={
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Unknown Gluten Marker",
                    "test_name_normalized": "Unknown Gluten Marker",
                    "result_value_raw": "< 5",
                    "unit_raw": "lab-unit",
                    "target_unit": "lab-unit",
                    "limit_raw": "< 10 lab limit",
                    "confidence": 0.9,
                    "warnings": [],
                    "metadata": {},
                    "matched_lab_test_type_id": None,
                }
            ]
        },
    )
    test_db.add(import_row)
    test_db.commit()

    result = ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="create_adhoc", lab_test_type_id=gluten.id)],
        sample_user.id,
    )

    created = (
        test_db.query(TestResult)
        .filter(TestResult.id == result["created_result_ids"][0])
        .one()
    )
    assert created.test_type == "Gluten"
    assert created.unit == "ppm"
    assert created.method == "ELISA"
    assert "< 10 lab limit" in created.notes


def test_confirm_pulls_awaiting_release_lot_out_of_release_queue(
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    sample_lot.status = LotStatus.AWAITING_RELEASE
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="o" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data={
            "date_tested": "2026-06-20",
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Total Plate Count",
                    "test_name_normalized": "Total Plate Count",
                    "result_value_raw": "< 10",
                    "unit_raw": "CFU/g",
                    "target_unit": "CFU/g",
                    "limit_raw": "< 10000",
                    "confidence": 0.9,
                    "warnings": [],
                    "metadata": {},
                    "matched_lab_test_type_id": None,
                }
            ],
        },
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="apply")],
        sample_user.id,
    )

    test_db.refresh(sample_lot)
    assert sample_lot.status != LotStatus.AWAITING_RELEASE


def test_preview_defaults_existing_draft_to_skip(
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    existing = TestResult(
        lot_id=sample_lot.id,
        test_type="Total Plate Count",
        result_value="< 100",
        unit="CFU/g",
        status=TestResultStatus.DRAFT,
    )
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="d" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data={
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Total Plate Count",
                    "test_name_normalized": "Total Plate Count",
                    "result_value_raw": "< 10",
                    "unit_raw": "CFU/g",
                    "target_unit": "CFU/g",
                    "limit_raw": None,
                    "confidence": 0.9,
                    "warnings": [],
                    "metadata": {},
                    "matched_lab_test_type_id": None,
                }
            ]
        },
    )
    test_db.add_all([existing, import_row])
    test_db.commit()

    preview = ResultImportService().preview_rows(test_db, import_row.id, sample_lot.id)

    assert preview["rows"][0]["suggested_action"] == "skip"
    assert preview["rows"][0]["existing_result"]["id"] == existing.id


def test_harken_metal_names_normalize(test_db):
    service = ResultImportService()
    normalized = service._normalize_extraction(
        test_db,
        {
            "rows": [
                {
                    "row_id": "1",
                    "test_name_raw": "Pb (Lead)",
                    "result_value_raw": "0.1",
                    "confidence": 0.9,
                },
                {
                    "row_id": "2",
                    "test_name_raw": "Hg/Mercury",
                    "result_value_raw": "0.01",
                    "confidence": 0.9,
                },
            ]
        },
    )

    assert [row["test_name_normalized"] for row in normalized["rows"]] == [
        "Lead",
        "Mercury",
    ]


def test_total_yeast_mold_count_uses_builtin_without_fuzzy(
    test_db, sample_lab_test_types
):
    yeast_mold = LabTestType(
        test_name="Yeast & Mold",
        test_category="Microbiological",
        default_unit="CFU/g",
        test_method="AOAC 997.02",
        is_active=True,
    )
    test_db.add(yeast_mold)
    test_db.commit()

    normalized = ResultImportService()._normalize_extraction(
        test_db,
        {
            "rows": [
                {
                    "row_id": "1",
                    "test_name_raw": "Total Yeast & Mold Count",
                    "confidence": 0.95,
                }
            ]
        },
    )

    row = normalized["rows"][0]
    assert row["test_name_normalized"] == "Yeast & Mold"
    assert row["matched_lab_test_type_id"] == yeast_mold.id
    assert row["match_source"] == "builtin_alias"
    assert row["warnings"] == []


def test_builtin_alias_can_find_punctuation_equivalent_lab_type(test_db):
    yeast_mold = LabTestType(
        test_name="Yeast and Mold",
        test_category="Microbiological",
        default_unit="CFU/g",
        test_method="AOAC 997.02",
        is_active=True,
    )
    test_db.add(yeast_mold)
    test_db.commit()

    normalized = ResultImportService()._normalize_extraction(
        test_db,
        {
            "rows": [
                {
                    "row_id": "1",
                    "test_name_raw": "Total Yeast & Mold Count",
                    "confidence": 0.95,
                }
            ]
        },
    )

    row = normalized["rows"][0]
    assert row["test_name_normalized"] == "Yeast and Mold"
    assert row["matched_lab_test_type_id"] == yeast_mold.id
    assert row["match_source"] == "builtin_alias"
    assert row["warnings"] == []


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("Yst Mold", "Yeast & Mold"),
        ("Plate Count", "Total Plate Count"),
    ],
)
def test_safe_fuzzy_matches_record_warning(
    test_db, sample_lab_test_types, raw_name, expected
):
    if expected == "Yeast & Mold":
        test_db.add(
            LabTestType(
                test_name="Yeast & Mold",
                test_category="Microbiological",
                default_unit="CFU/g",
                test_method="AOAC 997.02",
                is_active=True,
            )
        )
        test_db.commit()

    normalized = ResultImportService()._normalize_extraction(
        test_db,
        {"rows": [{"row_id": "1", "test_name_raw": raw_name, "confidence": 0.95}]},
    )

    row = normalized["rows"][0]
    assert row["test_name_normalized"] == expected
    assert row["match_source"] == "fuzzy"
    assert row["metadata"]["fuzzy_source"] == raw_name
    assert row["metadata"]["fuzzy_target"] == expected
    assert any("Fuzzy matched" in warning for warning in row["warnings"])


@pytest.mark.parametrize(
    "raw_name",
    [
        "Mold",
        "Total Count",
        "Heavy Metals",
        "Heavy Metal",  # singular variant must also be rejected
        "Metals Panel",  # category + grouping word
        "Yeast",  # bare component of a combined test (Yeast & Mold)
    ],
)
def test_broad_fuzzy_phrases_remain_unmatched(test_db, sample_lab_test_types, raw_name):
    test_db.add(
        LabTestType(
            test_name="Yeast & Mold",
            test_category="Microbiological",
            default_unit="CFU/g",
            test_method="AOAC 997.02",
            is_active=True,
        )
    )
    test_db.commit()

    normalized = ResultImportService()._normalize_extraction(
        test_db,
        {"rows": [{"row_id": "1", "test_name_raw": raw_name, "confidence": 0.95}]},
    )

    row = normalized["rows"][0]
    assert row["test_name_normalized"] == raw_name
    assert row["matched_lab_test_type_id"] is None
    assert row["match_source"] == "unmatched"


def test_near_tie_fuzzy_phrase_remains_unmatched(test_db):
    test_db.add_all(
        [
            LabTestType(
                test_name="Alpha Beta",
                test_category="Chemical",
                default_unit="ppm",
                is_active=True,
            ),
            LabTestType(
                test_name="Alpha Beto",
                test_category="Chemical",
                default_unit="ppm",
                is_active=True,
            ),
        ]
    )
    test_db.commit()

    row = ResultImportService()._normalize_extraction(
        test_db,
        {"rows": [{"row_id": "1", "test_name_raw": "Alpha Bet", "confidence": 0.95}]},
    )["rows"][0]

    assert row["test_name_normalized"] == "Alpha Bet"
    assert row["matched_lab_test_type_id"] is None
    assert row["match_source"] == "unmatched"


def test_approved_lab_scoped_alias_beats_global_and_pending_disabled_ignored(
    test_db, sample_lab_test_types
):
    tpc, lead = sample_lab_test_types[0], sample_lab_test_types[2]
    test_db.add_all(
        [
            LabTestAlias(
                raw_phrase="TPC Count",
                normalized_key=normalize_alias_key("TPC Count"),
                lab_name="Acme",
                lab_test_type_id=lead.id,
                status="disabled",
                source="manual_override",
            ),
            LabTestAlias(
                raw_phrase="TPC Count",
                normalized_key=normalize_alias_key("TPC Count"),
                lab_name="Acme",
                lab_test_type_id=lead.id,
                status="pending",
                source="manual_override",
            ),
            LabTestAlias(
                raw_phrase="TPC Count",
                normalized_key=normalize_alias_key("TPC Count"),
                lab_name=None,
                lab_test_type_id=lead.id,
                status="approved",
                source="manual_override",
            ),
        ]
    )
    scoped_alias = LabTestAlias(
        raw_phrase="TPC Count",
        normalized_key=normalize_alias_key("TPC Count"),
        lab_name="Acme",
        lab_test_type_id=tpc.id,
        status="approved",
        source="manual_override",
    )
    test_db.add(scoped_alias)
    test_db.commit()

    row = ResultImportService()._normalize_extraction(
        test_db,
        {
            "lab_name": "Acme",
            "rows": [{"row_id": "1", "test_name_raw": "TPC Count", "confidence": 0.95}],
        },
    )["rows"][0]

    assert row["test_name_normalized"] == "Total Plate Count"
    assert row["matched_lab_test_type_id"] == tpc.id
    assert row["match_source"] == "approved_alias"
    assert row["alias_id"] == scoped_alias.id


def test_alias_target_inactive_is_ignored(test_db, sample_lab_test_types):
    lead = sample_lab_test_types[2]
    lead.is_active = False
    alias = LabTestAlias(
        raw_phrase="Pb Alias",
        normalized_key=normalize_alias_key("Pb Alias"),
        lab_name=None,
        lab_test_type_id=lead.id,
        status="approved",
        source="manual_override",
    )
    test_db.add(alias)
    test_db.commit()

    row = ResultImportService()._normalize_extraction(
        test_db,
        {"rows": [{"row_id": "1", "test_name_raw": "Pb Alias", "confidence": 0.95}]},
    )["rows"][0]

    assert row["matched_lab_test_type_id"] is None
    assert row["match_source"] == "unmatched"


def test_fuzzy_off_panel_preview_uses_lab_type_defaults(
    test_db, sample_lot, sample_product_with_specs, sample_user
):
    gluten = test_db.query(LabTestType).filter_by(test_name="Gluten").one()
    gluten.default_specification = "< 20 ppm"
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="c" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data=ResultImportService()._normalize_extraction(
            test_db,
            {
                "rows": [
                    {
                        "row_id": "row-1",
                        "test_name_raw": "Glutn",
                        "result_value_raw": "5",
                        "unit_raw": "ppm",
                        "confidence": 0.95,
                    }
                ]
            },
        ),
    )
    test_db.add(import_row)
    test_db.commit()

    preview = ResultImportService().preview_rows(test_db, import_row.id, sample_lot.id)[
        "rows"
    ][0]

    assert preview["resolved_test_name"] == "Gluten"
    assert preview["lab_test_type_id"] == gluten.id
    assert preview["suggested_action"] == "create_adhoc"
    assert preview["unit"] == "ppm"
    assert preview["specification"] == "< 20 ppm"
    assert preview["method"] == "ELISA"


def test_normalize_alias_key_transformations():
    assert normalize_alias_key("Yeast & Mold (Total)!") == "yeast and mold total"
    assert normalize_alias_key("  Heavy   Metals  ") == "heavy metals"
    assert normalize_alias_key("E. coli") == "e coli"


def _fuzzy_import_row(test_db, sample_user, raw_name, file_hash):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key=f"pdfs/result-imports/{file_hash}.pdf",
        file_hash=file_hash,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data=ResultImportService()._normalize_extraction(
            test_db,
            {
                "rows": [
                    {
                        "row_id": "row-1",
                        "test_name_raw": raw_name,
                        "result_value_raw": "5",
                        "unit_raw": "ppm",
                        "confidence": 0.95,
                    }
                ]
            },
        ),
    )
    test_db.add(import_row)
    test_db.commit()
    return import_row


def test_fuzzy_on_panel_preview_uses_product_spec(
    test_db, sample_lot, sample_product_with_specs, sample_user
):
    # "Plate Count" fuzzy-matches the on-panel "Total Plate Count" spec, so the
    # preview is on-panel and uses the product spec/method.
    import_row = _fuzzy_import_row(test_db, sample_user, "Plate Count", "a" * 64)
    preview = ResultImportService().preview_rows(test_db, import_row.id, sample_lot.id)[
        "rows"
    ][0]
    assert preview["resolved_test_name"] == "Total Plate Count"
    assert preview["suggested_action"] == "apply"
    assert preview["specification"] == "< 10000"
    assert preview["method"] == "AOAC 990.12"


def test_fuzzy_target_with_approved_result_previews_skip(
    test_db, sample_lot, sample_product_with_specs, sample_user
):
    gluten = test_db.query(LabTestType).filter_by(test_name="Gluten").one()
    test_db.add(
        TestResult(
            lot_id=sample_lot.id,
            test_type="Gluten",
            result_value="3",
            unit="ppm",
            status=TestResultStatus.APPROVED,
            lab_test_type_id=gluten.id,
        )
    )
    test_db.commit()
    import_row = _fuzzy_import_row(test_db, sample_user, "Glutn", "b" * 64)
    preview = ResultImportService().preview_rows(test_db, import_row.id, sample_lot.id)[
        "rows"
    ][0]
    assert preview["suggested_action"] == "skip"


def test_fuzzy_target_with_existing_draft_previews_replace(
    test_db, sample_lot, sample_product_with_specs, sample_user
):
    gluten = test_db.query(LabTestType).filter_by(test_name="Gluten").one()
    test_db.add(
        TestResult(
            lot_id=sample_lot.id,
            test_type="Gluten",
            result_value="3",
            unit="ppm",
            status=TestResultStatus.DRAFT,
            lab_test_type_id=gluten.id,
        )
    )
    test_db.commit()
    import_row = _fuzzy_import_row(test_db, sample_user, "Glutn", "d" * 64)
    preview = ResultImportService().preview_rows(test_db, import_row.id, sample_lot.id)[
        "rows"
    ][0]
    assert preview["suggested_action"] == "replace"


@pytest.mark.parametrize(
    ("unit", "specification", "method"),
    [
        ("", "< 20 ppm", "ELISA"),
        ("ppm", "   ", "ELISA"),
        ("ppm", "< 20 ppm", "\t"),
    ],
)
def test_confirm_rejects_adhoc_missing_metadata(
    unit,
    specification,
    method,
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    gluten = test_db.query(LabTestType).filter_by(test_name="Gluten").one()
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="d" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data={
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Gluten",
                    "test_name_normalized": "Gluten",
                    "result_value_raw": "5",
                    "warnings": [],
                    "metadata": {},
                    "matched_lab_test_type_id": gluten.id,
                }
            ],
            "lab_name": "Acme",
        },
    )
    test_db.add(import_row)
    test_db.commit()

    with pytest.raises(ValueError, match="needs Unit, Spec, and Method"):
        ResultImportService().confirm(
            test_db,
            import_row.id,
            sample_lot.id,
            [
                RowAction(
                    row_id="row-1",
                    action="create_adhoc",
                    lab_test_type_id=gluten.id,
                    test_name="Gluten",
                    unit=unit,
                    specification=specification,
                    method=method,
                )
            ],
            sample_user.id,
        )


def test_confirm_saves_adhoc_metadata_and_records_fuzzy_alias_suggestion(
    test_db, sample_lot, sample_user, sample_product_with_specs
):
    gluten = test_db.query(LabTestType).filter_by(test_name="Gluten").one()
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/glutn.pdf",
        file_hash="e" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data=ResultImportService()._normalize_extraction(
            test_db,
            {
                "lab_name": "Acme",
                "rows": [
                    {
                        "row_id": "row-1",
                        "test_name_raw": "Glutn",
                        "result_value_raw": "5",
                        "unit_raw": "ppm",
                        "confidence": 0.95,
                    }
                ],
            },
        ),
    )
    test_db.add(import_row)
    test_db.commit()

    result = ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [
            RowAction(
                row_id="row-1",
                action="create_adhoc",
                lab_test_type_id=gluten.id,
                test_name="Gluten",
                result_value="5",
                unit="ppm",
                specification="< 20 ppm",
                method="ELISA",
            )
        ],
        sample_user.id,
    )

    created = (
        test_db.query(TestResult).filter_by(id=result["created_result_ids"][0]).one()
    )
    assert created.unit == "ppm"
    assert created.specification == "< 20 ppm"
    assert created.method == "ELISA"
    audit = (
        test_db.query(AuditLog)
        .filter(AuditLog.table_name == "test_results", AuditLog.record_id == created.id)
        .one()
    )
    assert audit.get_new_values_dict()["unit"] == "ppm"
    alias = test_db.query(LabTestAlias).one()
    assert alias.raw_phrase == "Glutn"
    assert alias.lab_name == "Acme"
    assert alias.lab_test_type_id == gluten.id
    assert alias.status == "pending"


def test_confirm_records_fuzzy_override_as_manual_alias_suggestion(
    test_db, sample_lot, sample_user, sample_product_with_specs
):
    lead = test_db.query(LabTestType).filter_by(test_name="Lead").one()
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/glutn.pdf",
        file_hash="f" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data=ResultImportService()._normalize_extraction(
            test_db,
            {
                "lab_name": "Acme",
                "rows": [
                    {
                        "row_id": "row-1",
                        "test_name_raw": "Glutn",
                        "result_value_raw": "0.1",
                        "unit_raw": "ppm",
                        "confidence": 0.95,
                    }
                ],
            },
        ),
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [
            RowAction(
                row_id="row-1",
                action="apply",
                lab_test_type_id=lead.id,
                test_name="Lead",
                result_value="0.1",
            )
        ],
        sample_user.id,
    )

    alias = test_db.query(LabTestAlias).one()
    assert alias.raw_phrase == "Glutn"
    assert alias.lab_test_type_id == lead.id
    assert alias.source == "manual_override"


def test_confirm_records_unmatched_manual_mapping_alias_suggestion(
    test_db, sample_lot, sample_user, sample_product_with_specs
):
    gluten = test_db.query(LabTestType).filter_by(test_name="Gluten").one()
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/manual.pdf",
        file_hash="4" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data={
            "lab_name": "Acme",
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Outside Gluten",
                    "test_name_normalized": "Outside Gluten",
                    "result_value_raw": "5",
                    "unit_raw": "ppm",
                    "confidence": 0.95,
                    "warnings": [],
                    "metadata": {},
                    "matched_lab_test_type_id": None,
                    "match_source": "unmatched",
                }
            ],
        },
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [
            RowAction(
                row_id="row-1",
                action="create_adhoc",
                lab_test_type_id=gluten.id,
                test_name="Gluten",
                result_value="5",
                unit="ppm",
                specification="< 20 ppm",
                method="ELISA",
            )
        ],
        sample_user.id,
    )

    alias = test_db.query(LabTestAlias).one()
    assert alias.raw_phrase == "Outside Gluten"
    assert alias.lab_test_type_id == gluten.id
    assert alias.source == "manual_override"


def test_confirm_create_adhoc_on_panel_uses_product_spec_and_ignores_client_metadata(
    test_db, sample_lot, sample_user, sample_product_with_specs
):
    # A create_adhoc that resolves onto the lot's panel must use the product
    # spec and ignore client-sent Unit/Spec/Method (no ad-hoc requirement).
    lead = test_db.query(LabTestType).filter_by(test_name="Lead").one()
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/onpanel.pdf",
        file_hash="1" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data=ResultImportService()._normalize_extraction(
            test_db,
            {
                "rows": [
                    {
                        "row_id": "row-1",
                        "test_name_raw": "Lead",
                        "result_value_raw": "0.1",
                        "unit_raw": "ppm",
                        "confidence": 0.95,
                    }
                ]
            },
        ),
    )
    test_db.add(import_row)
    test_db.commit()

    result = ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [
            RowAction(
                row_id="row-1",
                action="create_adhoc",
                lab_test_type_id=lead.id,
                test_name="Lead",
                result_value="0.1",
                unit="WRONG-UNIT",
                specification="WRONG-SPEC",
                method="WRONG-METHOD",
            )
        ],
        sample_user.id,
    )

    created = (
        test_db.query(TestResult).filter_by(id=result["created_result_ids"][0]).one()
    )
    assert created.specification == "< 0.5"  # product spec, not the client value
    assert created.unit != "WRONG-UNIT"
    assert created.method != "WRONG-METHOD"


def test_confirm_does_not_record_suggestion_for_builtin_match(
    test_db, sample_lot, sample_user, sample_product_with_specs
):
    yeast_mold = LabTestType(
        test_name="Yeast & Mold",
        test_category="Microbiological",
        default_unit="CFU/g",
        test_method="AOAC 997.02",
        is_active=True,
    )
    test_db.add(yeast_mold)
    test_db.commit()
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/builtin.pdf",
        file_hash="2" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data=ResultImportService()._normalize_extraction(
            test_db,
            {
                "rows": [
                    {
                        "row_id": "row-1",
                        "test_name_raw": "Total Yeast & Mold Count",
                        "result_value_raw": "10",
                        "unit_raw": "CFU/g",
                        "confidence": 0.95,
                    }
                ]
            },
        ),
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [
            RowAction(
                row_id="row-1",
                action="create_adhoc",
                lab_test_type_id=yeast_mold.id,
                test_name="Yeast & Mold",
                result_value="10",
                unit="CFU/g",
                specification="< 100 CFU/g",
                method="AOAC 997.02",
            )
        ],
        sample_user.id,
    )

    assert test_db.query(LabTestAlias).count() == 0


def test_confirm_does_not_record_suggestion_for_exact_match(
    test_db, sample_lot, sample_user, sample_product_with_specs
):
    lead = test_db.query(LabTestType).filter_by(test_name="Lead").one()
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/exact.pdf",
        file_hash="5" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data=ResultImportService()._normalize_extraction(
            test_db,
            {
                "rows": [
                    {
                        "row_id": "row-1",
                        "test_name_raw": "Lead",
                        "result_value_raw": "0.1",
                        "unit_raw": "ppm",
                        "confidence": 0.95,
                    }
                ]
            },
        ),
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [
            RowAction(
                row_id="row-1",
                action="apply",
                lab_test_type_id=lead.id,
                test_name="Lead",
                result_value="0.1",
            )
        ],
        sample_user.id,
    )

    assert test_db.query(LabTestAlias).count() == 0


def test_confirm_does_not_record_suggestion_for_approved_alias_match(
    test_db, sample_lot, sample_user, sample_product_with_specs
):
    gluten = test_db.query(LabTestType).filter_by(test_name="Gluten").one()
    test_db.add(
        LabTestAlias(
            raw_phrase="Acme Gluten",
            normalized_key=normalize_alias_key("Acme Gluten"),
            lab_name="Acme",
            lab_test_type_id=gluten.id,
            status="approved",
            source="manual_override",
        )
    )
    test_db.commit()
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/approved-alias.pdf",
        file_hash="6" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data=ResultImportService()._normalize_extraction(
            test_db,
            {
                "lab_name": "Acme",
                "rows": [
                    {
                        "row_id": "row-1",
                        "test_name_raw": "Acme Gluten",
                        "result_value_raw": "5",
                        "unit_raw": "ppm",
                        "confidence": 0.95,
                    }
                ],
            },
        ),
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [
            RowAction(
                row_id="row-1",
                action="create_adhoc",
                lab_test_type_id=gluten.id,
                test_name="Gluten",
                result_value="5",
                unit="ppm",
                specification="< 20 ppm",
                method="ELISA",
            )
        ],
        sample_user.id,
    )

    aliases = test_db.query(LabTestAlias).all()
    assert len(aliases) == 1
    assert aliases[0].status == "approved"


def test_confirm_rolls_back_results_when_alias_suggestion_fails(
    test_db, sample_lot, sample_user, sample_product_with_specs, monkeypatch
):
    gluten = test_db.query(LabTestType).filter_by(test_name="Gluten").one()
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/rollback.pdf",
        file_hash="3" * 64,
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        uploaded_by_id=sample_user.id,
        extracted_data=ResultImportService()._normalize_extraction(
            test_db,
            {
                "lab_name": "Acme",
                "rows": [
                    {
                        "row_id": "row-1",
                        "test_name_raw": "Glutn",
                        "result_value_raw": "5",
                        "unit_raw": "ppm",
                        "confidence": 0.95,
                    }
                ],
            },
        ),
    )
    test_db.add(import_row)
    test_db.commit()

    def _boom(*args, **kwargs):
        raise RuntimeError("alias suggestion write failed")

    monkeypatch.setattr(
        ResultImportService, "_record_alias_suggestion_for_action", _boom
    )

    with pytest.raises(RuntimeError):
        ResultImportService().confirm(
            test_db,
            import_row.id,
            sample_lot.id,
            [
                RowAction(
                    row_id="row-1",
                    action="create_adhoc",
                    lab_test_type_id=gluten.id,
                    test_name="Gluten",
                    result_value="5",
                    unit="ppm",
                    specification="< 20 ppm",
                    method="ELISA",
                )
            ],
            sample_user.id,
        )

    # Nothing was committed: no draft result and no alias suggestion persisted.
    test_db.rollback()
    assert test_db.query(TestResult).filter_by(lot_id=sample_lot.id).count() == 0
    assert test_db.query(LabTestAlias).count() == 0


def test_metal_per_serving_column_is_primary_result(test_db):
    # Any metals COA (lab-agnostic): when both per-gram and per-serving columns
    # are printed, the per-serving value is stored as the primary result and the
    # mass-basis value is preserved in metadata.
    normalized = ResultImportService()._normalize_extraction(
        test_db,
        {
            "rows": [
                {
                    "row_id": "1",
                    "test_name_raw": "Pb (Lead)",
                    "result_value_raw": "0.023",
                    "unit_raw": "ug/g",
                    "per_serving": "0.842",
                    "confidence": 0.9,
                }
            ],
        },
    )

    row = normalized["rows"][0]
    assert row["test_name_normalized"] == "Lead"
    assert row["result_value_raw"] == "0.842"
    assert row["metadata"]["serving_value"] == "0.842"
    assert row["metadata"]["mass_basis_value"] == "0.023"
    assert row["metadata"]["conversion_note"] == "Reported on per-serving basis"


def test_metal_per_serving_unit_value_is_primary_result(test_db):
    # When the printed primary value itself is per-serving (no separate column),
    # keep it as-is instead of discarding it.
    normalized = ResultImportService()._normalize_extraction(
        test_db,
        {
            "lab_name": "Harken Research",
            "rows": [
                {
                    "row_id": "1",
                    "test_name_raw": "Pb (Lead)",
                    "result_value_raw": "0.5",
                    "unit_raw": "mcg/serving",
                    "confidence": 0.9,
                }
            ],
        },
    )

    row = normalized["rows"][0]
    assert row["test_name_normalized"] == "Lead"
    assert row["result_value_raw"] == "0.5"
    assert row["metadata"]["serving_value"] == "0.5"


def test_is_metal_detects_non_named_heavy_metals_by_category(test_db):
    # Guards against the singular/plural property-name regression: a heavy-metal
    # test not in the hard-coded METALS map is still detected via test_category.
    service = ResultImportService()
    chromium = LabTestType(test_name="Chromium", test_category="Heavy Metals")
    assert chromium.is_heavy_metal is True
    assert service._is_metal("Chromium", chromium) is True
    micro = LabTestType(test_name="Total Plate Count", test_category="Microbiological")
    assert service._is_metal("Total Plate Count", micro) is False
    # Named metals are detected even without a resolved lab type.
    assert service._is_metal("Lead", None) is True


def test_resolve_test_fields_uses_per_serving_unit_for_promoted_metal(
    test_db, sample_lot
):
    # A promoted per-serving metal result carries the per-serving unit, not the
    # spec's mass-basis (ppm) unit, so the COA labels it correctly.
    service = ResultImportService()
    row = {"metadata": {"serving_value": "0.842"}, "test_name_normalized": "Lead"}
    _, unit, _, _, _ = service._resolve_test_fields(
        test_db, sample_lot, row, None, "Lead"
    )
    assert unit == "µg/serving"


def test_existing_result_matches_on_lab_test_type_despite_name_drift(test_db):
    # A shared lab_test_type_id accepts the replacement even when the stored
    # test_type text differs (legacy naming).
    service = ResultImportService()
    legacy = TestResult(test_type="Pb", lab_test_type_id=43)
    assert service._existing_result_matches_target(legacy, "Lead", 43) is True
    assert service._existing_result_matches_target(legacy, "Lead", 99) is False
    name_only = TestResult(test_type="Lead", lab_test_type_id=None)
    assert service._existing_result_matches_target(name_only, "Lead", 43) is True
    assert service._existing_result_matches_target(name_only, "Arsenic", 43) is False


def test_harken_ppb_metal_converts_to_ug_per_g(test_db):
    normalized = ResultImportService()._normalize_extraction(
        test_db,
        {
            "lab_name": "Harken Research",
            "rows": [
                {
                    "row_id": "1",
                    "test_name_raw": "Pb (Lead)",
                    "result_value_raw": "<50",
                    "unit_raw": "ppb",
                    "confidence": 0.9,
                }
            ],
        },
    )

    row = normalized["rows"][0]
    assert row["target_unit"] == "ug/g"
    assert row["result_value_raw"] == "<0.05"


def test_reference_and_lot_identifier_pair_is_not_multi_sample(test_db):
    service = ResultImportService()
    normalized = service._normalize_extraction(
        test_db,
        {
            "identifiers": [
                {"type": "reference_number", "value": "241101-001", "confidence": 0.9},
                {"type": "lot_number", "value": "TEST123", "confidence": 0.9},
            ],
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Lead",
                    "result_value_raw": "0.1",
                    "confidence": 0.9,
                }
            ],
        },
    )

    assert not any(
        warning.startswith("Multiple sample") for warning in normalized["warnings"]
    )


def test_multiple_reference_identifiers_are_multi_sample(test_db):
    service = ResultImportService()
    normalized = service._normalize_extraction(
        test_db,
        {
            "identifiers": [
                {"type": "reference_number", "value": "241101-001", "confidence": 0.9},
                {"type": "reference_number", "value": "241101-002", "confidence": 0.9},
            ],
            "rows": [
                {
                    "row_id": "row-1",
                    "test_name_raw": "Lead",
                    "result_value_raw": "0.1",
                    "confidence": 0.9,
                }
            ],
        },
    )

    assert any(
        warning.startswith("Multiple sample") for warning in normalized["warnings"]
    )


def test_top_level_and_row_reference_conflict_is_multi_sample(test_db):
    service = ResultImportService()
    normalized = service._normalize_extraction(
        test_db,
        {
            "identifiers": [
                {"type": "reference_number", "value": "241101-001", "confidence": 0.9}
            ],
            "rows": [
                {
                    "row_id": "row-1",
                    "reference_number": "241101-002",
                    "test_name_raw": "Lead",
                    "result_value_raw": "0.1",
                    "confidence": 0.9,
                }
            ],
        },
    )

    assert any(
        warning.startswith("Multiple sample") for warning in normalized["warnings"]
    )


def test_multiple_row_lot_numbers_are_multi_sample(test_db):
    service = ResultImportService()
    normalized = service._normalize_extraction(
        test_db,
        {
            "rows": [
                {
                    "row_id": "row-1",
                    "lot_number": "LOT-A",
                    "test_name_raw": "Lead",
                    "result_value_raw": "0.1",
                    "confidence": 0.9,
                },
                {
                    "row_id": "row-2",
                    "lot_number": "LOT-B",
                    "test_name_raw": "Mercury",
                    "result_value_raw": "0.01",
                    "confidence": 0.9,
                },
            ],
        },
    )

    assert any(
        warning.startswith("Multiple sample") for warning in normalized["warnings"]
    )


def test_top_level_and_row_lot_conflict_is_multi_sample(test_db):
    service = ResultImportService()
    normalized = service._normalize_extraction(
        test_db,
        {
            "identifiers": [
                {"type": "lot_number", "value": "LOT-A", "confidence": 0.9}
            ],
            "rows": [
                {
                    "row_id": "row-1",
                    "lot_number": "LOT-B",
                    "test_name_raw": "Lead",
                    "result_value_raw": "0.1",
                    "confidence": 0.9,
                }
            ],
        },
    )

    assert any(
        warning.startswith("Multiple sample") for warning in normalized["warnings"]
    )


def test_process_import_rejects_multi_sample_pdf(test_db, sample_user, monkeypatch):
    class DummyStorage:
        def download(self, key):
            return b"%PDF"

    class DummyProvider:
        def extract(self, pdf_bytes, text, filename):
            return {
                "identifiers": [
                    {"type": "sample", "value": "241101-001", "confidence": 0.9},
                    {"type": "sample", "value": "241101-002", "confidence": 0.9},
                ],
                "rows": [
                    {
                        "row_id": "row-1",
                        "test_name_raw": "Lead",
                        "result_value_raw": "0.1",
                        "confidence": 0.9,
                    }
                ],
                "warnings": [],
            }

    monkeypatch.setattr(
        "app.services.result_import_service.get_storage_service", lambda: DummyStorage()
    )
    monkeypatch.setattr(
        "app.services.result_import_service.get_extraction_provider",
        lambda: DummyProvider(),
    )
    import_row = ResultImport(
        original_filename="multi.pdf",
        storage_key="pdfs/result-imports/multi.pdf",
        file_hash="e" * 64,
        status=ResultImportStatus.PROCESSING,
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    processed = ResultImportService().process_import(test_db, import_row.id)

    assert processed.status == ResultImportStatus.FAILED
    assert "Multiple sample" in processed.error_message


def test_queued_processing_ids_returns_restart_work(test_db, sample_user):
    processing = ResultImport(
        original_filename="queued.pdf",
        storage_key="pdfs/result-imports/queued.pdf",
        file_hash="f" * 64,
        status=ResultImportStatus.PROCESSING,
        uploaded_by_id=sample_user.id,
    )
    failed = ResultImport(
        original_filename="failed.pdf",
        storage_key="pdfs/result-imports/failed.pdf",
        file_hash="g" * 64,
        status=ResultImportStatus.FAILED,
        uploaded_by_id=sample_user.id,
    )
    test_db.add_all([processing, failed])
    test_db.commit()

    assert ResultImportService().queued_processing_ids(test_db) == [processing.id]


def test_processing_claim_allows_only_one_worker(test_db, sample_user):
    processing = ResultImport(
        original_filename="queued.pdf",
        storage_key="pdfs/result-imports/queued.pdf",
        file_hash="m" * 64,
        status=ResultImportStatus.PROCESSING,
        uploaded_by_id=sample_user.id,
    )
    test_db.add(processing)
    test_db.commit()

    service = ResultImportService()

    assert service.claim_processing_import(test_db, processing.id, "worker-a") is True
    assert service.claim_processing_import(test_db, processing.id, "worker-b") is False


def test_processing_finish_does_not_overwrite_cancelled_import(test_db, sample_user):
    claim_id = "worker-a"
    processing = ResultImport(
        original_filename="queued.pdf",
        storage_key="pdfs/result-imports/queued.pdf",
        file_hash="n" * 64,
        status=ResultImportStatus.PROCESSING,
        error_message=f"{ResultImportService.PROCESSING_CLAIM_PREFIX}{claim_id}",
        uploaded_by_id=sample_user.id,
    )
    test_db.add(processing)
    test_db.commit()

    processing.status = ResultImportStatus.CANCELLED
    test_db.commit()

    result = ResultImportService()._finish_processing_import(
        test_db,
        processing.id,
        claim_id,
        {"status": ResultImportStatus.NEEDS_CONFIRMATION, "error_message": None},
    )

    assert result.status == ResultImportStatus.CANCELLED


def test_retry_audits_requeue(test_db, sample_user, monkeypatch):
    class DummyStorage:
        def exists(self, key):
            return True

    monkeypatch.setattr(
        "app.services.result_import_service.get_storage_service",
        lambda: DummyStorage(),
    )

    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa-retry.pdf",
        file_hash="hash-retry-audit",
        status=ResultImportStatus.FAILED,
        error_message="Failed to process PDF: boom",
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    ResultImportService().retry(test_db, import_row.id, sample_user.id)

    entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "result_imports",
            AuditLog.record_id == import_row.id,
            AuditLog.action == AuditAction.UPDATE,
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert entry is not None
    assert entry.user_id == sample_user.id
    assert entry.get_new_values_dict().get("status") == "processing"


def test_upload_failure_deletes_uploaded_file(test_db, sample_user, monkeypatch):
    class DummyStorage:
        def __init__(self):
            self.uploaded = []
            self.deleted = []

        def upload(self, content, key, content_type="application/octet-stream"):
            self.uploaded.append(key)
            return key

        def delete(self, key):
            self.deleted.append(key)
            return True

    storage = DummyStorage()
    service = ResultImportService()

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(
        "app.services.result_import_service.get_storage_service", lambda: storage
    )
    monkeypatch.setattr(service, "_page_count", lambda content: 1)
    monkeypatch.setattr(service, "_log_audit", fail_audit)

    try:
        service.create_uploads(
            test_db,
            [("coa.pdf", b"not really a pdf", "application/pdf")],
            sample_user.id,
        )
    except RuntimeError as exc:
        assert "audit failed" in str(exc)
    else:
        raise AssertionError("upload should propagate DB/audit failure")

    assert storage.uploaded
    assert storage.deleted == storage.uploaded


def test_revert_audits_deletes_and_revert_event(
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa-revert.pdf",
        file_hash="hash-revert-audit",
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        extracted_data={"rows": [_audit_row()]},
        uploaded_by_id=sample_user.id,
    )
    test_db.add(import_row)
    test_db.commit()

    service = ResultImportService()
    result = service.confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="apply")],
        sample_user.id,
    )
    created_id = result["created_result_ids"][0]

    service.revert(test_db, import_row.id, sample_user.id, UserRole.QC_MANAGER)

    delete_entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "test_results",
            AuditLog.record_id == created_id,
            AuditLog.action == AuditAction.DELETE,
        )
        .first()
    )
    assert delete_entry is not None
    assert delete_entry.reason

    revert_event = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "result_imports",
            AuditLog.record_id == import_row.id,
            AuditLog.action == AuditAction.UPDATE,
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert revert_event is not None
    assert revert_event.get_new_values_dict().get("status") == "reverted"


def test_revert_audits_updated_result_restore_and_pdf_detach(
    test_db,
    sample_lot,
    sample_user,
    sample_product_with_specs,
):
    existing = TestResult(
        lot_id=sample_lot.id,
        test_type="Total Plate Count",
        result_value="old value",
        status=TestResultStatus.DRAFT,
    )
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/coa-revert-update.pdf",
        file_hash="hash-revert-update-audit",
        status=ResultImportStatus.NEEDS_CONFIRMATION,
        extracted_data={"rows": [_audit_row(value="new value")]},
        uploaded_by_id=sample_user.id,
    )
    test_db.add_all([existing, import_row])
    test_db.commit()

    service = ResultImportService()
    service.confirm(
        test_db,
        import_row.id,
        sample_lot.id,
        [RowAction(row_id="row-1", action="replace")],
        sample_user.id,
    )

    service.revert(test_db, import_row.id, sample_user.id, UserRole.QC_MANAGER)

    restore_entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "test_results",
            AuditLog.record_id == existing.id,
            AuditLog.action == AuditAction.UPDATE,
            AuditLog.reason == "Result import reverted: draft value restored",
        )
        .first()
    )
    assert restore_entry is not None
    assert restore_entry.get_old_values_dict().get("result_value") == "new value"
    assert restore_entry.get_new_values_dict().get("result_value") == "old value"

    detach_entry = (
        test_db.query(AuditLog)
        .filter(
            AuditLog.table_name == "lots",
            AuditLog.record_id == sample_lot.id,
            AuditLog.action == AuditAction.UPDATE,
            AuditLog.reason == "Result import reverted: source PDF detached",
        )
        .first()
    )
    assert detach_entry is not None
    assert detach_entry.get_old_values_dict().get("attached_pdfs")
    assert detach_entry.get_new_values_dict().get("attached_pdfs") == []


def test_revert_blocks_if_any_imported_field_changed(test_db, sample_lot, sample_user):
    result = TestResult(
        lot_id=sample_lot.id,
        test_type="Lead",
        result_value="0.1",
        unit="ppm",
        test_date=date(2026, 6, 20),
        pdf_source="pdfs/result-imports/coa.pdf",
        status=TestResultStatus.DRAFT,
        notes="imported",
    )
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="h" * 64,
        status=ResultImportStatus.CONFIRMED,
        uploaded_by_id=sample_user.id,
        confirmed_by_id=sample_user.id,
        selected_lot_id=sample_lot.id,
        confirmed_at=datetime.utcnow(),
    )
    test_db.add_all([result, import_row])
    test_db.flush()
    ledger = ResultImportLedger(
        result_import_id=import_row.id,
        lot_id=sample_lot.id,
        action_type="confirm",
        created_result_ids=[],
        updated_results=[
            {
                "id": result.id,
                "old": {
                    "test_type": "Lead",
                    "result_value": None,
                    "unit": "ppm",
                    "test_date": None,
                    "pdf_source": None,
                    "confidence_score": None,
                    "specification": None,
                    "method": None,
                    "notes": None,
                    "lab_test_type_id": None,
                    "include_on_coa": True,
                },
                "new": ResultImportService()._result_snapshot(result),
            }
        ],
        pdf_attachment={
            "storage_key": "pdfs/result-imports/coa.pdf",
            "import_id": import_row.id,
        },
        applied_by_id=sample_user.id,
    )
    test_db.add(ledger)
    test_db.commit()

    result.notes = "user changed notes"
    test_db.commit()

    try:
        ResultImportService().revert(
            test_db, import_row.id, sample_user.id, sample_user.role
        )
    except ValueError as exc:
        assert "changed after import" in str(exc)
    else:
        raise AssertionError("revert should block after post-import field edits")


def test_revert_blocks_if_created_result_changed(test_db, sample_lot, sample_user):
    result = TestResult(
        lot_id=sample_lot.id,
        test_type="Lead",
        result_value="0.1",
        unit="ppm",
        pdf_source="pdfs/result-imports/coa.pdf",
        status=TestResultStatus.DRAFT,
    )
    import_row = ResultImport(
        original_filename="coa.pdf",
        storage_key="pdfs/result-imports/coa.pdf",
        file_hash="l" * 64,
        status=ResultImportStatus.CONFIRMED,
        uploaded_by_id=sample_user.id,
        confirmed_by_id=sample_user.id,
        selected_lot_id=sample_lot.id,
        confirmed_at=datetime.utcnow(),
    )
    test_db.add_all([result, import_row])
    test_db.flush()
    snapshot = ResultImportService()._result_snapshot(result)
    ledger = ResultImportLedger(
        result_import_id=import_row.id,
        lot_id=sample_lot.id,
        action_type="confirm",
        created_result_ids=[result.id],
        updated_results=[],
        pdf_attachment={
            "storage_key": "pdfs/result-imports/coa.pdf",
            "import_id": import_row.id,
        },
        applied_rows=[
            {
                "row_id": "row-1",
                "test_result_id": result.id,
                "action": "apply",
                "result_snapshot": snapshot,
            }
        ],
        applied_by_id=sample_user.id,
    )
    test_db.add(ledger)
    test_db.commit()

    result.result_value = "0.2"
    test_db.commit()

    try:
        ResultImportService().revert(
            test_db, import_row.id, sample_user.id, sample_user.role
        )
    except ValueError as exc:
        assert "changed after import" in str(exc)
    else:
        raise AssertionError("revert should block after created row edits")


def test_revert_does_not_delete_shared_pdf_reference(
    test_db, sample_lot, sample_product, sample_user, monkeypatch
):
    class DummyStorage:
        def __init__(self):
            self.deleted = []

        def delete(self, key):
            self.deleted.append(key)
            return True

    storage = DummyStorage()
    monkeypatch.setattr(
        "app.services.result_import_service.get_storage_service", lambda: storage
    )

    shared_key = "pdfs/result-imports/shared.pdf"
    result = TestResult(
        lot_id=sample_lot.id,
        test_type="Lead",
        result_value="0.1",
        unit="ppm",
        pdf_source=shared_key,
        status=TestResultStatus.DRAFT,
    )
    import_row = ResultImport(
        original_filename="shared.pdf",
        storage_key=shared_key,
        file_hash="i" * 64,
        status=ResultImportStatus.CONFIRMED,
        uploaded_by_id=sample_user.id,
        confirmed_by_id=sample_user.id,
        selected_lot_id=sample_lot.id,
        confirmed_at=datetime.utcnow(),
    )
    other_lot = Lot(
        lot_number="OTHER123",
        lot_type=LotType.STANDARD,
        reference_number="241101-999",
        status=LotStatus.AWAITING_RESULTS,
        attached_pdfs=[
            {"storage_key": shared_key, "source": "manual", "import_id": None}
        ],
    )
    test_db.add_all([result, import_row, other_lot])
    test_db.flush()
    snapshot = ResultImportService()._result_snapshot(result)
    ledger = ResultImportLedger(
        result_import_id=import_row.id,
        lot_id=sample_lot.id,
        action_type="confirm",
        created_result_ids=[result.id],
        updated_results=[],
        pdf_attachment={"storage_key": shared_key, "import_id": import_row.id},
        applied_rows=[
            {
                "row_id": "row-1",
                "test_result_id": result.id,
                "action": "apply",
                "result_snapshot": snapshot,
            }
        ],
        applied_by_id=sample_user.id,
    )
    test_db.add(ledger)
    test_db.commit()

    ResultImportService().revert(test_db, import_row.id, sample_user.id, UserRole.ADMIN)

    assert storage.deleted == []


def test_revert_deletes_unshared_pdf_reference(
    test_db, sample_lot, sample_product, sample_user, monkeypatch
):
    class DummyStorage:
        def __init__(self):
            self.deleted = []

        def delete(self, key):
            self.deleted.append(key)
            return True

    storage = DummyStorage()
    monkeypatch.setattr(
        "app.services.result_import_service.get_storage_service", lambda: storage
    )

    storage_key = "pdfs/result-imports/unshared.pdf"
    result = TestResult(
        lot_id=sample_lot.id,
        test_type="Lead",
        result_value="0.1",
        unit="ppm",
        pdf_source=storage_key,
        status=TestResultStatus.DRAFT,
    )
    import_row = ResultImport(
        original_filename="unshared.pdf",
        storage_key=storage_key,
        file_hash="u" * 64,
        status=ResultImportStatus.CONFIRMED,
        uploaded_by_id=sample_user.id,
        confirmed_by_id=sample_user.id,
        selected_lot_id=sample_lot.id,
        confirmed_at=datetime.utcnow(),
    )
    sample_lot.attached_pdfs = [
        {"storage_key": storage_key, "source": "import", "import_id": None}
    ]
    test_db.add_all([result, import_row])
    test_db.flush()
    snapshot = ResultImportService()._result_snapshot(result)
    sample_lot.attached_pdfs = [
        {"storage_key": storage_key, "source": "import", "import_id": import_row.id}
    ]
    ledger = ResultImportLedger(
        result_import_id=import_row.id,
        lot_id=sample_lot.id,
        action_type="confirm",
        created_result_ids=[result.id],
        updated_results=[],
        pdf_attachment={"storage_key": storage_key, "import_id": import_row.id},
        applied_rows=[
            {
                "row_id": "row-1",
                "test_result_id": result.id,
                "action": "apply",
                "result_snapshot": snapshot,
            }
        ],
        applied_by_id=sample_user.id,
    )
    test_db.add(ledger)
    test_db.commit()

    ResultImportService().revert(test_db, import_row.id, sample_user.id, UserRole.ADMIN)

    assert storage.deleted == [storage_key]


def test_release_source_pdfs_are_ordered_and_deduped(test_db, sample_lot):
    sample_lot.attached_pdfs = [
        "legacy.pdf",
        {
            "filename": "import.pdf",
            "storage_key": "pdfs/import.pdf",
            "source": "import",
            "import_id": 1,
            "added_at": datetime.utcnow().isoformat(),
        },
    ]
    old_result = TestResult(
        lot_id=sample_lot.id,
        test_type="Lead",
        result_value="0.1",
        pdf_source="pdfs/import.pdf",
        status=TestResultStatus.DRAFT,
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    test_db.add(old_result)
    test_db.commit()

    source_pdfs = ReleaseService().get_source_pdfs(test_db, sample_lot.id)
    assert source_pdfs[0] == "pdfs/import.pdf"
    assert source_pdfs.count("pdfs/import.pdf") == 1
    assert "pdfs/legacy.pdf" in source_pdfs
