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
    ("JWT_SECRET_KEY", "JWT authentication"),
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
    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True
    )

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
            warnings.append("No AI provider keys configured — set at least one of: " +
                            ", ".join(k for k, _ in AI_PROVIDER_KEYS))
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
