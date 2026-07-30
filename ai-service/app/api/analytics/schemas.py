from pydantic import BaseModel, Field


class SentimentSummaryResponse(BaseModel):
    store_id: str = Field(..., description="Store identifier")
    total: int = Field(..., ge=0, description="Total tickets analyzed")
    positive_count: int = Field(..., ge=0, description="Tickets with positive sentiment")
    neutral_count: int = Field(..., ge=0, description="Tickets with neutral sentiment")
    negative_count: int = Field(..., ge=0, description="Tickets with negative sentiment")
    positive_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of positive tickets")
    neutral_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of neutral tickets")
    negative_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of negative tickets")
