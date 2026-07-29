from typing import Optional

from pydantic import BaseModel, Field


class Image(BaseModel):
    url: str = Field(..., min_length=1)
    alt_text: Optional[str] = None
    width: Optional[int] = Field(default=None, ge=0)
    height: Optional[int] = Field(default=None, ge=0)
    position: Optional[int] = Field(default=None, ge=0)
