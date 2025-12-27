"""
Key Reveal Service - Secure private key reveal with rate limiting

Provides controlled access to private keys with:
- Hourly and daily rate limits
- Time-limited reveal windows
- Audit logging
- IP tracking
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.database import get_database
from app.services.exchanger_deposit_service import ExchangerDepositService

logger = logging.getLogger(__name__)


class KeyRevealService:
    """Service for secure private key reveals"""

    # Rate limits
    MAX_HOURLY_REVEALS = 5
    MAX_DAILY_REVEALS = 20
    REVEAL_WINDOW_SECONDS = 300  # 5 minutes

    @staticmethod
    async def request_key_reveal(
        user_id: str,
        asset: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> tuple[bool, str, Optional[Dict]]:
        """
        Request to reveal a private key with rate limiting.

        Args:
            user_id: User requesting reveal
            asset: Asset for which to reveal key
            ip_address: IP address of requester
            user_agent: User agent string

        Returns:
            Tuple of (success, message, reveal_data)
            reveal_data contains: private_key, expires_at, remaining_hourly, remaining_daily
        """
        try:
            db = get_database()

            # Check if user has exchanger deposit for this asset
            deposit = await ExchangerDepositService.get_deposit_wallet(user_id, asset)
            if not deposit:
                return False, f"No deposit wallet found for {asset}", None

            # Check if private key exists
            encrypted_key = deposit.get("encrypted_private_key")
            if not encrypted_key:
                return False, "Private key not available", None

            # Check rate limits
            can_reveal, hourly_remaining, daily_remaining = await KeyRevealService._check_rate_limits(user_id)

            if not can_reveal:
                return False, f"Rate limit exceeded. Try again later.", None

            # Decrypt private key
            try:
                fernet = Fernet(settings.ENCRYPTION_KEY.encode())
                private_key = fernet.decrypt(encrypted_key.encode()).decode()
            except Exception as e:
                logger.error(f"Failed to decrypt private key: {e}")
                return False, "Failed to decrypt private key", None

            # Create reveal record
            expires_at = datetime.utcnow() + timedelta(seconds=KeyRevealService.REVEAL_WINDOW_SECONDS)

            reveal_record = {
                "user_id": user_id,
                "asset": asset,
                "revealed_at": datetime.utcnow(),
                "expires_at": expires_at,
                "ip_address": ip_address,
                "user_agent": user_agent
            }

            await db.key_reveals.insert_one(reveal_record)

            # Log security event
            await KeyRevealService._log_key_reveal(
                user_id=user_id,
                asset=asset,
                ip_address=ip_address
            )

            logger.info(f"Private key revealed for user {user_id}, asset {asset}")

            return True, "Private key revealed successfully", {
                "private_key": private_key,
                "expires_at": expires_at,
                "reveal_window_seconds": KeyRevealService.REVEAL_WINDOW_SECONDS,
                "remaining_hourly": hourly_remaining - 1,
                "remaining_daily": daily_remaining - 1
            }

        except Exception as e:
            logger.error(f"Failed to reveal private key: {e}")
            return False, f"Failed to reveal key: {str(e)}", None

    @staticmethod
    async def _check_rate_limits(user_id: str) -> tuple[bool, int, int]:
        """
        Check if user has exceeded rate limits.

        Args:
            user_id: User ID

        Returns:
            Tuple of (can_reveal, hourly_remaining, daily_remaining)
        """
        try:
            db = get_database()
            now = datetime.utcnow()

            # Check hourly limit
            hourly_cutoff = now - timedelta(hours=1)
            hourly_count = await db.key_reveals.count_documents({
                "user_id": user_id,
                "revealed_at": {"$gte": hourly_cutoff}
            })

            if hourly_count >= KeyRevealService.MAX_HOURLY_REVEALS:
                return False, 0, 0

            # Check daily limit
            daily_cutoff = now - timedelta(days=1)
            daily_count = await db.key_reveals.count_documents({
                "user_id": user_id,
                "revealed_at": {"$gte": daily_cutoff}
            })

            if daily_count >= KeyRevealService.MAX_DAILY_REVEALS:
                return False, KeyRevealService.MAX_HOURLY_REVEALS - hourly_count, 0

            hourly_remaining = KeyRevealService.MAX_HOURLY_REVEALS - hourly_count
            daily_remaining = KeyRevealService.MAX_DAILY_REVEALS - daily_count

            return True, hourly_remaining, daily_remaining

        except Exception as e:
            logger.error(f"Failed to check rate limits: {e}")
            # Fail secure - deny if we can't check
            return False, 0, 0

    @staticmethod
    async def get_reveal_limits(user_id: str) -> Dict:
        """
        Get current reveal limits for user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with limit info
        """
        try:
            db = get_database()
            now = datetime.utcnow()

            # Count hourly reveals
            hourly_cutoff = now - timedelta(hours=1)
            hourly_count = await db.key_reveals.count_documents({
                "user_id": user_id,
                "revealed_at": {"$gte": hourly_cutoff}
            })

            # Count daily reveals
            daily_cutoff = now - timedelta(days=1)
            daily_count = await db.key_reveals.count_documents({
                "user_id": user_id,
                "revealed_at": {"$gte": daily_cutoff}
            })

            return {
                "max_hourly": KeyRevealService.MAX_HOURLY_REVEALS,
                "max_daily": KeyRevealService.MAX_DAILY_REVEALS,
                "hourly_used": hourly_count,
                "daily_used": daily_count,
                "hourly_remaining": max(0, KeyRevealService.MAX_HOURLY_REVEALS - hourly_count),
                "daily_remaining": max(0, KeyRevealService.MAX_DAILY_REVEALS - daily_count),
                "reveal_window_seconds": KeyRevealService.REVEAL_WINDOW_SECONDS
            }

        except Exception as e:
            logger.error(f"Failed to get reveal limits: {e}")
            return {
                "max_hourly": KeyRevealService.MAX_HOURLY_REVEALS,
                "max_daily": KeyRevealService.MAX_DAILY_REVEALS,
                "hourly_used": 0,
                "daily_used": 0,
                "hourly_remaining": KeyRevealService.MAX_HOURLY_REVEALS,
                "daily_remaining": KeyRevealService.MAX_DAILY_REVEALS,
                "reveal_window_seconds": KeyRevealService.REVEAL_WINDOW_SECONDS
            }

    @staticmethod
    async def get_reveal_history(user_id: str, limit: int = 20) -> list:
        """
        Get user's key reveal history.

        Args:
            user_id: User ID
            limit: Maximum number of records

        Returns:
            List of reveal records (without keys)
        """
        try:
            db = get_database()

            cursor = db.key_reveals.find(
                {"user_id": user_id},
                {"private_key": 0}  # Exclude actual key
            ).sort("revealed_at", -1).limit(limit)

            history = await cursor.to_list(length=limit)

            # Convert ObjectId to string
            for record in history:
                record["_id"] = str(record["_id"])

            return history

        except Exception as e:
            logger.error(f"Failed to get reveal history: {e}")
            return []

    @staticmethod
    async def _log_key_reveal(
        user_id: str,
        asset: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Log key reveal event for security audit.

        Args:
            user_id: User ID
            asset: Asset
            ip_address: IP address
        """
        try:
            db = get_database()

            await db.security_logs.insert_one({
                "event_type": "key_reveal",
                "user_id": user_id,
                "asset": asset,
                "ip_address": ip_address,
                "timestamp": datetime.utcnow(),
                "severity": "high"
            })

        except Exception as e:
            logger.error(f"Failed to log key reveal: {e}")
            # Don't fail the operation if logging fails

    @staticmethod
    async def cleanup_expired_reveals() -> int:
        """
        Clean up expired reveal records (older than 7 days).
        Should be run as a background job.

        Returns:
            Number of records deleted
        """
        try:
            db = get_database()
            cutoff = datetime.utcnow() - timedelta(days=7)

            result = await db.key_reveals.delete_many({
                "revealed_at": {"$lt": cutoff}
            })

            logger.info(f"Cleaned up {result.deleted_count} expired key reveal records")
            return result.deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired reveals: {e}")
            return 0
