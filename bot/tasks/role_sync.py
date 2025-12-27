"""
Role Sync Task - Syncs Discord server roles to database
Runs on startup and every 3 hours
"""

import discord
import asyncio
import logging
from datetime import datetime
from typing import Optional

from api.client import APIClient

logger = logging.getLogger(__name__)


class RoleSyncTask:
    """Background task that syncs all guild members' roles to the database"""

    def __init__(self, bot: discord.Bot, api: APIClient, bot_config):
        self.bot = bot
        self.api = api
        self.config = bot_config
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.sync_interval = 3 * 60 * 60  # 3 hours in seconds

    def start(self):
        """Start the background task"""
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._sync_loop())
            logger.info("Role sync task started")

    def stop(self):
        """Stop the background task"""
        self.running = False
        if self.task:
            self.task.cancel()
        logger.info("Role sync task stopped")

    async def _sync_loop(self):
        """Main loop that syncs roles periodically"""
        await self.bot.wait_until_ready()

        while self.running:
            try:
                await self._sync_all_roles()

                # Wait for 3 hours before next sync
                await asyncio.sleep(self.sync_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in role sync loop: {e}", exc_info=True)
                # Wait a bit before retrying on error
                await asyncio.sleep(60)

    async def _sync_all_roles(self):
        """Sync all guild members' roles to the database"""
        try:
            guild = self.bot.get_guild(self.config.DISCORD_GUILD_ID)
            if not guild:
                logger.error(f"Could not find guild with ID {self.config.DISCORD_GUILD_ID}")
                return

            logger.info(f"🔄 Starting role sync for {guild.name} ({guild.member_count} members)...")

            synced = 0
            failed = 0

            # Sync roles for all guild members
            for member in guild.members:
                try:
                    # Skip bots
                    if member.bot:
                        continue

                    # Get role IDs and names (exclude @everyone role)
                    roles = [role for role in member.roles if role.id != guild.id]
                    role_ids = [role.id for role in roles]
                    role_names = [role.name for role in roles]

                    # Sync to database via API
                    await self.api.post(
                        "/api/v1/users/sync-roles",
                        data={
                            "discord_id": str(member.id),
                            "role_ids": role_ids,
                            "role_names": role_names,
                            "username": member.name,
                            "discriminator": member.discriminator,
                            "global_name": member.global_name
                        },
                        discord_user_id="SYSTEM"  # System sync
                    )

                    synced += 1

                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to sync roles for user {member.id}: {e}")

            logger.info(f"✅ Role sync complete: {synced} users synced, {failed} failed")

        except Exception as e:
            logger.error(f"Error syncing all roles: {e}", exc_info=True)
