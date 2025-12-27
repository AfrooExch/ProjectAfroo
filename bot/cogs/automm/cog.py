"""
AutoMM Escrow Cog for V4
P2P escrow system for secure transactions between users
"""

import logging
import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
from config import Config
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)


class AutoMMCog(commands.Cog):
    """AutoMM P2P Escrow System"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        logger.info("AutoMM cog loaded")

    @commands.Cog.listener()
    async def on_ready(self):
        from cogs.automm.views.automm_panel import AutoMMPanelView
        self.bot.add_view(AutoMMPanelView(self.bot))
        logger.info("AutoMM persistent views registered")


def setup(bot: discord.Bot):
    bot.add_cog(AutoMMCog(bot))
