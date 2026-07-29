from pydantic import BaseModel, Field, field_validator


class ChunkingConfig(BaseModel):
    chunk_size: int = Field(default=1000, ge=1, description="Target chunk size in characters or tokens")
    overlap: int = Field(default=200, ge=0, description="Overlap between consecutive chunks")
    strategy: str = Field(default="recursive", description="Chunking strategy name")

    @field_validator("overlap")
    @classmethod
    def overlap_must_be_less_than_size(cls, v: int, info) -> int:
        size = info.data.get("chunk_size", 1000)
        if v >= size:
            raise ValueError(f"overlap ({v}) must be less than chunk_size ({size})")
        return v
