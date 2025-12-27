"""
Input Validators - Security validation for all user inputs
Prevents injection, validates crypto addresses, amounts, etc.
"""

import re
from typing import Optional
from decimal import Decimal


class CryptoValidators:
    """Validators for cryptocurrency-related inputs"""

    # Address patterns for different blockchains
    ADDRESS_PATTERNS = {
        "BTC": r"^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,90}$",
        "LTC": r"^[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}$",
        "ETH": r"^0x[a-fA-F0-9]{40}$",
        "SOL": r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"
    }

    # Transaction hash patterns
    TX_HASH_PATTERNS = {
        "BTC": r"^[a-fA-F0-9]{64}$",
        "LTC": r"^[a-fA-F0-9]{64}$",
        "ETH": r"^0x[a-fA-F0-9]{64}$",
        "SOL": r"^[1-9A-HJ-NP-Za-km-z]{87,88}$"
    }

    # Minimum amounts per asset
    MIN_AMOUNTS = {
        "BTC": 0.000001,
        "ETH": 0.0001,
        "LTC": 0.0006,
        "SOL": 0.001,
        "USDT-SOL": 0.1,
        "USDT-ETH": 0.1,
        "USDC-SOL": 0.1,
        "USDC-ETH": 0.1
    }

    # Maximum amounts per asset (anti-money laundering)
    MAX_AMOUNTS = {
        "BTC": 10.0,
        "ETH": 100.0,
        "LTC": 1000.0,
        "SOL": 5000.0,
        "USDT-SOL": 500000.0,
        "USDT-ETH": 500000.0,
        "USDC-SOL": 500000.0,
        "USDC-ETH": 500000.0
    }

    @staticmethod
    def validate_address(address: str, blockchain: str) -> bool:
        """
        Validate cryptocurrency address format.

        Args:
            address: Crypto address to validate
            blockchain: Blockchain type (BTC, ETH, LTC, SOL)

        Returns:
            True if valid, False otherwise
        """
        if not address or not blockchain:
            return False

        # Get base blockchain (remove token suffix)
        base_blockchain = blockchain.split("-")[0] if "-" in blockchain else blockchain

        pattern = CryptoValidators.ADDRESS_PATTERNS.get(base_blockchain)
        if not pattern:
            return False

        return bool(re.match(pattern, address.strip()))

    @staticmethod
    def validate_tx_hash(tx_hash: str, blockchain: str) -> bool:
        """
        Validate transaction hash format.

        Args:
            tx_hash: Transaction hash
            blockchain: Blockchain type

        Returns:
            True if valid, False otherwise
        """
        if not tx_hash or not blockchain:
            return False

        base_blockchain = blockchain.split("-")[0] if "-" in blockchain else blockchain

        pattern = CryptoValidators.TX_HASH_PATTERNS.get(base_blockchain)
        if not pattern:
            return False

        return bool(re.match(pattern, tx_hash.strip()))

    @staticmethod
    def validate_amount(amount: float, asset: str) -> tuple[bool, str]:
        """
        Validate transaction amount.

        Args:
            amount: Amount to validate
            asset: Asset code

        Returns:
            Tuple of (is_valid, error_message)
        """
        if amount <= 0:
            return False, "Amount must be positive"

        min_amount = CryptoValidators.MIN_AMOUNTS.get(asset, 0)
        if amount < min_amount:
            return False, f"Amount below minimum for {asset}: {min_amount}"

        max_amount = CryptoValidators.MAX_AMOUNTS.get(asset, float('inf'))
        if amount > max_amount:
            return False, f"Amount exceeds maximum for {asset}: {max_amount}"

        return True, ""

    @staticmethod
    def validate_asset(asset: str) -> bool:
        """
        Validate asset code.

        Args:
            asset: Asset code to validate

        Returns:
            True if valid, False otherwise
        """
        valid_assets = [
            "BTC", "ETH", "LTC", "SOL",
            "USDT-SOL", "USDT-ETH",
            "USDC-SOL", "USDC-ETH"
        ]
        return asset in valid_assets

    @staticmethod
    def sanitize_string(value: str, max_length: int = 500) -> str:
        """
        Sanitize string input to prevent injection.

        Args:
            value: String to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized string
        """
        if not value:
            return ""

        # Remove control characters
        sanitized = re.sub(r'[\x00-\x1F\x7F]', '', value)

        # Limit length
        sanitized = sanitized[:max_length]

        # Remove leading/trailing whitespace
        sanitized = sanitized.strip()

        return sanitized


class UserValidators:
    """Validators for user-related inputs"""

    @staticmethod
    def validate_discord_id(discord_id: str) -> bool:
        """
        Validate Discord ID format.

        Args:
            discord_id: Discord user ID

        Returns:
            True if valid, False otherwise
        """
        if not discord_id:
            return False

        # Discord IDs are 17-19 digit numbers
        return bool(re.match(r'^\d{17,19}$', discord_id))

    @staticmethod
    def validate_username(username: str) -> tuple[bool, str]:
        """
        Validate username.

        Args:
            username: Username to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not username:
            return False, "Username required"

        if len(username) < 3:
            return False, "Username too short (min 3 characters)"

        if len(username) > 32:
            return False, "Username too long (max 32 characters)"

        # Only alphanumeric, underscore, hyphen
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            return False, "Username can only contain letters, numbers, underscore, and hyphen"

        return True, ""


class RateLimitValidators:
    """Validators for rate limiting checks"""

    # Rate limit tiers
    RATE_LIMITS = {
        "api_general": {"requests": 100, "window": 60},  # 100 per minute
        "api_auth": {"requests": 10, "window": 60},  # 10 per minute
        "wallet_operations": {"requests": 20, "window": 60},  # 20 per minute
        "swap_operations": {"requests": 10, "window": 60},  # 10 per minute
        "exchange_creation": {"requests": 5, "window": 60},  # 5 per minute
        "admin_operations": {"requests": 50, "window": 60},  # 50 per minute
    }

    @staticmethod
    def get_rate_limit(operation: str) -> dict:
        """
        Get rate limit for operation.

        Args:
            operation: Operation type

        Returns:
            Dict with requests and window
        """
        return RateLimitValidators.RATE_LIMITS.get(
            operation,
            {"requests": 100, "window": 60}  # Default
        )


def validate_pagination(offset: int, limit: int) -> tuple[int, int]:
    """
    Validate and sanitize pagination parameters.

    Args:
        offset: Offset for pagination
        limit: Limit for pagination

    Returns:
        Tuple of (validated_offset, validated_limit)
    """
    # Ensure positive values
    offset = max(0, offset)

    # Limit max results
    limit = max(1, min(limit, 100))

    return offset, limit
