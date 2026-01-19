"""COA category order schemas for request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class COACategoryOrderUpdate(BaseModel):
    """Schema for updating the COA category order."""

    category_order: List[str] = Field(
        ...,
        description="Ordered list of category names for COA display",
        min_length=1,
    )


class COACategoryOrderResponse(BaseModel):
    """COA category order response schema."""

    id: int
    category_order: List[str]
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
