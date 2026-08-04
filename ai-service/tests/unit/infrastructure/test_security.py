"""Tests for JWT security utilities."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt as pyjwt
import pytest

from app.core.security import (
    XML_EMAIL_CLAIM,
    XML_NAMEIDENTIFIER_CLAIM,
    XML_ROLE_CLAIM,
    decode_jwt,
    get_email_from_token,
    get_organization_id_from_token,
    get_roles_from_token,
    get_scopes_from_token,
    get_store_id_from_token,
    get_tenant_id_from_token,
    get_user_id_from_token,
)

ISSUER = "AI-Sales-Agent"
AUDIENCE = "AI-Sales-Agent"


class TestJwtSecurity:
    """Purpose: Validate JWT encode/decode/verify operations."""

    def setup_method(self):
        self.secret = "test-secret-key-for-testing"
        self.valid_payload = {
            "sub": "user-1",
            "email": "user-1@example.com",
            "store_id": "store-1",
            "organization_id": "org-1",
            "roles": ["Seller"],
            "scopes": ["read", "write"],
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }
        self.token = pyjwt.encode(self.valid_payload, self.secret, algorithm="HS256")

    def _patch_settings(self, mock_settings):
        mock_settings.JWT_SECRET_KEY = self.secret
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_ISSUER = ISSUER
        mock_settings.JWT_AUDIENCE = AUDIENCE

    @patch("app.core.security.auth_settings")
    def test_decode_valid_token(self, mock_settings):
        """Preconditions: Valid JWT token. Input: Token string. Execution: decode_jwt(). Expected: Payload dict."""
        self._patch_settings(mock_settings)

        payload = decode_jwt(self.token)
        assert payload["sub"] == "user-1"
        assert payload["store_id"] == "store-1"
        assert payload["roles"] == ["Seller"]

    @patch("app.core.security.auth_settings")
    def test_decode_legacy_issuer_audience(self, mock_settings):
        """Preconditions: Token with legacy iss/aud but both configured. Input: Token. Execution: decode_jwt(). Expected: Payload dict."""
        self._patch_settings(mock_settings)
        mock_settings.JWT_ISSUER = f"{ISSUER},ai-commerce"
        mock_settings.JWT_AUDIENCE = f"{AUDIENCE},ai-service"

        legacy_payload = self.valid_payload.copy()
        legacy_payload["iss"] = "ai-commerce"
        legacy_payload["aud"] = "ai-service"
        legacy_token = pyjwt.encode(legacy_payload, self.secret, algorithm="HS256")

        payload = decode_jwt(legacy_token)
        assert payload["sub"] == "user-1"

    @patch("app.core.security.auth_settings")
    def test_decode_expired_token(self, mock_settings):
        """Preconditions: Expired JWT. Input: Expired token. Execution: decode_jwt(). Expected: ExpiredSignatureError."""
        self._patch_settings(mock_settings)

        expired_payload = self.valid_payload.copy()
        expired_payload["exp"] = datetime.now(UTC) - timedelta(hours=1)
        expired_token = pyjwt.encode(expired_payload, self.secret, algorithm="HS256")

        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_jwt(expired_token)

    @patch("app.core.security.auth_settings")
    def test_decode_invalid_token(self, mock_settings):
        """Preconditions: Invalid token string. Input: Garbage. Execution: decode_jwt(). Expected: PyJWTError."""
        self._patch_settings(mock_settings)

        with pytest.raises(pyjwt.PyJWTError):
            decode_jwt("invalid.token.string")

    @patch("app.core.security.auth_settings")
    def test_decode_valid_token_alias_path(self, mock_settings):
        """Preconditions: Valid token. Input: Token. Execution: decode_jwt(). Expected: Payload."""
        self._patch_settings(mock_settings)

        payload = decode_jwt(self.token)
        assert payload["sub"] == "user-1"

    def test_get_store_id_from_token(self):
        """Preconditions: Payload with store_id. Input: Payload. Execution: get_store_id_from_token(). Expected: store_id value."""
        payload = {"store_id": "store-1"}
        assert get_store_id_from_token(payload) == "store-1"

    def test_get_store_id_legacy_fallback(self):
        """Preconditions: Payload with legacy tenant_id. Input: Payload. Execution: get_store_id_from_token(). Expected: tenant_id value."""
        payload = {"tenant_id": "store-2"}
        assert get_store_id_from_token(payload) == "store-2"

    def test_get_store_id_missing(self):
        """Preconditions: Payload without tenant info. Input: Payload. Execution: get_store_id_from_token(). Expected: None."""
        payload = {"sub": "user-1"}
        assert get_store_id_from_token(payload) is None

    def test_get_tenant_id_from_token_legacy_alias(self):
        """Preconditions: Payload with store_id. Input: Payload. Execution: get_tenant_id_from_token(). Expected: store_id value."""
        payload = {"store_id": "store-1"}
        assert get_tenant_id_from_token(payload) == "store-1"

    def test_get_organization_id_from_token(self):
        """Preconditions: Payload with organization_id. Input: Payload. Execution: get_organization_id_from_token(). Expected: organization_id value."""
        payload = {"organization_id": "org-1"}
        assert get_organization_id_from_token(payload) == "org-1"

    def test_get_organization_id_fallback(self):
        """Preconditions: Payload with legacy org_id. Input: Payload. Execution: get_organization_id_from_token(). Expected: org_id value."""
        payload = {"org_id": "org-2"}
        assert get_organization_id_from_token(payload) == "org-2"

    def test_get_user_id_from_token(self):
        """Preconditions: Payload with sub. Input: Payload. Execution: get_user_id_from_token(). Expected: sub value."""
        payload = {"sub": "user-1"}
        assert get_user_id_from_token(payload) == "user-1"

    def test_get_user_id_from_token_fallback(self):
        """Preconditions: Payload with user_id. Input: Payload. Execution: get_user_id_from_token(). Expected: user_id value."""
        payload = {"user_id": "user-2"}
        assert get_user_id_from_token(payload) == "user-2"

    def test_get_user_id_from_xml_claim(self):
        """Preconditions: Payload with XML nameidentifier claim only. Input: Payload. Execution: get_user_id_from_token(). Expected: Claim value."""
        payload = {XML_NAMEIDENTIFIER_CLAIM: "user-3"}
        assert get_user_id_from_token(payload) == "user-3"

    def test_get_email_from_token(self):
        """Preconditions: Payload with email. Input: Payload. Execution: get_email_from_token(). Expected: email value."""
        payload = {"email": "a@b.com"}
        assert get_email_from_token(payload) == "a@b.com"

    def test_get_email_from_xml_claim(self):
        """Preconditions: Payload with XML email claim only. Input: Payload. Execution: get_email_from_token(). Expected: Claim value."""
        payload = {XML_EMAIL_CLAIM: "c@d.com"}
        assert get_email_from_token(payload) == "c@d.com"

    def test_get_roles_from_token_maps_seller(self):
        """Preconditions: Payload with Seller role. Input: Payload. Execution: get_roles_from_token(). Expected: Mapped admin role."""
        payload = {"roles": ["Seller"]}
        assert get_roles_from_token(payload) == ["admin"]

    def test_get_roles_from_token_maps_super_admin(self):
        """Preconditions: Payload with SuperAdmin role. Input: Payload. Execution: get_roles_from_token(). Expected: Mapped super_admin role."""
        payload = {XML_ROLE_CLAIM: "SuperAdmin"}
        assert get_roles_from_token(payload) == ["super_admin"]

    def test_get_roles_from_token_passthrough(self):
        """Preconditions: Payload with unmapped roles. Input: Payload. Execution: get_roles_from_token(). Expected: Unchanged roles."""
        payload = {"roles": ["admin", "editor"]}
        assert get_roles_from_token(payload) == ["admin", "editor"]

    def test_get_roles_from_token_single(self):
        """Preconditions: Payload with role string. Input: Payload. Execution: get_roles_from_token(). Expected: Role in list."""
        payload = {"role": ["viewer"]}
        assert get_roles_from_token(payload) == ["viewer"]

    def test_get_scopes_from_token(self):
        """Preconditions: Payload with scopes. Input: Payload. Execution: get_scopes_from_token(). Expected: List of scopes."""
        payload = {"scopes": ["read", "write"]}
        assert get_scopes_from_token(payload) == ["read", "write"]

    @patch("app.core.security.auth_settings")
    def test_decode_token_wrong_secret(self, mock_settings):
        """Preconditions: Token signed with different secret. Input: Token. Execution: decode_jwt(). Expected: PyJWTError."""
        mock_settings.JWT_SECRET_KEY = "different-secret"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_ISSUER = ISSUER
        mock_settings.JWT_AUDIENCE = AUDIENCE

        with pytest.raises(pyjwt.PyJWTError):
            decode_jwt(self.token)
