"""JWT validation utilities implementing the .NET JWT Authentication Contract (v1.0).

The FastAPI service is a resource server only: it validates access tokens issued by the
.NET backend (HS256, issuer/audience `AI-Sales-Agent`, zero clock skew) and never issues
tokens. Claims are extracted strictly per the contract — the ASP.NET long-form role URI is
the ONLY role source, and tenant identity (`store_id`, `org_id`) comes from claims only.
"""

import uuid
from datetime import UTC, datetime

import jwt as pyjwt

from app.core.auth_settings import auth_settings

# ASP.NET claim URIs (contract section 4)
ROLE_CLAIM = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"
EMAIL_CLAIM = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"

# Contract section 6: exact role values, normalized to internal lowercase names.
ROLE_MAPPING = {
    "Admin": "admin",
    "SuperAdmin": "super_admin",
}

# Contract section 11: exact error responses.
ERR_MISSING_HEADER = "Authorization header is missing"
ERR_INVALID_FORMAT = "Invalid token format"
ERR_EXPIRED = "Token has expired"
ERR_BAD_SIGNATURE = "Token signature is invalid"
ERR_BAD_ISSUER = "Invalid token issuer"
ERR_BAD_AUDIENCE = "Invalid token audience"
ERR_MISSING_CLAIM = "Required claim is missing"
ERR_NO_STORE = "No store associated with this account"
ERR_NO_ORG = "No organization associated with this account"
ERR_INSUFFICIENT = "Insufficient permissions"


class JWTAuthenticationError(Exception):
    """Authentication failure carrying the contract HTTP status and message."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _auth_error(status_code: int, detail: str) -> JWTAuthenticationError:
    return JWTAuthenticationError(status_code=status_code, detail=detail)


def decode_jwt(token: str) -> dict:
    """Strictly validate and decode a .NET access token.

    Enforces signature, issuer, audience and expiration exactly as configured on the
    .NET backend (ValidateIssuer/Audience/Lifetime/IssuerSigningKey, ClockSkew zero).
    """
    try:
        return pyjwt.decode(
            token,
            auth_settings.JWT_SECRET,
            algorithms=[auth_settings.JWT_ALGORITHM],
            issuer=auth_settings.JWT_ISSUER,
            audience=auth_settings.JWT_AUDIENCE,
            leeway=0,  # ClockSkew = TimeSpan.Zero — no tolerance
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
                "require": ["sub", "exp", "iss", "aud"],
            },
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise _auth_error(401, ERR_EXPIRED) from exc
    except pyjwt.InvalidIssuerError as exc:
        raise _auth_error(401, ERR_BAD_ISSUER) from exc
    except pyjwt.InvalidAudienceError as exc:
        raise _auth_error(401, ERR_BAD_AUDIENCE) from exc
    except pyjwt.InvalidSignatureError as exc:
        raise _auth_error(401, ERR_BAD_SIGNATURE) from exc
    except pyjwt.MissingRequiredClaimError as exc:
        raise _auth_error(401, ERR_MISSING_CLAIM) from exc
    except pyjwt.InvalidTokenError as exc:
        raise _auth_error(401, ERR_INVALID_FORMAT) from exc


def verify_jwt(token: str) -> dict:
    """Alias for decode_jwt; validates the token and returns its payload."""
    return decode_jwt(token)


def _parse_guid(value: object) -> str | None:
    if value is None:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise _auth_error(401, ERR_INVALID_FORMAT) from exc


def get_user_id_from_token(payload: dict) -> str:
    """User ID from `sub` (primary) or `nameid` — both carry the same GUID (contract §3/§8)."""
    value = payload.get("sub") or payload.get("nameid")
    if value is None:
        raise _auth_error(401, ERR_MISSING_CLAIM)
    return _parse_guid(value)


def get_email_from_token(payload: dict) -> str | None:
    """Email from the standard `email` claim, falling back to the ASP.NET URI form."""
    return payload.get("email") or payload.get(EMAIL_CLAIM)


def get_role_from_token(payload: dict) -> str | None:
    """Role from the ASP.NET long-form URI claim ONLY (contract §4 — never `role`/`roles`)."""
    value = payload.get(ROLE_CLAIM)
    if isinstance(value, str) and value:
        return ROLE_MAPPING.get(value, value)
    return None


def get_roles_from_token(payload: dict) -> list:
    """Role list for request.state compatibility; empty when the contract role claim is absent."""
    role = get_role_from_token(payload)
    return [role] if role else []


def get_store_id_from_token(payload: dict) -> str | None:
    """Store ID from the `store_id` claim only (contract §9: never from body/query, never legacy keys)."""
    return _parse_guid(payload.get("store_id"))


def get_organization_id_from_token(payload: dict) -> str | None:
    """Organization ID from the `org_id` claim only (contract §3/§8)."""
    return _parse_guid(payload.get("org_id"))


def get_permissions_from_token(payload: dict) -> list[str]:
    """All values of the repeatable `permission` claim (contract §3/§6)."""
    value = payload.get("permission")
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def get_security_stamp_from_token(payload: dict) -> str | None:
    """Security stamp — present in the token but MUST NOT be validated by FastAPI (contract §5/§7)."""
    return payload.get("security_stamp")


def get_jti_from_token(payload: dict) -> str | None:
    return payload.get("jti")


def get_iat_from_token(payload: dict) -> int | None:
    return payload.get("iat")


def get_exp_from_token(payload: dict) -> int | None:
    return payload.get("exp")


def get_expires_at_from_token(payload: dict) -> datetime | None:
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        return datetime.fromtimestamp(exp, tz=UTC)
    return None
