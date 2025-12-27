"""
Security utilities for authentication and authorization
Matches V3 encryption approach with ENCRYPTION_KEY from environment
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import secrets
import os
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Encryption for private keys (V3 approach)
encryption_key = os.getenv('ENCRYPTION_KEY')
if not encryption_key:
    logger.warning("⚠️ ENCRYPTION_KEY not found in environment! Generating a temporary key.")
    logger.warning("⚠️ Add ENCRYPTION_KEY to your .env file to persist encryption across restarts!")
    logger.warning("⚠️ Generate a key with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
    encryption_key = Fernet.generate_key().decode()

# Ensure key is in bytes
if isinstance(encryption_key, str):
    encryption_key = encryption_key.encode()

cipher_suite = Fernet(encryption_key)
logger.info("✅ Encryption system initialized")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> dict:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        if payload.get("type") != token_type:
            raise ValueError("Invalid token type")

        return payload
    except JWTError:
        raise ValueError("Invalid token")


def encrypt_private_key(private_key: str) -> str:
    """Encrypt a private key for storage"""
    return cipher_suite.encrypt(private_key.encode()).decode()


def decrypt_private_key(encrypted_key: str) -> str:
    """Decrypt a private key from storage"""
    return cipher_suite.decrypt(encrypted_key.encode()).decode()


def is_encrypted(value: str) -> bool:
    """
    Check if a value appears to be encrypted.
    Fernet tokens start with 'gAAAAA' when base64 encoded (V3 approach)

    Args:
        value: The value to check

    Returns:
        True if the value appears to be encrypted
    """
    if not value or not isinstance(value, str):
        return False

    return value.startswith('gAAAAA')


def get_decrypted_private_key(encrypted_or_plain: str) -> str:
    """
    Safely decrypt a private key, handling both encrypted and plain formats.
    Matches V3 implementation.

    Args:
        encrypted_or_plain: Private key that may be encrypted or plain text

    Returns:
        Decrypted private key as plain text
    """
    if is_encrypted(encrypted_or_plain):
        return decrypt_private_key(encrypted_or_plain)
    return encrypted_or_plain


def generate_secure_token(length: int = 32) -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(length)


def generate_transfer_code() -> str:
    """Generate a one-time transfer code (12 characters)"""
    # Format: XXXX-XXXX-XXXX
    part1 = secrets.token_hex(2).upper()
    part2 = secrets.token_hex(2).upper()
    part3 = secrets.token_hex(2).upper()
    return f"{part1}-{part2}-{part3}"
