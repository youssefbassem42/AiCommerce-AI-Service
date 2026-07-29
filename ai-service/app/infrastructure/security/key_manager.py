import logging
import os
from typing import Optional

from app.infrastructure.security.encryption import EncryptionService, generate_encryption_key
from app.core.config import settings

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
            self._encryption_service: Optional[EncryptionService] = None
            self._initialized = True

    def _get_encryption_service(self) -> EncryptionService:
        if self._encryption_service is None:
            key = os.getenv("ENCRYPTION_KEY", "")
            if not key:
                logger.warning("ENCRYPTION_KEY not set. Generating temporary key.")
                key = generate_encryption_key()
                os.environ["ENCRYPTION_KEY"] = key
            self._encryption_service = EncryptionService(key=key)
        return self._encryption_service

    def encrypt_secret(self, plaintext: str) -> str:
        return self._get_encryption_service().encrypt(plaintext)

    def decrypt_secret(self, encrypted_data: str) -> str:
        return self._get_encryption_service().decrypt(encrypted_data)

    def get_provider_api_key(self, provider_name: str, env_var: Optional[str] = None) -> Optional[str]:
        env_var = env_var or f"{provider_name.upper()}_API_KEY"
        return os.getenv(env_var)

    def set_provider_api_key(self, provider_name: str, api_key: str) -> None:
        env_var = f"{provider_name.upper()}_API_KEY"
        os.environ[env_var] = api_key
