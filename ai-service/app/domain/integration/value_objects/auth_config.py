from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class AuthType(str, Enum):
    APIKEY = "apiKey"
    BEARER = "bearer"
    BASIC = "basic"
    OAUTH2 = "oauth2"


class CredentialsLocation(str, Enum):
    HEADER = "header"
    QUERY = "query"
    COOKIE = "cookie"


class AuthConfig(BaseModel):
    """Authentication configuration for an external API.

    Encapsulates the static parts of the security scheme declared in OpenAPI.
    Dynamic values (the secret itself) are stored encrypted separately on the
    integration connection aggregate.
    """

    type: AuthType
    credentials_location: CredentialsLocation = CredentialsLocation.HEADER
    scheme: Optional[str] = Field(default=None, max_length=32)
    name: Optional[str] = Field(default=None, max_length=128)
    token_url: Optional[str] = Field(default=None, max_length=512)
    flow: Optional[str] = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_consistency(self) -> "AuthConfig":
        if self.type == AuthType.APIKEY and not self.name:
            raise ValueError("API key auth requires 'name' (e.g. X-API-Key or Authorization).")
        if self.type in (AuthType.BEARER, AuthType.BASIC):
            if not self.scheme:
                raise ValueError(f"{self.type.value} auth requires 'scheme'.")
            if self.credentials_location != CredentialsLocation.HEADER:
                raise ValueError("Bearer/basic auth must use header credentials location.")
        if self.type == AuthType.OAUTH2 and not self.token_url:
            raise ValueError("OAuth2 auth requires 'token_url'.")
        return self

    def credentials_key(self) -> str:
        """Return the canonical key used to look up the secret in the credentials map."""
        if self.type == AuthType.APIKEY:
            return self.name or "api_key"
        if self.type == AuthType.BEARER:
            return "access_token"
        if self.type == AuthType.BASIC:
            return "basic"
        if self.type == AuthType.OAUTH2:
            return "access_token"
        return "secret"
