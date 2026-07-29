import jwt as pyjwt
from app.core.auth_settings import auth_settings


def decode_jwt(token: str) -> dict:
    payload = pyjwt.decode(
        token,
        auth_settings.JWT_SECRET_KEY or auth_settings.JWT_PUBLIC_KEY,
        algorithms=[auth_settings.JWT_ALGORITHM],
        issuer=auth_settings.JWT_ISSUER,
        audience=auth_settings.JWT_AUDIENCE,
        options={"verify_exp": True},
    )
    return payload


def verify_jwt(token: str) -> dict:
    return decode_jwt(token)


def get_tenant_id_from_token(payload: dict) -> str | None:
    return payload.get("tenant_id") or payload.get("store_id")


def get_user_id_from_token(payload: dict) -> str | None:
    return payload.get("sub") or payload.get("user_id")


def get_roles_from_token(payload: dict) -> list:
    roles = payload.get("roles")
    if roles is not None:
        if isinstance(roles, str):
            return [roles]
        if isinstance(roles, list):
            return roles
    role = payload.get("role")
    if role is not None:
        return [role] if isinstance(role, str) else list(role)
    return []


def get_scopes_from_token(payload: dict) -> list:
    scopes = payload.get("scopes", [])
    if isinstance(scopes, str):
        return scopes.split()
    if isinstance(scopes, list):
        return scopes
    return []
