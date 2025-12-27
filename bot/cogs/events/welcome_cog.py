"""
Welcome Cog - Logs member joins to welcome channel
"""

import discord
from discord.ext import commands
import logging
from datetime import timezone

from config import Config
from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT

logger = logging.getLogger(__name__)


class WelcomeCog(commands.Cog):
    """Handles member join events and logs them to welcome channel"""

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.config = Config()
        logger.info("Welcome cog loaded")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Log member joins to welcome channel"""
        try:
            # Get welcome channel
            welcome_channel_id = self.config.welcome_channel
            if not welcome_channel_id:
                logger.warning("Welcome channel not configured")
                return

            welcome_channel = member.guild.get_channel(welcome_channel_id)
            if not welcome_channel:
                logger.error(f"Welcome channel {welcome_channel_id} not found")
                return

            # Calculate account age
            account_created = member.created_at
            created_timestamp = int(account_created.timestamp())

            # Create welcome embed
            embed = create_themed_embed(
                title=f"Welcome {member.name}!",
                description=f"{member.mention} just joined the server!",
                color=PURPLE_GRADIENT
            )

            # Set member's avatar as thumbnail
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            else:
                embed.set_thumbnail(url=member.default_avatar.url)

            # Add account info
            embed.add_field(
                name="📅 Account Created",
                value=f"<t:{created_timestamp}:F>\n<t:{created_timestamp}:R>",
                inline=False
            )

            embed.add_field(
                name="👤 User ID",
                value=f"`{member.id}`",
                inline=False
            )

            embed.set_footer(text=f"Member #{member.guild.member_count}")

            # Send to welcome channel
            await welcome_channel.send(embed=embed)
            logger.info(f"Logged member join: {member.name} ({member.id})")

        except Exception as e:
            logger.error(f"Error logging member join: {e}", exc_info=True)
