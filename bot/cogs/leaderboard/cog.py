"""
Leaderboard Cog for V4
Displays top exchangers, customers, swaps, and wallet balances
"""

import logging
import asyncio
from typing import Optional

import discord
from discord.ext import commands, tasks
from discord.commands import SlashCommandGroup

from config import Config
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)


class LeaderboardCog(commands.Cog):
    """Leaderboard system"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.leaderboard_message: Optional[discord.Message] = None
        self.leaderboard_channel_id: Optional[int] = None
        logger.info("Leaderboard cog loaded")

    @commands.Cog.listener()
    async def on_ready(self):
        """Register persistent views on bot startup"""
        from cogs.leaderboard.views.leaderboard_view import LeaderboardView

        # Register persistent view
        self.bot.add_view(LeaderboardView())

        logger.info("Leaderboard persistent views registered")


def setup(bot: discord.Bot):
    """Load the cog"""
    bot.add_cog(LeaderboardCog(bot))
