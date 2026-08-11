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

# ASP.NET claim URIs (contract section 4).
# .NET's JwtTokenService writes ClaimTypes.* as long-form URIs (no outbound claim
# mapping is applied when a JwtSecurityToken is constructed from Claim objects), so
# FastAPI must read the exact URIs the .NET backend emits.
ROLE_CLAIM = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"
EMAIL_CLAIM = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
NAME_IDENTIFIER_CLAIM = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier"

# The .NET backend adds the ASP.NET security stamp as the `security_stamp` claim and
# rejects (OnTokenValidated -> context.Fail) any token that lacks it. FastAPI mirrors the
# presence requirement; value comparison is out of scope (requires the .NET user DB).
SECURITY_STAMP_CLAIM = "security_stamp"

# The .NET backend embeds the e-commerce admin panel credentials used for the
# integration "Sync Now" flow (e-commerce login before connection/sync). Values are
# present when the account has an e-commerce store attached; FastAPI treats them as
# the source for integration authentication and never persists them.
STORE_ADMIN_EMAIL_CLAIM = "store_admin_email"
STORE_ADMIN_PASSWORD_CLAIM = "store_admin_password"

# Contract section 6: exact role values, normalized to internal lowercase names.
ROLE_MAPPING = {
    "Admin": "admin",
    "SuperAdmin": "super_admin",
}

# Contract section 6 / .NET Permissions.All: the exact permission values the .NET
# PermissionAuthorizationHandler checks against the repeatable `permission` claim.
PERMISSION_USERS_MANAGE = "Users.Manage"
PERMISSION_STORES_READ = "Stores.Read"
PERMISSION_STORES_MANAGE = "Stores.Manage"
PERMISSION_SUBSCRIPTIONS_MANAGE = "Subscriptions.Manage"
PERMISSION_ORGANIZATIONS_MANAGE = "Organizations.Manage"
PERMISSIONS_ALL = (
    PERMISSION_USERS_MANAGE,
    PERMISSION_STORES_READ,
    PERMISSION_STORES_MANAGE,
    PERMISSION_SUBSCRIPTIONS_MANAGE,
    PERMISSION_ORGANIZATIONS_MANAGE,
)

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
    Additionally requires the `security_stamp` claim, mirroring the .NET
    OnTokenValidated presence check (the stamp VALUE is only compared against the
    .NET user store, which a resource server cannot do).
    """
    try:
        payload = pyjwt.decode(
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
                "require": ["sub", "exp", "iss", "aud", SECURITY_STAMP_CLAIM],
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

    if not isinstance(payload.get(SECURITY_STAMP_CLAIM), str) or not payload[SECURITY_STAMP_CLAIM].strip():
        raise _auth_error(401, ERR_MISSING_CLAIM)
    return payload


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
    """User ID from `sub` (primary) or the ASP.NET NameIdentifier claim (contract §3/§8).

    .NET writes BOTH `sub` (JwtRegisteredClaimNames.Sub) and
    `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier`
    (ClaimTypes.NameIdentifier) with the same GUID. The short `nameid` form is kept only
    for backward compatibility with early contract tokens.
    """
    value = payload.get("sub") or payload.get(NAME_IDENTIFIER_CLAIM) or payload.get("nameid")
    if value is None:
        raise _auth_error(401, ERR_MISSING_CLAIM)
    return _parse_guid(value)


def get_email_from_token(payload: dict) -> str | None:
    """Email from the standard `email` claim, falling back to the ASP.NET URI form."""
    return payload.get("email") or payload.get(EMAIL_CLAIM)


def get_role_from_token(payload: dict) -> str | None:
    """Primary role from the ASP.NET long-form URI claim ONLY (contract §4 — never `role`/`roles`).

    When .NET emits several role claims they serialize as a JSON array; the first entry is
    the primary role. Each value is normalized (Admin -> admin, SuperAdmin -> super_admin).
    """
    value = payload.get(ROLE_CLAIM)
    roles = _as_string_list(value)
    if not roles:
        return None
    return ROLE_MAPPING.get(roles[0], roles[0])


def get_roles_from_token(payload: dict) -> list:
    """ALL roles from the ASP.NET long-form role claim(s) (contract §6).

    Mirrors .NET `claims.AddRange(roles.Select(role => new Claim(ClaimTypes.Role, role)))`
    — a user can hold several roles, and .NET's `User.IsInRole(role)` matches any of them.
    Empty when no role claim is present.
    """
    value = payload.get(ROLE_CLAIM)
    roles = _as_string_list(value)
    return [ROLE_MAPPING.get(r, r) for r in roles]


def _as_string_list(value: object) -> list[str]:
    """Normalize a single claim value or a repeated-claim JSON array to a string list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str) and v]
    if isinstance(value, str) and value:
        return [value]
    return []


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


def get_store_admin_email_from_token(payload: dict) -> str | None:
    """E-commerce admin panel email from the `store_admin_email` claim (integration login)."""
    return payload.get(STORE_ADMIN_EMAIL_CLAIM)


def get_store_admin_password_from_token(payload: dict) -> str | None:
    """E-commerce admin panel password from the `store_admin_password` claim (integration login)."""
    return payload.get(STORE_ADMIN_PASSWORD_CLAIM)


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
