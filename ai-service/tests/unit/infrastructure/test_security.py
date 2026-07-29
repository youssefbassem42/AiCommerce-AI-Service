"""Tests for JWT security utilities."""
from datetime import datetime, timedelta, UTC
from unittest.mock import patch

import jwt as pyjwt
import pytest

from app.core.security import decode_jwt, verify_jwt, get_tenant_id_from_token, get_user_id_from_token, get_roles_from_token, get_scopes_from_token


class TestJwtSecurity:
    """Purpose: Validate JWT encode/decode/verify operations."""

    def setup_method(self):
        self.secret = "test-secret-key-for-testing"
        self.valid_payload = {
            "sub": "user-1",
            "tenant_id": "store-1",
            "roles": ["admin"],
            "scopes": ["read", "write"],
            "iss": "ai-commerce",
            "aud": "ai-service",
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }
        self.token = pyjwt.encode(self.valid_payload, self.secret, algorithm="HS256")

    @patch("app.core.security.auth_settings")
    def test_decode_valid_token(self, mock_settings):
        """Preconditions: Valid JWT token. Input: Token string. Execution: decode_jwt(). Expected: Payload dict."""
        mock_settings.JWT_SECRET_KEY = self.secret
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_ISSUER = "ai-commerce"
        mock_settings.JWT_AUDIENCE = "ai-service"

        payload = decode_jwt(self.token)
        assert payload["sub"] == "user-1"
        assert payload["tenant_id"] == "store-1"
        assert payload["roles"] == ["admin"]

    @patch("app.core.security.auth_settings")
    def test_decode_expired_token(self, mock_settings):
        """Preconditions: Expired JWT. Input: Expired token. Execution: decode_jwt(). Expected: ExpiredSignatureError."""
        mock_settings.JWT_SECRET_KEY = self.secret
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_ISSUER = "ai-commerce"
        mock_settings.JWT_AUDIENCE = "ai-service"

        expired_payload = self.valid_payload.copy()
        expired_payload["exp"] = datetime.now(UTC) - timedelta(hours=1)
        expired_token = pyjwt.encode(expired_payload, self.secret, algorithm="HS256")

        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_jwt(expired_token)

    @patch("app.core.security.auth_settings")
    def test_decode_invalid_token(self, mock_settings):
        """Preconditions: Invalid token string. Input: Garbage. Execution: decode_jwt(). Expected: PyJWTError."""
        mock_settings.JWT_SECRET_KEY = self.secret
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_ISSUER = "ai-commerce"
        mock_settings.JWT_AUDIENCE = "ai-service"

        with pytest.raises(pyjwt.PyJWTError):
            decode_jwt("invalid.token.string")

    @patch("app.core.security.auth_settings")
    def test_verify_jwt_valid(self, mock_settings):
        """Preconditions: Valid token. Input: Token. Execution: verify_jwt(). Expected: Payload."""
        mock_settings.JWT_SECRET_KEY = self.secret
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_ISSUER = "ai-commerce"
        mock_settings.JWT_AUDIENCE = "ai-service"

        payload = verify_jwt(self.token)
        assert payload["sub"] == "user-1"

    @patch("app.core.security.auth_settings")
    def test_get_tenant_id_from_token(self, mock_settings):
        """Preconditions: Payload with tenant_id. Input: Payload. Execution: get_tenant_id_from_token(). Expected: tenant_id value."""
        payload = {"tenant_id": "store-1"}
        assert get_tenant_id_from_token(payload) == "store-1"

    def test_get_tenant_id_fallback(self):
        """Preconditions: Payload with store_id instead. Input: Payload. Execution: get_tenant_id_from_token(). Expected: store_id value."""
        payload = {"store_id": "store-2"}
        assert get_tenant_id_from_token(payload) == "store-2"

    def test_get_tenant_id_missing(self):
        """Preconditions: Payload without tenant info. Input: Payload. Execution: get_tenant_id_from_token(). Expected: None."""
        payload = {"sub": "user-1"}
        assert get_tenant_id_from_token(payload) is None

    def test_get_user_id_from_token(self):
        """Preconditions: Payload with sub. Input: Payload. Execution: get_user_id_from_token(). Expected: sub value."""
        payload = {"sub": "user-1"}
        assert get_user_id_from_token(payload) == "user-1"

    def test_get_user_id_from_token_fallback(self):
        """Preconditions: Payload with user_id. Input: Payload. Execution: get_user_id_from_token(). Expected: user_id value."""
        payload = {"user_id": "user-2"}
        assert get_user_id_from_token(payload) == "user-2"

    def test_get_roles_from_token(self):
        """Preconditions: Payload with roles list. Input: Payload. Execution: get_roles_from_token(). Expected: List of roles."""
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
        mock_settings.JWT_ISSUER = "ai-commerce"
        mock_settings.JWT_AUDIENCE = "ai-service"

        with pytest.raises(pyjwt.PyJWTError):
            decode_jwt(self.token)
