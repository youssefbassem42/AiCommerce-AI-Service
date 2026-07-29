from pydantic import BaseModel, Field


class ChunkReferenceSchema(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    content_snippet: str
    score: float
    rank: int


class CitationSchema(BaseModel):
    index: int
    chunk_id: str
    document_title: str
    content_snippet: str
    score: float
    rank: int


class UsageSchema(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


class RAGChatRequestSchema(BaseModel):
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


class RAGChatResponseSchema(BaseModel):
    response: str
    citations: list[CitationSchema]
    chunk_references: list[ChunkReferenceSchema]
    confidence_score: float
    latency_ms: float
    model: str
    provider: str
    usage: UsageSchema
    business_summary_version: int | None = None
    conversation_id: str | None = None
