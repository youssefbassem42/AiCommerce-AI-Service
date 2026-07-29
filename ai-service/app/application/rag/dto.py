from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.application.dto.ai_dto import UsageDTO


class ChunkReference(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    content_snippet: str = Field(..., description="First ~200 chars of the chunk")
    score: float
    rank: int


class Citation(BaseModel):
    index: int = Field(..., description="Citation number referenced in the response")
    chunk_id: str
    document_title: str
    content_snippet: str
    score: float
    rank: int


class RAGRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    store_id: str
    organization_id: Optional[str] = None
    customer_id: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=64, le=8192)

    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    use_hybrid: bool = False
    use_mmr: bool = False
    rerank: bool = False
    language: Optional[str] = None
    knowledge_scope: Optional[str] = None
    stream: bool = False


class RAGStreamingChunk(BaseModel):
    type: str = "content"
    content: Optional[str] = None
    finish_reason: Optional[str] = None
    citations: list[Citation] = Field(default_factory=list)
    chunk_references: list[ChunkReference] = Field(default_factory=list)
    confidence_score: Optional[float] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    usage: Optional[UsageDTO] = None
    latency_ms: Optional[float] = None
    business_summary_version: Optional[int] = None
    conversation_id: Optional[str] = None


class RAGResponse(BaseModel):
    response: str
    citations: list[Citation]
    chunk_references: list[ChunkReference]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    latency_ms: float
    model: str
    provider: str
    usage: UsageDTO
    business_summary_version: Optional[int] = None
    conversation_id: Optional[str] = None
