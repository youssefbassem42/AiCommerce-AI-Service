from datetime import UTC, datetime

from pydantic import Field

from app.shared.kernel.entity import Entity


class Prompt(Entity[str]):
    key: str = Field(..., description="Unique hierarchical key, e.g. bundle.agent.system_prompt")
    type: str = Field(default="system", description="Prompt type: system, user, or template")
    content: str = Field(..., description="The prompt text")
    description: str = Field(default="", description="Human-readable description of what this prompt is used for")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    version: int = Field(default=1, ge=1)
    is_active: bool = Field(default=True)
    variables: list[str] = Field(default_factory=list, description="Expected template variable names")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
