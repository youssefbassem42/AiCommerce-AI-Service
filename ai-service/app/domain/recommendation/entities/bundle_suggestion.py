from datetime import datetime, UTC
from typing import List
from pydantic import Field
from app.shared.kernel.entity import Entity

class BundleSuggestion(Entity[str]):
    """Domain representation of product bundling suggestions (e.g. Frequently Bought Together)."""
    store_id: str = Field(..., description="Commerce store context ID")
    title: str = Field(..., description="Name of the bundle suggestion")
    product_ids: List[str] = Field(..., description="Product IDs included in the bundle")
    total_price: float = Field(..., description="Total price of the bundle")
    discount_percentage: float = Field(..., description="Discount if bought together")
    status: str = Field(default="active", description="Bundle status (active, draft, expired)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
