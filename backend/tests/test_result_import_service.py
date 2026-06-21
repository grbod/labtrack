"""Tests for the results importer service."""

from datetime import date, datetime, timedelta

from app.models import ResultImport, ResultImportStatus, TestResult, TestResultStatus
from app.services.release_service import ReleaseService
from app.services.result_extraction_provider import MockExtractionProvider
from app.services.result_import_service import ResultImportService
from app.schemas.result_import import RowAction


def test_mock_provider_does_not_invent_rows():
    provider = MockExtractionProvider()
    extracted = provider.extract(b"%PDF", "No known tests here", "unknown.pdf")
    assert extracted["rows"] == []
    assert extracted["warnings"]


def test_candidate_matching_uses_lot_identifiers(test_db, sample_lot):
    service = ResultImportService()
    extracted = {"identifiers": [{"type": "reference_number", "value": "241101-001"}]}
    candidates = service.match_candidates(test_db, extracted, "result.pdf")
    assert candidates[0]["lot_id"] == sample_lot.id
    assert "reference matched" in candidates[0]["reasons"]


def test_upload_fails_without_openrouter_key_when_live_provider(test_db, sample_user, monkeypatch):
    monkeypatch.setattr("app.services.result_import_service.settings.ai_provider", "openrouter")
    monkeypatch.setattr("app.services.result_import_service.settings.openrouter_api_key", None)

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
    created = test_db.query(TestResult).filter(TestResult.id == result["created_result_ids"][0]).one()
    assert created.status == TestResultStatus.DRAFT
    assert created.result_value == "< 10"
    assert created.pdf_source == "pdfs/result-imports/coa.pdf"
    test_db.refresh(sample_lot)
    assert sample_lot.attached_pdfs[0]["source"] == "import"


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
                {"row_id": "1", "test_name_raw": "Pb (Lead)", "result_value_raw": "0.1", "confidence": 0.9},
                {"row_id": "2", "test_name_raw": "Hg/Mercury", "result_value_raw": "0.01", "confidence": 0.9},
            ]
        },
    )

    assert [row["test_name_normalized"] for row in normalized["rows"]] == ["Lead", "Mercury"]


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

    monkeypatch.setattr("app.services.result_import_service.get_storage_service", lambda: DummyStorage())
    monkeypatch.setattr("app.services.result_import_service.get_extraction_provider", lambda: DummyProvider())
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
