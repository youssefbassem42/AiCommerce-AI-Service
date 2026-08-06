"""Tests for JWT validation utilities implementing the .NET JWT Authentication Contract (v1.0)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt as pyjwt
import pytest

from app.core.security import (
    EMAIL_CLAIM,
    ERR_BAD_AUDIENCE,
    ERR_BAD_ISSUER,
    ERR_BAD_SIGNATURE,
    ERR_EXPIRED,
    ERR_INVALID_FORMAT,
    ERR_MISSING_CLAIM,
    NAME_IDENTIFIER_CLAIM,
    ROLE_CLAIM,
    JWTAuthenticationError,
    decode_jwt,
    get_email_from_token,
    get_expires_at_from_token,
    get_organization_id_from_token,
    get_permissions_from_token,
    get_role_from_token,
    get_roles_from_token,
    get_store_id_from_token,
    get_user_id_from_token,
    verify_jwt,
)

ISSUER = "AI-Sales-Agent"
AUDIENCE = "AI-Sales-Agent"

USER_GUID = "11111111-1111-1111-1111-111111111111"
STORE_GUID = "22222222-2222-2222-2222-222222222222"
ORG_GUID = "33333333-3333-3333-3333-333333333333"


class TestJwtSecurity:
    """Purpose: Validate JWT encode/decode/verify operations against the contract."""

    def setup_method(self):
        self.secret = "test-secret-key-for-testing"
        self.valid_payload = {
            "sub": USER_GUID,
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier": USER_GUID,
            "email": "user-1@example.com",
            "security_stamp": "test-security-stamp",
            "store_id": STORE_GUID,
            "org_id": ORG_GUID,
            ROLE_CLAIM: "Admin",
            "permission": ["kb:read", "kb:write"],
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }
        self.token = pyjwt.encode(self.valid_payload, self.secret, algorithm="HS256")

    def _patch_settings(self, mock_settings):
        mock_settings.JWT_SECRET = self.secret
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_ISSUER = ISSUER
        mock_settings.JWT_AUDIENCE = AUDIENCE

    def _sign(self, payload: dict) -> str:
        return pyjwt.encode({**self.valid_payload, **payload}, self.secret, algorithm="HS256")

    @patch("app.core.security.auth_settings")
    def test_decode_valid_token(self, mock_settings):
        """Preconditions: Contract-compliant JWT. Input: Token. Execution: decode_jwt(). Expected: Payload."""
        self._patch_settings(mock_settings)

        payload = decode_jwt(self.token)
        assert payload["sub"] == USER_GUID
        assert payload["store_id"] == STORE_GUID

    @patch("app.core.security.auth_settings")
    def test_verify_jwt_alias(self, mock_settings):
        """Preconditions: Valid token. Input: Token. Execution: verify_jwt(). Expected: Payload."""
        self._patch_settings(mock_settings)
        assert verify_jwt(self.token)["sub"] == USER_GUID

    @patch("app.core.security.auth_settings")
    def test_decode_wrong_issuer(self, mock_settings):
        """Preconditions: Token signed with a different issuer. Expected: 401 ERR_BAD_ISSUER."""
        self._patch_settings(mock_settings)
        with pytest.raises(JWTAuthenticationError) as exc_info:
            decode_jwt(self._sign({"iss": "ai-commerce"}))
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == ERR_BAD_ISSUER

    @patch("app.core.security.auth_settings")
    def test_decode_wrong_audience(self, mock_settings):
        """Preconditions: Token with a different audience. Expected: 401 ERR_BAD_AUDIENCE."""
        self._patch_settings(mock_settings)
        with pytest.raises(JWTAuthenticationError) as exc_info:
            decode_jwt(self._sign({"aud": "ai-service"}))
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == ERR_BAD_AUDIENCE

    @patch("app.core.security.auth_settings")
    def test_decode_invalid_signature(self, mock_settings):
        """Preconditions: Token signed with a different secret. Expected: 401 ERR_BAD_SIGNATURE."""
        self._patch_settings(mock_settings)
        with pytest.raises(JWTAuthenticationError) as exc_info:
            decode_jwt(pyjwt.encode(self.valid_payload, "a-different-secret", algorithm="HS256"))
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == ERR_BAD_SIGNATURE

    @patch("app.core.security.auth_settings")
    def test_decode_expired_token(self, mock_settings):
        """Preconditions: Expired JWT. Expected: 401 ERR_EXPIRED (no clock skew leeway)."""
        self._patch_settings(mock_settings)
        expired = self._sign({"exp": datetime.now(UTC) - timedelta(hours=1)})
        with pytest.raises(JWTAuthenticationError) as exc_info:
            decode_jwt(expired)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == ERR_EXPIRED

    @patch("app.core.security.auth_settings")
    def test_decode_missing_required_claim(self, mock_settings):
        """Preconditions: Token without `sub`. Expected: 401 ERR_MISSING_CLAIM."""
        self._patch_settings(mock_settings)
        payload = self.valid_payload.copy()
        payload.pop("sub")
        with pytest.raises(JWTAuthenticationError) as exc_info:
            decode_jwt(pyjwt.encode(payload, self.secret, algorithm="HS256"))
        assert exc_info.value.detail == ERR_MISSING_CLAIM

    @patch("app.core.security.auth_settings")
    def test_decode_missing_security_stamp(self, mock_settings):
        """Preconditions: Token without `security_stamp` (as .NET would reject in OnTokenValidated).
        Expected: 401 ERR_MISSING_CLAIM."""
        self._patch_settings(mock_settings)
        payload = self.valid_payload.copy()
        payload.pop("security_stamp")
        with pytest.raises(JWTAuthenticationError) as exc_info:
            decode_jwt(pyjwt.encode(payload, self.secret, algorithm="HS256"))
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == ERR_MISSING_CLAIM

    @patch("app.core.security.auth_settings")
    def test_decode_empty_security_stamp_rejected(self, mock_settings):
        """Preconditions: Token with blank security_stamp. Expected: 401 ERR_MISSING_CLAIM
        (mirrors .NET string.IsNullOrWhiteSpace check)."""
        self._patch_settings(mock_settings)
        payload = self.valid_payload.copy()
        payload["security_stamp"] = "   "
        with pytest.raises(JWTAuthenticationError) as exc_info:
            decode_jwt(pyjwt.encode(payload, self.secret, algorithm="HS256"))
        assert exc_info.value.detail == ERR_MISSING_CLAIM

    @patch("app.core.security.auth_settings")
    def test_decode_invalid_token(self, mock_settings):
        """Preconditions: Garbage token string. Expected: 401 ERR_INVALID_FORMAT."""
        self._patch_settings(mock_settings)
        with pytest.raises(JWTAuthenticationError) as exc_info:
            decode_jwt("invalid.token.string")
        assert exc_info.value.detail == ERR_INVALID_FORMAT

    def test_get_store_id_from_token(self):
        """Preconditions: Payload with store_id. Expected: normalized GUID."""
        payload = {"store_id": STORE_GUID}
        assert get_store_id_from_token(payload) == STORE_GUID

    def test_get_store_id_rejects_legacy_tenant_id(self):
        """Preconditions: Payload with legacy tenant_id. Expected: None (contract §9 — legacy ignored)."""
        payload = {"tenant_id": STORE_GUID}
        assert get_store_id_from_token(payload) is None

    def test_get_store_id_missing(self):
        """Preconditions: Payload without store claim. Expected: None."""
        payload = {"sub": USER_GUID}
        assert get_store_id_from_token(payload) is None

    def test_get_organization_id_from_token(self):
        """Preconditions: Payload with org_id. Expected: normalized GUID."""
        payload = {"org_id": ORG_GUID}
        assert get_organization_id_from_token(payload) == ORG_GUID

    def test_get_organization_id_rejects_legacy_organization_id(self):
        """Preconditions: Payload with legacy organization_id key. Expected: None."""
        payload = {"organization_id": ORG_GUID}
        assert get_organization_id_from_token(payload) is None

    def test_get_user_id_from_token(self):
        """Preconditions: Payload with sub. Expected: sub value."""
        payload = {"sub": USER_GUID}
        assert get_user_id_from_token(payload) == USER_GUID

    def test_get_user_id_from_nameid(self):
        """Preconditions: Payload with nameid. Expected: nameid value."""
        payload = {"nameid": USER_GUID}
        assert get_user_id_from_token(payload) == USER_GUID

    def test_get_user_id_from_nameidentifier_uri(self):
        """Preconditions: Payload with the ASP.NET ClaimTypes.NameIdentifier URI (what .NET actually emits).
        Expected: URI value."""
        payload = {NAME_IDENTIFIER_CLAIM: USER_GUID}
        assert get_user_id_from_token(payload) == USER_GUID

    def test_get_user_id_prefers_sub(self):
        """Preconditions: Payload with both sub and NameIdentifier URI. Expected: sub wins."""
        payload = {"sub": USER_GUID, NAME_IDENTIFIER_CLAIM: ORG_GUID}
        assert get_user_id_from_token(payload) == USER_GUID

    def test_get_user_id_missing(self):
        """Preconditions: Payload without sub/nameid. Expected: 401 ERR_MISSING_CLAIM."""
        with pytest.raises(JWTAuthenticationError) as exc_info:
            get_user_id_from_token({"email": "a@b.com"})
        assert exc_info.value.detail == ERR_MISSING_CLAIM

    def test_get_user_id_rejects_non_guid(self):
        """Preconditions: Non-GUID sub. Expected: 401 ERR_INVALID_FORMAT."""
        with pytest.raises(JWTAuthenticationError) as exc_info:
            get_user_id_from_token({"sub": "not-a-guid"})
        assert exc_info.value.detail == ERR_INVALID_FORMAT

    def test_get_email_from_token(self):
        """Preconditions: Payload with email. Expected: email value."""
        payload = {"email": "a@b.com"}
        assert get_email_from_token(payload) == "a@b.com"

    def test_get_email_from_xml_claim(self):
        """Preconditions: Payload with ASP.NET email URI. Expected: claim value."""
        payload = {EMAIL_CLAIM: "c@d.com"}
        assert get_email_from_token(payload) == "c@d.com"

    def test_get_role_from_token_maps_admin(self):
        """Preconditions: URI role claim Admin. Expected: mapped `admin`."""
        payload = {ROLE_CLAIM: "Admin"}
        assert get_role_from_token(payload) == "admin"

    def test_get_role_from_token_maps_super_admin(self):
        """Preconditions: URI role claim SuperAdmin. Expected: mapped `super_admin`."""
        payload = {ROLE_CLAIM: "SuperAdmin"}
        assert get_role_from_token(payload) == "super_admin"

    def test_get_role_from_token_ignores_short_role_claim(self):
        """Preconditions: Only short `roles` claim present. Expected: None (URI claim is the only source)."""
        payload = {"roles": ["Admin"]}
        assert get_role_from_token(payload) is None

    def test_get_roles_from_token_uri_only(self):
        """Preconditions: URI role claim present. Expected: mapped single-element list."""
        payload = {ROLE_CLAIM: "SuperAdmin"}
        assert get_roles_from_token(payload) == ["super_admin"]

    def test_get_roles_from_token_empty_when_absent(self):
        """Preconditions: No role claims. Expected: empty list."""
        assert get_roles_from_token({"sub": USER_GUID}) == []

    def test_get_roles_from_token_multiple(self):
        """Preconditions: Multiple role claims (JSON array) as .NET emits them.
        Expected: ALL roles mapped — .NET User.IsInRole matches any of them."""
        payload = {ROLE_CLAIM: ["Seller", "Admin"]}
        assert get_roles_from_token(payload) == ["Seller", "admin"]

    def test_get_role_from_token_primary_from_list(self):
        """Preconditions: Multiple role claims. Expected: first entry is the primary role."""
        payload = {ROLE_CLAIM: ["SuperAdmin", "Admin"]}
        assert get_role_from_token(payload) == "super_admin"

    def test_get_permissions_from_token_single(self):
        """Preconditions: Permission claim as a string. Expected: single-element list."""
        payload = {"permission": "kb:read"}
        assert get_permissions_from_token(payload) == ["kb:read"]

    def test_get_permissions_from_token_list(self):
        """Preconditions: Repeatable permission claim as a list. Expected: all values."""
        payload = {"permission": ["kb:read", "kb:write"]}
        assert get_permissions_from_token(payload) == ["kb:read", "kb:write"]

    def test_get_permissions_from_token_missing(self):
        """Preconditions: No permission claims. Expected: empty list."""
        assert get_permissions_from_token({"sub": USER_GUID}) == []

    def test_get_expires_at_from_token(self):
        """Preconditions: Numeric exp claim. Expected: timezone-aware UTC datetime."""
        exp = int(datetime.now(UTC).timestamp()) + 60
        expires_at = get_expires_at_from_token({"exp": exp})
        assert expires_at is not None
        assert expires_at.tzinfo == UTC
