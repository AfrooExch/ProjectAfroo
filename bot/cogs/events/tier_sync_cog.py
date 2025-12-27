"""
Tier Sync Cog - Syncs customer tier roles from database to Discord
Automatically assigns tier roles based on vouch volume
"""

import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime
from typing import Dict, List

from api.client import APIClient
from api.errors import APIError

logger = logging.getLogger(__name__)


class TierSyncCog(commands.Cog):
    """
    Syncs customer tier roles from database to Discord server

    Features:
    - Automatic role assignment on bot startup
    - Periodic sync every 6 hours
    - Manual sync command for admins
    - Role cleanup (removes old tier roles)
    """

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.api: APIClient = bot.api_client
        self.tier_role_ids = {}  # Will be fetched from backend API
        self.tier_sync_task.start()
        logger.info("✅ Tier sync system initialized")

    def cog_unload(self):
        """Stop background task when cog unloads"""
        self.tier_sync_task.cancel()

    @tasks.loop(hours=6)
    async def tier_sync_task(self):
        """Background task to sync tier roles every 6 hours"""
        await self.sync_all_tiers()

    @tier_sync_task.before_loop
    async def before_tier_sync(self):
        """Wait for bot to be ready before starting sync"""
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        """Run initial tier sync on bot startup"""
        if hasattr(self.bot, '_tiers_synced'):
            return  # Already synced

        logger.info("🔄 Starting initial tier role sync...")

        try:
            # Run full tier sync
            result = await self.sync_all_tiers()

            self.bot._tiers_synced = True

            if result.get("success"):
                logger.info(
                    f"✅ Initial tier sync complete: "
                    f"{result.get('synced', 0)} roles assigned, "
                    f"{result.get('removed', 0)} roles removed, "
                    f"{result.get('failed', 0)} failed"
                )
            else:
                logger.error(f"❌ Initial tier sync failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"❌ Initial tier sync failed: {e}", exc_info=True)

    async def sync_all_tiers(self) -> Dict:
        """
        Sync all customer tier roles from database to Discord.

        Returns:
            Dict with sync results
        """
        try:
            # Get tier assignments from API
            response = await self.api.get(
                "/api/v1/admin/tiers/sync",
                discord_user_id="SYSTEM"
            )

            if not response.get("success"):
                logger.error(f"Failed to get tier assignments: {response.get('error')}")
                return {"success": False, "error": response.get("error")}

            role_assignments = response.get("role_assignments", [])
            # Get tier role IDs from backend (single source of truth)
            self.tier_role_ids = response.get("tier_role_ids", {})

            if not role_assignments:
                logger.info("No tier role assignments to sync")
                return {"success": True, "synced": 0, "removed": 0, "failed": 0}

            guild = self.bot.guilds[0]  # Assuming single guild
            if not guild:
                logger.error("No guild found")
                return {"success": False, "error": "No guild found"}

            # Get all tier roles from server by ID (fetched from backend)
            tier_role_map = {}
            for tier_name, role_id in self.tier_role_ids.items():
                role = guild.get_role(role_id)
                if role:
                    tier_role_map[tier_name] = role
                    logger.debug(f"Found tier role: {role.name} (ID: {role_id})")
                else:
                    logger.warning(f"Tier role not found in server: {tier_name} (ID: {role_id})")

            if not tier_role_map:
                logger.error("No tier roles found in Discord server. Please create the tier roles first.")
                return {"success": False, "error": "No tier roles found in Discord server"}

            synced = 0
            removed = 0
            failed = 0

            # Process each user
            for assignment in role_assignments:
                try:
                    discord_id = int(assignment["discord_id"])
                    tier = assignment["tier"]

                    # Get member
                    member = guild.get_member(discord_id)
                    if not member:
                        logger.debug(f"Member {discord_id} not found in server (may have left)")
                        continue

                    # Get target tier role
                    target_role = tier_role_map.get(tier)
                    if not target_role:
                        logger.warning(f"Tier role {tier} not found for user {discord_id}")
                        failed += 1
                        continue

                    # Get all tier roles currently assigned to member
                    current_tier_roles = [role for role in member.roles if role in tier_role_map.values()]

                    # Check if user already has correct tier
                    if target_role in current_tier_roles and len(current_tier_roles) == 1:
                        # Already has correct tier role
                        continue

                    # Remove all tier roles
                    for old_role in current_tier_roles:
                        if old_role != target_role:
                            try:
                                await member.remove_roles(old_role, reason="Tier update")
                                removed += 1
                                logger.info(f"Removed {old_role.name} from {member.name}")
                            except discord.Forbidden:
                                logger.error(f"Missing permissions to remove {old_role.name} from {member.name}")
                            except Exception as e:
                                logger.error(f"Failed to remove {old_role.name} from {member.name}: {e}")

                    # Add new tier role if not already assigned
                    if target_role not in member.roles:
                        try:
                            await member.add_roles(target_role, reason=f"Customer tier: {tier}")
                            synced += 1
                            logger.info(f"✅ Assigned {target_role.name} to {member.name} ({tier} - ${assignment.get('vouch_volume', 0):,.2f})")
                        except discord.Forbidden:
                            logger.error(f"Missing permissions to add {target_role.name} to {member.name}")
                            failed += 1
                        except Exception as e:
                            logger.error(f"Failed to add {target_role.name} to {member.name}: {e}")
                            failed += 1

                except ValueError:
                    logger.error(f"Invalid discord_id: {assignment.get('discord_id')}")
                    failed += 1
                except Exception as e:
                    logger.error(f"Failed to sync tier for {assignment.get('discord_id')}: {e}", exc_info=True)
                    failed += 1

            logger.info(f"🎉 Tier sync complete: {synced} assigned, {removed} removed, {failed} failed")

            return {
                "success": True,
                "synced": synced,
                "removed": removed,
                "failed": failed,
                "total_processed": len(role_assignments)
            }

        except APIError as e:
            logger.error(f"API error during tier sync: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Error syncing tiers: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def sync_user_tier(self, discord_id: str) -> Dict:
        """
        Sync tier role for a single user.

        Args:
            discord_id: Discord user ID

        Returns:
            Dict with sync result
        """
        try:
            # Get user's tier from API
            response = await self.api.get(
                f"/api/v1/admin/tiers/user/{discord_id}",
                discord_user_id="SYSTEM"
            )

            if not response.get("success") or not response.get("tier"):
                return {"success": False, "error": "User has no tier"}

            tier = response["tier"]

            # Fetch tier role IDs if not already loaded
            if not self.tier_role_ids:
                sync_response = await self.api.get(
                    "/api/v1/admin/tiers/sync",
                    discord_user_id="SYSTEM"
                )
                if sync_response.get("success"):
                    self.tier_role_ids = sync_response.get("tier_role_ids", {})

            tier_role_id = self.tier_role_ids.get(tier)

            if not tier_role_id:
                return {"success": False, "error": f"Invalid tier: {tier}"}

            guild = self.bot.guilds[0]
            member = guild.get_member(int(discord_id))

            if not member:
                return {"success": False, "error": "User not found in server"}

            # Get tier role
            tier_role = guild.get_role(tier_role_id)
            if not tier_role:
                return {"success": False, "error": f"Tier role not found: {tier} (ID: {tier_role_id})"}

            # Remove old tier roles
            all_tier_roles = [guild.get_role(role_id) for role_id in self.tier_role_ids.values()]
            all_tier_roles = [r for r in all_tier_roles if r]  # Remove None values

            for old_role in member.roles:
                if old_role in all_tier_roles and old_role != tier_role:
                    await member.remove_roles(old_role, reason="Tier update")

            # Add new tier role
            if tier_role not in member.roles:
                await member.add_roles(tier_role, reason=f"Customer tier: {tier}")

            logger.info(f"✅ Synced tier for {member.name}: {tier_role.name}")

            return {
                "success": True,
                "discord_id": discord_id,
                "tier": tier,
                "tier_role": tier_role.name
            }

        except Exception as e:
            logger.error(f"Failed to sync user tier: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


def setup(bot: discord.Bot):
    """Required function to load cog"""
    bot.add_cog(TierSyncCog(bot))
