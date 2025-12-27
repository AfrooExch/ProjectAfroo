"""
Application System Cog for V4
Handles exchanger applications and approval process
"""

import logging

import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup

from config import Config
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)


class ApplicationsCog(commands.Cog):
    """Exchanger application system"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        logger.info("Applications cog loaded")

    @commands.Cog.listener()
    async def on_ready(self):
        """Register persistent views on bot startup"""
        from cogs.applications.views.application_panel import ApplicationPanelView

        # Register persistent view
        self.bot.add_view(ApplicationPanelView(self.bot))

        logger.info("Applications persistent views registered")


def setup(bot: discord.Bot):
    """Load the cog"""
    bot.add_cog(ApplicationsCog(bot))
