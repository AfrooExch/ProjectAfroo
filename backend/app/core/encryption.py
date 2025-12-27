"""
Encryption utilities for sensitive data (private keys, etc.)
Uses Fernet (AES-256-CBC) symmetric encryption
"""

import logging
from cryptography.fernet import Fernet
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EncryptionService:
    """Service for encrypting/decrypting sensitive data"""

    def __init__(self):
        """Initialize encryption with key from settings"""
        try:
            # Get encryption key from environment
            key = settings.ENCRYPTION_KEY

            if not key:
                raise ValueError("ENCRYPTION_KEY not set in environment")

            # Ensure key is bytes
            if isinstance(key, str):
                key = key.encode('utf-8')

            self.cipher = Fernet(key)
            logger.info("✅ Encryption service initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize encryption service: {e}")
            raise

    def encrypt(self, data: str) -> str:
        """
        Encrypt plaintext data

        Args:
            data: Plaintext string to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        try:
            if not data:
                raise ValueError("Cannot encrypt empty data")

            # Convert to bytes if string
            if isinstance(data, str):
                data = data.encode('utf-8')

            # Encrypt and return as string
            encrypted = self.cipher.encrypt(data)
            return encrypted.decode('utf-8')

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted data

        Args:
            encrypted_data: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string
        """
        try:
            if not encrypted_data:
                raise ValueError("Cannot decrypt empty data")

            # Convert to bytes if string
            if isinstance(encrypted_data, str):
                encrypted_data = encrypted_data.encode('utf-8')

            # Decrypt and return as string
            decrypted = self.cipher.decrypt(encrypted_data)
            return decrypted.decode('utf-8')

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

    def encrypt_private_key(self, private_key: str) -> str:
        """
        Encrypt a private key for storage

        Args:
            private_key: Plaintext private key

        Returns:
            Encrypted private key (safe for database storage)
        """
        if not private_key or not private_key.strip():
            raise ValueError("Private key cannot be empty")

        return self.encrypt(private_key.strip())

    def decrypt_private_key(self, encrypted_key: str) -> str:
        """
        Decrypt a stored private key

        Args:
            encrypted_key: Encrypted private key from database

        Returns:
            Decrypted private key (plaintext)
        """
        if not encrypted_key or not encrypted_key.strip():
            raise ValueError("Encrypted key cannot be empty")

        return self.decrypt(encrypted_key.strip())


# Global encryption service instance
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Get singleton encryption service instance"""
    global _encryption_service

    if _encryption_service is None:
        _encryption_service = EncryptionService()

    return _encryption_service
