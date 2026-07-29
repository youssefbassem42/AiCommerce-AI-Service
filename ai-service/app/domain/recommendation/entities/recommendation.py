from datetime import datetime, UTC
from typing import List
from pydantic import Field
from app.shared.kernel.aggregate_root import AggregateRoot

class Recommendation(AggregateRoot[str]):
    """Domain Aggregate Root representing a product recommendation sent to a customer."""
    conversation_id: str = Field(..., description="ID of the conversation where the recommendation occurred")
    customer_id: str = Field(..., description="ID of the customer who received recommendations")
    recommended_product_ids: List[str] = Field(..., description="List of recommended product IDs")
    store_id: str = Field(..., description="ID of the store")
    accepted: bool = Field(..., description="Whether the customer accepted the recommendation")
    rationale: str = Field(..., description="Explanation of why these products were recommended")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
