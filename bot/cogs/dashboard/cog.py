"""
User Dashboard Cog for V4
Provides user stats, recovery codes, active tickets, and settings
"""

import logging

import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup

from config import Config
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)


class DashboardCog(commands.Cog):
    """User dashboard system"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        logger.info("Dashboard cog loaded")

    @commands.Cog.listener()
    async def on_ready(self):
        """Register persistent views on bot startup"""
        from cogs.dashboard.views.dashboard_panel import DashboardPanelView

        # Register persistent view
        self.bot.add_view(DashboardPanelView(self.bot))

        logger.info("Dashboard persistent views registered")


def setup(bot: discord.Bot):
    """Load the cog"""
    bot.add_cog(DashboardCog(bot))
