from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class GenerateBusinessSummaryRequestSchema(BaseModel):
    model: Optional[str] = Field(default=None, description="LLM model override")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=256)


class BusinessSummarySectionSchema(BaseModel):
    business_overview: str = ""
    business_policies: str = ""
    faqs: str = ""
    shipping_policy: str = ""
    refund_policy: str = ""
    customer_service_guidelines: str = ""
    tone_of_voice: str = ""
    brand_identity: str = ""


class BusinessSummaryGenerationResponseSchema(BaseModel):
    id: str
    document_id: str
    version_number: int
    title: str
    summary: str
    metadata: dict[str, Any]
    sections: dict[str, str] = Field(default_factory=dict)
    document_count: int = 0
    model: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PaginatedBusinessSummaryHistoryResponseSchema(BaseModel):
    items: list[BusinessSummaryGenerationResponseSchema]
    total: int
    page: int
    page_size: int
