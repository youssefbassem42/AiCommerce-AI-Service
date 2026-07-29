from pydantic import BaseModel, Field


class SentimentAnalysisRequest(BaseModel):
    messages: list[str] = Field(..., description="Conversation messages to analyze")
    store_id: str
    customer_id: str


class SentimentAnalysisResult(BaseModel):
    sentiment: str = Field(..., description="positive, neutral, or negative")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    category: str = Field(..., description="e.g. billing, shipping, product_quality, general")
    priority: str = Field(..., description="low, medium, high, urgent")
    summary: str = Field(..., description="Brief summary of the issue")
    suggested_response: str = Field(..., description="Suggested AI-generated response")
