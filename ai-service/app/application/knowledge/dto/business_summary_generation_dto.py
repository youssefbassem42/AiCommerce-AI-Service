from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class BusinessSummaryGenerationResponseDTO(BaseModel):
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
