from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RetrievedChunkDTO(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    chunk_index: int
    content: str
    score: float
    rank: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    language: Optional[str] = None
    source_type: Optional[str] = None


class RetrievalQueryDTO(BaseModel):
    query: str
    strategy: str = Field(default="semantic", description="semantic | hybrid | mmr | reranked")
    top_k: int = Field(default=10, ge=1, le=100)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class UnifiedRetrievalResult(BaseModel):
    query: str
    results: list[RetrievedChunkDTO]
    total_count: int
    strategy: str
    latency_ms: float
    filters_applied: dict[str, Any] = Field(default_factory=dict)
