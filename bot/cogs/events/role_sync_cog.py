"""
Role Sync Cog - Syncs Discord roles to API database
Ensures API always has up-to-date permission information
"""

import discord
from discord.ext import commands
import logging

from api.client import APIClient
from api.errors import APIError

logger = logging.getLogger(__name__)


class RoleSyncCog(commands.Cog):
    """
    Syncs Discord roles to API for permission validation

    Events:
        - on_member_update: Sync roles when they change
        - on_member_join: Sync roles when member joins
    """

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.api: APIClient = bot.api_client
        logger.info("✅ Role sync system initialized")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """
        Sync roles when member's roles change

        This ensures the API has up-to-date permission information
        """
        # Check if roles changed
        if before.roles != after.roles:
            try:
                # Extract role IDs
                role_ids = [role.id for role in after.roles]

                # Sync to API
                await self.api.post(
                    "/api/v1/users/sync-roles",
                    data={
                        "discord_id": str(after.id),
                        "role_ids": role_ids,
                        "username": after.name,
                        "discriminator": after.discriminator,
                        "global_name": after.global_name if hasattr(after, 'global_name') else None
                    },
                    discord_user_id=str(after.id),
                    discord_roles=role_ids
                )

                logger.info(
                    f"✅ Synced roles for {after.name} "
                    f"({len(role_ids)} roles)"
                )

            except APIError as e:
                logger.error(
                    f"❌ Failed to sync roles for {after.name}: {e}",
                    exc_info=True
                )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Sync roles when member joins

        Creates user in database if they don't exist
        """
        try:
            # Extract role IDs
            role_ids = [role.id for role in member.roles]

            # Sync to API (will create user if doesn't exist)
            await self.api.post(
                "/api/v1/users/sync-roles",
                data={
                    "discord_id": str(member.id),
                    "role_ids": role_ids,
                    "username": member.name,
                    "discriminator": member.discriminator,
                    "global_name": member.global_name if hasattr(member, 'global_name') else None
                },
                discord_user_id=str(member.id),
                discord_roles=role_ids
            )

            logger.info(f"✅ Synced new member: {member.name}")

        except APIError as e:
            logger.error(
                f"❌ Failed to sync new member {member.name}: {e}",
                exc_info=True
            )

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Sync all members on bot startup (optional, can be resource-intensive)

        Only runs if bot is not already synced
        """
        if hasattr(self.bot, '_roles_synced'):
            return  # Already synced

        logger.info("🔄 Starting initial role sync...")

        try:
            guild = self.bot.guilds[0]  # Assuming single guild
            synced = 0
            failed = 0

            for member in guild.members:
                try:
                    role_ids = [role.id for role in member.roles]

                    await self.api.post(
                        "/api/v1/users/sync-roles",
                        data={
                            "discord_id": str(member.id),
                            "role_ids": role_ids,
                            "username": member.name,
                            "discriminator": member.discriminator,
                            "global_name": member.global_name if hasattr(member, 'global_name') else None
                        },
                        discord_user_id=str(member.id),
                        discord_roles=role_ids
                    )

                    synced += 1

                except APIError as e:
                    logger.warning(f"Failed to sync {member.name}: {e}")
                    failed += 1

            self.bot._roles_synced = True
            logger.info(
                f"✅ Initial role sync complete: "
                f"{synced} synced, {failed} failed"
            )

        except Exception as e:
            logger.error(f"❌ Initial role sync failed: {e}", exc_info=True)


def setup(bot: discord.Bot):
    """Required function to load cog"""
    bot.add_cog(RoleSyncCog(bot))
