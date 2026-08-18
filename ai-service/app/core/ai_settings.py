from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """Configuration settings specific to the AI module, loaded from environment variables."""

    AZURE_ENDPOINT: str = Field(default="")
    AZURE_DEPLOYMENT: str = Field(default="")
    OLLAMA_URL: str = Field(default="http://localhost:11434")

    DEFAULT_PROVIDER: str = Field(default="openai")
    DEFAULT_MODEL: str = Field(default="gpt-4o-mini")
    EMBEDDING_PROVIDER: str = Field(default="gemini")
    REQUEST_TIMEOUT: float = Field(default=30.0)
    MAX_RETRIES: int = Field(default=3)

    ENABLE_STREAMING: bool = Field(default=True)
    ENABLE_TOOL_CALLS: bool = Field(default=True)
    ENABLE_JSON_MODE: bool = Field(default=True)

    # Promo codes are real coupons created on the store's connected
    # e-commerce platform. Enabled by default; when no coupon-capable
    # integration exists the flow degrades gracefully (no code is shown).
    PROMO_CODES_ENABLED: bool = Field(default=True)
    PROMO_CODE_VALID_DAYS: int = Field(
        default=30,
        description="Days a generated promo code stays valid (CreateCouponDto expiryDate, L4)",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)


@lru_cache
def get_ai_settings() -> AISettings:
    return AISettings()


ai_settings = get_ai_settings()
