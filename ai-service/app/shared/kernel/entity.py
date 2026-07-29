from typing import Generic, TypeVar
from pydantic import BaseModel, Field

ID = TypeVar("ID")

class Entity(BaseModel, Generic[ID]):
    """Base class for Domain Entities."""
    id: ID = Field(description="Unique business identifier for the entity")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
