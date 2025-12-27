"""
Tier Role Service - Assigns Discord roles based on customer tiers
Syncs customer tier roles from database to Discord server
"""

import logging
from typing import Dict, List, Optional
from bson import ObjectId
from datetime import datetime

from app.core.database import get_db_collection
from app.core.config import settings

logger = logging.getLogger(__name__)

# Tier role names (must match Discord server role names exactly)
TIER_ROLE_NAMES = {
    'Legend': '🌟 Legend',
    'Elite': '👑 Elite',
    'Diamond': '💠 Diamond',
    'Platinum': '💎 Platinum',
    'Gold': '🥇 Gold',
    'Silver': '🥈 Silver',
    'Bronze': '🥉 Bronze',
}


class TierRoleService:
    """Service for syncing customer tier roles to Discord"""

    @staticmethod
    async def sync_all_tier_roles() -> Dict:
        """
        Sync all customer tier roles to Discord.
        Called by Discord bot on startup and periodically.

        Returns:
            Dict with sync results
        """
        try:
            logger.info("Starting customer tier role sync...")

            stats_db = await get_db_collection("user_statistics")
            users_db = await get_db_collection("users")

            # Get all users with customer tiers
            cursor = stats_db.find({
                "customer_tier": {"$ne": None, "$exists": True}
            })

            users_with_tiers = await cursor.to_list(length=10000)

            logger.info(f"Found {len(users_with_tiers)} users with customer tiers")

            # Build sync list
            role_assignments = []
            for stats in users_with_tiers:
                user = await users_db.find_one({"_id": stats["user_id"]})
                if not user:
                    continue

                role_assignments.append({
                    "discord_id": user["discord_id"],
                    "username": user.get("username", "Unknown"),
                    "tier": stats["customer_tier"],
                    "tier_role": stats.get("customer_tier_role", TIER_ROLE_NAMES.get(stats["customer_tier"])),
                    "vouch_volume": stats.get("vouch_volume_usd", 0.0)
                })

            logger.info(f"Tier role sync prepared: {len(role_assignments)} users to sync")

            return {
                "success": True,
                "total_users": len(role_assignments),
                "role_assignments": role_assignments,
                "sync_time": datetime.utcnow()
            }

        except Exception as e:
            logger.error(f"Failed to sync tier roles: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    async def get_user_tier(discord_id: str) -> Optional[Dict]:
        """
        Get customer tier for a specific user.

        Args:
            discord_id: Discord user ID

        Returns:
            Dict with tier info or None
        """
        try:
            users_db = await get_db_collection("users")
            stats_db = await get_db_collection("user_statistics")

            # Find user
            user = await users_db.find_one({"discord_id": discord_id})
            if not user:
                return None

            # Get stats
            stats = await stats_db.find_one({"user_id": user["_id"]})
            if not stats or not stats.get("customer_tier"):
                return None

            return {
                "discord_id": discord_id,
                "tier": stats["customer_tier"],
                "tier_role": stats.get("customer_tier_role", TIER_ROLE_NAMES.get(stats["customer_tier"])),
                "vouch_volume": stats.get("vouch_volume_usd", 0.0),
                "vouch_count": stats.get("vouch_count", 0)
            }

        except Exception as e:
            logger.error(f"Failed to get user tier: {e}", exc_info=True)
            return None

    @staticmethod
    async def update_tier_for_user(discord_id: str, new_tier: str, new_volume: float) -> Dict:
        """
        Manually update tier for a user.
        Useful for admin overrides.

        Args:
            discord_id: Discord user ID
            new_tier: New tier name (Legend, Elite, etc.)
            new_volume: New vouch volume in USD

        Returns:
            Dict with update result
        """
        try:
            users_db = await get_db_collection("users")
            stats_db = await get_db_collection("user_statistics")

            # Validate tier
            if new_tier not in TIER_ROLE_NAMES:
                return {
                    "success": False,
                    "error": f"Invalid tier: {new_tier}"
                }

            # Find user
            user = await users_db.find_one({"discord_id": discord_id})
            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }

            # Update stats
            await stats_db.update_one(
                {"user_id": user["_id"]},
                {
                    "$set": {
                        "customer_tier": new_tier,
                        "customer_tier_role": TIER_ROLE_NAMES[new_tier],
                        "vouch_volume_usd": new_volume,
                        "updated_at": datetime.utcnow()
                    }
                },
                upsert=True
            )

            logger.info(f"Updated tier for user {discord_id}: {new_tier} (${new_volume:,.2f})")

            return {
                "success": True,
                "discord_id": discord_id,
                "tier": new_tier,
                "tier_role": TIER_ROLE_NAMES[new_tier],
                "vouch_volume": new_volume
            }

        except Exception as e:
            logger.error(f"Failed to update user tier: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    async def get_tier_distribution() -> Dict:
        """
        Get distribution of users across tiers.

        Returns:
            Dict with tier counts
        """
        try:
            stats_db = await get_db_collection("user_statistics")

            distribution = {}
            for tier in TIER_ROLE_NAMES.keys():
                count = await stats_db.count_documents({"customer_tier": tier})
                distribution[tier] = count

            # Count users with no tier
            no_tier = await stats_db.count_documents({
                "$or": [
                    {"customer_tier": None},
                    {"customer_tier": {"$exists": False}}
                ]
            })

            return {
                "success": True,
                "distribution": distribution,
                "no_tier": no_tier,
                "total": sum(distribution.values()) + no_tier
            }

        except Exception as e:
            logger.error(f"Failed to get tier distribution: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    async def remove_tier_from_user(discord_id: str) -> Dict:
        """
        Remove tier from a user (admin action).

        Args:
            discord_id: Discord user ID

        Returns:
            Dict with removal result
        """
        try:
            users_db = await get_db_collection("users")
            stats_db = await get_db_collection("user_statistics")

            # Find user
            user = await users_db.find_one({"discord_id": discord_id})
            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }

            # Remove tier fields
            await stats_db.update_one(
                {"user_id": user["_id"]},
                {
                    "$unset": {
                        "customer_tier": "",
                        "customer_tier_role": ""
                    },
                    "$set": {
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.info(f"Removed tier from user {discord_id}")

            return {
                "success": True,
                "discord_id": discord_id,
                "message": "Tier removed"
            }

        except Exception as e:
            logger.error(f"Failed to remove user tier: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
