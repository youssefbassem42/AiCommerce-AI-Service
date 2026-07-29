import base64
import logging
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

NONCE_LENGTH = 12


def generate_encryption_key() -> str:
    key = AESGCM.generate_key(bit_length=256)
    return base64.b64encode(key).decode("utf-8")


class EncryptionService:
    """AES-256-GCM encryption/decryption service."""

    def __init__(self, key: Optional[str] = None):
        if key is None:
            key = os.getenv("ENCRYPTION_KEY", "")
        if not key:
            raise ValueError("Encryption key is not configured")
        self._key = base64.b64decode(key.encode("utf-8"))
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(NONCE_LENGTH)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("utf-8")

    def decrypt(self, encrypted_data: str) -> str:
        raw = base64.b64decode(encrypted_data.encode("utf-8"))
        nonce = raw[:NONCE_LENGTH]
        ciphertext = raw[NONCE_LENGTH:]
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
