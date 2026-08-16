from pydantic import BaseModel


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
