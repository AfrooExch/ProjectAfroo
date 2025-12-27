"""
Premade Messages Cog
Allows exchangers to save and quickly send premade messages
"""

import discord
from discord.ext import commands
import logging

from config import config
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT
from cogs.premade.views import PremadePanelView

logger = logging.getLogger(__name__)


class PremadeCog(commands.Cog):
    """
    Premade Messages Cog

    Allows exchangers to:
    - Create premade messages (crypto wallets, TOS, PayPal info, etc.)
    - Send premade messages quickly with a dropdown
    - Manage and delete premade messages
    """

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        logger.info("Premade cog loaded")

    @discord.slash_command(
        name="premade",
        description="[EXCHANGER] Manage and send premade messages"
    )
    async def premade(self, ctx: discord.ApplicationContext):
        """Show premade panel"""
        # Check if user is exchanger or admin
        if not config.is_exchanger(ctx.author) and not config.is_admin(ctx.author):
            embed = create_themed_embed(
                title="Permission Denied",
                description="This command is only available to Exchangers.",
                color=PURPLE_GRADIENT
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        # Show premade panel
        view = PremadePanelView()
        embed = create_themed_embed(
            title="📝 Premade Messages",
            description=(
                "Manage your premade messages for quick responses.\n\n"
                "**Create Premade:** Save a new premade message (wallet addresses, TOS, PayPal, etc.)\n"
                "**Send Premade:** Send a premade message to this channel\n"
                "**Manage Premades:** View and delete your premades"
            ),
            color=PURPLE_GRADIENT
        )
        embed.add_field(
            name="💡 Use Cases",
            value="• Crypto wallet addresses\n• Custom TOS\n• Payment info (PayPal, CashApp)\n• Frequently sent messages",
            inline=False
        )

        await ctx.respond(embed=embed, view=view, ephemeral=True)


def setup(bot: discord.Bot):
    """Required function to load cog"""
    bot.add_cog(PremadeCog(bot))
