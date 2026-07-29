"""Tests for the ApiKey domain entity."""
from datetime import datetime, timedelta, UTC

import pytest

from app.domain.auth.entities.api_key import ApiKey


class TestApiKeyEntity:
    """Purpose: Validate ApiKey entity creation and business logic."""

    def test_create_api_key(self):
        """Preconditions: Valid parameters. Input: All required fields. Execution: Create entity. Expected: Entity with correct values."""
        key = ApiKey(
            id="test-id",
            key_hash="hashed_value",
            key_prefix="ak_abc123",
            name="Test Key",
            store_id="store-1",
            scopes=["read", "write"],
            is_active=True,
        )
        assert key.id == "test-id"
        assert key.key_hash == "hashed_value"
        assert key.key_prefix == "ak_abc123"
        assert key.name == "Test Key"
        assert key.store_id == "store-1"
        assert key.scopes == ["read", "write"]
        assert key.is_active is True
        assert key.is_expired is False
        assert key.created_at is not None

    def test_api_key_has_scope(self):
        """Preconditions: Key with scopes. Input: Check scope. Execution: has_scope(). Expected: True for matching scope."""
        key = ApiKey(
            id="test-id", key_hash="hash", key_prefix="ak_abc", name="Key",
            store_id="s1", scopes=["read", "write"],
        )
        assert key.has_scope("read") is True
        assert key.has_scope("write") is True
        assert key.has_scope("admin") is False

    def test_api_key_wildcard_scope(self):
        """Preconditions: Key with wildcard scope. Input: Check any scope. Execution: has_scope(). Expected: True."""
        key = ApiKey(
            id="test-id", key_hash="hash", key_prefix="ak_abc", name="Key",
            store_id="s1", scopes=["*"],
        )
        assert key.has_scope("anything") is True

    def test_api_key_is_expired(self):
        """Preconditions: Key with past expiration. Input: None. Execution: is_expired. Expected: True."""
        key = ApiKey(
            id="test-id", key_hash="hash", key_prefix="ak_abc", name="Key",
            store_id="s1", expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert key.is_expired is True

    def test_api_key_is_not_expired(self):
        """Preconditions: Key with future expiration. Input: None. Execution: is_expired. Expected: False."""
        key = ApiKey(
            id="test-id", key_hash="hash", key_prefix="ak_abc", name="Key",
            store_id="s1", expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert key.is_expired is False

    def test_api_key_no_expiration(self):
        """Preconditions: Key without expiration. Input: None. Execution: is_expired. Expected: False."""
        key = ApiKey(
            id="test-id", key_hash="hash", key_prefix="ak_abc", name="Key",
            store_id="s1", expires_at=None,
        )
        assert key.is_expired is False

    def test_api_key_inactive(self):
        """Preconditions: Key marked inactive. Input: None. Execution: Check is_active. Expected: False."""
        key = ApiKey(
            id="test-id", key_hash="hash", key_prefix="ak_abc", name="Key",
            store_id="s1", is_active=False,
        )
        assert key.is_active is False

    def test_api_key_empty_scopes(self):
        """Preconditions: Key with empty scopes. Input: Check scope. Execution: has_scope(). Expected: False."""
        key = ApiKey(
            id="test-id", key_hash="hash", key_prefix="ak_abc", name="Key",
            store_id="s1", scopes=[],
        )
        assert key.has_scope("anything") is False

    def test_api_key_id_empty(self):
        """Preconditions: Empty ID. Input: Empty string ID. Execution: Create entity. Expected: Entity with empty ID."""
        key = ApiKey(
            id="", key_hash="hash", key_prefix="ak_abc", name="Key",
            store_id="s1",
        )
        assert key.id == ""
