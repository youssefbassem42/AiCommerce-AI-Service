from pydantic import BaseModel, Field


class Image(BaseModel):
    url: str = Field(..., min_length=1)
    alt_text: str | None = None
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    position: int | None = Field(default=None, ge=0)
