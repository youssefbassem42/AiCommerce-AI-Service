from datetime import datetime, UTC
from typing import Optional, Any, Annotated
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator, PlainSerializer, WithJsonSchema

def validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str) and ObjectId.is_valid(v):
        return v
    raise ValueError(f"Invalid ObjectId: {v}")

PyObjectId = Annotated[
    str,
    BeforeValidator(validate_object_id),
    PlainSerializer(lambda x: str(x), return_type=str),
    WithJsonSchema({"type": "string", "example": "60b8d2f5f1d8c92d88a4e8d3"}),
]

class BaseMongoDocument(BaseModel):
    """Base MongoDB Document class with standard audit fields and ObjectId handling."""
    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: Optional[datetime] = Field(None)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    def to_mongo_dict(self) -> dict[str, Any]:
        """Convert the model into a standard dictionary suitable for Mongo driver."""
        data = self.model_dump(by_alias=True, exclude={"id"})
        data["_id"] = ObjectId(self.id)
        return data

    @classmethod
    def from_mongo_dict(cls, data: dict[str, Any]) -> Any:
        """Create a document instance from a MongoDB BSON dictionary."""
        if not data:
            return None
        doc_data = data.copy()
        if "_id" in doc_data and isinstance(doc_data["_id"], ObjectId):
            doc_data["_id"] = str(doc_data["_id"])
        return cls(**doc_data)
