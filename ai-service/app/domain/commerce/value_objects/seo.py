from typing import Optional

from pydantic import BaseModel, Field


class SEO(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url_slug: Optional[str] = None
