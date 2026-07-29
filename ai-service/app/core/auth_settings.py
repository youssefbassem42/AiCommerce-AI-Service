from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class AuthSettings(BaseSettings):
    JWT_SECRET_KEY: str = Field(default="")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_PUBLIC_KEY: str = Field(default="")
    JWT_ISSUER: str = Field(default="ai-commerce")
    JWT_AUDIENCE: str = Field(default="ai-service")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    JWT_REQUIRED: bool = Field(default=False)
    BCRYPT_ROUNDS: int = Field(default=12)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()


auth_settings = get_auth_settings()
