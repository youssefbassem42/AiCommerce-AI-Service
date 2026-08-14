import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.mongo_settings import MongoSettings
from app.core.openai_settings import OpenAISettings
from app.core.qdrant_settings import QdrantSettings
from app.core.redis_settings import RedisSettings

load_dotenv()

REQUIRED_SECRETS = [
    ("JWT_SECRET", "JWT authentication"),
]

AI_PROVIDER_KEYS = [
    ("OPENAI_API_KEY", "OpenAI"),
    ("GEMINI_API_KEY", "Gemini"),
    ("CLAUDE_API_KEY", "Claude"),
    ("DEEPSEEK_API_KEY", "DeepSeek"),
    ("MISTRAL_API_KEY", "Mistral"),
    ("OPENROUTER_API_KEY", "OpenRouter"),
]


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Commerce Platform"
    MONGO_SETTINGS: MongoSettings = MongoSettings()
    OPEN_AI_SETTINGS: OpenAISettings = OpenAISettings()
    QDRANT_SETTINGS: QdrantSettings = QdrantSettings()
    REDIS_SETTINGS: RedisSettings = RedisSettings()
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://ai-commerce-frontend-tau.vercel.app",
        "https://naviai-eg.vercel.app",
        "https://aicommerce-ai-service-production.up.railway.app",
    ]
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_LLM_PER_MINUTE: int = 20
    RATE_LIMIT_WIDGET_BOOTSTRAP_PER_MINUTE: int = 30
    RATE_LIMIT_WIDGET_SESSION_PER_MINUTE: int = 60

    # AI usage quota defaults (enforcement works even before .NET provisions a
    # plan for the store; the trusted plan claims override once provisioned).
    QUOTA_DEFAULT_TOKEN_LIMIT: int = 1_000_000
    QUOTA_BUDGET_HEADROOM: float = 2.0
    QUOTA_MAX_OUTPUT_TOKENS: int = 1024
    CONSUMER_DAILY_LIMIT_DEFAULT_MAX: int = 15
    QUOTA_PERIOD_DAYS: int = 30
    QUOTA_REDIS_TTL_DAYS: int = 90
    QUOTA_FAIL_OPEN: bool = False

    # .NET backend (plan/subscription authority) integration.
    NET_BACKEND_BASE_URL: str = "https://aisales123.runasp.net"
    NET_BACKEND_TIMEOUT_SECONDS: float = 8.0
    NET_BACKEND_MAX_RETRIES: int = 2

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    def validate_required(self) -> list[str]:
        warnings: list[str] = []
        for var, name in REQUIRED_SECRETS:
            if not os.getenv(var):
                warnings.append(f"{var} ({name}) is not set")
        provided = []
        for var, name in AI_PROVIDER_KEYS:
            val = os.getenv(var)
            if val and val.strip():
                provided.append(name)
        if not provided:
            warnings.append(
                "No AI provider keys configured — set at least one of: " + ", ".join(k for k, _ in AI_PROVIDER_KEYS)
            )
        return warnings


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    warnings = s.validate_required()
    if warnings:
        import logging

        logger = logging.getLogger(__name__)
        for w in warnings:
            logger.warning("Configuration warning: %s", w)
    return s


settings = get_settings()
