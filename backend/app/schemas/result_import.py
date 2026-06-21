"""Schemas for results importer API."""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ExtractedIdentifier(BaseModel):
    type: str
    value: str
    confidence: float = 0.0


class ExtractedResultRow(BaseModel):
    row_id: str
    test_name_raw: str
    test_name_normalized: str
    result_value_raw: Optional[str] = None
    unit_raw: Optional[str] = None
    target_unit: Optional[str] = None
    limit_raw: Optional[str] = None
    test_date: Optional[date] = None
    received_date: Optional[date] = None
    confidence: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    matched_lab_test_type_id: Optional[int] = None


class ResultExtraction(BaseModel):
    identifiers: List[ExtractedIdentifier] = Field(default_factory=list)
    lab_name: Optional[str] = None
    date_tested: Optional[date] = None
    report_date: Optional[date] = None
    received_date: Optional[date] = None
    rows: List[ExtractedResultRow] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ResultImportCandidate(BaseModel):
    lot_id: int
    reference_number: str
    lot_number: str
    status: str
    score: float
    reasons: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)


class ResultImportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    storage_key: Optional[str]
    file_hash: str
    status: str
    extracted_data: Optional[Dict[str, Any]]
    match_candidates: Optional[List[Dict[str, Any]]]
    warnings: Optional[List[str]]
    error_message: Optional[str]
    selected_lot_id: Optional[int]
    uploaded_by_id: Optional[int]
    confirmed_by_id: Optional[int]
    confirmed_at: Optional[datetime]
    openrouter_model: Optional[str]
    usage_metadata: Optional[Dict[str, Any]]
    duplicate_of_id: Optional[int]
    duplicate_summary: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class ResultImportList(BaseModel):
    items: List[ResultImportRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class ResultImportUploadResponse(BaseModel):
    items: List[ResultImportRead]
    duplicates: List[ResultImportRead] = Field(default_factory=list)


class RowAction(BaseModel):
    row_id: str
    action: Literal["apply", "replace", "skip", "create_adhoc"]
    test_result_id: Optional[int] = None
    lab_test_type_id: Optional[int] = None
    test_name: Optional[str] = None


class ConfirmResultImportRequest(BaseModel):
    lot_id: int
    row_actions: List[RowAction]


class LinkCandidateRead(BaseModel):
    lot_id: int
    reference_number: str
    lot_number: str
    status: str
    products: List[str] = Field(default_factory=list)


class ExistingResultPreview(BaseModel):
    id: int
    test_type: str
    result_value: Optional[str] = None
    unit: Optional[str] = None
    status: str
    test_date: Optional[date] = None
    pdf_source: Optional[str] = None


class ResultImportRowPreview(BaseModel):
    row_id: str
    resolved_test_name: Optional[str] = None
    unit: Optional[str] = None
    specification: Optional[str] = None
    method: Optional[str] = None
    lab_test_type_id: Optional[int] = None
    requires_lab_test_mapping: bool = False
    suggested_action: Literal["apply", "replace", "skip", "create_adhoc"]
    warnings: List[str] = Field(default_factory=list)
    existing_result: Optional[ExistingResultPreview] = None


class ResultImportPreview(BaseModel):
    import_id: int
    lot_id: int
    rows: List[ResultImportRowPreview]


class ConfirmResultImportResponse(BaseModel):
    import_id: int
    lot_id: int
    created_result_ids: List[int]
    updated_result_ids: List[int]
    skipped_row_ids: List[str]
    status: str
