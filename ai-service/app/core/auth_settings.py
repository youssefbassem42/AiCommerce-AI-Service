from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    JWT_SECRET_KEY: str = Field(default="")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_PUBLIC_KEY: str = Field(default="")
    JWT_ISSUER: str = Field(default="AI-Sales-Agent")
    JWT_AUDIENCE: str = Field(default="AI-Sales-Agent")
    JWT_REQUIRED: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()


auth_settings = get_auth_settings()
