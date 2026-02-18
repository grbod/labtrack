"""Schemas for Daane Labs test mappings."""

from typing import List, Optional
from pydantic import BaseModel


class DaaneTestMappingItem(BaseModel):
    lab_test_type_id: int
    test_name: str
    test_method: Optional[str] = None
    default_unit: Optional[str] = None
    daane_method: Optional[str] = None
    match_type: str
    match_reason: Optional[str] = None


class DaaneTestMappingListResponse(BaseModel):
    items: List[DaaneTestMappingItem]
    total: int
