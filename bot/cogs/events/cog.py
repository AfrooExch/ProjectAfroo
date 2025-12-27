"""
Events Cog - Discord event handlers
Entry point for events module
"""

import discord
from discord.ext import commands
import logging

from cogs.events.role_sync_cog import RoleSyncCog
from cogs.events.welcome_cog import WelcomeCog
from cogs.events.tier_sync_cog import TierSyncCog

logger = logging.getLogger(__name__)


def setup(bot: discord.Bot):
    """
    Required function to load all event cogs

    Loads:
        - Role Sync Cog
        - Welcome Cog
        - Tier Sync Cog
    """
    # Add Role Sync Cog
    bot.add_cog(RoleSyncCog(bot))

    # Add Welcome Cog
    bot.add_cog(WelcomeCog(bot))

    # Add Tier Sync Cog
    bot.add_cog(TierSyncCog(bot))

    logger.info("✅ Events module loaded (with Tier Sync)")
