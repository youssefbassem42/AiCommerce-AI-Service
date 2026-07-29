from datetime import datetime, UTC
from typing import Dict, Any
from pydantic import Field
from app.shared.kernel.entity import Entity

class DashboardInsight(Entity[str]):
    """Domain representation of analytics dashboard insights for merchants."""
    store_id: str = Field(..., description="ID of the store for which the metric is calculated")
    recommendations : list[str] = Field(..., description="Recommendations for the store")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context or breakdown")
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
