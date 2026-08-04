import jwt as pyjwt

from app.core.auth_settings import auth_settings

XML_ROLE_CLAIM = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"
XML_NAMEIDENTIFIER_CLAIM = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier"
XML_EMAIL_CLAIM = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"

ROLE_MAPPING = {
    "Seller": "admin",
    "seller": "admin",
    "Admin": "admin",
    "admin": "admin",
    "store_admin": "admin",
    "StoreAdmin": "admin",
    "SuperAdmin": "super_admin",
    "superadmin": "super_admin",
    "super_admin": "super_admin",
}


def decode_jwt(token: str) -> dict:
    key = auth_settings.JWT_SECRET_KEY or auth_settings.JWT_PUBLIC_KEY
    algorithms = [auth_settings.JWT_ALGORITHM]
    issuers = [v for v in auth_settings.JWT_ISSUER.split(",") if v.strip()] or [None]
    audiences = [v for v in auth_settings.JWT_AUDIENCE.split(",") if v.strip()] or [None]

    last_exc: Exception | None = None
    for issuer in issuers:
        for audience in audiences:
            try:
                return pyjwt.decode(
                    token,
                    key,
                    algorithms=algorithms,
                    issuer=issuer,
                    audience=audience,
                    options={"verify_exp": True},
                )
            except (pyjwt.InvalidIssuerError, pyjwt.InvalidAudienceError) as exc:
                last_exc = exc
                continue
    if last_exc is not None:
        raise last_exc
    raise pyjwt.InvalidTokenError("Token could not be validated against any configured issuer/audience")


def get_store_id_from_token(payload: dict) -> str | None:
    return payload.get("store_id") or payload.get("tenant_id")


def get_tenant_id_from_token(payload: dict) -> str | None:
    """Legacy alias for get_store_id_from_token, kept during the tenant_id -> store_id transition."""
    return get_store_id_from_token(payload)


def get_organization_id_from_token(payload: dict) -> str | None:
    return payload.get("organization_id") or payload.get("org_id")


def get_user_id_from_token(payload: dict) -> str | None:
    return payload.get("sub") or payload.get("user_id") or payload.get(XML_NAMEIDENTIFIER_CLAIM)


def get_email_from_token(payload: dict) -> str | None:
    return payload.get("email") or payload.get(XML_EMAIL_CLAIM)


def _raw_roles_from_token(payload: dict) -> list:
    for key in ("roles", "role", XML_ROLE_CLAIM):
        value = payload.get(key)
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return list(value)
    return []


def get_roles_from_token(payload: dict) -> list:
    return [ROLE_MAPPING.get(role, role) for role in _raw_roles_from_token(payload)]


def get_scopes_from_token(payload: dict) -> list:
    scopes = payload.get("scopes", [])
    if isinstance(scopes, str):
        return scopes.split()
    if isinstance(scopes, list):
        return scopes
    return []
