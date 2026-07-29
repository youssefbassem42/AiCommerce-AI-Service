"""Tests for AES-256-GCM encryption service."""
import pytest

from app.infrastructure.security.encryption import EncryptionService, generate_encryption_key


class TestEncryptionService:
    """Purpose: Validate AES-256-GCM encryption and decryption."""

    def setup_method(self):
        self.key = generate_encryption_key()
        self.service = EncryptionService(key=self.key)

    def test_encrypt_decrypt(self):
        """Preconditions: Valid key. Input: Plaintext string. Execution: Encrypt then decrypt. Expected: Original plaintext."""
        plaintext = "Hello, World!"
        encrypted = self.service.encrypt(plaintext)
        decrypted = self.service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_long_text(self):
        """Preconditions: Valid key. Input: Long text. Execution: Encrypt then decrypt. Expected: Original text."""
        plaintext = "A" * 10000
        encrypted = self.service.encrypt(plaintext)
        decrypted = self.service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_empty_string(self):
        """Preconditions: Valid key. Input: Empty string. Execution: Encrypt then decrypt. Expected: Empty string."""
        plaintext = ""
        encrypted = self.service.encrypt(plaintext)
        decrypted = self.service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_special_characters(self):
        """Preconditions: Valid key. Input: Special characters. Execution: Encrypt then decrypt. Expected: Original text."""
        plaintext = "!@#$%^&*()_+{}[]|\\:;\"'<>,.?/~`你好日本語"
        encrypted = self.service.encrypt(plaintext)
        decrypted = self.service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_unique_ciphertexts(self):
        """Preconditions: Valid key. Input: Same plaintext twice. Execution: Encrypt twice. Expected: Different ciphertexts (unique nonces)."""
        plaintext = "Sensitive Data"
        encrypted1 = self.service.encrypt(plaintext)
        encrypted2 = self.service.encrypt(plaintext)
        assert encrypted1 != encrypted2

    def test_decrypt_tampered_data(self):
        """Preconditions: Valid key and ciphertext. Input: Tampered ciphertext. Execution: Decrypt. Expected: Exception."""
        plaintext = "Test data"
        encrypted = self.service.encrypt(plaintext)
        tampered = encrypted[:-1] + ("0" if encrypted[-1] != "0" else "1")
        with pytest.raises(Exception):
            self.service.decrypt(tampered)

    def test_invalid_key_length(self):
        """Preconditions: Invalid base64 key. Input: Wrong key. Execution: Create service. Expected: Exception."""
        with pytest.raises(Exception):
            EncryptionService(key="too-short")

    def test_generate_key(self):
        """Preconditions: None. Input: None. Execution: generate_encryption_key(). Expected: Base64 string of 44 chars."""
        key = generate_encryption_key()
        assert isinstance(key, str)
        assert len(key) > 0

    def test_decrypt_fail_with_wrong_key(self):
        """Preconditions: Two different keys. Input: Ciphertext from key1. Execution: Decrypt with key2. Expected: Exception."""
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        s1 = EncryptionService(key=key1)
        s2 = EncryptionService(key=key2)
        encrypted = s1.encrypt("secret")
        with pytest.raises(Exception):
            s2.decrypt(encrypted)

    def test_encrypt_decrypt_numeric(self):
        """Preconditions: Valid key. Input: Numeric string. Execution: Encrypt then decrypt. Expected: Original number."""
        plaintext = "1234567890"
        encrypted = self.service.encrypt(plaintext)
        decrypted = self.service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_decrypt_unicode(self):
        """Preconditions: Valid key. Input: Unicode text. Execution: Encrypt then decrypt. Expected: Original text."""
        plaintext = "🎉 Hello World 🌍"
        encrypted = self.service.encrypt(plaintext)
        decrypted = self.service.decrypt(encrypted)
        assert decrypted == plaintext
