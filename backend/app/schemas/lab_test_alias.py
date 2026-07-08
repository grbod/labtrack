"""Schemas for lab test alias review."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LabTestAliasRead(BaseModel):
    id: int
    raw_phrase: str
    normalized_key: str
    lab_name: Optional[str] = None
    lab_test_type_id: int
    target_test_name: Optional[str] = None
    target_test_category: Optional[str] = None
    target_default_unit: Optional[str] = None
    target_default_specification: Optional[str] = None
    target_test_method: Optional[str] = None
    status: str
    source: str
    suggestion_count: int
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    last_result_import_id: Optional[int] = None
    last_lot_id: Optional[int] = None
    last_filename: Optional[str] = None
    last_suggested_by_id: Optional[int] = None
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    disabled_by_id: Optional[int] = None
    disabled_at: Optional[datetime] = None
    disable_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LabTestAliasList(BaseModel):
    items: list[LabTestAliasRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class LabTestBuiltinAliasRead(BaseModel):
    raw_phrase: str
    normalized_key: str
    lab_test_type_id: Optional[int] = None
    target_test_name: str
    target_test_category: Optional[str] = None
    target_default_unit: Optional[str] = None
    target_default_specification: Optional[str] = None
    target_test_method: Optional[str] = None


class LabTestBuiltinAliasList(BaseModel):
    items: list[LabTestBuiltinAliasRead]
    total: int


class LabTestAliasUpdate(BaseModel):
    raw_phrase: Optional[str] = Field(None, min_length=1, max_length=255)
    lab_name: Optional[str] = Field(None, max_length=255)
    lab_test_type_id: Optional[int] = None


class LabTestAliasApproveResponse(BaseModel):
    alias: LabTestAliasRead
    disabled_competitors: int = 0


class LabTestAliasDisableRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)
