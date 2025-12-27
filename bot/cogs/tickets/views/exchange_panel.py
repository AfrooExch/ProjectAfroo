"""
Exchange Panel View - Main exchange panel with start button
"""

import discord
import logging

from utils.view_manager import PersistentView
from utils.embeds import create_exchange_panel_embed, create_themed_embed
from utils.colors import PURPLE_GRADIENT, ERROR_RED
from utils.auth import get_user_context
from cogs.tickets.views.exchange_views import SendMethodSelector
from cogs.tickets.session_manager import ExchangeSessionManager

logger = logging.getLogger(__name__)


class ExchangePanelView(PersistentView):
    """Main exchange panel view with persistent button"""

    def __init__(self, bot: discord.Bot):
        super().__init__(bot)

    @discord.ui.button(
        label="🚀 Start Exchange",
        style=discord.ButtonStyle.primary,
        custom_id="start_exchange_button"
    )
    async def start_exchange(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Handle start exchange button click - initiates multi-step dropdown flow"""
        try:
            await interaction.response.defer(ephemeral=True)

            logger.info(f"Start exchange clicked by {interaction.user.name}")

            # Get user context
            user_id, roles = get_user_context(interaction)

            # Get API client from bot
            api = self.bot.api_client

            # Create session manager
            session_manager = ExchangeSessionManager()

            # Create or get session
            session = session_manager.get_or_create_session(user_id)

            # Start with send method selection
            embed = create_themed_embed(
                title="Create Exchange Ticket",
                description=(
                    "Welcome to Afroo Exchange!\n\n"
                    "Let's get started by selecting your **sending** payment method.\n\n"
                    "**Step 1 of 4:** Select Sending Method"
                ),
                color=PURPLE_GRADIENT
            )

            embed.set_footer(text="This process will guide you through 4 simple steps")

            view = SendMethodSelector(session_manager, api, bot=self.bot)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

            logger.info(f"User {user_id} started exchange ticket creation")

        except Exception as e:
            logger.error(f"Error starting exchange flow: {e}", exc_info=True)
            embed = create_themed_embed(
                title="Error",
                description="An error occurred while starting the exchange process. Please try again or contact support.",
                color=ERROR_RED
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def send_exchange_panel(channel: discord.TextChannel):
    """
    Send or update exchange panel in channel

    Args:
        channel: Channel to send panel to
    """
    embed = create_exchange_panel_embed()
    view = ExchangePanelView(channel.guild._state._get_client())

    # Try to find existing panel message
    async for message in channel.history(limit=50):
        if message.author.bot and message.embeds:
            # Check if this is the exchange panel
            if "AFROO EXCHANGE" in message.embeds[0].description:
                # Update existing message
                await message.edit(embed=embed, view=view)
                logger.info(f"Updated exchange panel in {channel.name}")
                return

    # No existing panel found, send new one
    await channel.send(embed=embed, view=view)
    logger.info(f"Sent new exchange panel to {channel.name}")
