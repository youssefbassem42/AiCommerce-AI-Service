import os
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_JWT_SECRET_LENGTH = 32


class AuthSettings(BaseSettings):
    JWT_SECRET: str = Field(default="")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_PUBLIC_KEY: str = Field(default="")
    JWT_ISSUER: str = Field(default="AI-Sales-Agent")
    JWT_AUDIENCE: str = Field(default="AI-Sales-Agent")
    JWT_REQUIRED: bool = Field(default=False)
    WIDGET_TOKEN_TTL_MINUTES: int = Field(default=15)
    WIDGET_ISSUER: str = Field(default="AI-Commerce-Widget")
    WIDGET_AUDIENCE: str = Field(default="AI-Commerce-Widget")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        """Validate the shared HS256 secret.

        `JWT_SECRET` is the contract-mandated variable. During the transition from the
        legacy `JWT_SECRET_KEY` name, the latter is accepted as a fallback.
        """
        secret = value or os.getenv("JWT_SECRET_KEY", "")
        if not secret:
            raise ValueError(
                "JWT_SECRET is not configured. Set the shared HS256 secret matching the .NET "
                "backend's Jwt:SecretKey (minimum 32 characters)."
            )
        if len(secret.encode("utf-8")) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters long "
                f"(got {len(secret.encode('utf-8'))})."
            )
        return secret


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()


auth_settings = get_auth_settings()
