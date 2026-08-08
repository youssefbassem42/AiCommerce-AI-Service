import base64
import hashlib
import logging
import os
from typing import Optional

from app.infrastructure.security.encryption import EncryptionService, generate_encryption_key

logger = logging.getLogger(__name__)


class KeyManager:
    """Manages encryption keys and provider secrets."""

    _instance: Optional["KeyManager"] = None

    def __new__(cls) -> "KeyManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._encryption_service: EncryptionService | None = None
            self._initialized = True

    def _get_encryption_service(self) -> EncryptionService:
        if self._encryption_service is None:
            key = os.getenv("ENCRYPTION_KEY", "")
            if not key:
                secret = os.getenv("JWT_SECRET", "")
                if secret:
                    digest = hashlib.sha256(secret.encode("utf-8")).digest()
                    key = base64.b64encode(digest).decode("utf-8")
                    logger.warning(
                        "ENCRYPTION_KEY not set; deriving a stable key from JWT_SECRET so "
                        "encrypted credentials survive restarts."
                    )
                else:
                    logger.warning("ENCRYPTION_KEY not set. Generating temporary key.")
                    key = generate_encryption_key()
                    os.environ["ENCRYPTION_KEY"] = key
            self._encryption_service = EncryptionService(key=key)
        return self._encryption_service

    def encrypt_secret(self, plaintext: str) -> str:
        return self._get_encryption_service().encrypt(plaintext)

    def decrypt_secret(self, encrypted_data: str) -> str:
        return self._get_encryption_service().decrypt(encrypted_data)

    def get_provider_api_key(self, provider_name: str, env_var: str | None = None) -> str | None:
        env_var = env_var or f"{provider_name.upper()}_API_KEY"
        return os.getenv(env_var)

    def set_provider_api_key(self, provider_name: str, api_key: str) -> None:
        env_var = f"{provider_name.upper()}_API_KEY"
        os.environ[env_var] = api_key
