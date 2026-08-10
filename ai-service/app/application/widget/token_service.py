"""Widget session token issuance and validation.

The AI service is both the issuer (bootstrap) and the validator (AuthMiddleware) of
widget session tokens. Tokens are short-lived and scoped:

- `aud`/`iss` `AI-Commerce-Widget` — never passes the SaaS JWT path.
- Claims carry the tenant resolved server-side (`store_id`, `organization_id`,
  `widget_id`) plus the granted `scopes`; no tenant value is ever client-supplied.
- `exp` enforces the configured session TTL (default 15 minutes).
- Powered by HMAC-SHA256 with the shared `JWT_SECRET` so no additional secret
  distribution is required (widget issuer/audience are distinct from the SaaS contract).

`peek_issuer` decodes WITHOUT verification purely to dispatch the request to the
widget path; the token is fully validated right after.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt as pyjwt

from app.core.auth_settings import auth_settings
from app.core.security import (
    ERR_BAD_AUDIENCE,
    ERR_BAD_ISSUER,
    ERR_EXPIRED,
    ERR_INVALID_FORMAT,
    ERR_MISSING_CLAIM,
    JWTAuthenticationError,
)

WIDGET_SCOPES_SEPARATOR = " "


@dataclass(frozen=True)
class WidgetTokenClaims:
    widget_id: str
    store_id: str
    organization_id: str
    scopes: list[str]


class WidgetTokenService:
    ISSUER: str = auth_settings.WIDGET_ISSUER
    AUDIENCE: str = auth_settings.WIDGET_AUDIENCE

    def __init__(self) -> None:
        self._secret = auth_settings.JWT_SECRET
        self._algorithm = auth_settings.JWT_ALGORITHM

    def peek_issuer(self, token: str) -> str | None:
        """Unverified issuer peek, used only to route the request to the widget path."""
        try:
            payload = pyjwt.decode(token, options={"verify_signature": False})
        except Exception:
            return None
        issuer = payload.get("iss")
        return issuer if isinstance(issuer, str) else None

    def create_session_token(
        self,
        widget_id: str,
        store_id: str,
        organization_id: str,
        scopes: list[str],
        expires_in_seconds: int | None = None,
    ) -> tuple[str, int]:
        """Issue a widget session token. Returns (token, expires_in_seconds)."""
        ttl_seconds = expires_in_seconds or (
            auth_settings.WIDGET_TOKEN_TTL_MINUTES * 60
        )
        now = datetime.now(UTC)
        payload = {
            "sub": widget_id,
            "iss": self.ISSUER,
            "aud": self.AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
            "widget_id": widget_id,
            "store_id": store_id,
            "organization_id": organization_id,
            "scopes": scopes,
            "jti": secrets.token_urlsafe(16),
        }
        token = pyjwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, ttl_seconds

    def validate(self, token: str) -> WidgetTokenClaims:
        """Strictly validate a widget session token and extract its claims."""
        try:
            payload = pyjwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                issuer=self.ISSUER,
                audience=self.AUDIENCE,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iss": True,
                    "verify_aud": True,
                    "require": ["sub", "iss", "aud", "exp", "widget_id", "store_id", "organization_id", "scopes"],
                },
            )
        except pyjwt.ExpiredSignatureError as exc:
            raise JWTAuthenticationError(401, ERR_EXPIRED) from exc
        except pyjwt.InvalidIssuerError as exc:
            raise JWTAuthenticationError(401, ERR_BAD_ISSUER) from exc
        except pyjwt.InvalidAudienceError as exc:
            raise JWTAuthenticationError(401, ERR_BAD_AUDIENCE) from exc
        except (pyjwt.InvalidSignatureError, pyjwt.MissingRequiredClaimError, pyjwt.InvalidTokenError) as exc:
            raise JWTAuthenticationError(401, ERR_INVALID_FORMAT) from exc

        scopes = payload.get("scopes")
        if not isinstance(scopes, list) or not all(isinstance(s, str) and s for s in scopes):
            raise JWTAuthenticationError(401, ERR_MISSING_CLAIM)

        return WidgetTokenClaims(
            widget_id=str(payload["widget_id"]),
            store_id=str(payload["store_id"]),
            organization_id=str(payload["organization_id"]),
            scopes=scopes,
        )


widget_token_service = WidgetTokenService()


def peek_issuer(token: str) -> str | None:
    """Module-level convenience delegating to the singleton (used by AuthMiddleware)."""
    return widget_token_service.peek_issuer(token)
