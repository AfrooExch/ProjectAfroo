"""
Milestone Service - User tier/achievement system
Grants Discord roles based on total exchange volume milestones
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database import get_db_collection

logger = logging.getLogger(__name__)


class MilestoneService:
    """Service for milestone/tier management"""

    # Milestone tiers from V3 config.json
    # Based on total USD volume traded
    MILESTONES = {
        "tier1": {
            "name": "Bronze Trader",
            "threshold": 500.0,
            "role_name": "Bronze Trader",
            "emoji": "🥉",
            "color": 0xCD7F32  # Bronze color
        },
        "tier2": {
            "name": "Silver Trader",
            "threshold": 2500.0,
            "role_name": "Silver Trader",
            "emoji": "🥈",
            "color": 0xC0C0C0  # Silver color
        },
        "tier3": {
            "name": "Gold Trader",
            "threshold": 5000.0,
            "role_name": "Gold Trader",
            "emoji": "🥇",
            "color": 0xFFD700  # Gold color
        },
        "tier4": {
            "name": "Platinum Trader",
            "threshold": 10000.0,
            "role_name": "Platinum Trader",
            "emoji": "💎",
            "color": 0xE5E4E2  # Platinum color
        },
        "tier5": {
            "name": "Diamond Trader",
            "threshold": 25000.0,
            "role_name": "Diamond Trader",
            "emoji": "💠",
            "color": 0xB9F2FF  # Diamond color
        },
        "tier6": {
            "name": "Elite Trader",
            "threshold": 50000.0,
            "role_name": "Elite Trader",
            "emoji": "👑",
            "color": 0xFFD700  # Gold color
        }
    }

    @staticmethod
    async def check_and_grant_milestones(user_id: str) -> List[Dict]:
        """
        Check if user has reached any new milestones and grant them.

        Called after each completed exchange.

        Args:
            user_id: User ID to check

        Returns:
            List of newly earned milestones
        """
        try:
            # Get user statistics
            stats_db = await get_db_collection("user_statistics")
            user_stats = await stats_db.find_one({"user_id": ObjectId(user_id)})

            if not user_stats:
                logger.warning(f"No statistics found for user {user_id}")
                return []

            total_volume_usd = user_stats.get("total_volume_usd", 0.0)

            # Get current milestones from database
            current_milestones = user_stats.get("milestones_earned", [])

            # Check which milestones should be earned
            newly_earned = []

            for tier_id, tier_info in MilestoneService.MILESTONES.items():
                threshold = tier_info["threshold"]

                # Check if user has reached threshold and hasn't earned it yet
                if total_volume_usd >= threshold and tier_id not in current_milestones:
                    # Grant milestone
                    success = await MilestoneService._grant_milestone(
                        user_id=user_id,
                        tier_id=tier_id,
                        tier_info=tier_info,
                        current_volume=total_volume_usd
                    )

                    if success:
                        newly_earned.append({
                            "tier_id": tier_id,
                            "name": tier_info["name"],
                            "threshold": threshold,
                            "emoji": tier_info["emoji"],
                            "role_name": tier_info["role_name"]
                        })

            return newly_earned

        except Exception as e:
            logger.error(f"Error checking milestones for user {user_id}: {e}", exc_info=True)
            return []

    @staticmethod
    async def _grant_milestone(
        user_id: str,
        tier_id: str,
        tier_info: Dict,
        current_volume: float
    ) -> bool:
        """Grant milestone to user"""
        try:
            stats_db = await get_db_collection("user_statistics")

            # Update user statistics with new milestone
            result = await stats_db.update_one(
                {"user_id": ObjectId(user_id)},
                {
                    "$addToSet": {"milestones_earned": tier_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            if result.modified_count > 0:
                logger.info(
                    f"Milestone granted: User {user_id} earned {tier_info['name']} "
                    f"(${current_volume:.2f} volume)"
                )

                # Record milestone achievement
                await MilestoneService._record_achievement(
                    user_id=user_id,
                    tier_id=tier_id,
                    tier_info=tier_info,
                    volume_at_achievement=current_volume
                )

                # TODO: Grant Discord role
                # This will be done by Discord bot via webhook or API call
                await MilestoneService._request_discord_role_grant(
                    user_id=user_id,
                    role_name=tier_info["role_name"]
                )

                return True

            return False

        except Exception as e:
            logger.error(f"Error granting milestone: {e}", exc_info=True)
            return False

    @staticmethod
    async def _record_achievement(
        user_id: str,
        tier_id: str,
        tier_info: Dict,
        volume_at_achievement: float
    ):
        """Record milestone achievement in dedicated collection"""
        try:
            achievements_db = await get_db_collection("user_achievements")

            achievement_dict = {
                "user_id": ObjectId(user_id),
                "achievement_type": "milestone",
                "tier_id": tier_id,
                "tier_name": tier_info["name"],
                "threshold": tier_info["threshold"],
                "volume_at_achievement": volume_at_achievement,
                "earned_at": datetime.utcnow()
            }

            await achievements_db.insert_one(achievement_dict)

            logger.info(f"Recorded achievement: {tier_info['name']} for user {user_id}")

        except Exception as e:
            logger.error(f"Error recording achievement: {e}", exc_info=True)

    @staticmethod
    async def _request_discord_role_grant(user_id: str, role_name: str):
        """
        Request Discord bot to grant role to user.

        This can be implemented in multiple ways:
        1. Webhook to Discord bot
        2. RabbitMQ/Redis queue
        3. Database table that bot polls
        4. Direct Discord API call

        For now, we'll use a simple database table approach.
        """
        try:
            pending_roles_db = await get_db_collection("pending_discord_role_grants")

            role_grant_dict = {
                "user_id": ObjectId(user_id),
                "role_name": role_name,
                "reason": "milestone_achievement",
                "status": "pending",
                "created_at": datetime.utcnow(),
                "processed_at": None
            }

            await pending_roles_db.insert_one(role_grant_dict)

            logger.info(f"Requested Discord role grant: {role_name} for user {user_id}")

        except Exception as e:
            logger.error(f"Error requesting Discord role grant: {e}", exc_info=True)

    @staticmethod
    async def get_user_milestones(user_id: str) -> Dict:
        """
        Get user's milestone progress.

        Args:
            user_id: User ID

        Returns:
            Dict with milestone progress
        """
        try:
            stats_db = await get_db_collection("user_statistics")
            user_stats = await stats_db.find_one({"user_id": ObjectId(user_id)})

            if not user_stats:
                return {
                    "total_volume_usd": 0.0,
                    "milestones_earned": [],
                    "current_tier": None,
                    "next_tier": None,
                    "progress_to_next": 0.0
                }

            total_volume = user_stats.get("total_volume_usd", 0.0)
            earned_milestones = user_stats.get("milestones_earned", [])

            # Find current and next tier
            current_tier = None
            next_tier = None

            sorted_tiers = sorted(
                MilestoneService.MILESTONES.items(),
                key=lambda x: x[1]["threshold"]
            )

            for tier_id, tier_info in sorted_tiers:
                if tier_id in earned_milestones:
                    current_tier = {
                        "tier_id": tier_id,
                        "name": tier_info["name"],
                        "threshold": tier_info["threshold"],
                        "emoji": tier_info["emoji"]
                    }
                elif next_tier is None and total_volume < tier_info["threshold"]:
                    next_tier = {
                        "tier_id": tier_id,
                        "name": tier_info["name"],
                        "threshold": tier_info["threshold"],
                        "emoji": tier_info["emoji"],
                        "progress": (total_volume / tier_info["threshold"]) * 100
                    }

            return {
                "total_volume_usd": total_volume,
                "milestones_earned": [
                    {
                        "tier_id": tid,
                        "name": MilestoneService.MILESTONES[tid]["name"],
                        "threshold": MilestoneService.MILESTONES[tid]["threshold"],
                        "emoji": MilestoneService.MILESTONES[tid]["emoji"]
                    }
                    for tid in earned_milestones
                    if tid in MilestoneService.MILESTONES
                ],
                "current_tier": current_tier,
                "next_tier": next_tier,
                "all_tiers": [
                    {
                        "tier_id": tid,
                        "name": tinfo["name"],
                        "threshold": tinfo["threshold"],
                        "emoji": tinfo["emoji"],
                        "earned": tid in earned_milestones
                    }
                    for tid, tinfo in sorted_tiers
                ]
            }

        except Exception as e:
            logger.error(f"Error getting user milestones: {e}", exc_info=True)
            return {}

    @staticmethod
    async def get_milestone_leaderboard(limit: int = 100) -> List[Dict]:
        """
        Get leaderboard of users by milestone tier.

        Args:
            limit: Max number of users to return

        Returns:
            List of users with their highest tier
        """
        try:
            stats_db = await get_db_collection("user_statistics")

            # Find users with milestones
            cursor = stats_db.find(
                {"milestones_earned": {"$exists": True, "$ne": []}},
                {"user_id": 1, "milestones_earned": 1, "total_volume_usd": 1}
            ).sort("total_volume_usd", -1).limit(limit)

            leaderboard = []

            async for user_stat in cursor:
                earned_milestones = user_stat.get("milestones_earned", [])

                # Find highest tier
                highest_tier = None
                highest_threshold = 0

                for tier_id in earned_milestones:
                    if tier_id in MilestoneService.MILESTONES:
                        tier_info = MilestoneService.MILESTONES[tier_id]
                        if tier_info["threshold"] > highest_threshold:
                            highest_threshold = tier_info["threshold"]
                            highest_tier = {
                                "tier_id": tier_id,
                                "name": tier_info["name"],
                                "emoji": tier_info["emoji"]
                            }

                if highest_tier:
                    leaderboard.append({
                        "user_id": str(user_stat["user_id"]),
                        "total_volume_usd": user_stat.get("total_volume_usd", 0.0),
                        "highest_tier": highest_tier,
                        "milestone_count": len(earned_milestones)
                    })

            return leaderboard

        except Exception as e:
            logger.error(f"Error getting milestone leaderboard: {e}", exc_info=True)
            return []

    @staticmethod
    async def send_congratulations_message(user_id: str, milestone: Dict):
        """
        Send congratulations message to user.

        This should be handled by Discord bot, but we can create a notification record.
        """
        try:
            notifications_db = await get_db_collection("user_notifications")

            notification_dict = {
                "user_id": ObjectId(user_id),
                "type": "milestone_achieved",
                "title": f"Milestone Achieved: {milestone['name']}!",
                "message": (
                    f"Congratulations! You've reached the {milestone['name']} milestone "
                    f"with over ${milestone['threshold']:.0f} in total volume!\n\n"
                    f"You've been granted the **{milestone['role_name']}** role!"
                ),
                "data": milestone,
                "read": False,
                "created_at": datetime.utcnow()
            }

            await notifications_db.insert_one(notification_dict)

            logger.info(f"Created congratulations notification for user {user_id}")

        except Exception as e:
            logger.error(f"Error sending congratulations message: {e}", exc_info=True)
