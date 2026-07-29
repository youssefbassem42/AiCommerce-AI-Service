from typing import Any, Optional

from pydantic import BaseModel, Field


class RetrievedChunkSchema(BaseModel):
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


class RetrievalRequestSchema(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Search query text")
    top_k: int = Field(default=10, ge=1, le=100)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    use_hybrid: bool = Field(default=False, description="Enable hybrid keyword+vector search")
    use_mmr: bool = Field(default=False, description="Enable MMR diversity")
    mmr_lambda: float = Field(default=0.7, ge=0.0, le=1.0)
    rerank: bool = Field(default=False, description="Enable LLM cross-encoder re-ranking")
    rerank_top_k: int = Field(default=5, ge=1, le=50)
    embedding_model: str = Field(default="gemini-embedding-001")
    organization_id: Optional[str] = None
    store_id: Optional[str] = None
    language: Optional[str] = None
    document_type: Optional[str] = None
    knowledge_scope: Optional[str] = None
    business_version: Optional[int] = Field(default=None, ge=1)


class RetrievalResponseSchema(BaseModel):
    query: str
    results: list[RetrievedChunkSchema]
    total_count: int
    strategy: str
    latency_ms: float
    filters_applied: dict[str, Any] = Field(default_factory=dict)
