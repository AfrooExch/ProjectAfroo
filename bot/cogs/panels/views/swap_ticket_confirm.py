"""
Swap Ticket Confirmation View - Confirms swap and creates private ticket channel
"""

import discord
import logging
from typing import Dict, Any

from utils.embeds import create_themed_embed
from utils.colors import PURPLE_GRADIENT, ERROR_RED

logger = logging.getLogger(__name__)


class SwapTicketConfirmView(discord.ui.View):
    """Confirmation view that creates swap ticket on confirm"""

    def __init__(
        self,
        bot: discord.Bot,
        user_id: int,
        from_asset: str,
        to_asset: str,
        amount: float,
        destination_address: str,
        quote: Dict[str, Any]
    ):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.from_asset = from_asset
        self.to_asset = to_asset
        self.amount = amount
        self.destination_address = destination_address
        self.quote = quote

    @discord.ui.button(
        label="Confirm",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def confirm_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Create swap ticket"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your confirmation.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Import handler
            from cogs.panels.handlers.swap_handler import create_swap_ticket

            # Prepare session data
            session_data = {
                "from_asset": self.from_asset,
                "to_asset": self.to_asset,
                "amount": self.amount,
                "destination_address": self.destination_address,
                "quote": self.quote
            }

            # Create swap ticket
            await create_swap_ticket(
                bot=self.bot,
                user=interaction.user,
                guild=interaction.guild,
                session_data=session_data
            )

            # Confirm - ephemeral message will auto-dismiss
            await interaction.followup.send(
                "✅ Swap ticket created! Check your private swap channel.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error creating swap ticket: {e}", exc_info=True)
            await interaction.followup.send(
                embed=create_themed_embed(
                    title="❌ Failed to Create Swap",
                    description=f"An error occurred: {str(e)}\n\n> Please try again or contact support.",
                    color=ERROR_RED
                ),
                ephemeral=True
            )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        emoji="❌"
    )
    async def cancel_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction
    ):
        """Cancel swap creation"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your confirmation.",
                ephemeral=True
            )
            return

        # Disable buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="❌ Swap cancelled.",
            embed=None,
            view=self
        )
