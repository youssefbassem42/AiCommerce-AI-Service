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
    conversation_id: str | None = None
    store_id: str
    organization_id: str | None = None
    customer_id: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)

    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    use_hybrid: bool = False
    use_mmr: bool = False
    rerank: bool = False
    language: str | None = None
    knowledge_scope: str | None = None
    stream: bool = False
    fallback_providers: list[str] = Field(default_factory=list, description="Plan-allowed failover providers")


class RAGStreamingChunk(BaseModel):
    type: str = "content"
    content: str | None = None
    finish_reason: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    chunk_references: list[ChunkReference] = Field(default_factory=list)
    confidence_score: float | None = None
    model: str | None = None
    provider: str | None = None
    usage: UsageDTO | None = None
    latency_ms: float | None = None
    business_summary_version: int | None = None
    conversation_id: str | None = None


class RAGResponse(BaseModel):
    response: str
    citations: list[Citation]
    chunk_references: list[ChunkReference]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    latency_ms: float
    model: str
    provider: str
    usage: UsageDTO
    business_summary_version: int | None = None
    conversation_id: str | None = None
