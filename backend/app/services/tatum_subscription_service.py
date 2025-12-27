"""
Tatum Subscription Service - Manages blockchain address monitoring
Automatically creates and manages Tatum webhook subscriptions
"""

from typing import Optional, Dict, Tuple
from datetime import datetime
from bson import ObjectId
import logging
import httpx

from app.core.database import get_db_collection
from app.core.config import settings

logger = logging.getLogger(__name__)


class TatumSubscriptionService:
    """Service for managing Tatum webhook subscriptions"""

    # Blockchain type mapping for Tatum
    CHAIN_MAPPING = {
        "BTC": "bitcoin",
        "LTC": "litecoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "USDT-SOL": "solana",
        "USDT-ETH": "ethereum",
        "USDC-SOL": "solana",
        "USDC-ETH": "ethereum"
    }

    @staticmethod
    async def create_subscription(
        user_id: str,
        asset: str,
        address: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Create Tatum webhook subscription for address monitoring.

        Args:
            user_id: User ID
            asset: Asset code (BTC, ETH, etc.)
            address: Blockchain address to monitor

        Returns:
            Tuple of (success, message, subscription_id)
        """
        try:
            subscriptions_db = await get_db_collection("tatum_subscriptions")

            # Check if subscription already exists
            existing = await subscriptions_db.find_one({
                "user_id": ObjectId(user_id),
                "asset": asset,
                "address": address,
                "status": "active"
            })

            if existing:
                logger.info(
                    f"Subscription already exists: {existing['subscription_id']}"
                )
                return True, "Subscription already active", existing["subscription_id"]

            # Get chain type for Tatum
            chain = TatumSubscriptionService.CHAIN_MAPPING.get(asset)
            if not chain:
                return False, f"Asset {asset} not supported for subscriptions", None

            # Webhook URL
            webhook_url = f"{settings.TATUM_WEBHOOK_BASE_URL}/api/v1/webhooks/tatum"

            # Create subscription via Tatum API
            async with httpx.AsyncClient() as client:
                headers = {
                    "x-api-key": settings.TATUM_API_KEY,
                    "Content-Type": "application/json"
                }

                payload = {
                    "type": "ADDRESS_TRANSACTION",
                    "attr": {
                        "address": address,
                        "chain": chain,
                        "url": webhook_url
                    }
                }

                response = await client.post(
                    f"{settings.TATUM_API_URL}/v3/subscription",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    subscription_id = data.get("id")

                    if not subscription_id:
                        return False, "No subscription ID returned from Tatum", None

                    # Store subscription
                    await TatumSubscriptionService._store_subscription(
                        user_id=user_id,
                        asset=asset,
                        address=address,
                        subscription_id=subscription_id,
                        webhook_url=webhook_url
                    )

                    logger.info(
                        f"Created Tatum subscription: {subscription_id} "
                        f"for {asset} {address}"
                    )

                    return True, "Subscription created successfully", subscription_id

                elif response.status_code == 409:
                    # Subscription already exists in Tatum
                    # Extract subscription ID from error message if possible
                    error_data = response.json()
                    error_msg = error_data.get("message", "")

                    # Try to extract ID from error message
                    import re
                    match = re.search(r'already exists \(([^)]+)\)', error_msg)
                    if match:
                        subscription_id = match.group(1)

                        # Store it in our database
                        await TatumSubscriptionService._store_subscription(
                            user_id=user_id,
                            asset=asset,
                            address=address,
                            subscription_id=subscription_id,
                            webhook_url=webhook_url
                        )

                        return True, "Existing subscription registered", subscription_id

                    return False, "Subscription exists in Tatum but ID unknown", None

                else:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get("message", response.text)
                    logger.error(
                        f"Tatum subscription failed: {response.status_code} - {error_msg}"
                    )
                    return False, f"Tatum API error: {error_msg}", None

        except Exception as e:
            logger.error(f"Failed to create Tatum subscription: {e}", exc_info=True)
            return False, str(e), None

    @staticmethod
    async def _store_subscription(
        user_id: str,
        asset: str,
        address: str,
        subscription_id: str,
        webhook_url: str
    ):
        """Store subscription in database"""
        subscriptions_db = await get_db_collection("tatum_subscriptions")

        subscription_dict = {
            "user_id": ObjectId(user_id),
            "asset": asset,
            "address": address,
            "subscription_id": subscription_id,
            "webhook_url": webhook_url,
            "status": "active",
            "created_at": datetime.utcnow(),
            "last_checked": datetime.utcnow()
        }

        await subscriptions_db.insert_one(subscription_dict)

    @staticmethod
    async def cancel_subscription(subscription_id: str) -> Tuple[bool, str]:
        """
        Cancel Tatum subscription.

        Args:
            subscription_id: Tatum subscription ID

        Returns:
            Tuple of (success, message)
        """
        try:
            # Cancel in Tatum
            async with httpx.AsyncClient() as client:
                headers = {
                    "x-api-key": settings.TATUM_API_KEY
                }

                response = await client.delete(
                    f"{settings.TATUM_API_URL}/v3/subscription/{subscription_id}",
                    headers=headers,
                    timeout=30.0
                )

                if response.status_code in [200, 204]:
                    # Update database
                    subscriptions_db = await get_db_collection("tatum_subscriptions")
                    await subscriptions_db.update_one(
                        {"subscription_id": subscription_id},
                        {
                            "$set": {
                                "status": "cancelled",
                                "cancelled_at": datetime.utcnow()
                            }
                        }
                    )

                    logger.info(f"Cancelled Tatum subscription: {subscription_id}")
                    return True, "Subscription cancelled successfully"

                else:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get("message", response.text)
                    return False, f"Tatum API error: {error_msg}"

        except Exception as e:
            logger.error(f"Failed to cancel subscription: {e}", exc_info=True)
            return False, str(e)

    @staticmethod
    async def list_subscriptions(
        user_id: Optional[str] = None,
        asset: Optional[str] = None,
        status: str = "active"
    ) -> list:
        """
        List Tatum subscriptions.

        Args:
            user_id: Filter by user (optional)
            asset: Filter by asset (optional)
            status: Filter by status (default: active)

        Returns:
            List of subscription records
        """
        subscriptions_db = await get_db_collection("tatum_subscriptions")

        query = {"status": status}
        if user_id:
            query["user_id"] = ObjectId(user_id)
        if asset:
            query["asset"] = asset

        cursor = subscriptions_db.find(query).sort("created_at", -1)
        subscriptions = await cursor.to_list(length=1000)

        # Serialize ObjectIds
        for sub in subscriptions:
            sub["_id"] = str(sub["_id"])
            sub["user_id"] = str(sub["user_id"])

        return subscriptions

    @staticmethod
    async def get_subscription(subscription_id: str) -> Optional[dict]:
        """Get subscription by Tatum subscription ID"""
        subscriptions_db = await get_db_collection("tatum_subscriptions")

        subscription = await subscriptions_db.find_one({
            "subscription_id": subscription_id
        })

        if subscription:
            subscription["_id"] = str(subscription["_id"])
            subscription["user_id"] = str(subscription["user_id"])

        return subscription

    @staticmethod
    async def update_last_checked(subscription_id: str):
        """Update last checked timestamp for subscription"""
        subscriptions_db = await get_db_collection("tatum_subscriptions")

        await subscriptions_db.update_one(
            {"subscription_id": subscription_id},
            {"$set": {"last_checked": datetime.utcnow()}}
        )
