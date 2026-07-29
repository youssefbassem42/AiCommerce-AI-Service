from pydantic import BaseModel


class SEO(BaseModel):
    title: str | None = None
    description: str | None = None
    url_slug: str | None = None
