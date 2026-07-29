"""Tests for ApiKeyRepository."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.mongodb.repositories.api_key_repository import ApiKeyRepository


class TestApiKeyRepository:
    """Purpose: Validate ApiKeyRepository business logic methods."""

    def test_hash_and_verify_key(self):
        """Preconditions: Raw API key string. Input: Raw key. Execution: hash_key then verify_key. Expected: True for same key, False for different."""
        raw_key = "test-api-key-12345"
        hashed = ApiKeyRepository.hash_key(raw_key, rounds=4)
        assert ApiKeyRepository.verify_key(raw_key, hashed) is True
        assert ApiKeyRepository.verify_key("wrong-key", hashed) is False

    def test_hash_key_produces_different_hashes(self):
        """Preconditions: Same raw key. Input: Hash twice. Execution: Compare hashes. Expected: Different hashes (due to salt)."""
        raw_key = "same-key"
        hash1 = ApiKeyRepository.hash_key(raw_key, rounds=4)
        hash2 = ApiKeyRepository.hash_key(raw_key, rounds=4)
        assert hash1 != hash2

    def test_generate_key_prefix(self):
        """Preconditions: Raw key. Input: Full raw key. Execution: generate_key_prefix(). Expected: Prefix starting with ak_."""
        raw_key = "abcdef1234567890"
        prefix = ApiKeyRepository.generate_key_prefix(raw_key)
        assert prefix.startswith("ak_")
        assert len(prefix) == 11

    def test_generate_key_prefix_short_key(self):
        """Preconditions: Short raw key. Input: Short string. Execution: generate_key_prefix(). Expected: Prefix with truncated key."""
        raw_key = "abc"
        prefix = ApiKeyRepository.generate_key_prefix(raw_key)
        assert prefix.startswith("ak_")

    def test_verify_key_wrong_hash_format(self):
        """Preconditions: Invalid hash. Input: Malformed hash. Execution: verify_key. Expected: False (no exception)."""
        result = ApiKeyRepository.verify_key("key", "not-a-valid-hash")
        assert result is False

    def test_verify_key_empty_key(self):
        """Preconditions: Empty key. Input: Empty string. Execution: verify_key. Expected: False."""
        hashed = ApiKeyRepository.hash_key("real-key", rounds=4)
        result = ApiKeyRepository.verify_key("", hashed)
        assert result is False

    def test_verify_key_empty_hash(self):
        """Preconditions: Empty hash. Input: Empty string. Execution: verify_key. Expected: False."""
        result = ApiKeyRepository.verify_key("key", "")
        assert result is False
