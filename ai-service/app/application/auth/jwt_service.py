"""JWT validation service — the single entry point for token validation.

Used by both the AuthMiddleware (request.state population) and the FastAPI auth
dependencies (endpoint enforcement), so authentication logic lives in exactly one place.
"""

from datetime import UTC, datetime

from app.core.security import (
    decode_jwt,
    get_email_from_token,
    get_exp_from_token,
    get_iat_from_token,
    get_jti_from_token,
    get_organization_id_from_token,
    get_permissions_from_token,
    get_role_from_token,
    get_roles_from_token,
    get_security_stamp_from_token,
    get_store_id_from_token,
    get_user_id_from_token,
)
from app.domain.auth.entities.authenticated_user import AuthenticatedUser


def _to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


class JWTValidationService:
    """Validates a Bearer access token and reconstructs the contract user identity."""

    def validate(self, token: str) -> AuthenticatedUser:
        payload = decode_jwt(token)
        roles = get_roles_from_token(payload)
        return AuthenticatedUser(
            user_id=get_user_id_from_token(payload),
            email=get_email_from_token(payload),
            role=roles[0] if roles else (get_role_from_token(payload) or ""),
            roles=roles,
            security_stamp=get_security_stamp_from_token(payload),
            jti=get_jti_from_token(payload),
            store_id=get_store_id_from_token(payload),
            organization_id=get_organization_id_from_token(payload),
            permissions=get_permissions_from_token(payload),
            issued_at=_to_datetime(get_iat_from_token(payload)),
            expires_at=_to_datetime(get_exp_from_token(payload)),
        )

    def __call__(self, token: str) -> AuthenticatedUser:
        return self.validate(token)


jwt_validation_service = JWTValidationService()
