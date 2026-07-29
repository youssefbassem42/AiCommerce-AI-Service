from pydantic import BaseModel, Field


class RetrievalConfig(BaseModel):
    top_k: int = Field(default=10, ge=1, le=100, description="Maximum results to return")
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum similarity score")
    use_hybrid: bool = Field(default=False, description="Enable hybrid search (keyword + vector)")
    use_mmr: bool = Field(default=False, description="Enable MMR diversity re-ranking")
    mmr_lambda: float = Field(default=0.7, ge=0.0, le=1.0, description="MMR relevance vs diversity (1=relevance only)")
    rerank: bool = Field(default=False, description="Enable LLM cross-encoder re-ranking")
    rerank_top_k: int = Field(default=5, ge=1, le=50, description="Results to consider for re-ranking")
    hybrid_vector_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="Vector score weight in hybrid")
    embedding_model: str = Field(default="gemini-embedding-001", description="Model for query embedding")
    collection_prefix: str = Field(default="kb", description="Collection name prefix for tenant isolation")


class RetrievalFilters(BaseModel):
    organization_id: str | None = Field(default=None, description="Tenant organization ID")
    store_id: str | None = Field(default=None, description="Store context ID")
    language: str | None = Field(default=None, description="Document language filter")
    document_type: str | None = Field(default=None, description="Source document type")
    document_status: str | None = Field(default=None, description="Document status filter ('active', 'archived')")
    knowledge_scope: str | None = Field(default=None, description="Knowledge scope/category")
    knowledge_version: int | None = Field(default=None, ge=1, description="Knowledge base version filter")
    business_version: int | None = Field(default=None, ge=1, description="Business summary version")
    chunk_ids: list[str] | None = Field(default=None, description="Specific chunk IDs to restrict to")
